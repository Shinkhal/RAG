import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config.env_config import get_settings
from app.db import get_session
from app.db.models import Account, LoginSession

router = APIRouter()
SESSION_AGE = timedelta(days=7)
DUMMY_SALT = bytes(16)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class AccountResponse(BaseModel):
    id: str
    email: str


def protect_mutation(request: Request) -> None:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("X-RAG-Request") != "1":
            raise HTTPException(403, "Missing request header")


def _cookie_name() -> str:
    return "__Host-rag_session" if get_settings().is_production else "rag_session"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000).hex()


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
            )
        )
        if account:
            return account
    raise HTTPException(401, "Sign in to continue")


async def current_user_id(account: Account = Depends(current_account)) -> str:
    return account.id


async def _start_session(db: AsyncSession, account: Account, request: Request, response: Response):
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    prior_token = request.cookies.get(_cookie_name(), "")
    await db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
    if len(prior_token) == 43:
        await db.execute(
            delete(LoginSession).where(LoginSession.token_hash == _token_hash(prior_token))
        )
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
    return AccountResponse(id=account.id, email=account.email)


@router.post("/signup", status_code=201, dependencies=[Depends(protect_mutation)])
async def signup(
    data: Credentials, request: Request, response: Response, db: AsyncSession = Depends(get_session)
) -> AccountResponse:
    email = data.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Enter a valid email address")
    if len(data.password) < 15:
        raise HTTPException(422, "Use at least 15 characters for your password")

    salt = secrets.token_bytes(16)
    account = Account(
        id=str(uuid.uuid4()),
        email=email,
        password_salt=salt.hex(),
        password_hash=await run_in_threadpool(_password_hash, data.password, salt),
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
    data: Credentials, request: Request, response: Response, db: AsyncSession = Depends(get_session)
) -> AccountResponse:
    account = await db.scalar(select(Account).where(Account.email == data.email.strip().lower()))
    salt = bytes.fromhex(account.password_salt) if account else DUMMY_SALT
    actual = await run_in_threadpool(_password_hash, data.password, salt)
    expected = account.password_hash if account else "0" * 64
    if not secrets.compare_digest(actual, expected) or account is None:
        raise HTTPException(401, "Incorrect email or password")
    return await _start_session(db, account, request, response)


@router.get("/me")
async def me(response: Response, account: Account = Depends(current_account)) -> AccountResponse:
    response.headers["Cache-Control"] = "no-store"
    return AccountResponse(id=account.id, email=account.email)


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
