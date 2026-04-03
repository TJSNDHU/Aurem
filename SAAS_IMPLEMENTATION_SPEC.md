# AUREM AI - SAAS FREEMIUM MODEL
## Technical Implementation Specification

**Version:** 1.0  
**Date:** January 2026  
**Implementation Timeline:** Phased Approach (2-4 weeks for production-ready)

---

## 🎯 BUSINESS REQUIREMENTS

### 4-Tier Subscription Model
1. **FREE** - Existing AUREM system (limited features)
2. **STARTER** - $99/month
3. **PROFESSIONAL** - $399/month  
4. **ENTERPRISE** - $999/month
5. **CUSTOM À LA CARTE** - User picks specific features

### Critical Success Criteria
✅ **ZERO loose ends** - Everything must work perfectly  
✅ **NO broken links** - All integrations must be tested  
✅ **Build ONCE** - Production-ready from day one  
✅ **Feature Customization** - Users can build their own plan

---

## 🗄️ DATABASE SCHEMA DESIGN

### New Collections Required:

#### 1. **subscriptions** Collection
```javascript
{
  "id": "sub_xxxxx",  // Unique subscription ID
  "user_id": "user_xxxxx",  // Reference to users collection
  "tier": "free|starter|professional|enterprise|custom",  // Subscription tier
  "status": "active|cancelled|past_due|trialing",  // Subscription status
  "stripe_subscription_id": "sub_stripe_xxxxx",  // Stripe subscription ID
  "stripe_customer_id": "cus_stripe_xxxxx",  // Stripe customer ID
  
  // Billing
  "amount": 99.00,  // Monthly amount in USD
  "currency": "usd",
  "billing_cycle": "monthly|annual",  // Billing frequency
  "trial_ends_at": "2026-02-15T00:00:00Z",  // Trial end date (if applicable)
  "current_period_start": "2026-01-01T00:00:00Z",
  "current_period_end": "2026-02-01T00:00:00Z",
  
  // Custom À La Carte (for custom tier)
  "custom_features": [
    {
      "feature_id": "multi_agent",
      "feature_name": "Multi-Agent Crews",
      "price": 50.00,
      "enabled": true
    },
    {
      "feature_id": "voice_to_voice",
      "feature_name": "Voice-to-Voice AI",
      "price": 30.00,
      "enabled": true
    }
  ],
  
  // Usage Tracking
  "usage": {
    "ai_tokens_used": 15000,  // Current period token usage
    "ai_tokens_limit": 50000,  // Token limit for tier
    "formulas_count": 5,  // Number of formulas stored
    "formulas_limit": 20,  // Formula limit for tier
    "content_generated": 12,  // Content pieces generated this period
    "content_limit": 50,  // Content limit for tier
    "workflows_count": 3,  // Active automation workflows
    "workflows_limit": 5  // Workflow limit for tier
  },
  
  // Feature Flags (what this subscription has access to)
  "features": {
    "ai_chat": true,
    "voice_tts": "browser|openai|voxtral",  // Voice quality level
    "voice_to_voice": false,
    "multi_agent": false,
    "crew_ai": [],  // Array of available crews ["editorial", "biotech", ...]
    "automation_workflows": 5,  // Max workflows allowed
    "video_upscaling": false,
    "competitive_intelligence": false,
    "api_access": false,
    "white_label": false,
    "3d_visualization": false,
    "embeddable_widget": false,
    "priority_support": false,
    "custom_development": false
  },
  
  // Metadata
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-15T10:30:00Z",
  "cancelled_at": null,  // Cancellation timestamp
  "cancellation_reason": null,  // Why they cancelled
  "brand_id": "aurem"  // For RLS (multi-tenant)
}
```

#### 2. **users** Collection (Updates to existing)
```javascript
{
  "id": "user_xxxxx",
  "email": "customer@example.com",
  "name": "John Doe",
  "password_hash": "...",
  
  // NEW FIELDS FOR SAAS
  "subscription_id": "sub_xxxxx",  // Current active subscription
  "subscription_tier": "professional",  // Quick reference
  "stripe_customer_id": "cus_stripe_xxxxx",  // Stripe customer ID
  "trial_used": false,  // Has user used their free trial?
  "onboarding_completed": false,  // Has user completed onboarding?
  
  // Existing fields...
  "created_at": "2026-01-01T00:00:00Z",
  "brand_id": "aurem"
}
```

#### 3. **subscription_plans** Collection (Master plan configuration)
```javascript
{
  "id": "plan_starter",
  "tier": "starter",
  "name": "Starter",
  "tagline": "Perfect for solopreneurs",
  "price_monthly": 99.00,
  "price_annual": 950.00,  // 20% discount
  "currency": "usd",
  "stripe_price_id_monthly": "price_stripe_xxxxx",  // Stripe price ID
  "stripe_price_id_annual": "price_stripe_xxxxx",
  
  // Feature Limits
  "limits": {
    "ai_tokens": 50000,  // per month
    "formulas": 20,
    "content_pieces": 50,  // per month
    "workflows": 5,
    "video_upscaling": 0  // 0 = disabled
  },
  
  // Feature Access
  "features": {
    "ai_chat": true,
    "voice_tts": "openai",  // browser|openai|voxtral
    "voice_to_voice": false,
    "multi_agent": false,
    "crew_ai": [],
    "automation_workflows": 5,
    "video_upscaling": false,
    "competitive_intelligence": false,
    "api_access": false,
    "white_label": false,
    "3d_visualization": false,
    "embeddable_widget": false,
    "priority_support": false,
    "custom_development": false,
    "remove_branding": true
  },
  
  // Marketing Copy
  "features_list": [
    "20 Formula Storage",
    "50 AI Content/Month",
    "Premium OpenAI TTS",
    "5 Automation Workflows",
    "Email Support (48hr)"
  ],
  
  "active": true,
  "created_at": "2026-01-01T00:00:00Z"
}
```

#### 4. **feature_catalog** Collection (À La Carte Options)
```javascript
{
  "id": "feature_voice_to_voice",
  "name": "Voice-to-Voice AI",
  "description": "Full conversational AI with Whisper + TTS",
  "category": "voice",  // voice|automation|intelligence|brand
  "price_monthly": 30.00,
  "price_annual": 288.00,  // 20% discount
  "currency": "usd",
  "stripe_price_id_monthly": "price_stripe_xxxxx",
  
  // Feature Configuration
  "feature_key": "voice_to_voice",  // Used in subscription.features
  "dependencies": ["ai_chat"],  // Required features
  "conflicts": [],  // Mutually exclusive features
  
  // Marketing
  "icon": "🎙️",
  "tagline": "Real-time conversational AI",
  "benefits": [
    "Near-zero latency responses",
    "Natural voice interactions",
    "Custom wake word support"
  ],
  
  "active": true,
  "popular": true,  // Show "Popular" badge
  "created_at": "2026-01-01T00:00:00Z"
}
```

#### 5. **usage_logs** Collection (Track usage for limits)
```javascript
{
  "id": "log_xxxxx",
  "user_id": "user_xxxxx",
  "subscription_id": "sub_xxxxx",
  "resource_type": "ai_tokens|formula|content|workflow|video",  // What was used
  "amount": 1500,  // Tokens used, or 1 for countable resources
  "metadata": {
    "model": "gpt-4o",
    "endpoint": "/api/aurem/chat",
    "formula_id": "form_xxxxx"  // If applicable
  },
  "timestamp": "2026-01-15T10:30:00Z",
  "brand_id": "aurem"
}
```

---

## 🔌 BACKEND API ENDPOINTS

### Authentication & User Management

#### POST `/api/auth/register`
**Purpose:** Register new user (starts with FREE tier)
```json
Request:
{
  "email": "user@example.com",
  "password": "SecurePassword123",
  "name": "John Doe"
}

Response:
{
  "success": true,
  "user": {
    "id": "user_xxxxx",
    "email": "user@example.com",
    "subscription_tier": "free"
  },
  "token": "jwt_token_here"
}
```

#### POST `/api/auth/login`
**Purpose:** Existing endpoint - no changes needed
**Note:** After login, fetch subscription details

---

### Subscription Management

#### GET `/api/subscriptions/plans`
**Purpose:** Get all available subscription plans
```json
Response:
{
  "plans": [
    {
      "id": "plan_free",
      "tier": "free",
      "name": "Free Forever",
      "price_monthly": 0,
      "features": {...},
      "limits": {...},
      "features_list": [...]
    },
    {
      "id": "plan_starter",
      "tier": "starter",
      "name": "Starter",
      "price_monthly": 99,
      "price_annual": 950,
      "features": {...},
      "limits": {...},
      "features_list": [...]
    },
    ...
  ]
}
```

#### GET `/api/subscriptions/features/catalog`
**Purpose:** Get à la carte feature catalog
```json
Response:
{
  "features": [
    {
      "id": "feature_voice_to_voice",
      "name": "Voice-to-Voice AI",
      "price_monthly": 30,
      "icon": "🎙️",
      ...
    },
    ...
  ],
  "categories": ["voice", "automation", "intelligence", "brand"]
}
```

#### GET `/api/subscriptions/me`
**Purpose:** Get current user's subscription details
**Auth:** Required
```json
Response:
{
  "subscription": {
    "id": "sub_xxxxx",
    "tier": "professional",
    "status": "active",
    "amount": 399,
    "current_period_end": "2026-02-01T00:00:00Z",
    "features": {...},
    "usage": {
      "ai_tokens_used": 15000,
      "ai_tokens_limit": 200000,
      "formulas_count": 12,
      "formulas_limit": 50,
      ...
    }
  }
}
```

#### POST `/api/subscriptions/checkout`
**Purpose:** Create Stripe checkout session for subscription
**Auth:** Required
```json
Request:
{
  "plan_id": "plan_starter",
  "billing_cycle": "monthly",  // monthly|annual
  "custom_features": []  // For custom à la carte (optional)
}

Response:
{
  "success": true,
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_xxxxx",
  "session_id": "cs_xxxxx"
}
```

#### POST `/api/subscriptions/upgrade`
**Purpose:** Upgrade/downgrade subscription tier
**Auth:** Required
```json
Request:
{
  "new_plan_id": "plan_professional"
}

Response:
{
  "success": true,
  "message": "Upgraded to Professional tier",
  "subscription": {...}
}
```

#### POST `/api/subscriptions/cancel`
**Purpose:** Cancel subscription (continues until period end)
**Auth:** Required
```json
Request:
{
  "reason": "Too expensive",  // Optional
  "feedback": "Great product but need to cut costs"  // Optional
}

Response:
{
  "success": true,
  "message": "Subscription will cancel on 2026-02-01",
  "access_until": "2026-02-01T00:00:00Z"
}
```

#### POST `/api/subscriptions/resume`
**Purpose:** Resume cancelled subscription
**Auth:** Required
```json
Response:
{
  "success": true,
  "message": "Subscription resumed",
  "subscription": {...}
}
```

---

### Feature Usage Tracking

#### POST `/api/subscriptions/usage/track`
**Purpose:** Track resource usage (called internally)
**Auth:** Internal only
```json
Request:
{
  "user_id": "user_xxxxx",
  "resource_type": "ai_tokens",
  "amount": 1500,
  "metadata": {
    "model": "gpt-4o",
    "endpoint": "/api/aurem/chat"
  }
}
```

#### POST `/api/subscriptions/usage/check`
**Purpose:** Check if user can perform action (rate limiting)
**Auth:** Internal only
```json
Request:
{
  "user_id": "user_xxxxx",
  "resource_type": "formula",  // Check formula limit
  "action": "create"  // create|read|update|delete
}

Response:
{
  "allowed": true,  // or false
  "usage": {
    "current": 5,
    "limit": 20,
    "remaining": 15
  },
  "upgrade_required": false,
  "message": "15 formulas remaining"
}
```

---

### Admin Panel Endpoints

#### GET `/api/admin/subscriptions`
**Purpose:** Get all subscriptions (admin only)
**Auth:** Admin role required
```json
Response:
{
  "subscriptions": [
    {
      "id": "sub_xxxxx",
      "user": {
        "email": "user@example.com",
        "name": "John Doe"
      },
      "tier": "professional",
      "status": "active",
      "amount": 399,
      "created_at": "2026-01-01T00:00:00Z"
    },
    ...
  ],
  "stats": {
    "total": 150,
    "active": 120,
    "cancelled": 20,
    "past_due": 10,
    "mrr": 35000  // Monthly Recurring Revenue
  }
}
```

#### POST `/api/admin/subscriptions/:subscription_id/modify`
**Purpose:** Admin manually modify subscription
**Auth:** Admin role required
```json
Request:
{
  "tier": "enterprise",
  "amount": 999,
  "features": {...},
  "reason": "Custom enterprise deal"
}
```

---

## 🎨 FRONTEND COMPONENTS TO BUILD

### 1. Pricing Page (`/pricing`)
**File:** `/app/frontend/src/pages/PricingPage.jsx`

**Features:**
- Display all 4 tiers in card format
- Toggle monthly/annual pricing
- "Build Your Own" custom à la carte section
- Feature comparison table
- FAQ section

**Components:**
- `<PricingCard />` - Individual tier card
- `<PricingToggle />` - Monthly/Annual switch
- `<FeatureComparison />` - Feature comparison table
- `<CustomBuilder />` - À la carte feature selector
- `<FAQ />` - Pricing FAQs

### 2. Subscription Dashboard (`/dashboard/subscription`)
**File:** `/app/frontend/src/platform/SubscriptionManager.jsx`

**Features:**
- Current plan details
- Usage meters (tokens, formulas, content, etc.)
- Upgrade/downgrade buttons
- Billing history
- Cancel/resume subscription
- Add à la carte features

**Components:**
- `<UsageMeter />` - Visual usage bars
- `<BillingHistory />` - Invoice list
- `<UpgradePrompt />` - Contextual upgrade suggestions

### 3. Onboarding Flow (`/onboarding`)
**File:** `/app/frontend/src/platform/AuremOnboarding.jsx` (Update existing)

**Steps:**
1. Welcome screen
2. Choose your plan (with 14-day trial for paid tiers)
3. Customize features (if custom plan)
4. Enter payment info (Stripe checkout)
5. Setup workspace (business name, etc.)
6. Quick tutorial

### 4. Feature Upgrade Prompts (In-App)
**File:** `/app/frontend/src/components/UpgradeModal.jsx`

**Triggers:**
- User hits formula limit → "Upgrade to store more formulas"
- User tries to use locked feature → "Unlock Voice-to-Voice AI"
- User hits content limit → "Generate unlimited content with Professional"

### 5. Admin Subscription Panel
**File:** `/app/frontend/src/components/admin/SubscriptionAdmin.jsx`

**Features:**
- List all subscriptions
- Filter by tier/status
- MRR/ARR metrics
- Churn analysis
- Manual subscription modification

---

## 🔐 FEATURE FLAG MIDDLEWARE

### Backend Middleware (`/app/backend/middleware/subscription_guard.py`)
**Already exists - needs update**

```python
async def require_feature(feature_key: str):
    """
    Decorator to protect routes by feature access.
    
    Usage:
    @app.get("/api/voice/to-voice")
    @require_feature("voice_to_voice")
    async def voice_endpoint(user=Depends(get_current_user)):
        ...
    """
    async def check_access(user_id: str):
        subscription = await db.subscriptions.find_one({"user_id": user_id})
        
        if not subscription:
            raise HTTPException(403, "No active subscription")
        
        if not subscription["features"].get(feature_key):
            raise HTTPException(
                403,
                detail={
                    "error": "feature_locked",
                    "message": f"This feature requires a higher tier",
                    "feature": feature_key,
                    "current_tier": subscription["tier"]
                }
            )
        
        return subscription
    
    return Depends(check_access)
```

### Frontend Feature Flags (`/app/frontend/src/contexts/SubscriptionContext.js`)

```javascript
export const SubscriptionContext = createContext();

export function SubscriptionProvider({ children }) {
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Fetch subscription on mount
  useEffect(() => {
    fetchSubscription();
  }, []);
  
  const fetchSubscription = async () => {
    const response = await fetch('/api/subscriptions/me');
    const data = await response.json();
    setSubscription(data.subscription);
    setLoading(false);
  };
  
  // Check if user has access to feature
  const hasFeature = (feature_key) => {
    return subscription?.features?.[feature_key] || false;
  };
  
  // Check usage limit
  const checkLimit = (resource_type) => {
    const usage = subscription?.usage || {};
    return {
      current: usage[`${resource_type}_count`] || usage[`${resource_type}_used`] || 0,
      limit: usage[`${resource_type}_limit`] || 0,
      remaining: (usage[`${resource_type}_limit`] || 0) - (usage[`${resource_type}_count`] || usage[`${resource_type}_used`] || 0),
      percentage: ((usage[`${resource_type}_count`] || usage[`${resource_type}_used`] || 0) / (usage[`${resource_type}_limit`] || 1)) * 100
    };
  };
  
  return (
    <SubscriptionContext.Provider value={{
      subscription,
      loading,
      hasFeature,
      checkLimit,
      refreshSubscription: fetchSubscription
    }}>
      {children}
    </SubscriptionContext.Provider>
  );
}

// Hook
export function useSubscription() {
  return useContext(SubscriptionContext);
}
```

---

## 💳 STRIPE INTEGRATION

### Stripe Products & Prices Setup (Manual in Stripe Dashboard)

1. **Create Products:**
   - Free (no Stripe product needed)
   - Starter
   - Professional
   - Enterprise
   - Each à la carte feature

2. **Create Prices for each product:**
   - Monthly recurring
   - Annual recurring (with 20% discount)

3. **Store Stripe IDs in database:**
   ```javascript
   subscription_plans.stripe_price_id_monthly = "price_xxxxx"
   subscription_plans.stripe_price_id_annual = "price_xxxxx"
   ```

### Webhook Handler (`/api/webhooks/stripe`)
**File:** `/app/backend/routers/stripe_webhook.py`

**Events to Handle:**
- `checkout.session.completed` - New subscription created
- `customer.subscription.updated` - Subscription changed (upgrade/downgrade)
- `customer.subscription.deleted` - Subscription cancelled
- `invoice.payment_succeeded` - Payment successful
- `invoice.payment_failed` - Payment failed

---

## 📊 USAGE TRACKING IMPLEMENTATION

### Automatic Usage Tracking

**Wrap all AI endpoints:**
```python
# Before calling LLM
await track_usage(user_id, "ai_tokens", tokens_to_use, metadata)

# Check limit first
can_use = await check_usage_limit(user_id, "ai_tokens", tokens_to_use)
if not can_use:
    raise HTTPException(429, "Token limit exceeded. Upgrade to continue.")

# Proceed with LLM call...
```

**Track on every action:**
- Formula creation → `track_usage(user_id, "formula", 1)`
- Content generation → `track_usage(user_id, "content", 1)`
- Workflow creation → `track_usage(user_id, "workflow", 1)`
- Video upscaling → `track_usage(user_id, "video", 1)`

---

## 🧪 TESTING CHECKLIST

### Unit Tests
- [ ] Subscription CRUD operations
- [ ] Feature flag checks
- [ ] Usage limit enforcement
- [ ] Stripe webhook handling
- [ ] À la carte feature pricing

### Integration Tests
- [ ] User registration → Free tier created
- [ ] Upgrade flow → Stripe checkout → Webhook → Tier updated
- [ ] Downgrade flow → Proration calculated
- [ ] Cancellation → Access continues until period end
- [ ] Usage tracking → Limits enforced
- [ ] Feature locks → API returns 403 when locked

### E2E Tests (via testing_agent_v3_fork)
- [ ] Complete user journey: Register → Trial → Upgrade → Use features → Cancel
- [ ] Custom à la carte: Build custom plan → Checkout → Features activated
- [ ] Limit enforcement: Hit formula limit → Upgrade prompt → Upgrade → Limit increased
- [ ] Payment failure: Simulate failed payment → Subscription past_due → Retry payment

---

## 📅 IMPLEMENTATION PHASES

### PHASE 1: Database & Core Logic (Week 1)
**Deliverables:**
1. ✅ Create new collections (subscriptions, subscription_plans, feature_catalog, usage_logs)
2. ✅ Seed initial subscription plans (FREE, Starter, Pro, Enterprise)
3. ✅ Seed feature catalog (20+ à la carte features)
4. ✅ Update users collection schema
5. ✅ Create subscription service (`/app/backend/services/subscription_service.py`)
6. ✅ Usage tracking middleware

**Testing:**
- Database queries work correctly
- Subscription CRUD operations functional
- Usage tracking logs correctly

---

### PHASE 2: Backend APIs (Week 1-2)
**Deliverables:**
1. ✅ `/api/subscriptions/plans` - Get all plans
2. ✅ `/api/subscriptions/features/catalog` - Get à la carte options
3. ✅ `/api/subscriptions/me` - Get user subscription
4. ✅ `/api/subscriptions/checkout` - Stripe checkout
5. ✅ `/api/subscriptions/upgrade` - Upgrade tier
6. ✅ `/api/subscriptions/cancel` - Cancel subscription
7. ✅ Feature flag middleware (`@require_feature()`)
8. ✅ Usage limit middleware (`@check_limit()`)
9. ✅ Stripe webhook handler
10. ✅ Admin subscription panel API

**Testing:**
- All endpoints return correct data
- Stripe integration works (test mode)
- Feature flags properly block unauthorized access
- Usage limits enforced correctly

---

### PHASE 3: Frontend UI (Week 2-3)
**Deliverables:**
1. ✅ Pricing page with 4 tiers
2. ✅ Custom à la carte builder
3. ✅ Subscription dashboard (usage meters, billing)
4. ✅ Upgrade modals (contextual prompts)
5. ✅ Onboarding flow (updated)
6. ✅ Admin subscription panel
7. ✅ SubscriptionContext (React Context)
8. ✅ Feature-gated components (`hasFeature()` checks)

**Testing:**
- UI renders correctly on mobile/desktop
- Stripe checkout flow works end-to-end
- Upgrade modals trigger correctly
- Usage meters display real-time data

---

### PHASE 4: Integration & Testing (Week 3-4)
**Deliverables:**
1. ✅ Comprehensive E2E tests (testing_agent_v3_fork)
2. ✅ Stripe webhook testing (use Stripe CLI)
3. ✅ Load testing (100+ concurrent users)
4. ✅ Security audit (API authorization, payment security)
5. ✅ Documentation (API docs, user guides)

**Testing:**
- Complete user journeys work flawlessly
- No broken links or edge cases
- Performance under load
- Security vulnerabilities patched

---

## 🚨 CRITICAL REQUIREMENTS

### ZERO Loose Ends Checklist:
- [ ] All API endpoints have error handling
- [ ] All database operations have try/catch
- [ ] All Stripe webhooks are idempotent
- [ ] All frontend forms have validation
- [ ] All usage limits are enforced
- [ ] All feature flags are checked before access
- [ ] All payments are secure (PCI compliant via Stripe)
- [ ] All admin actions are logged
- [ ] All errors are user-friendly
- [ ] All loading states are handled
- [ ] All edge cases are covered

### NO Broken Links Checklist:
- [ ] All navigation links work
- [ ] All API calls have fallbacks
- [ ] All Stripe redirects work
- [ ] All email links work
- [ ] All webhook URLs are correct
- [ ] All environment variables are set

---

## 📝 NEXT STEPS

1. **Review this specification** - Does it cover all your requirements?
2. **Approve to proceed** - Give me the green light
3. **Implementation starts** - I'll build systematically, test at each phase

**Estimated Timeline:**
- Phase 1 (Database): 2-3 days
- Phase 2 (Backend): 3-4 days
- Phase 3 (Frontend): 4-5 days
- Phase 4 (Testing): 2-3 days

**Total: 11-15 days for production-ready implementation**

---

**⚠️ IMPORTANT:** This is a LARGE project. I will build it systematically, test each component, and ensure ZERO loose ends. Do you approve this spec to proceed?
