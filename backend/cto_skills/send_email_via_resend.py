"""Send email via Resend skill."""
from typing import Any

from .registry import skill


@skill(
    name="send_email_via_resend",
    description=(
        "Send a transactional email via Resend. Use for one-off "
        "founder-initiated emails. NOT for blast campaigns (those use "
        "the auto_blast pipeline)."
    ),
    requires_keys=["RESEND_API_KEY"],
)
async def send_email_via_resend(to: str, subject: str,
                                  html: str = "",
                                  text: str = "") -> dict[str, Any]:
    from services.email_service_resend import send_email
    body = html if html else f"<pre>{text}</pre>"
    res = await send_email(to=to, subject=subject, html=body)
    return {"to": to, "subject": subject, "delivered": bool(res),
             "provider_response": res}
