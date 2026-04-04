# 🚀 AUREM PRODUCTION DEPLOYMENT GUIDE
**Small Business AI Platform - Launch Checklist**

## ✅ PRE-LAUNCH CHECKLIST

### 1. Backend Services (CRITICAL)
- [x] Multi-tenancy middleware active
- [x] Lead capture system operational
- [x] Shopify webhook receivers ready
- [x] Email notification service configured
- [x] Vector DB multi-tenant isolation
- [x] Usage metering service created
- [x] Database connections verified
- [ ] **EMERGENT_LLM_KEY** set in production `.env`
- [ ] **RESEND_API_KEY** set in production `.env` (optional but recommended)
- [ ] **JWT_SECRET** changed from default

### 2. Frontend Services
- [x] Leads Dashboard (`/leads`) accessible
- [x] Routes configured in App.js
- [x] API URL configured (`REACT_APP_BACKEND_URL`)
- [ ] Build optimized production bundle
- [ ] Test on mobile devices
- [ ] Verify all UI components load

### 3. Security
- [x] Multi-tenant data isolation (tested)
- [x] JWT authentication active
- [x] CORS configured
- [ ] Change default JWT_SECRET
- [ ] Enable HTTPS (production)
- [ ] Rate limiting configured
- [ ] Webhook signature verification (Shopify)

### 4. Integrations
- [ ] **Email (Resend)**: Add API key or accept logging mode
- [ ] **Shopify**: Configure webhooks in customer stores
- [ ] **Google Calendar**: OAuth setup (optional, can add later)
- [ ] **Emergent LLM**: Verify key has sufficient balance

### 5. Monitoring & Logging
- [x] Backend logs (`/var/log/supervisor/backend.*.log`)
- [ ] Set up error alerting (Sentry/similar)
- [ ] Monitor lead capture rate
- [ ] Track API response times
- [ ] Database backup schedule

### 6. Documentation
- [x] Multi-tenancy implementation guide
- [x] Lead capture system docs
- [ ] Customer onboarding guide (see below)
- [ ] Admin setup instructions
- [ ] Troubleshooting guide

---

## 🎯 LAUNCH SEQUENCE (Do This Now)

### Phase 1: Environment Variables (15 minutes)

**File**: `/app/backend/.env`

```bash
# CRITICAL - Change these before launch
JWT_SECRET="your-super-secret-jwt-key-change-this-now"  # MUST CHANGE
EMERGENT_LLM_KEY="your-emergent-llm-key"  # Required for AI

# RECOMMENDED - Email notifications
RESEND_API_KEY="re_your_resend_key"  # Optional: logs to console if not set

# Already configured (verify)
MONGO_URL="your-mongodb-connection-string"
DB_NAME="aurem_database"

# Shopify (per-tenant, configured later)
# Each customer adds their own via BYON (Bring Your Own Number)
```

**File**: `/app/frontend/.env`

```bash
REACT_APP_BACKEND_URL="https://your-production-domain.com"
```

### Phase 2: Test Critical Flows (30 minutes)

**Test 1: Lead Capture**
```bash
# 1. Send test message via AUREM Chat
curl -X POST https://your-domain/api/aurem/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I want to book an appointment tomorrow. My name is Test User, email test@example.com",
    "session_id": "test_session_001"
  }'

# 2. Check if lead was captured
curl https://your-domain/api/leads/stats

# 3. View leads dashboard
# Visit: https://your-domain/leads
```

**Test 2: Shopify Sync**
```bash
# Simulate Shopify order
curl -X POST https://your-domain/api/shopify/test/simulate-order

# Check if inventory decreased
# (View in Shopify dashboard or query database)
```

**Test 3: Multi-Tenancy**
```bash
# Login as different tenants
# Verify leads don't cross-contaminate
```

### Phase 3: Customer Onboarding (Create Process)

**For Each New Customer**:

1. **Create Tenant Account**
   - Sign up via `/auth`
   - Assign unique `tenant_id` (auto-generated from email domain)

2. **Connect Shopify (If Applicable)**
   - Customer goes to Shopify Admin
   - Settings → Notifications → Webhooks
   - Add webhook: `https://your-domain/api/shopify/webhooks/orders/create`
   - Add webhook: `https://your-domain/api/shopify/webhooks/products/update`
   - Copy webhook secret → store in AUREM

3. **Configure Email Notifications**
   - Business owner's email stored in profile
   - Receives alerts when leads captured

4. **Show Dashboard**
   - Direct customer to `/leads`
   - Show "Today's Impact" metrics
   - Train on lead management

### Phase 4: Production Deployment

**Option A: Deploy on Emergent** (Recommended)
- Use Emergent's native deployment
- Environment variables auto-configured
- HTTPS enabled by default
- Scaling handled automatically

**Option B: Deploy on Vercel/Railway**
- Export codebase (use "Save to GitHub" feature)
- Connect to Vercel/Railway
- Configure environment variables
- Deploy

**Option C: Self-Hosted**
- Set up production server (Ubuntu/AWS/GCP)
- Install Docker
- Configure reverse proxy (Nginx)
- Set up SSL certificate (Let's Encrypt)
- Run containers

---

## 📊 SUCCESS METRICS (Track These)

### Day 1-7:
- [ ] 10+ businesses onboarded
- [ ] 50+ leads captured
- [ ] 10+ appointments booked
- [ ] Zero cross-tenant data leaks
- [ ] < 2 second API response time

### Day 8-30:
- [ ] 100+ businesses
- [ ] 500+ leads captured
- [ ] 25%+ conversion rate
- [ ] Customer testimonials collected
- [ ] Feature requests prioritized

---

## 🆘 TROUBLESHOOTING

### "Leads not capturing"
1. Check backend logs: `tail -f /var/log/supervisor/backend.err.log`
2. Verify `/api/leads/test-capture` works
3. Check if `TenantContext` is set
4. Ensure database connection active

### "Email notifications not sending"
1. Check if `RESEND_API_KEY` is set
2. View console logs (emails logged if no key)
3. Verify Resend account has credits
4. Check spam folder

### "Shopify webhooks failing"
1. Check Shopify webhook delivery logs
2. Verify webhook URL is correct
3. Test signature verification
4. Check MongoDB connection

### "Multi-tenancy not working"
1. Verify `TenantMiddleware` is registered
2. Check JWT contains `tenant_id` or email
3. Test with different user accounts
4. Query database to verify `tenant_id` field

---

## 🎓 CUSTOMER TRAINING MATERIALS

### For Business Owners:

**"Your AI Just Captured a Lead - Now What?"**

1. **Check Email**: You'll get instant notification
2. **Open Dashboard**: Visit `/leads` to see details
3. **Review Transcript**: Read full AI conversation
4. **Take Action**:
   - Click "📞 Call Now" to phone customer
   - Click "📧 Email" to send follow-up
   - Mark as "Contacted" after reaching out
5. **Track ROI**: Watch "Today's Impact" metrics grow

**"Understanding Your Dashboard"**

- **💰 Leads Captured**: How many potential customers AI found
- **✅ Converted**: How many became actual sales
- **💵 Estimated Value**: Projected revenue from leads
- **📈 Conversion Rate**: Your closing percentage

**"Best Practices"**

- ✅ Respond to leads within 24 hours (ideally 1 hour)
- ✅ Review AI transcripts before calling
- ✅ Mark lead status to track pipeline
- ✅ Check dashboard daily

---

## 🚀 LAUNCH DAY TIMELINE

### Morning (9 AM - 12 PM)
- [ ] Final environment variable check
- [ ] Deploy to production
- [ ] Smoke test all features
- [ ] Monitor error logs

### Afternoon (12 PM - 5 PM)
- [ ] Onboard first 3 customers
- [ ] Watch for first captured lead
- [ ] Respond to support questions
- [ ] Fix any bugs immediately

### Evening (5 PM - 9 PM)
- [ ] Review day's metrics
- [ ] Document any issues
- [ ] Plan tomorrow's improvements
- [ ] Celebrate launch! 🎉

---

## 📱 MARKETING COPY (For Customer Acquisition)

### Headline:
**"Your AI Captured 12 Leads While You Slept"**

### Subheadline:
Never miss a customer again. AUREM AI works 24/7 to capture leads, book appointments, and track inventory—so you can focus on running your business.

### Feature Bullets:
- ✅ **24/7 Lead Capture**: AI detects buying intent and saves customer info automatically
- ✅ **Instant Alerts**: Get notified the second a lead is captured
- ✅ **Smart Inventory**: Never promise out-of-stock products (Shopify sync)
- ✅ **One Dashboard**: See leads, conversions, and revenue in real-time
- ✅ **Multi-Channel**: Works on WhatsApp, SMS, Email, and Web Chat

### Pricing Tiers (Suggested):

**Free Plan**: 50 leads/month, basic features  
**Starter ($49/mo)**: 500 leads/month, email notifications  
**Professional ($149/mo)**: Unlimited leads, Shopify sync, priority support  
**Enterprise (Custom)**: White-label, dedicated instance, SLA  

---

## ✅ FINAL PRE-LAUNCH VERIFICATION

Run this checklist 1 hour before launch:

```bash
# 1. Backend health check
curl https://your-domain/api/health

# 2. Test lead capture
curl -X POST https://your-domain/api/leads/test-capture \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"test","conversation_id":"launch_test","user_message":"I want to buy your product"}'

# 3. Check logs for errors
tail -n 100 /var/log/supervisor/backend.err.log | grep ERROR

# 4. Verify frontend loads
curl -I https://your-domain/leads

# 5. Check database connection
# (Monitor logs for "MongoDB connected" message)
```

---

## 🎉 YOU'RE READY TO LAUNCH!

Once all checkboxes above are ✅, you're ready to onboard customers.

**First Customer Onboarding Script**:
1. "Welcome to AUREM! Let's get you set up in 5 minutes."
2. "Create your account at [your-domain]/auth"
3. "Visit [your-domain]/leads to see your dashboard"
4. "Send a test message to trigger lead capture"
5. "Watch the magic happen! 🎯"

---

**Questions? Issues? Next Steps?**
- Phase C (Human Panic Button): Add sentiment analysis
- Phase D (Omnichannel Hub): Unified inbox
- Integrations: Google Calendar OAuth, more platforms

**You're now officially a "Small Business Killer" platform! 🚀**
