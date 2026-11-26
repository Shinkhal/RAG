import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config.env_config import get_settings
from app.db import get_session
from app.db.models import Account, LoginSession, PasswordResetToken
from app.services.email import send_password_reset_email
from app.utils.logger import logger

router = APIRouter()
SESSION_AGE = timedelta(days=7)
RESET_TOKEN_AGE = timedelta(minutes=30)
HASH_ITERATIONS = 600_000
DUMMY_HASH = f"pbkdf2_sha256${HASH_ITERATIONS}${'00' * 16}${'00' * 32}"


class LoginCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class SignupCredentials(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class AccountResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    created_at: datetime


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=256)
    password: str = Field(min_length=1, max_length=128)


class MessageResponse(BaseModel):
    message: str


def protect_mutation(request: Request) -> None:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("X-RAG-Request") != "1":
            raise HTTPException(403, "Missing request header")


def _cookie_name() -> str:
    return "__Host-rag_session" if get_settings().is_production else "rag_session"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, HASH_ITERATIONS).hex()
    return f"pbkdf2_sha256${HASH_ITERATIONS}${salt.hex()}${digest}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_hex, expected_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    actual_hex = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations).hex()
    return secrets.compare_digest(actual_hex, expected_hex)


def _to_account_response(account: Account) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        first_name=account.first_name,
        last_name=account.last_name,
        email=account.email,
        created_at=account.created_at,
    )


async def current_account(request: Request, db: AsyncSession = Depends(get_session)) -> Account:
    protect_mutation(request)
    token = request.cookies.get(_cookie_name(), "")
    if len(token) == 43:
        account = await db.scalar(
            select(Account)
            .join(LoginSession, Account.id == LoginSession.account_id)
            .where(
                LoginSession.token_hash == _token_hash(token),
                LoginSession.expires_at > datetime.now(UTC),
                Account.is_active.is_(True),
            )
        )
        if account:
            return account
    raise HTTPException(401, "Sign in to continue")


async def current_user_id(account: Account = Depends(current_account)) -> str:
    return account.id


async def _start_session(
    db: AsyncSession, account: Account, request: Request, response: Response
) -> AccountResponse:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    prior_token = request.cookies.get(_cookie_name(), "")
    await db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
    if len(prior_token) == 43:
        await db.execute(
            delete(LoginSession).where(LoginSession.token_hash == _token_hash(prior_token))
        )
    account.last_login_at = now
    db.add(
        LoginSession(
            token_hash=_token_hash(token), account_id=account.id, expires_at=now + SESSION_AGE
        )
    )
    await db.commit()
    response.set_cookie(
        _cookie_name(),
        token,
        max_age=int(SESSION_AGE.total_seconds()),
        secure=get_settings().is_production,
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return _to_account_response(account)


@router.post("/signup", status_code=201, dependencies=[Depends(protect_mutation)])
async def signup(
    data: SignupCredentials,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> AccountResponse:
    first_name = data.first_name.strip()
    last_name = data.last_name.strip()
    if not first_name or not last_name:
        raise HTTPException(422, "Enter your first and last name")

    email = data.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Enter a valid email address")
    if len(data.password) < 8:
        raise HTTPException(422, "Use at least 8 characters for your password")

    account = Account(
        id=str(uuid.uuid4()),
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=await run_in_threadpool(_hash_password, data.password),
    )
    db.add(account)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "An account already uses that email address") from exc
    return await _start_session(db, account, request, response)


@router.post("/login", dependencies=[Depends(protect_mutation)])
async def login(
    data: LoginCredentials,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> AccountResponse:
    account = await db.scalar(select(Account).where(Account.email == data.email.strip().lower()))
    stored_hash = account.password_hash if account else DUMMY_HASH
    valid = await run_in_threadpool(_verify_password, data.password, stored_hash)
    if not valid or account is None or not account.is_active:
        raise HTTPException(401, "Incorrect email or password")
    return await _start_session(db, account, request, response)


@router.get("/me")
async def me(response: Response, account: Account = Depends(current_account)) -> AccountResponse:
    response.headers["Cache-Control"] = "no-store"
    return _to_account_response(account)


@router.post("/logout", status_code=204, dependencies=[Depends(protect_mutation)])
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_session)
) -> None:
    token = request.cookies.get(_cookie_name(), "")
    if len(token) == 43:
        await db.execute(delete(LoginSession).where(LoginSession.token_hash == _token_hash(token)))
        await db.commit()
    response.delete_cookie(
        _cookie_name(), secure=get_settings().is_production, httponly=True, samesite="lax"
    )


@router.post("/forgot-password", dependencies=[Depends(protect_mutation)])
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_session),
) -> MessageResponse:
    email = data.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Enter a valid email address")

    account = await db.scalar(
        select(Account).where(Account.email == email, Account.is_active.is_(True))
    )
    if account:
        now = datetime.now(UTC)
        await db.execute(
            delete(PasswordResetToken).where(
                (PasswordResetToken.account_id == account.id)
                | (PasswordResetToken.expires_at <= now)
            )
        )
        raw_token = secrets.token_urlsafe(32)
        db.add(
            PasswordResetToken(
                token_hash=_token_hash(raw_token),
                account_id=account.id,
                expires_at=now + RESET_TOKEN_AGE,
            )
        )
        await db.commit()

        reset_url = f"{get_settings().frontend_url}/reset-password?token={quote(raw_token)}"
        try:
            await send_password_reset_email(
                to_email=account.email,
                first_name=account.first_name,
                reset_url=reset_url,
                expires_minutes=int(RESET_TOKEN_AGE.total_seconds() // 60),
            )
        except Exception as exc:
            logger.error("Failed to send password reset email: %s", exc)
            raise HTTPException(503, "Unable to send reset email right now. Try again later.") from exc

    return MessageResponse(
        message="If an account exists for that email, a password reset link has been sent."
    )


@router.post("/reset-password", dependencies=[Depends(protect_mutation)])
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_session),
) -> MessageResponse:
    if len(data.password) < 8:
        raise HTTPException(422, "Use at least 8 characters for your password")

    now = datetime.now(UTC)
    reset_record = await db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _token_hash(data.token.strip()),
            PasswordResetToken.expires_at > now,
            PasswordResetToken.used_at.is_(None),
        )
    )
    if not reset_record:
        raise HTTPException(400, "This reset link is invalid or has expired")

    account = await db.scalar(
        select(Account).where(Account.id == reset_record.account_id, Account.is_active.is_(True))
    )
    if not account:
        raise HTTPException(400, "This reset link is invalid or has expired")

    account.password_hash = await run_in_threadpool(_hash_password, data.password)
    reset_record.used_at = now
    await db.execute(delete(LoginSession).where(LoginSession.account_id == account.id))
    await db.commit()

    return MessageResponse(message="Your password has been reset. You can now sign in.")
