from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.concurrency import run_in_threadpool

from app.config.env_config import get_settings

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates" / "emails"

_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_email_template(template_name: str, context: dict[str, Any]) -> tuple[str, str]:
    """Render both plain-text (.txt) and HTML (.html) email templates."""
    text_body = _jinja_env.get_template(f"{template_name}.txt").render(**context)
    html_body = _jinja_env.get_template(f"{template_name}.html").render(**context)
    return text_body, html_body


def _send_smtp_sync(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        raise RuntimeError(
            "SMTP is not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in your environment."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    if settings.smtp_port == 465 and not settings.smtp_use_tls:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


async def send_templated_email(
    to_email: str, subject: str, template_name: str, context: dict[str, Any]
) -> None:
    text_body, html_body = render_email_template(template_name, context)
    await run_in_threadpool(_send_smtp_sync, to_email, subject, text_body, html_body)


async def send_password_reset_email(
    to_email: str, first_name: str, reset_url: str, expires_minutes: int = 30
) -> None:
    await send_templated_email(
        to_email=to_email,
        subject="Reset your RAG Workspace password",
        template_name="password_reset",
        context={
            "preheader": f"Reset your RAG Workspace password (link valid for {expires_minutes} minutes).",
            "first_name": first_name,
            "reset_url": reset_url,
            "expires_minutes": expires_minutes,
        },
    )


async def send_welcome_email(to_email: str, first_name: str, workspace_url: str) -> None:
    await send_templated_email(
        to_email=to_email,
        subject="Welcome to RAG Workspace",
        template_name="welcome",
        context={
            "preheader": "Your private document workspace is ready.",
            "first_name": first_name,
            "workspace_url": workspace_url,
        },
    )


async def send_password_changed_email(to_email: str, first_name: str, login_url: str) -> None:
    await send_templated_email(
        to_email=to_email,
        subject="Your RAG Workspace password was changed",
        template_name="password_changed",
        context={
            "preheader": "Your password was recently changed.",
            "first_name": first_name,
            "login_url": login_url,
        },
    )


async def send_usage_alert_email(
    to_email: str,
    first_name: str,
    summary: str,
    workspace_url: str,
    heading: str = "Your workspace usage summary",
    uploads_used: int | None = None,
    uploads_limit: int | None = None,
    queries_used: int | None = None,
    queries_limit: int | None = None,
    period_label: str = "",
) -> None:
    context: dict[str, Any] = {
        "preheader": summary,
        "first_name": first_name,
        "heading": heading,
        "summary": summary,
        "workspace_url": workspace_url,
        "period_label": period_label,
    }
    if uploads_used is not None:
        context["uploads_used"] = uploads_used
    if uploads_limit is not None:
        context["uploads_limit"] = uploads_limit
    if queries_used is not None:
        context["queries_used"] = queries_used
    if queries_limit is not None:
        context["queries_limit"] = queries_limit

    await send_templated_email(
        to_email=to_email,
        subject=f"RAG Workspace — {heading}",
        template_name="usage_alert",
        context=context,
    )


async def send_document_processed_email(
    to_email: str,
    first_name: str,
    document_name: str,
    status_label: str,
    workspace_url: str,
    notebook_title: str = "",
    error_message: str = "",
) -> None:
    await send_templated_email(
        to_email=to_email,
        subject=f'RAG Workspace — "{document_name}" is {status_label}',
        template_name="document_processed",
        context={
            "preheader": f'Your document "{document_name}" is {status_label}.',
            "first_name": first_name,
            "document_name": document_name,
            "status_label": status_label,
            "notebook_title": notebook_title,
            "error_message": error_message,
            "workspace_url": workspace_url,
        },
    )
