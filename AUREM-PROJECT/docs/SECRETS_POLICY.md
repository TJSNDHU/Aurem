# AUREM Secrets Management & Key Rotation Policy

## 🔒 Security Classification: INTERNAL USE ONLY
**Last Updated:** April 2, 2026
**Owner:** Security Team

---

## 1. Environment Variables Inventory

### Backend Secrets (backend/.env)
| Secret Name | Purpose | Rotation Period | Owner |
|-------------|---------|-----------------|-------|
| `ANTHROPIC_API_KEY` | Claude LLM | 90 days | TJ |
| `OPENROUTER_API_KEY` | LLM routing | 90 days | TJ |
| `EMERGENT_LLM_KEY` | Universal LLM | Managed by Emergent | Emergent |
| `TWILIO_ACCOUNT_SID` | SMS/WhatsApp | 90 days | TJ |
| `TWILIO_AUTH_TOKEN` | SMS/WhatsApp | 90 days | TJ |
| `RESEND_API_KEY` | Email delivery | 90 days | TJ |
| `STRIPE_API_KEY` | Payments | 90 days | TJ |
| `MONGO_URL` | Database | 180 days | TJ |
| `JWT_SECRET` | Auth tokens | 90 days | TJ |
| `ENCRYPTION_KEY` | Data encryption | 180 days | TJ |
| `OMNIDIM_API_KEY` | Voice AI | 90 days | TJ |
| `FLAGSHIP_API_TOKEN` | Shipping | 90 days | TJ |
| `CLOUDINARY_API_SECRET` | Media storage | 90 days | TJ |

### Frontend Secrets (frontend/.env)
| Secret Name | Purpose | Notes |
|-------------|---------|-------|
| `REACT_APP_STRIPE_PUBLISHABLE_KEY` | Stripe checkout | Public key - safe |
| `REACT_APP_VAPID_PUBLIC_KEY` | Push notifications | Public key - safe |

---

## 2. Key Rotation Schedule

### 90-Day Rotation (Critical)
- [ ] **Next Due:** July 1, 2026
- OpenRouter API Key
- Twilio Auth Token
- Resend API Key
- Stripe API Key
- OmniDimension API Key
- JWT Secret
- Cloudinary API Secret

### 180-Day Rotation (Infrastructure)
- [ ] **Next Due:** October 1, 2026
- MongoDB Connection String
- Encryption Key

---

## 3. Rotation Procedure

### Step 1: Generate New Key
```bash
# For JWT/encryption secrets, generate locally:
openssl rand -hex 32
```

### Step 2: Update in Emergent
1. Go to Emergent dashboard
2. Navigate to Environment Variables
3. Update the key value
4. Redeploy the application

### Step 3: Verify
```bash
# Test the endpoint that uses the key
curl -X POST $API_URL/api/health/secrets-check
```

### Step 4: Revoke Old Key
- Log into provider dashboard (Twilio, Stripe, etc.)
- Revoke the old key
- Confirm new key is working

---

## 4. Emergency Key Revocation

If a key is compromised:

1. **Immediately** revoke the key in the provider's dashboard
2. Generate a new key
3. Update in Emergent environment variables
4. Trigger manual redeploy
5. Audit access logs for unauthorized usage
6. Document the incident

---

## 5. Access Control

### Who Has Access
| Person | Keys Accessible | Reason |
|--------|-----------------|--------|
| TJ | All | Owner |
| Gurnaman | Development only | Developer |
| Emergent Platform | Managed keys | Deployment |

### Access Logging
All secret access is logged via `SecretsAuditLog` service:
- Timestamp
- Accessor identity
- Action (read/write)
- Source IP
- Success/failure

---

## 6. Storage Rules

### ✅ DO
- Store all secrets in `.env` files
- Use environment variables in code
- Encrypt secrets at rest
- Use separate keys for dev/staging/prod

### ❌ DON'T
- Hardcode secrets in source code
- Commit `.env` files to git
- Share secrets via email/chat
- Use same key across environments
- Store secrets in frontend code

---

## 7. Secrets Manager Migration (Future)

### Phase 1: Current (Environment Variables)
- Secrets in `.env` files
- Managed via Emergent dashboard

### Phase 2: Planned (HashiCorp Vault)
- Self-hosted or cloud Vault
- Dynamic secret generation
- Automatic rotation
- Audit trail

### Migration Checklist
- [ ] Set up Vault instance
- [ ] Create mount points for each environment
- [ ] Migrate secrets one service at a time
- [ ] Update application to fetch from Vault
- [ ] Remove `.env` secrets post-migration

---

## 8. Compliance Notes

- All secrets must be rotated within 90 days of suspected compromise
- Access logs retained for 1 year minimum
- Key rotation documented and signed off by owner
- Annual security review of all active keys

---

**Document Classification:** Internal Only
**Do Not Share Externally**
