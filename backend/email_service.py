import os
import smtplib
import asyncio
import httpx
from functools import partial
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ── Config — always read at call time so Railway env vars are picked up ───────

def _gmail_user() -> str:
    return os.environ.get("GMAIL_USER", "").strip()

def _gmail_password() -> str:
    return os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()

def _resend_key() -> str:
    return os.environ.get("RESEND_API_KEY", "").strip()

def _brevo_key() -> str:
    return os.environ.get("BREVO_API_KEY", "").strip()

def _app_url() -> str:
    return os.environ.get("APP_URL", "http://localhost:8000").rstrip("/")

def _from_name_email() -> tuple[str, str]:
    """Returns (display_name, email) for the FROM field."""
    gmail = _gmail_user()
    if gmail:
        return ("Perde", gmail)
    raw = os.environ.get("FROM_EMAIL", "Perde <noreply@example.com>")
    # parse "Name <email>" format
    if "<" in raw and ">" in raw:
        name = raw.split("<")[0].strip()
        email = raw.split("<")[1].replace(">", "").strip()
        return (name, email)
    return ("Perde", raw.strip())


# ── Main send function ────────────────────────────────────────────────────────

async def send_edit_notification(
    *,
    story_id: int,
    story_title: str,
    editor_name: str,
    recipients: list[dict],
    content_preview: str,
    timestamp: str,
):
    """Send email notifications to all contributors except the editor."""
    if not recipients:
        print("[email] No recipients — skipping notification")
        return

    preview = content_preview[:200]
    story_url = f"{_app_url()}/editor.html?id={story_id}"

    has_brevo = bool(_brevo_key())
    has_resend = bool(_resend_key())
    has_gmail = bool(_gmail_user() and _gmail_password())

    print(f"[email] Sending to {[r['email'] for r in recipients]}")
    print(f"[email] Backends — Brevo: {has_brevo} | Resend: {has_resend} | Gmail: {has_gmail}")

    if has_brevo:
        await _send_via_brevo(
            story_title=story_title,
            editor_name=editor_name,
            recipients=recipients,
            preview=preview,
            story_url=story_url,
        )
    elif has_resend:
        await _send_via_resend(
            story_title=story_title,
            editor_name=editor_name,
            recipients=recipients,
            preview=preview,
            story_url=story_url,
        )
    elif has_gmail:
        # Gmail SMTP — only reliable locally (cloud platforms block SMTP ports)
        await _send_via_gmail(
            story_title=story_title,
            editor_name=editor_name,
            recipients=recipients,
            preview=preview,
            story_url=story_url,
        )
    else:
        print(
            f"[email stub] No backend configured. Would notify "
            f"{[r['email'] for r in recipients]} about '{story_title}' by {editor_name}"
        )


# ── Brevo (Sendinblue) backend ────────────────────────────────────────────────

async def _send_via_brevo(*, story_title, editor_name, recipients, preview, story_url):
    """
    Send via Brevo API (HTTPS — works on Railway free tier).
    Allows sending FROM a Gmail address after a one-time email verification.
    Free tier: 300 emails/day.
    """
    from_name, from_email = _from_name_email()
    subject = f'[Perde] {editor_name} updated "{story_title}"'

    async with httpx.AsyncClient() as client:
        for recipient in recipients:
            body = (
                f"Hi {recipient['display_name']},\n\n"
                f"{editor_name} just made an edit to \"{story_title}\".\n\n"
                f"---\n{preview}...\n---\n\n"
                f"Open the story: {story_url}\n\n"
                f"— Perde"
            )
            try:
                resp = await client.post(
                    "https://api.brevo.com/v3/smtp/email",
                    json={
                        "sender": {"name": from_name, "email": from_email},
                        "to": [{"email": recipient["email"],
                                 "name": recipient["display_name"]}],
                        "subject": subject,
                        "textContent": body,
                    },
                    headers={
                        "api-key": _brevo_key(),
                        "Content-Type": "application/json",
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                print(f"[email] Brevo: sent to {recipient['email']}")
            except Exception as exc:
                print(f"[email] Brevo failed for {recipient['email']}: {exc}")


# ── Resend backend ────────────────────────────────────────────────────────────

async def _send_via_resend(*, story_title, editor_name, recipients, preview, story_url):
    """Send via Resend API. Requires a verified FROM domain."""
    _, from_email_addr = _from_name_email()
    from_field = os.environ.get("FROM_EMAIL", f"Perde <{from_email_addr}>")
    subject = f'[Perde] {editor_name} updated "{story_title}"'

    async with httpx.AsyncClient() as client:
        for recipient in recipients:
            body = (
                f"Hi {recipient['display_name']},\n\n"
                f"{editor_name} just made an edit to \"{story_title}\".\n\n"
                f"---\n{preview}...\n---\n\n"
                f"Open the story: {story_url}\n\n"
                f"— Perde"
            )
            try:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    json={
                        "from": from_field,
                        "to": [recipient["email"]],
                        "subject": subject,
                        "text": body,
                    },
                    headers={"Authorization": f"Bearer {_resend_key()}"},
                    timeout=10,
                )
                resp.raise_for_status()
                print(f"[email] Resend: sent to {recipient['email']}")
            except Exception as exc:
                print(f"[email] Resend failed for {recipient['email']}: {exc}")


# ── Gmail SMTP backend (local dev only) ───────────────────────────────────────

def _smtp_send_blocking(gmail_user, gmail_password, recipient, subject, body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Perde <{gmail_user}>"
    msg["To"] = recipient["email"]
    msg.attach(MIMEText(body, "plain", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipient["email"], msg.as_string())


async def _send_via_gmail(*, story_title, editor_name, recipients, preview, story_url):
    gmail_user = _gmail_user()
    gmail_password = _gmail_password()
    subject = f'[Perde] {editor_name} updated "{story_title}"'
    loop = asyncio.get_event_loop()
    for recipient in recipients:
        body = (
            f"Hi {recipient['display_name']},\n\n"
            f"{editor_name} just made an edit to \"{story_title}\".\n\n"
            f"---\n{preview}...\n---\n\n"
            f"Open the story: {story_url}\n\n"
            f"— Perde"
        )
        try:
            await loop.run_in_executor(
                None,
                partial(_smtp_send_blocking, gmail_user, gmail_password, recipient, subject, body)
            )
            print(f"[email] Gmail: sent to {recipient['email']}")
        except smtplib.SMTPAuthenticationError as exc:
            print(f"[email] Gmail auth failed — check GMAIL_USER and GMAIL_APP_PASSWORD: {exc}")
        except Exception as exc:
            print(f"[email] Gmail failed for {recipient['email']}: {exc}")
