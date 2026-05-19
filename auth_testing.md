# AUREM Auth Testing Playbook

## Step 1 — MongoDB Verification
```
mongosh "$MONGO_URL"
use <db>
db.users.findOne({email: "teji.ss1986@gmail.com"})           # admin (super_admin)
db.platform_users.findOne({business_id: "AURE-RUGC"})        # tenant
```
Verify bcrypt hash starts with `$2b$` for both `password` and (if set) `pin_hash`.

## Step 2 — Existing Endpoints
```
API=$REACT_APP_BACKEND_URL
# Admin (works post-rotation 2026-02-04)
curl -X POST $API/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teji.ss1986@gmail.com","password":"<REDACTED_OLD_PASS>"}'
# Customer email/password
curl -X POST $API/api/platform/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"<email or BIN>","password":"<pw>"}'
```

## Step 3 — New BIN+PIN Endpoints (iter 305e)
- `POST /api/platform/auth/login-pin` — body `{bin, pin}` → JWT
- `POST /api/platform/auth/setup-pin` — body `{pin}` (auth required) → 200
- `POST /api/platform/auth/change-pin` — body `{old_pin, new_pin}` (auth required)
- `POST /api/platform/auth/forgot-pin` — body `{email or bin}` → emails magic link
- `POST /api/platform/auth/reset-pin` — body `{token, new_pin}`

## Step 4 — Lockout / Rate Limit
3 wrong PINs = 15-min lockout (`pin_login_attempts` collection, key `{ip}:{bin}`).

## Step 5 — Forgot Password (existing)
- `POST /api/auth/forgot-password` (if wired), else add per playbook.
