"""Pull verbose detail on every A2P campaign + brand under the account."""
import os, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from twilio.rest import Client

c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
print("=== BRANDS ===")
for b in c.messaging.v1.brand_registrations.list():
    print(json.dumps({
        "sid": b.sid, "status": b.status, "tcr_id": getattr(b,"tcr_id",None),
        "brand_score": getattr(b,"brand_score",None),
        "failure_reason": getattr(b,"failure_reason",None),
        "identity_status": getattr(b,"identity_status",None),
        "russell_3000": getattr(b,"russell_3000",None),
        "tax_exempt_status": getattr(b,"tax_exempt_status",None),
    }, default=str, indent=2))

print("\n=== MESSAGING SERVICES + CAMPAIGNS ===")
for s in c.messaging.v1.services.list():
    print(f"\n--- MS {s.sid} · {s.friendly_name} ---")
    print(json.dumps({
        "use_case": getattr(s,"usecase",None),
        "smart_encoding": s.smart_encoding,
        "scan_message_content": getattr(s,"scan_message_content",None),
        "fallback_to_long_code": s.fallback_to_long_code,
        "status_callback": s.status_callback,
        "inbound_request_url": s.inbound_request_url,
    }, default=str, indent=2))
    # Phone numbers attached
    pns = c.messaging.v1.services(s.sid).phone_numbers.list()
    print(f"  phone_numbers ({len(pns)}): {[p.phone_number for p in pns]}")
    try:
        for cp in c.messaging.v1.services(s.sid).us_app_to_person.list():
            print("  CAMPAIGN:")
            print(json.dumps({
                "sid": cp.sid,
                "campaign_status": getattr(cp,"campaign_status",None),
                "campaign_id": getattr(cp,"campaign_id",None),
                "use_case": getattr(cp,"us_app_to_person_usecase",None),
                "description": getattr(cp,"description",None),
                "rate_limits": getattr(cp,"rate_limits",None),
                "errors": getattr(cp,"errors",None),
                "message_samples": getattr(cp,"message_samples",None),
                "has_embedded_links": getattr(cp,"has_embedded_links",None),
                "has_embedded_phone": getattr(cp,"has_embedded_phone",None),
                "message_flow": getattr(cp,"message_flow",None),
                "opt_in_message": getattr(cp,"opt_in_message",None),
                "date_created": getattr(cp,"date_created",None),
                "date_updated": getattr(cp,"date_updated",None),
            }, default=str, indent=2))
    except Exception as e:
        print(f"  campaign list err: {e}")
