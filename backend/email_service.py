import os
import smtplib
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Config ────────────────────────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
APP_URL = os.environ.get("APP_URL", "http://localhost:8000")

# Gmail SMTP config
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# Which backend to use
def _use_gmail() -> bool:
    return bool(GMAIL_USER and GMAIL_APP_PASSWORD)

def _use_resend() -> bool:
    return bool(RESEND_API_KEY)


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
        return

    preview = content_preview[:200]
    story_url = f"{APP_URL}/editor.html?id={story_id}"

    if _use_gmail():
        await _send_via_gmail(
            story_id=story_id,
            story_title=story_title,
            editor_name=editor_name,
            recipients=recipients,
            preview=preview,
            story_url=story_url,
        )
    elif _use_resend():
        await _send_via_resend(
            story_id=story_id,
            story_title=story_title,
            editor_name=editor_name,
            recipients=recipients,
            preview=preview,
            story_url=story_url,
        )
    else:
        print(
            f"[email stub] Would notify {[r['email'] for r in recipients]} "
            f"about edit to '{story_title}' by {editor_name}"
        )


# ── Gmail SMTP backend ────────────────────────────────────────────────────────

async def _send_via_gmail(*, story_id, story_title, editor_name, recipients, preview, story_url):
    """Send via Gmail SMTP using App Password. No domain needed."""
    subject = f'[Perde] {editor_name} updated "{story_title}"'

    for recipient in recipients:
        body = (
            f"Hi {recipient['display_name']},\n\n"
            f"{editor_name} just made an edit to \"{story_title}\".\n\n"
            f"---\n{preview}...\n---\n\n"
            f"Open the story: {story_url}\n\n"
            f"— Perde"
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Perde <{GMAIL_USER}>"
        msg["To"] = recipient["email"]
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                server.sendmail(GMAIL_USER, recipient["email"], msg.as_string())
            print(f"[email] Gmail: sent to {recipient['email']}")
        except Exception as exc:
            print(f"[email] Gmail failed for {recipient['email']}: {exc}")


# ── Resend API backend ────────────────────────────────────────────────────────

async def _send_via_resend(*, story_id, story_title, editor_name, recipients, preview, story_url):
    """Send via Resend API."""
    FROM_EMAIL = os.environ.get("FROM_EMAIL", f"Perde <noreply@resend.dev>")
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
                        "from": FROM_EMAIL,
                        "to": [recipient["email"]],
                        "subject": subject,
                        "text": body,
                    },
                    headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                    timeout=10,
                )
                resp.raise_for_status()
                print(f"[email] Resend: sent to {recipient['email']}")
            except Exception as exc:
                print(f"[email] Resend failed for {recipient['email']}: {exc}")
