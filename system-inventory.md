# AUREM System Inventory (2026-03-28)

## Backend Routes [LIVE]
- `/api/auth` (OAuth2/JWT)
- `/api/customers` (CRUD)
- `/api/billing` (Stripe/Paddle)
- `/api/automations` (Workflow engine)
- `/api/monitoring` (Health checks)
- `/api/self-heal` (Security remediation)

## Frontend Pages [LIVE]
- `/dashboard` (Main console)
- `/automations` (Flow builder)
- `/customers` (CRM view)
- `/billing` (Subscription mgmt)
- `/security` (Audit logs)

## ORA Skills [PARTIAL]
- `api-security-best-practices`
- `frontend-security-coder` 
- `backend-security-coder`
- `cc-skill-security-review`

## Integrations [LIVE]
- Stripe/Paddle (Payments)
- Twilio (Voice/SMS)
- SendGrid (Email)
- Slack (Alerts)
- GSuite (Calendar/Contacts)

## Security [BROKEN]
- Hardcoded secrets detection
- CSP implementation
- Rate limiting gaps
- AuthZ permission model

## Modes [LIVE]
- Production mode
- Debug mode
- Maintenance mode
- Security lockdown

## UI Components [PARTIAL]
- SecureToast (Missing CSP)
- AuthGuard (Complete)
- DataTable (Needs sanitization)
- FileUpload (Virus scan pending)
- AuditLogger (Complete)

## Background Jobs [LIVE]
- Nightly backups
- Security scans
- Billing sync
- Monitoring pings
- Data cleanup
