import os
import smtplib
import asyncio
import httpx
from functools import partial
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ── Config — read at call time, not import time ───────────────────────────────
# (Railway injects env vars before the process starts, but reading at module
#  level inside functions ensures we always get the live value)

def _gmail_user() -> str:
    return os.environ.get("GMAIL_USER", "").strip()

def _gmail_password() -> str:
    # Strip spaces — Gmail shows app passwords with spaces (abcd efgh ijkl mnop)
    return os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()

def _resend_key() -> str:
    return os.environ.get("RESEND_API_KEY", "").strip()

def _app_url() -> str:
    return os.environ.get("APP_URL", "http://localhost:8000").rstrip("/")

def _from_email() -> str:
    return os.environ.get("FROM_EMAIL", "Perde <noreply@resend.dev>")


# ── Main send function ────────────────────────────────────────────────────────

async def send_edit_notification(
    *,
    story_id: int,
    story_title: str,
    editor_name: str,
    recipients: list[dict],  # list of {"email": str, "display_name": str}
    content_preview: str,
    timestamp: str,
):
    """Send email notifications to all contributors except the editor."""
    if not recipients:
        print("[email] No recipients — skipping notification")
        return

    preview = content_preview[:200]
    story_url = f"{_app_url()}/editor.html?id={story_id}"

    print(f"[email] Sending notification to {[r['email'] for r in recipients]}")
    print(f"[email] GMAIL_USER set: {bool(_gmail_user())} | RESEND_KEY set: {bool(_resend_key())}")

    if _gmail_user() and _gmail_password():
        await _send_via_gmail(
            story_title=story_title,
            editor_name=editor_name,
            recipients=recipients,
            preview=preview,
            story_url=story_url,
        )
    elif _resend_key():
        await _send_via_resend(
            story_title=story_title,
            editor_name=editor_name,
            recipients=recipients,
            preview=preview,
            story_url=story_url,
        )
    else:
        print(
            f"[email stub] No email backend configured. Would notify "
            f"{[r['email'] for r in recipients]} about '{story_title}' by {editor_name}"
        )


# ── Gmail SMTP backend ────────────────────────────────────────────────────────

def _smtp_send_blocking(gmail_user: str, gmail_password: str, recipient: dict,
                         subject: str, body: str):
    """Blocking SMTP call — run in thread pool to avoid blocking the event loop."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Perde <{gmail_user}>"
    msg["To"] = recipient["email"]
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipient["email"], msg.as_string())


async def _send_via_gmail(*, story_title, editor_name, recipients, preview, story_url):
    """Send via Gmail SMTP. Runs in a thread pool to avoid blocking the event loop."""
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


# ── Resend API backend ────────────────────────────────────────────────────────

async def _send_via_resend(*, story_title, editor_name, recipients, preview, story_url):
    """Send via Resend API."""
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
                        "from": _from_email(),
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
