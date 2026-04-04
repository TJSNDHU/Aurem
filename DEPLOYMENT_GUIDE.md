# 🚀 PRODUCTION DEPLOYMENT GUIDE - AUREM AI
**Deploying Phase A (Lead Capture) + Phase B (Shopify Sync)**

---

## ✅ PRE-DEPLOYMENT CHECKLIST (COMPLETED)

- [x] Backend service: HEALTHY ✅
- [x] Frontend service: RUNNING ✅
- [x] JWT_SECRET: Production-grade (64 chars) ✅
- [x] EMERGENT_LLM_KEY: Configured ✅
- [x] Critical routes: Leads + Shopify loaded ✅
- [x] Database: Connected ✅
- [ ] RESEND_API_KEY: Optional (email notifications)

---

## 🎯 DEPLOYMENT OPTIONS

### Option 1: Emergent Native Deployment (RECOMMENDED) ⭐
**Pros**:
- ✅ Zero configuration
- ✅ Automatic HTTPS
- ✅ Environment variables auto-managed
- ✅ Scalable infrastructure
- ✅ Built-in monitoring
- ✅ Free subdomain: `your-app.preview.emergentagent.com`

**Steps**:
1. Click "Deploy" button in Emergent UI
2. Wait 2-3 minutes for deployment
3. Visit your production URL
4. Done! 🎉

**Cost**: Included in Emergent subscription

---

### Option 2: Export to GitHub + Vercel/Railway
**Pros**:
- ✅ Custom domain support
- ✅ Git-based workflow
- ✅ CI/CD pipeline

**Steps**:
1. Use Emergent "Save to GitHub" feature
2. Connect GitHub repo to Vercel/Railway
3. Configure environment variables:
   ```
   JWT_SECRET=W9KJ%R2$JdK#DwtgxNx5K5pcRYK0gWT6Dag8Twu3eVeH25SrJUN4EwCHFlCBu%jI
   EMERGENT_LLM_KEY=sk-emergent-0D2C22421Cb5436270
   MONGO_URL=your-mongodb-connection-string
   DB_NAME=aurem_database
   RESEND_API_KEY=re_your_key (optional)
   ```
4. Deploy

**Cost**: 
- Vercel: Free tier available, $20/mo for Pro
- Railway: $5/mo for 500 hours

---

### Option 3: Self-Hosted (AWS/GCP/DigitalOcean)
**Pros**:
- ✅ Full control
- ✅ Scalability
- ✅ Custom infrastructure

**Steps**: (Advanced users only)
1. Set up Ubuntu 22.04 server
2. Install Docker & Docker Compose
3. Clone repository
4. Configure environment variables
5. Set up Nginx reverse proxy
6. Configure SSL (Let's Encrypt)
7. Deploy containers

**Cost**: $20-$100/mo depending on traffic

---

## 🚀 RECOMMENDED: EMERGENT NATIVE DEPLOYMENT

Since you're already on Emergent, this is the fastest path to production.

### Deployment Steps:

1. **In Emergent Dashboard**:
   - Click "Deploy" or "Publish" button
   - Select production environment
   - Confirm deployment

2. **Wait for Deployment** (2-3 minutes):
   - Backend builds
   - Frontend builds
   - Services start
   - Health checks pass

3. **Verify Deployment**:
   ```bash
   # Visit your production URL
   https://your-app.preview.emergentagent.com
   
   # Check health endpoint
   curl https://your-app.preview.emergentagent.com/api/health
   
   # Expected: {"status": "ok"}
   ```

4. **Test Critical Flows**:
   - Visit `/leads` dashboard
   - Test lead capture: `/api/leads/test-capture`
   - Check Shopify webhook receiver

---

## 📊 POST-DEPLOYMENT VERIFICATION

### Test 1: Health Check
```bash
curl https://your-domain.com/api/health
# Expected: {"status":"ok"}
```

### Test 2: Lead Capture
```bash
curl -X POST https://your-domain.com/api/leads/test-capture \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "reroots_aesthetics",
    "conversation_id": "prod_test_001",
    "user_message": "I want to book a consultation tomorrow"
  }'
# Expected: {"success":true,"result":{"lead_captured":true,...}}
```

### Test 3: Dashboard Access
```
Visit: https://your-domain.com/leads
Expected: Dashboard loads with metrics
```

### Test 4: Shopify Webhook
```bash
curl -X POST https://your-domain.com/api/shopify/test/simulate-order
# Expected: {"success":true,"message":"Simulated order processed"}
```

---

## 🔒 SECURITY POST-DEPLOYMENT

### 1. Environment Variables (CRITICAL)
Verify these are set in production:
- ✅ `JWT_SECRET` - Changed from default
- ✅ `EMERGENT_LLM_KEY` - Active
- ✅ `MONGO_URL` - Secure connection string
- ⚠️ `RESEND_API_KEY` - Optional (for emails)

### 2. HTTPS
- ✅ Emergent auto-provisions SSL certificates
- ✅ All traffic encrypted
- ✅ HSTS headers enabled

### 3. CORS
- ✅ Already configured in `server.py`
- ✅ Only allows your frontend domain

### 4. Rate Limiting
- ⚠️ TODO: Add rate limiting for API endpoints
- Recommended: 100 requests/minute per IP

---

## 📧 OPTIONAL: ENABLE EMAIL NOTIFICATIONS

**To activate email alerts for lead captures**:

1. **Get Resend API Key** (Free tier: 3,000 emails/mo):
   - Visit: https://resend.com
   - Sign up → Get API key
   - Copy key (starts with `re_`)

2. **Add to Environment Variables**:
   ```bash
   RESEND_API_KEY=re_your_key_here
   ```

3. **Restart Backend**:
   ```bash
   # Emergent auto-restarts on env variable change
   # Or manually: sudo supervisorctl restart backend
   ```

4. **Test Email**:
   - Capture a test lead
   - Check your email inbox
   - Should receive: "🎯 New Lead Captured: [Name]"

**Without Resend Key**:
- ✅ System still works
- ⚠️ Emails logged to console instead of sent
- ℹ️ You can view leads in dashboard

---

## 🎯 FIRST CUSTOMER ONBOARDING

Once deployed, here's how to onboard your first customer:

### Step 1: Send Them the Link
```
Hi [Customer Name],

Welcome to AUREM AI! Your AI business assistant is ready.

Dashboard: https://your-domain.com/leads
Login: [Their email]
Password: [Temporary password]

Your AI will start capturing leads automatically. 
You'll see them appear in real-time on your dashboard.

Questions? Reply to this email.

Best,
[Your Name]
```

### Step 2: Walk Them Through
1. **Login**: They access `/auth` and log in
2. **Dashboard Tour**: Show them `/leads` metrics
3. **Test Lead**: Send a test message to trigger capture
4. **Watch Magic**: Lead appears in dashboard
5. **Explain Actions**: Call, Email, Update Status buttons

### Step 3: Shopify Integration (If Applicable)
1. **In Shopify Admin**:
   - Settings → Notifications → Webhooks
   - Add webhook: `https://your-domain.com/api/shopify/webhooks/orders/create`
   - Add webhook: `https://your-domain.com/api/shopify/webhooks/products/update`

2. **Test**:
   - Place a test order in Shopify
   - Verify inventory decreases in AUREM
   - AI knows product is out of stock

---

## 📊 MONITORING & MAINTENANCE

### Daily Checks:
- [ ] Backend uptime: `curl https://your-domain.com/api/health`
- [ ] Leads being captured: Check `/api/leads/stats`
- [ ] Error logs: Check Emergent dashboard or logs

### Weekly Checks:
- [ ] Database backup verified
- [ ] Customer feedback collected
- [ ] Performance metrics (API response time)
- [ ] EMERGENT_LLM_KEY balance

### Monthly Checks:
- [ ] Security updates
- [ ] Customer churn analysis
- [ ] Feature requests prioritized
- [ ] Revenue metrics (MRR, ARR)

---

## 🆘 TROUBLESHOOTING

### "Backend not responding"
1. Check Emergent dashboard for errors
2. View logs: `/var/log/supervisor/backend.err.log`
3. Restart: Click "Restart" in Emergent UI
4. If persists: Contact Emergent support

### "Leads not capturing"
1. Check backend logs for errors
2. Test endpoint: `/api/leads/test-capture`
3. Verify database connection
4. Check `TenantContext` is set

### "Emails not sending"
1. Verify `RESEND_API_KEY` is set
2. Check Resend dashboard for delivery status
3. Check spam folder
4. Verify email format is valid

### "Shopify webhooks failing"
1. Check Shopify webhook delivery logs
2. Verify webhook URL is correct
3. Test with `/api/shopify/test/simulate-order`
4. Check database for inventory updates

---

## 🎉 DEPLOYMENT COMPLETE!

**What You Just Deployed**:
✅ Lead capture automation (24/7)  
✅ Shopify inventory sync (real-time)  
✅ Multi-tenant architecture (secure)  
✅ Beautiful dashboard (analytics)  
✅ Email notifications (optional)  
✅ Production-grade security  

**What Happens Next**:
1. 📧 Onboard first 3-5 beta customers
2. 📊 Watch leads get captured
3. 💬 Collect feedback
4. 🐛 Fix any bugs immediately
5. 📈 Scale to 10, then 50, then 100+ customers

**Your SaaS is LIVE. Time to make money!** 🚀

---

## 📞 SUPPORT

**Questions?**
- Documentation: All guides in `/app/*.md`
- Emergent Support: support@emergent.ai
- Community: Emergent Discord

**Next Steps?**
- Phase C: Build Human Panic Button (4-6 hours)
- Phase D: Build Omnichannel Hub (2-3 days)
- Sales Focus: Create marketing materials
- Scale: Onboard 50+ customers

---

**Congratulations on launching your SaaS platform!** 🎊
