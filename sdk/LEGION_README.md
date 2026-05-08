# Legion Sovereign Node — Boot-Kit

Tera phone ya local server ko AUREM ka **Sovereign Node** banata hai. Ek
chhoti Python script — 60s ke hisab se heartbeat bhejta hai, offline
queue drain karta hai, aur Empire HUD me green dot laata hai.

---

## Android (Termux)

```bash
pkg update && pkg install python curl git -y

# Download the bootkit
curl -O https://<your-aurem-url>/sdk/legion_bootkit.py
# OR if you've saved this repo locally:
#   git clone <your-repo> && cd repo/sdk

# Set the 2 required env vars
export AUREM_URL="https://ai-platform-preview-3.preview.emergentagent.com"
export AUREM_TOKEN="<paste admin JWT from /admin/pillars-map>"

# Optional customization
export LEGION_NODE_ID="legion"          # default: legion
export LEGION_NODE_NAME="Teji iPhone"   # default: hostname
export LEGION_BEAT_SEC=60               # default: 60

# Run
python3 legion_bootkit.py
```

You'll see heartbeat logs like:

```
[04:52:10] heartbeat #1 OK · queue=0 · drained-this-cycle=0 (total 0) · uptime=0s
[04:53:10] heartbeat #2 OK · queue=0 · drained-this-cycle=0 (total 0) · uptime=60s
```

Empire HUD → Legion node turns **GREEN** within 60s.

---

## iOS (iSH shell)

```bash
apk add python3
# same env + run as above
```

---

## Linux / macOS / local server

```bash
export AUREM_URL="..."
export AUREM_TOKEN="..."
python3 legion_bootkit.py
```

For persistent running on a Linux box, use systemd or tmux/screen:

```bash
tmux new -s legion
# inside tmux:
python3 legion_bootkit.py
# Detach: Ctrl+B, D
```

---

## Getting your AUREM_TOKEN

1. Login to `/admin` as super admin
2. Open DevTools → Application → Local Storage
3. Copy the `token` (or `aurem_token`) value
4. Paste into the `AUREM_TOKEN` export

---

## What does each beat do?

Every **60s** (configurable), the bootkit:

1. `POST /api/sovereign/heartbeat` — registers the node + updates `last_heartbeat_at`
2. `POST /api/sovereign/sync/{node_id}` — drains any events queued while offline
3. Logs to stdout so you can tail it

If heartbeat fails, AUREM marks the node **offline** after 120s and buffers
any pending events. As soon as beats resume, the queue drains automatically.

---

## Queue event shape (when AUREM buffers something for you)

When Legion is offline and AUREM wants to send it an event (e.g., an SMS
task, a local file sync, a restart command), it goes into `sovereign_queue`
with:

```json
{
  "node_id": "legion",
  "event_type": "sms_send",
  "event_payload": { "to": "+14161234567", "body": "..." },
  "status": "pending",
  "queued_at": "2026-04-24T04:50:00Z"
}
```

On next `/sync` drain, the bootkit prints them to stdout. Hook your own
processing logic into the `drain_queue()` function in `legion_bootkit.py`
to act on them (send the SMS, run the command, etc.).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `401 Unauthorized` | Token expired or not admin — regenerate |
| `Missing token` | AUREM_TOKEN env var not set |
| `name resolution failed` | AUREM_URL wrong or phone offline |
| Empire HUD still grey | Wait 60s for first beat, then refresh |
| Beats sending but "offline" in HUD | Check `HEARTBEAT_TIMEOUT_SEC` on backend (default 120s) |

---

**Truth-Sync**: This bootkit does NOT pretend to be online if the network
fails. Every failed beat is printed. The HUD will correctly mark you
offline. Kachra nahi, sirf asli data.
