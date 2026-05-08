#!/usr/bin/env python3
"""
One-shot warm onboarding email to Mike (directorytraffic@gmail.com).
Sends via Resend API directly — works regardless of aurem.live deploy
status. Logs to db.email_inbox + db.email_outbox for thread continuity
once production backend catches up.

Run: python3 /app/scripts/mike_warm_reply.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

import resend
from motor.motor_asyncio import AsyncIOMotorClient

resend.api_key = os.environ["RESEND_API_KEY"]

MIKE_EMAIL = "directorytraffic@gmail.com"
RESEND_FROM = os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>")

SUBJECT = "Re: Your Brampton Veterinarians preview"

BODY_TEXT = """Hey Mike!

So glad you wrote back — that genuinely made our day.

Your site is live right now:
https://brampton-veterinarians---vetlistorg-778a78.aurem.live

Feel free to share it, test it, and let us know if you'd like anything changed — services, photos, hours, contact info. We can update it within 24 hours, no charge.

READY TO MAKE IT OFFICIALLY YOURS?

Here's how it works in 3 simple steps:

STEP 1 — Choose Your Plan
https://aurem.live/#pricing

  Starter — $97/month CAD
    Your own branded website + AI that follows up with leads automatically.

  Growth — $449/month CAD
    Everything in Starter + AI voice calls, SMS follow-ups, and lead scouting.

  Enterprise — $997/month CAD
    Full autonomous sales system — Scout finds leads, Closer books them,
    you just show up.

STEP 2 — Sign Up & Get Your Dashboard
https://aurem.live/platform/login
Create your account → you'll get your own Business ID (BIN) and a private
dashboard to manage leads, calls, and your website.

STEP 3 — We Transfer Your Site
Once you're in, we move your existing site to your account and connect
it to your domain (vetlist.org if you'd like) — zero downtime.

Questions? Just reply here or book a quick 15-min call:
https://aurem.live/book

Looking forward to working with you, Mike.

Warm regards,
TJ
Founder, AUREM
ora@aurem.live
https://aurem.live
"""

BODY_HTML = BODY_TEXT.replace("\n\n", "</p><p>").replace("\n", "<br>")
BODY_HTML = f"<p>{BODY_HTML}</p>"


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)

    inbound_msg_id = f"<mike-may2-manual-{uuid.uuid4().hex[:8]}@aurem.live>"

    # 1. Log Mike's reply (placeholder — actual content not captured)
    await db.email_inbox.insert_one({
        "ts": datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc),
        "parsed": True,
        "sender": MIKE_EMAIL,
        "recipient": "ora@aurem.live",
        "subject": "Re: Your Brampton Veterinarians preview",
        "body": "(Mike replied on May 2 — original thread on tj@aurem.live; "
                "manually backfilled by /app/scripts/mike_warm_reply.py)",
        "message_id": inbound_msg_id,
        "replied": False,
        "received_via": "manual_trigger",
    })
    print(f"OK · inbound logged: msg_id={inbound_msg_id}")

    # 2. Send via Resend
    res = resend.Emails.send({
        "from": RESEND_FROM,
        "to": [MIKE_EMAIL],
        "subject": SUBJECT,
        "text": BODY_TEXT,
        "html": BODY_HTML,
        "headers": {
            "In-Reply-To": inbound_msg_id,
            "References": inbound_msg_id,
        },
        "reply_to": "ora@aurem.live",
    })
    resend_id = (res or {}).get("id")
    print(f"OK · resend send: id={resend_id}")

    # 3. Log outbound
    await db.email_outbox.insert_one({
        "ts": now,
        "to": MIKE_EMAIL,
        "from": RESEND_FROM,
        "subject": SUBJECT,
        "body": BODY_TEXT,
        "in_reply_to": inbound_msg_id,
        "resend_id": resend_id,
        "ok": bool(resend_id),
        "source": "manual_warm_onboarding",
    })

    # 4. Mark inbound as replied
    await db.email_inbox.update_one(
        {"message_id": inbound_msg_id},
        {"$set": {"replied": True, "replied_at": now, "resend_id": resend_id}},
    )
    print(f"OK · outbox logged + inbox marked replied")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
