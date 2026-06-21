import os
import httpx

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
APP_URL = os.environ.get("APP_URL", "http://localhost:8000")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "Perde <notifications@perde.app>")


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
    if not RESEND_API_KEY:
        print(
            f"[email stub] Would notify {[r['email'] for r in recipients]} "
            f"about edit to '{story_title}' by {editor_name}"
        )
        return

    preview = content_preview[:200]
    story_url = f"{APP_URL}/editor.html?id={story_id}"

    async with httpx.AsyncClient() as client:
        for recipient in recipients:
            body_text = (
                f"Hi {recipient['display_name']},\n\n"
                f"{editor_name} just made an edit to \"{story_title}\".\n\n"
                f"---\n{preview}...\n---\n\n"
                f"Open the story: {story_url}\n\n"
                f"— Perde"
            )

            payload = {
                "from": FROM_EMAIL,
                "to": [recipient["email"]],
                "subject": f'[Perde] {editor_name} updated "{story_title}"',
                "text": body_text,
            }

            try:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    json=payload,
                    headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                    timeout=10,
                )
                resp.raise_for_status()
            except Exception as exc:
                # Log but do not crash the save flow
                print(f"[email] Failed to notify {recipient['email']}: {exc}")
