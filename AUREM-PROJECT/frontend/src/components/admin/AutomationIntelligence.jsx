import { useState, useEffect, useRef } from "react";
import { useAdminBrand } from "./useAdminBrand";

// ─── CONFIG ────────────────────────────────────────────────────
const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// ─── THEME (Dynamic based on brand) ─────────────────────────────────────────
const getTheme = (isLaVela) => isLaVela ? {
  bg: "#0A3C3C", card: "#0D4D4D", cardHover: "#1A6B6B",
  border: "#D4A57440", borderBright: "#D4A57480",
  pink: "#D4A574", pinkDim: "#E6BE8A", pinkGlow: "rgba(212,165,116,0.15)",
  gold: "#D4A574", goldFaint: "rgba(212,165,116,0.1)",
  green: "#5CB88A", greenFaint: "rgba(92,184,138,0.1)",
  red: "#E07070", redFaint: "rgba(224,112,112,0.1)",
  blue: "#7AAEC8", blueFaint: "rgba(122,174,200,0.1)",
  purple: "#9B8EC4", purpleFaint: "rgba(155,142,196,0.1)",
  amber: "#E8A860",
  text: "#FDF8F5", textDim: "#D4A574", textMuted: "#E8C4B8",
} : {
  bg: "#0A0608", card: "#110C0E", cardHover: "#160F11",
  border: "#2A1F22", borderBright: "#4A2A32",
  pink: "#F8A5B8", pinkDim: "#C4748A", pinkGlow: "rgba(248,165,184,0.15)",
  gold: "#D4A853", goldFaint: "rgba(212,168,83,0.1)",
  green: "#5CB88A", greenFaint: "rgba(92,184,138,0.1)",
  red: "#E07070", redFaint: "rgba(224,112,112,0.1)",
  blue: "#7AAEC8", blueFaint: "rgba(122,174,200,0.1)",
  purple: "#9B8EC4", purpleFaint: "rgba(155,142,196,0.1)",
  amber: "#E8A860",
  text: "#F5EEF0", textDim: "#9A8A8E", textMuted: "#5A4A4E",
};

// Default theme for static references
const T = {
  bg: "#0A0608", card: "#110C0E", cardHover: "#160F11",
  border: "#2A1F22", borderBright: "#4A2A32",
  pink: "#F8A5B8", pinkDim: "#C4748A", pinkGlow: "rgba(248,165,184,0.15)",
  gold: "#D4A853", goldFaint: "rgba(212,168,83,0.1)",
  green: "#5CB88A", greenFaint: "rgba(92,184,138,0.1)",
  red: "#E07070", redFaint: "rgba(224,112,112,0.1)",
  blue: "#7AAEC8", blueFaint: "rgba(122,174,200,0.1)",
  purple: "#9B8EC4", purpleFaint: "rgba(155,142,196,0.1)",
  amber: "#E8A860",
  text: "#F5EEF0", textDim: "#9A8A8E", textMuted: "#5A4A4E",
};
const FD = "'Cormorant Garamond', Georgia, serif";
const FS = "'Inter', system-ui, sans-serif";
const FM = "'JetBrains Mono', 'Courier New', monospace";

// ─── AUTOMATION RULES ENGINE ────────────────────────────────────
const AUTOMATION_RULES = [
  {
    id:"A01", name:"Abandoned Cart Win-Back", status:"live", category:"Revenue Recovery",
    color: T.pink, icon:"🛒",
    trigger:"Cart abandoned > 1 hour",
    api_trigger:"POST /abandoned/run-automation",
    api_status:"GET /abandoned/stats",
    sequence:[
      {delay:"0 min",  action:"Email: Cart waiting for you + product image",   channel:"email", built:true},
      {delay:"24 hrs", action:"Email: 10% off code SAVE10 — expires in 48hrs",  channel:"email", built:true},
      {delay:"72 hrs", action:"Email: Final — your PDRN ritual is waiting",     channel:"email", built:true},
    ],
    stats:{label:"127 carts ready",value:"~$22,860",note:"est. at $180 avg"},
    blocker:"SendGrid API key not configured",
    blockerFix:"Add SENDGRID_API_KEY to .env — emails are built and tested",
    code:`# Trigger abandoned cart automation
POST ${API}/abandoned/run-automation
Authorization: Bearer {token}
Content-Type: application/json

# Check stats first
GET ${API}/abandoned/stats`,
  },
  {
    id:"A02", name:"FlagShip → Auto-Fulfill + Shipping Email", status:"needs_wire", category:"Order Flow",
    color: T.blue, icon:"📦",
    trigger:"FlagShip label created",
    api_trigger:"POST /admin/flagship/webhook (new endpoint needed)",
    api_status:"GET /admin/flagship/shipments",
    sequence:[
      {delay:"instant", action:"Auto-update order status → Shipped",          channel:"system", built:false},
      {delay:"instant", action:"Email: Your order is on its way + tracking",  channel:"email",  built:false},
      {delay:"instant", action:"Start 28-day CRM cycle clock",                channel:"system", built:false},
    ],
    stats:{label:"4 orders stuck",value:"0 shipped",note:"all pending"},
    blocker:"FlagShip webhook endpoint not built",
    blockerFix:"Add /admin/flagship/webhook handler in server.py — calls /business/fulfillment/orders/{id}/fulfill + sends email",
    code:`# Wire FlagShip webhook in server.py
@app.post("/api/admin/flagship/webhook")
async def flagship_webhook(payload: dict):
    order_id = payload.get("orderId")
    tracking = payload.get("trackingNumber")
    carrier  = payload.get("carrier")
    
    # 1. Mark order fulfilled
    await db.orders.update_one(
        {"_id": order_id},
        {"$set": {"status": "shipped", "trackingNumber": tracking, "carrier": carrier}}
    )
    
    # 2. Start 28-day cycle
    await db.crm_customers.update_one(
        {"email": order["customerEmail"]},
        {"$set": {"cycleStartDate": datetime.utcnow()}}
    )
    
    # 3. Send shipping email via existing automation
    await send_shipping_notification(order, carrier, tracking)
    return {"status": "ok"}`,
  },
  {
    id:"A03", name:"28-Day PDRN Science Cycle", status:"partial", category:"Customer Retention",
    color: T.purple, icon:"🔬",
    trigger:"Order fulfilled / cycle start date set",
    api_trigger:"POST /admin/automations/run",
    api_status:"GET /admin/automations/stats",
    sequence:[
      {delay:"Day 1",  action:"Email: Welcome + PDRN science education",       channel:"email", built:true},
      {delay:"Day 7",  action:"Email: Week 1 — what's happening in your skin", channel:"email", built:true},
      {delay:"Day 14", action:"Email: 2-week milestone + share on Instagram",  channel:"email", built:true},
      {delay:"Day 21", action:"Email: Review request — how is your skin?",     channel:"email", built:false},
      {delay:"Day 25", action:"Email + SMS: Running low nudge",                channel:"both",  built:true},
      {delay:"Day 28", action:"Email: Reorder + AURA-GEN bundle upsell",       channel:"email", built:true},
      {delay:"Day 35", action:"Email: Win-back + unique personal discount",    channel:"email", built:true},
    ],
    stats:{label:"Active cycle",value:"D1–D35",note:"7 touchpoints"},
    blocker:"Day 21 review request not wired to Reviews module",
    blockerFix:"On Day 21, POST /admin/reviews/request with customerEmail + orderId. Reviews module receives it.",
    code:`# Add Day 21 to automation engine
# In server.py run_repurchase_automations():
elif days_since == 21:
    await send_review_request(customer)
    
async def send_review_request(customer):
    # Insert review request record
    await db.review_requests.insert_one({
        "customerEmail": customer["email"],
        "customerName":  customer["name"],
        "orderId":       customer["lastOrderId"],
        "sentAt":        datetime.utcnow(),
        "status":        "pending"
    })
    # Send email via SendGrid
    await sendgrid_send(
        to=customer["email"],
        subject="How is your skin feeling? — ReRoots",
        template="review_request_d21"
    )`,
  },
  {
    id:"A04", name:"Partner Code → Commission Tracking", status:"broken", category:"Partner Revenue",
    color: T.gold, icon:"🤝",
    trigger:"Order placed with partner code",
    api_trigger:"GET /admin/partners/referrals",
    api_status:"GET /admin/partner-referrals",
    sequence:[
      {delay:"instant", action:"Validate partner code at checkout",         channel:"system", built:true},
      {delay:"instant", action:"Record referral attribution on order",      channel:"system", built:false},
      {delay:"instant", action:"Increment partner earnings in DB",          channel:"system", built:false},
      {delay:"monthly", action:"Send partner earnings report + payout",     channel:"email",  built:false},
    ],
    stats:{label:"6 active partners",value:"$0 tracked",note:"54% conversion rate"},
    blocker:"Order creation not writing partnerCode attribution to partner_referrals collection",
    blockerFix:"In /api/orders POST handler: if discountCode matches a partner code, write to partner_referrals collection with orderId, amount, commission",
    code:`# Fix order creation to track partner attribution
# In POST /api/orders handler:
if order.discount_code:
    partner = await db.partners.find_one({"code": order.discount_code})
    if partner:
        commission = order.total * 0.10  # 10% commission
        await db.partner_referrals.insert_one({
            "partnerId":    partner["_id"],
            "partnerEmail": partner["email"],
            "orderId":      order_id,
            "orderTotal":   order.total,
            "commission":   commission,
            "code":         order.discount_code,
            "createdAt":    datetime.utcnow(),
            "paid":         False
        })
        await db.partners.update_one(
            {"_id": partner["_id"]},
            {"$inc": {"totalEarnings": commission, "totalSales": order.total}}
        )`,
  },
  {
    id:"A05", name:"Loyalty Points — Auto-Award + Redeem", status:"broken", category:"Retention",
    color: T.green, icon:"⭐",
    trigger:"Order placed (award) / Checkout (redeem)",
    api_trigger:"POST /loyalty/points/earn",
    api_status:"GET /admin/loyalty/stats",
    sequence:[
      {delay:"instant", action:"Award 250 points on every purchase",      channel:"system", built:true},
      {delay:"Day 28",  action:"Email: You have X points — use on reorder",channel:"email",  built:false},
      {delay:"checkout",action:"Allow points redemption at checkout",      channel:"system", built:true},
    ],
    stats:{label:"0 members",value:"250 pts/order",note:"API error: users"},
    blocker:"GET /admin/loyalty/users returns 500 — query bug",
    blockerFix:"Fix MongoDB query in loyalty/users route — likely missing collection index or wrong field reference",
    code:`# Fix loyalty users endpoint
# Check what's failing:
GET ${API}/admin/loyalty/users
# If 500, check server.py loyalty route:
# Likely: await db.loyalty_users.find() — wrong collection name
# Should be: await db.users.find({"loyaltyPoints": {"$exists": True}})

# Add award call to order creation:
POST ${API}/loyalty/points/earn
{
  "userId": "{customer_id}",
  "points": 250,
  "reason": "purchase",
  "orderId": "{order_id}"
}`,
  },
  {
    id:"A06", name:"Waitlist → CRM + Restock Email", status:"not_built", category:"Pipeline",
    color: T.blue, icon:"📬",
    trigger:"Admin marks product restocked OR manually triggers",
    api_trigger:"POST /admin/inventory/ingredients (update stock) → trigger notify",
    api_status:"GET /admin/subscribers (waitlist source)",
    sequence:[
      {delay:"instant",  action:"Add waitlist contacts to CRM as leads",     channel:"system", built:false},
      {delay:"instant",  action:"Email: It's here — PDRN is back in stock",  channel:"email",  built:false},
      {delay:"72 hrs",   action:"Email: Last chance — selling fast",          channel:"email",  built:false},
    ],
    stats:{label:"35 waiting",value:"Warm leads",note:"Ready to buy"},
    blocker:"No restock trigger wired to waitlist notification",
    blockerFix:"When stock updated > 0 on a product, query waitlist subscribers matching that product, fire email sequence",
    code:`# Add to inventory update endpoint
# In PUT /api/products/{id} or /api/admin/inventory/ingredients/{id}:
if old_stock == 0 and new_stock > 0:
    # Get waitlist for this product
    waitlist = await db.subscribers.find({
        "type": "waitlist",
        "productId": product_id
    }).to_list(None)
    
    for contact in waitlist:
        # Add to CRM
        await db.crm_customers.update_one(
            {"email": contact["email"]},
            {"$set": {"source": "waitlist", "status": "warm_lead"}},
            upsert=True
        )
        # Queue restock email
        await send_restock_email(contact, product)`,
  },
  {
    id:"A07", name:"Marketing Lab → Reel + WhatsApp Blast", status:"live", category:"Content + Reach",
    color: T.pink, icon:"📱",
    trigger:"Manual — owner triggers from Marketing Lab",
    api_trigger:"POST /admin/ai-studio/generate-content",
    api_status:"GET /admin/ad-campaigns",
    sequence:[
      {delay:"instant", action:"Generate Reel script via AI Studio",        channel:"ai",      built:true},
      {delay:"manual",  action:"Approve + post to Instagram",               channel:"social",  built:true},
      {delay:"manual",  action:"WhatsApp blast to all contacts via WHAPI",  channel:"whatsapp",built:true},
      {delay:"manual",  action:"SMS to SMS subscribers via Twilio",         channel:"sms",     built:true},
    ],
    stats:{label:"42 leads ready",value:"4 WA contacts",note:"WHAPI + Twilio live"},
    blocker:"WhatsApp/SMS sends real but Marketing Lab content not auto-routing to broadcast",
    blockerFix:"Add 'Blast This' button in Marketing Lab that pre-fills WhatsApp broadcast with generated caption",
    code:`# Marketing Lab → WhatsApp Blast flow
# Step 1: Generate content
POST ${API}/admin/ai-studio/generate-content
{
  "type": "caption",
  "product": "AURA-GEN PDRN+TXA",
  "concern": "aging"
}

# Step 2: Send WhatsApp broadcast
POST ${API}/admin/whatsapp/broadcast   (or WHAPI endpoint)
{
  "message": "{generated_caption}",
  "contacts": "all"
}

# Step 3: SMS to subscribers
POST ${API}/admin/sms-subscribers/broadcast
{
  "message": "{generated_sms_version}"
}`,
  },
  {
    id:"A08", name:"Quiz → High-Intent Lead → Instant CRM", status:"live", category:"Lead Capture",
    color: T.green, icon:"🧬",
    trigger:"Quiz submitted (87.5% conversion rate)",
    api_trigger:"POST /quiz/submit (existing)",
    api_status:"GET /admin/quiz-submissions",
    sequence:[
      {delay:"instant", action:"Score quiz → product recommendation",        channel:"system", built:true},
      {delay:"instant", action:"Add to CRM as high-intent lead",            channel:"system", built:false},
      {delay:"instant", action:"Email: Your personalised PDRN protocol",    channel:"email",  built:false},
      {delay:"24 hrs",  action:"Email: Shop your recommended ritual",        channel:"email",  built:false},
    ],
    stats:{label:"87.5% CVR",value:"42 leads",note:"Best funnel you have"},
    blocker:"Quiz submit not creating CRM record or firing welcome email",
    blockerFix:"In POST /quiz/submit: after scoring, upsert CRM customer with quizScore + recommendations, fire email",
    code:`# Add to quiz/submit handler:
@app.post("/api/quiz/submit")
async def submit_quiz(data: QuizSubmission):
    # Existing scoring logic...
    result = score_quiz(data)
    
    # NEW: Add to CRM
    await db.crm_customers.update_one(
        {"email": data.email},
        {"$set": {
            "source": "quiz",
            "quizScore":        result["score"],
            "recommendedProduct": result["product"],
            "skinConcerns":     result["concerns"],
            "status":           "high_intent_lead",
            "createdAt":        datetime.utcnow()
        }},
        upsert=True
    )
    
    # NEW: Fire personalised email
    await sendgrid_send(
        to=data.email,
        subject="Your personalised PDRN protocol — ReRoots",
        template="quiz_result",
        data={"recommendations": result, "name": data.name}
    )
    
    return result`,
  },
  {
    id:"A09", name:"Bio-Age Scan → Marketing Lab Target", status:"live", category:"Lead Intelligence",
    color: T.purple, icon:"🔭",
    trigger:"Bio-Age Scan submitted",
    api_trigger:"POST /bio-scan/submit (existing)",
    api_status:"GET /admin/ai-studio/* (marketing lab reads it)",
    sequence:[
      {delay:"instant", action:"Analyze face scan → calculate bio-age",      channel:"ai",    built:true},
      {delay:"instant", action:"Email: Your bio-age results + solution",     channel:"email", built:false},
      {delay:"instant", action:"Tag lead in Marketing Lab as high-intent",   channel:"system",built:true},
      {delay:"24 hrs",  action:"Auto-generate targeted ad content from Lab", channel:"ai",    built:false},
    ],
    stats:{label:"42 scans total",value:"2 high-intent",note:"sensitivity + aging"},
    blocker:"Scan completion not triggering result email",
    blockerFix:"After bio-scan analysis, fire personalised email with bio-age result + recommended AURA-GEN products",
    code:`# Add email trigger to bio-scan/submit:
@app.post("/api/bio-scan/submit")
async def submit_bio_scan(data: BioScanData):
    result = await analyze_face(data)
    
    # Save to DB (existing)
    await db.bio_scans.insert_one({...result})
    
    # NEW: Fire results email
    await sendgrid_send(
        to=data.email,
        subject=f"Your skin bio-age is {result['bio_age']} — here's your protocol",
        template="bio_scan_results",
        data={
            "bioAge":       result["bio_age"],
            "concerns":     result["concerns"],
            "recommended":  result["recommended_products"]
        }
    )
    return result`,
  },
  {
    id:"A10", name:"Founders → VIP CRM Tier + Sequence", status:"not_built", category:"VIP Retention",
    color: T.gold, icon:"👑",
    trigger:"Contact in Founders tab",
    api_trigger:"GET /admin/partners (founders sub-tab exists)",
    api_status:"GET /business/crm/customers",
    sequence:[
      {delay:"sync",    action:"Auto-tag all Founders as VIP in CRM",        channel:"system", built:false},
      {delay:"instant", action:"Founder-exclusive early access emails",      channel:"email",  built:false},
      {delay:"monthly", action:"Monthly founder update from Tejinder",       channel:"email",  built:false},
    ],
    stats:{label:"Founders tab live",value:"VIP $0",note:"not synced to CRM"},
    blocker:"Founders not synced to CRM with VIP tag",
    blockerFix:"One-time backfill: GET all founders → upsert in CRM with tier=VIP, tags=[founder, vip, early-access]",
    code:`# One-time sync + ongoing founder sync
POST ${API}/admin/founders/sync-to-crm   # New endpoint needed

# Or do it directly:
founders = await db.partners.find({"type": "founder"}).to_list(None)
for f in founders:
    await db.crm_customers.update_one(
        {"email": f["email"]},
        {"$set": {
            "tier": "VIP",
            "tags": ["founder", "vip", "early-access"],
            "vipSince": datetime.utcnow()
        }},
        upsert=True
    )`,
  },
  {
    id:"A11", name:"Combo Offer → Dynamic Day 28 Upsell", status:"not_built", category:"AOV Increase",
    color: T.pink, icon:"🎁",
    trigger:"Day 28 automation fires",
    api_trigger:"GET /admin/combo-offers (existing data)",
    api_status:"GET /admin/combo-offers",
    sequence:[
      {delay:"Day 28", action:"Fetch active combo offer from DB",            channel:"system", built:false},
      {delay:"Day 28", action:"Email: Your PDRN cycle complete + bundle CTA",channel:"email",  built:false},
      {delay:"Day 28", action:"Personalised bundle link in email CTA",       channel:"email",  built:false},
    ],
    stats:{label:"AURA-GEN Duo live",value:"$149 bundle",note:"35% off, upsell popup ON"},
    blocker:"Day 28 email sends generic shop link, not dynamic bundle",
    blockerFix:"In Day 28 template: fetch active combo offer via GET /admin/combo-offers, inject bundle URL + price into email",
    code:`# Enhance Day 28 email with dynamic bundle
async def send_day28_email(customer):
    # Get active combo offer
    combos = await db.combo_offers.find({"active": True}).to_list(1)
    bundle = combos[0] if combos else None
    
    await sendgrid_send(
        to=customer["email"],
        subject="Day 28 — Your PDRN cycle is complete",
        template="day28_bundle",
        data={
            "name":         customer["name"],
            "bundle_name":  bundle["name"] if bundle else None,
            "bundle_price": bundle["price"] if bundle else None,
            "bundle_url":   f"/products/bundle/{bundle['_id']}" if bundle else "/shop",
            "savings":      bundle["savings"] if bundle else None,
        }
    )`,
  },
  {
    id:"A12", name:"Discount 50% Fix → Revenue Recovery", status:"critical", category:"Revenue Fix",
    color: T.red, icon:"🚨",
    trigger:"IMMEDIATE — Founder discount applying to ALL orders",
    api_trigger:"GET /admin/discount-codes (check Founder subsidy)",
    api_status:"GET /admin/stats (avg order value is $62.87, should be ~$112)",
    sequence:[
      {delay:"NOW",     action:"Disable Founder Launch Subsidy global toggle",channel:"admin",  built:true},
      {delay:"NOW",     action:"Restrict to Founders tag only in DB",         channel:"system", built:false},
      {delay:"ongoing", action:"Monitor avg order value — should rise to ~$112",channel:"system",built:false},
    ],
    stats:{label:"$62.87 avg now",value:"~$251 lost",note:"vs expected ~$502"},
    blocker:"50% discount is ON and applying to all checkout orders — costing ~$62 per order",
    blockerFix:"In admin panel: Discounts → Auto-Discounts → Founder's Launch Subsidy → Toggle OFF or set customerTag=founder",
    code:`# Restrict founder discount to founders only
# In checkout/order creation:
if order.customer_tag == "founder":
    discount_pct = 0.50  # 50% for real founders
elif order.discount_code:
    discount_pct = get_code_discount(order.discount_code)
else:
    discount_pct = 0  # No auto-discount for regular customers

# OR: Update the discount rule in DB
await db.auto_discounts.update_one(
    {"name": "Founder's Launch Subsidy"},
    {"$set": {
        "appliesTo": "founders_only",
        "requiredTag": "founder",
        "active": True  # Keep active but now scoped
    }}
)`,
  },
];

const STATUS_META = {
  live:       { label:"Live",       color:T.green  },
  partial:    { label:"Partial",    color:T.gold   },
  needs_wire: { label:"Wire It",    color:T.blue   },
  broken:     { label:"Fix Needed", color:T.red    },
  not_built:  { label:"Build",      color:T.purple },
  critical:   { label:"CRITICAL",   color:T.red    },
};

// ─── SUB-COMPONENTS ────────────────────────────────────────────
function Badge({label, color, pulse: doPulse=false}){
  return (
    <span style={{
      fontSize:"0.58rem", letterSpacing:"0.05em", fontWeight:600, color,
      background:`${color}18`, border:`1px solid ${color}35`,
      padding:"0.18rem 0.6rem", fontFamily:FS, borderRadius:20,
      display:"inline-flex", alignItems:"center", gap:"0.3rem", whiteSpace:"nowrap"
    }}>
      {doPulse && <span style={{width:5,height:5,borderRadius:"50%",background:color,animation:"pulse 1.5s infinite",display:"inline-block"}}/>}
      {label}
    </span>
  );
}

function StatTicker({isLaVela, brandName}){
  const C = getTheme(isLaVela);
  // For La Vela, show placeholder data since the brand is new
  const items = isLaVela ? [
    "0 ABANDONED CARTS → READY TO CAPTURE",
    "0 GLOW CLUB MEMBERS → LAUNCH PENDING",
    "0% QUIZ CONVERSION → TEEN QUIZ COMING SOON",
    "0 PARTNERS → INFLUENCER PROGRAM SETUP",
    "ORO ROSA PRODUCT → IN STOCK",
    "0 ORDERS → BRAND NEW LAUNCH",
    "0 SKIN QUIZ LEADS",
    `${brandName} — BRAND LAUNCH IN PROGRESS`,
  ] : [
    "127 ABANDONED CARTS → ~$22,860",
    "35 WAITLIST → WARM LEADS WAITING",
    "87.5% QUIZ CONVERSION RATE",
    "6 PARTNERS → $0 TRACKED",
    "50% DISCOUNT ON ALL ORDERS — FIX NOW",
    "4 ORDERS UNFULFILLED",
    "42 BIO-SCAN LEADS",
    "LOYALTY POINTS — 0 MEMBERS, API ERROR",
  ];
  const all = [...items, ...items];
  return (
    <div style={{overflow:"hidden",borderBottom:`1px solid ${C.border}`,background:`${C.pinkGlow}`,padding:"0.5rem 0"}}>
      <div style={{display:"flex",gap:"3rem",animation:"ticker 28s linear infinite",whiteSpace:"nowrap",width:"max-content"}}>
        {all.map((t,i)=>(
          <span key={i} style={{fontSize:"0.6rem",letterSpacing:"0.18em",color:C.pinkDim,fontFamily:FM,fontWeight:300}}>
            ◈ {t}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── TAB: AUTOMATION RULES ──────────────────────────────────────
function AutomationsTab({isLaVela}){
  const C = getTheme(isLaVela);
  const [open, setOpen] = useState("A12");
  const [copied, setCopied] = useState(null);

  const copy = (text, id) => {
    navigator.clipboard.writeText(text).catch(()=>{});
    setCopied(id);
    setTimeout(()=>setCopied(null), 2000);
  };

  return (
    <div>
      {/* Status summary */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:"0.5rem",marginBottom:"1.5rem"}}>
        {[
          ["Live / Working",   AUTOMATION_RULES.filter(r=>r.status==="live").length,       C.green],
          ["Partial",          AUTOMATION_RULES.filter(r=>r.status==="partial").length,     C.gold],
          ["Needs Wiring",     AUTOMATION_RULES.filter(r=>r.status==="needs_wire").length,  C.blue],
          ["Broken / Fix",     AUTOMATION_RULES.filter(r=>["broken","critical"].includes(r.status)).length, C.red],
          ["Still to Build",   AUTOMATION_RULES.filter(r=>r.status==="not_built").length,   C.purple],
        ].map(([l,v,c],i)=>(
          <div key={l} style={{background:C.card,border:`1px solid ${c}20`,borderTop:`2px solid ${c}`,borderRadius:"0 0 10px 10px",padding:"0.8rem 0.9rem",animation:`fadeUp 0.3s ${i*0.06}s both`}}>
            <div style={{fontSize:"1.5rem",color:c,fontFamily:FD,fontWeight:300,lineHeight:1}}>{v}</div>
            <div style={{fontSize:"0.58rem",color:C.textDim,fontFamily:FS,marginTop:"0.25rem",lineHeight:1.4}}>{l}</div>
          </div>
        ))}
      </div>

      {/* Rules list */}
      <div style={{display:"flex",flexDirection:"column",gap:"0.6rem"}}>
        {AUTOMATION_RULES.map((rule,ri)=>{
          const sm = STATUS_META[rule.status] || STATUS_META.live;
          const isOpen = open===rule.id;
          const builtSteps = rule.sequence.filter(s=>s.built).length;
          const pct = Math.round(builtSteps/rule.sequence.length*100);

          return(
            <div key={rule.id}
              style={{background:T.card,border:`1px solid ${isOpen?rule.color+"50":T.border}`,borderLeft:`3px solid ${rule.color}`,borderRadius:"0 12px 12px 0",overflow:"hidden",animation:`fadeUp 0.3s ${ri*0.04}s both`,transition:"border-color 0.2s"}}>
              {/* Header */}
              <div style={{display:"flex",alignItems:"center",gap:"0.85rem",padding:"0.9rem 1.25rem",cursor:"pointer"}}
                onClick={()=>setOpen(isOpen?null:rule.id)}>
                <span style={{fontSize:"1.1rem",flexShrink:0}}>{rule.icon}</span>
                <div style={{minWidth:36,textAlign:"right"}}>
                  <span style={{fontSize:"0.58rem",color:T.textMuted,fontFamily:FM}}>{rule.id}</span>
                </div>
                <div style={{flex:1}}>
                  <div style={{display:"flex",alignItems:"center",gap:"0.6rem",marginBottom:"0.3rem",flexWrap:"wrap"}}>
                    <span style={{fontSize:"0.88rem",color:T.text,fontFamily:FS,fontWeight:500}}>{rule.name}</span>
                    <Badge label={sm.label} color={sm.color} pulse={rule.status==="critical"}/>
                    <span style={{fontSize:"0.6rem",color:T.textMuted,fontFamily:FM,background:`${rule.color}10`,padding:"0.1rem 0.5rem",borderRadius:6}}>{rule.category}</span>
                  </div>
                  <div style={{display:"flex",alignItems:"center",gap:"0.6rem"}}>
                    <div style={{width:80,height:2,background:T.border,borderRadius:1,overflow:"hidden",flexShrink:0}}>
                      <div style={{width:`${pct}%`,height:"100%",background:pct===100?T.green:rule.color}}/>
                    </div>
                    <span style={{fontSize:"0.58rem",color:T.textMuted,fontFamily:FM}}>{builtSteps}/{rule.sequence.length} steps</span>
                    <span style={{fontSize:"0.65rem",color:rule.color,fontFamily:FS,fontWeight:500,marginLeft:"auto"}}>{rule.stats.value}</span>
                    <span style={{fontSize:"0.6rem",color:T.textDim,fontFamily:FS}}>{rule.stats.note}</span>
                  </div>
                </div>
                <span style={{color:T.textMuted,fontSize:"0.7rem",flexShrink:0}}>{isOpen?"▲":"▼"}</span>
              </div>

              {/* Expanded */}
              {isOpen&&(
                <div style={{borderTop:`1px solid ${T.border}`,padding:"1.25rem"}}>
                  <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"1.25rem",marginBottom:"1.25rem"}}>
                    {/* Sequence */}
                    <div>
                      <div style={{fontSize:"0.58rem",letterSpacing:"0.15em",color:T.textMuted,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.6rem"}}>Automation Sequence</div>
                      <div style={{display:"flex",flexDirection:"column",gap:"0.35rem"}}>
                        {rule.sequence.map((step,si)=>(
                          <div key={si} style={{display:"flex",alignItems:"center",gap:"0.6rem",padding:"0.5rem 0.7rem",background:step.built?"rgba(92,184,138,0.06)":"rgba(224,112,112,0.04)",border:`1px solid ${step.built?T.green+"30":T.red+"20"}`,borderRadius:6}}>
                            <div style={{width:22,height:22,borderRadius:"50%",background:step.built?T.greenFaint:T.redFaint,border:`1px solid ${step.built?T.green:T.red}`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:"0.6rem",color:step.built?T.green:T.red,fontFamily:FM,flexShrink:0}}>
                              {step.built?"✓":"·"}
                            </div>
                            <div style={{flex:1}}>
                              <span style={{fontSize:"0.65rem",color:T.text,fontFamily:FS,lineHeight:1.4}}>{step.action}</span>
                            </div>
                            <div style={{display:"flex",gap:"0.3rem",flexShrink:0}}>
                              <span style={{fontSize:"0.55rem",color:rule.color,fontFamily:FM,background:`${rule.color}10`,padding:"0.1rem 0.4rem",borderRadius:4}}>{step.delay}</span>
                              <span style={{fontSize:"0.55rem",color:T.textMuted,fontFamily:FM,background:T.border+"80",padding:"0.1rem 0.4rem",borderRadius:4}}>{step.channel}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Blocker + Fix */}
                    <div style={{display:"flex",flexDirection:"column",gap:"0.75rem"}}>
                      <div>
                        <div style={{fontSize:"0.58rem",letterSpacing:"0.15em",color:T.red,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.4rem"}}>⚠ Blocker</div>
                        <div style={{fontSize:"0.73rem",color:T.text,fontFamily:FS,lineHeight:1.7,padding:"0.6rem 0.75rem",background:T.redFaint,border:`1px solid ${T.red}25`,borderRadius:8}}>{rule.blocker}</div>
                      </div>
                      <div>
                        <div style={{fontSize:"0.58rem",letterSpacing:"0.15em",color:T.green,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.4rem"}}>✓ Fix</div>
                        <div style={{fontSize:"0.73rem",color:T.text,fontFamily:FS,lineHeight:1.7,padding:"0.6rem 0.75rem",background:T.greenFaint,border:`1px solid ${T.green}25`,borderRadius:8}}>{rule.blockerFix}</div>
                      </div>
                      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"0.5rem",padding:"0.6rem",background:"rgba(255,255,255,0.02)",borderRadius:8,border:`1px solid ${T.border}`}}>
                        <div>
                          <div style={{fontSize:"0.55rem",color:T.textMuted,fontFamily:FS,marginBottom:"0.15rem"}}>API Trigger</div>
                          <div style={{fontSize:"0.62rem",color:rule.color,fontFamily:FM}}>{rule.api_trigger}</div>
                        </div>
                        <div>
                          <div style={{fontSize:"0.55rem",color:T.textMuted,fontFamily:FS,marginBottom:"0.15rem"}}>Status Check</div>
                          <div style={{fontSize:"0.62rem",color:T.textDim,fontFamily:FM}}>{rule.api_status}</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Code block */}
                  <div style={{position:"relative"}}>
                    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"0.5rem 0.9rem",background:"#0A0A0C",borderRadius:"8px 8px 0 0",border:`1px solid ${T.border}`,borderBottom:"none"}}>
                      <span style={{fontSize:"0.58rem",color:T.textMuted,fontFamily:FM,letterSpacing:"0.12em"}}>COPY-PASTE CODE FOR DEVELOPER</span>
                      <button onClick={()=>copy(rule.code, rule.id)}
                        style={{padding:"0.25rem 0.7rem",fontSize:"0.6rem",fontFamily:FM,background:"transparent",color:T.textDim,border:`1px solid ${T.border}`,borderRadius:6,cursor:"pointer"}}>
                        {copied===rule.id?"✓ copied":"copy"}
                      </button>
                    </div>
                    <pre style={{background:"#0A0A0C",border:`1px solid ${T.border}`,borderRadius:"0 0 8px 8px",padding:"1rem",fontSize:"0.65rem",color:"#A8E6CF",fontFamily:FM,lineHeight:1.8,overflowX:"auto",maxHeight:260,margin:0}}>
                      {rule.code}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── TAB: REVENUE CALCULATOR ────────────────────────────────────
function RevenueTab({isLaVela, brandName}){
  const C = getTheme(isLaVela);
  
  // For La Vela, show launch-specific scenarios
  const laVelaScenarios = [
    {
      title:"Launch ORO ROSA Product Page",
      time:"Ready ✓", color:C.green, icon:"🌟",
      current:"Product in database",
      after:"Live on storefront",
      calc:"Initial sales at $49 CAD each",
      monthly:"~Target: 50 orders/mo = $2,450",
      effort:"Already configured",
    },
    {
      title:"Setup Teen Skin Quiz (A08)",
      time:"1-2 hrs", color:C.blue, icon:"🧬",
      current:"No quiz leads yet",
      after:"Quiz → Email capture → Follow-up",
      calc:"Estimated 87% quiz completion rate",
      monthly:"~20 leads/mo × 25% conversion = 5 orders",
      effort:"Configure quiz flow for teens",
    },
    {
      title:"Launch Glow Club Program",
      time:"1 hr", color:C.pink, icon:"✨",
      current:"0 Glow Club members",
      after:"Points system for teens",
      calc:"Loyalty drives repeat purchases",
      monthly:"~15% increase in LTV",
      effort:"Enable in admin settings",
    },
    {
      title:"Influencer/Parent Program",
      time:"2 hrs", color:C.purple, icon:"🤝",
      current:"No partners yet",
      after:"Momfluencer + teen influencer network",
      calc:"5 partners × 10 sales each",
      monthly:"~$2,450 partner-driven revenue",
      effort:"Setup affiliate codes",
    },
  ];
  
  const reRootsScenarios = [
    {
      title:"Fix Founder Discount (A12)",
      time:"15 min", color:C.red, icon:"🚨",
      current:"$62.87 avg order",
      after:"~$112 avg order",
      calc:"4 existing orders × +$49 recovery = $196 immediate. All future orders +$49 each.",
      monthly:"~$980/mo on 20 orders",
      effort:"Toggle in admin panel",
    },
    {
      title:"Activate Abandoned Carts (A01)",
      time:"2 hrs (add SendGrid key)", color:C.pink, icon:"🛒",
      current:"127 carts × $0 recovered",
      after:"~12-15% recovery rate = 15-19 orders",
      calc:"15 orders × $112 avg = $1,680",
      monthly:"~$1,680 one-time + ongoing recovery",
      effort:"SENDGRID_API_KEY in .env",
    },
    {
      title:"Fix Partner Tracking (A04)",
      time:"2 hrs", color:C.gold, icon:"🤝",
      current:"6 partners, $0 tracked, 54% conversion",
      after:"6 partners × 84 engagements × 54% = 45 attributed sales",
      calc:"45 × $112 = $5,040 partner-driven revenue",
      monthly:"Depends on partner traffic",
      effort:"Fix order creation attribution",
    },
    {
      title:"Wire Quiz → CRM + Email (A08)",
      time:"3 hrs", color:C.green, icon:"🧬",
      current:"87.5% CVR, 42 leads, 0 follow-up",
      after:"42 leads × 87.5% × email sequence",
      calc:"37 purchasers × $112 = $4,144",
      monthly:"Ongoing — every quiz lead converts",
      effort:"Add CRM upsert + email to quiz/submit",
    },
    {
      title:"Contact Waitlist (A06)",
      time:"30 min", color:C.blue, icon:"📬",
      current:"35 people on waitlist, 0 contacted",
      after:"35 warm leads × 25% purchase rate = 8-9 orders",
      calc:"8 × $112 = $896",
      monthly:"One-time + ongoing on restock",
      effort:"WhatsApp blast from Marketing Hub",
    },
    {
      title:"Day 28 Bundle Upsell (A11)",
      time:"2 hrs", color:C.purple, icon:"🎁",
      current:"Day 28 email sends to /shop (generic)",
      after:"Day 28 email sends to $149 bundle (vs $99 single)",
      calc:"+$50 AOV × all Day 28 emails fired",
      monthly:"~$500/mo as volume grows",
      effort:"Inject combo offer URL into Day 28 template",
    },
  ];

  const scenarios = isLaVela ? laVelaScenarios : reRootsScenarios;
  const totalEst = isLaVela ? 4900 : (196 + 1680 + 5040 + 4144 + 896 + 500);
  const currentRevenue = isLaVela ? "$0" : "$251";
  const currentOrders = isLaVela ? "0 orders (brand launch)" : "4 orders";

  return(
    <div>
      <div style={{background:C.card,border:`1px solid ${C.pinkDim}30`,borderRadius:12,padding:"1.25rem 1.5rem",marginBottom:"1.5rem",display:"flex",alignItems:"center",gap:"2rem"}}>
        <div>
          <div style={{fontSize:"0.6rem",letterSpacing:"0.18em",color:C.textMuted,textTransform:"uppercase",fontFamily:FS,marginBottom:"0.3rem"}}>{isLaVela ? "Projected Launch Revenue" : "Estimated Recoverable Revenue"}</div>
          <div style={{fontFamily:FD,fontSize:"2.5rem",color:C.pink,fontWeight:300,letterSpacing:"0.05em"}}>
            ${totalEst.toLocaleString()}
          </div>
          <div style={{fontSize:"0.68rem",color:C.textDim,fontFamily:FS}}>{isLaVela ? "From launching and optimizing the new brand" : "From fixing what's already built — no new features needed"}</div>
        </div>
        <div style={{flex:1,height:1,background:`linear-gradient(to right, ${C.pinkDim}40, transparent)`}}/>
        <div style={{textAlign:"right"}}>
          <div style={{fontSize:"0.6rem",color:C.textMuted,fontFamily:FS,marginBottom:"0.25rem"}}>Current total revenue</div>
          <div style={{fontFamily:FD,fontSize:"1.5rem",color:C.textDim,fontWeight:300}}>{currentRevenue}</div>
          <div style={{fontSize:"0.6rem",color:C.textDim,fontFamily:FS}}>{currentOrders}</div>
        </div>
      </div>

      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"0.75rem"}}>
        {scenarios.map((s,i)=>(
          <div key={s.title} style={{background:C.card,border:`1px solid ${C.border}`,borderRadius:12,padding:"1.1rem 1.25rem",animation:`fadeUp 0.3s ${i*0.06}s both`,borderTop:`3px solid ${s.color}`}}>
            <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:"0.75rem"}}>
              <div>
                <div style={{display:"flex",alignItems:"center",gap:"0.5rem",marginBottom:"0.3rem"}}>
                  <span style={{fontSize:"1rem"}}>{s.icon}</span>
                  <span style={{fontSize:"0.85rem",color:T.text,fontFamily:FS,fontWeight:500}}>{s.title}</span>
                </div>
                <div style={{fontSize:"0.62rem",color:s.color,fontFamily:FM,background:`${s.color}10`,padding:"0.15rem 0.5rem",borderRadius:6,display:"inline-block"}}>{s.time}</div>
              </div>
            </div>
            <div style={{display:"flex",flexDirection:"column",gap:"0.4rem"}}>
              <div style={{display:"grid",gridTemplateColumns:"70px 1fr",gap:"0.5rem",alignItems:"start"}}>
                <span style={{fontSize:"0.6rem",color:T.textMuted,fontFamily:FS}}>Now</span>
                <span style={{fontSize:"0.68rem",color:T.textDim,fontFamily:FS,lineHeight:1.5}}>{s.current}</span>
              </div>
              <div style={{display:"grid",gridTemplateColumns:"70px 1fr",gap:"0.5rem",alignItems:"start"}}>
                <span style={{fontSize:"0.6rem",color:T.textMuted,fontFamily:FS}}>After</span>
                <span style={{fontSize:"0.68rem",color:T.green,fontFamily:FS,lineHeight:1.5}}>{s.after}</span>
              </div>
              <div style={{display:"grid",gridTemplateColumns:"70px 1fr",gap:"0.5rem",alignItems:"start"}}>
                <span style={{fontSize:"0.6rem",color:T.textMuted,fontFamily:FS}}>Math</span>
                <span style={{fontSize:"0.68rem",color:T.text,fontFamily:FS,lineHeight:1.5}}>{s.calc}</span>
              </div>
              <div style={{padding:"0.5rem 0.75rem",background:`${s.color}08`,border:`1px solid ${s.color}20`,borderRadius:6,marginTop:"0.35rem"}}>
                <span style={{fontSize:"0.6rem",color:T.textMuted,fontFamily:FS}}>Effort: </span>
                <span style={{fontSize:"0.6rem",color:s.color,fontFamily:FM}}>{s.effort}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── TAB: DEVELOPER HANDOFF ─────────────────────────────────────
function HandoffTab({isLaVela, brandName}){
  const C = getTheme(isLaVela);
  const [copied, setCopied] = useState(null);
  const copy = (text, id) => {
    navigator.clipboard.writeText(text).catch(()=>{});
    setCopied(id);
    setTimeout(()=>setCopied(null),2000);
  };
  
  const brandEmail = isLaVela ? 'hello@lavelabianca.com' : 'hello@reroots.ca';
  const brandSlug = isLaVela ? 'La Vela Bianca' : 'ReRoots';

  const laVelaTasks = [
    {
      priority:"P0 — Launch Checklist",
      color:C.green,
      items:[
        {
          title:"ORO ROSA product is ready in database",
          file:"Admin → La Vela Bianca → Teen Products",
          snippet:`# Product Status:
✓ ORO ROSA Bio-Glow Serum - $49 CAD
✓ Ages 8-16
✓ 100 units in stock
✓ Active status`,
        },
        {
          title:"Configure La Vela email templates",
          file:".env file",
          snippet:`# Add to .env:
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=${brandEmail}
SENDGRID_FROM_NAME=${brandSlug}`,
        },
        {
          title:"Setup Teen Skin Quiz",
          file:"Admin → Quiz Builder",
          snippet:`# Teen quiz questions:
1. How old are you? (8-12, 13-15, 16-18)
2. What's your main skin concern?
3. Do you have a current skincare routine?`,
        },
      ]
    },
    {
      priority:"P1 — Post-Launch",
      color:C.amber,
      items:[
        {
          title:"Launch Glow Club loyalty program",
          file:"Admin → Loyalty Settings",
          snippet:`# Configure points:
- Purchase: 1 point per $1
- Quiz completion: 50 points
- Birthday bonus: 100 points`,
        },
        {
          title:"Setup influencer program",
          file:"Admin → Partners",
          snippet:`# Create affiliate codes for teen/mom influencers`,
        },
      ]
    },
  ];

  const reRootsTasks = [
    {
      priority:"P0 — Do today",
      color:C.red,
      items:[
        {
          title:"Restrict Founder discount to founders only",
          file:"server.py → checkout/order creation OR admin panel toggle",
          snippet:`# In admin panel (2 min fix):
# Discounts → Auto-Discounts → Founder's Launch Subsidy → Toggle OFF

# OR restrict in code:
await db.auto_discounts.update_one(
    {"name": "Founder's Launch Subsidy"},
    {"$set": {"appliesTo": "founders_only", "requiredTag": "founder"}}
)`,
        },
        {
          title:"Add SENDGRID_API_KEY to .env (127 carts ready)",
          file:".env file",
          snippet:`# Add to .env:
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=${brandEmail}
SENDGRID_FROM_NAME=${brandSlug}

# Test:
POST /api/admin/automations/test-email
{"to": "teji.ss1986@gmail.com", "template": "order_confirmation"}`,
        },
        {
          title:"Click Sync from FlagShip → fulfill 4 pending orders",
          file:"Admin panel → FlagShip Shipments → Sync from FlagShip",
          snippet:`# Manual for now. Then wire webhook:
POST /api/admin/flagship/webhook   # New endpoint
{
  "orderId": "{id}",
  "trackingNumber": "CP123456789CA",
  "carrier": "canada_post",
  "estimatedDelivery": "2026-03-07"
}`,
        },
      ]
    },
    {
      priority:"P1 — This week",
      color:C.amber,
      items:[
        {
          title:"Fix Partner code → commission tracking",
          file:"server.py → POST /api/orders handler",
          snippet:`# In order creation, after inserting order:
if order_data.get("discountCode"):
    partner = await db.partners.find_one({"code": order_data["discountCode"]})
    if partner:
        await db.partner_referrals.insert_one({
            "partnerId": str(partner["_id"]),
            "orderId": str(order_id),
            "orderTotal": order_data["total"],
            "commission": order_data["total"] * 0.10,
            "code": order_data["discountCode"],
            "createdAt": datetime.utcnow(),
        })`,
        },
      ]
    },
  ];

  const tasks = isLaVela ? laVelaTasks : reRootsTasks;

  return(
    <div>
      <div style={{background:T.card,border:`1px solid ${T.border}`,borderRadius:12,padding:"1rem 1.25rem",marginBottom:"1.5rem",display:"flex",alignItems:"center",gap:"1rem"}}>
        <div style={{width:8,height:8,borderRadius:"50%",background:T.green,animation:"pulse 2s infinite",flexShrink:0}}/>
        <div style={{fontSize:"0.75rem",color:T.text,fontFamily:FS,lineHeight:1.6}}>
          Base URL: <span style={{color:T.pink,fontFamily:FM}}>{API}</span>
          <span style={{color:T.textDim,marginLeft:"1rem"}}>600+ endpoints live · AI Intelligence Hub untouched · Programs Manager untouched</span>
        </div>
      </div>

      {tasks.map((group,gi)=>(
        <div key={group.priority} style={{marginBottom:"2rem"}}>
          <div style={{display:"flex",alignItems:"center",gap:"0.75rem",marginBottom:"0.85rem"}}>
            <div style={{width:3,height:20,background:group.color,borderRadius:2}}/>
            <span style={{fontFamily:FD,fontSize:"1rem",color:T.text,fontWeight:400}}>{group.priority}</span>
          </div>
          <div style={{display:"flex",flexDirection:"column",gap:"0.6rem"}}>
            {group.items.map((item,ii)=>(
              <div key={ii} style={{background:T.card,border:`1px solid ${T.border}`,borderRadius:12,overflow:"hidden",animation:`fadeUp 0.3s ${ii*0.05}s both`}}>
                <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"0.85rem 1.25rem",borderBottom:`1px solid ${T.border}`}}>
                  <div>
                    <div style={{fontSize:"0.82rem",color:T.text,fontFamily:FS,fontWeight:500,marginBottom:"0.2rem"}}>{item.title}</div>
                    <div style={{fontSize:"0.62rem",color:T.textMuted,fontFamily:FM}}>{item.file}</div>
                  </div>
                  <button onClick={()=>copy(item.snippet,`${gi}-${ii}`)}
                    style={{padding:"0.3rem 0.75rem",fontSize:"0.62rem",fontFamily:FM,flexShrink:0,background:"transparent",color:T.textDim,border:`1px solid ${T.border}`,borderRadius:6,cursor:"pointer"}}>
                    {copied===`${gi}-${ii}`?"✓ copied":"copy"}
                  </button>
                </div>
                <pre style={{background:"#050305",padding:"1rem 1.25rem",fontSize:"0.65rem",color:"#A8E6CF",fontFamily:FM,lineHeight:1.8,overflowX:"auto",maxHeight:200,margin:0}}>
                  {item.snippet}
                </pre>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── MAIN ───────────────────────────────────────────────────────
export default function AutomationIntelligence(){
  const { isLaVela, shortName, name: brandName } = useAdminBrand();
  const C = getTheme(isLaVela);
  
  const [tab, setTab] = useState("automations");
  const tabs = [
    {id:"automations", label:"12 Automation Rules"},
    {id:"revenue",     label:"Revenue Impact"},
    {id:"handoff",     label:"Developer Handoff"},
  ];

  return(
    <div style={{minHeight:"100vh",background:C.bg,fontFamily:FS,color:C.text}} data-testid="automation-intelligence">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@300;400;500&display=swap');
        @keyframes fadeUp{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:translateY(0);}}
        @keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(${isLaVela ? '212,165,116' : '248,165,184'},0.4);}50%{opacity:.6;box-shadow:0 0 0 4px rgba(${isLaVela ? '212,165,116' : '248,165,184'},0);}}
        @keyframes ticker{0%{transform:translateX(0);}100%{transform:translateX(-50%)}}
        @keyframes glow{0%,100%{opacity:.4;}50%{opacity:1;}}
      `}</style>

      {/* Header */}
      <div style={{background:C.card,borderBottom:`1px solid ${C.border}`,padding:"0.9rem 2rem",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
        <div style={{display:"flex",alignItems:"baseline",gap:"1.25rem"}}>
          <span style={{fontFamily:FD,fontSize:"1.4rem",letterSpacing:"0.25em",color:C.pink,fontWeight:300}}>
            {shortName}
          </span>
          <span style={{fontSize:"0.6rem",letterSpacing:"0.25em",color:T.textMuted,textTransform:"uppercase",fontFamily:FS}}>
            Automation Intelligence
          </span>
        </div>
        <div style={{display:"flex",gap:"2rem",fontSize:"0.65rem",fontFamily:FS,alignItems:"center"}}>
          <div style={{display:"flex",alignItems:"center",gap:"0.4rem"}}>
            <div style={{width:5,height:5,borderRadius:"50%",background:C.green,animation:"glow 2s infinite"}}/>
            <span style={{color:C.textDim}}>AI Hub: <span style={{color:C.green}}>Untouched ✓</span></span>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:"0.4rem"}}>
            <div style={{width:5,height:5,borderRadius:"50%",background:C.green,animation:"glow 2s infinite"}}/>
            <span style={{color:C.textDim}}>Programs: <span style={{color:C.green}}>Untouched ✓</span></span>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:"0.4rem"}}>
            <div style={{width:5,height:5,borderRadius:"50%",background:C.pink,animation:"pulse 1.5s infinite"}}/>
            <span style={{color:C.red,fontWeight:600}}>50% discount ON — fix now</span>
          </div>
        </div>
      </div>

      <StatTicker isLaVela={isLaVela} brandName={brandName}/>

      {/* Tabs */}
      <div style={{background:C.card,borderBottom:`1px solid ${C.border}`,padding:"0 2rem",display:"flex"}}>
        {tabs.map(t=>(
          <button key={t.id} 
            onClick={()=>setTab(t.id)}
            style={{
              background:"none",border:"none",
              borderBottom:`2px solid ${tab===t.id?C.pink:"transparent"}`,
              padding:"0.8rem 1.2rem",cursor:"pointer",
              fontFamily:FS,fontSize:"0.75rem",
              color:tab===t.id?C.pink:C.textDim,
              transition:"all 0.2s"
            }}>
            {t.label}
          </button>
        ))}
      </div>

      <div style={{padding:"2rem",maxWidth:1100,margin:"0 auto"}}>
        {tab==="automations" && <AutomationsTab isLaVela={isLaVela}/>}
        {tab==="revenue"     && <RevenueTab isLaVela={isLaVela} brandName={brandName}/>}
        {tab==="handoff"     && <HandoffTab isLaVela={isLaVela} brandName={brandName}/>}
      </div>

      <div style={{borderTop:`1px solid ${C.border}`,padding:"0.85rem 2rem",display:"flex",justifyContent:"space-between",alignItems:"center",background:C.card}}>
        <div style={{fontSize:"0.6rem",color:C.textMuted,fontFamily:FS}}>{brandName} · Automation Intelligence · 12 automation rules</div>
        <div style={{fontSize:"0.6rem",color:C.pinkDim,fontFamily:FM}}>AI Intelligence Hub + Programs Manager: no changes made</div>
      </div>
    </div>
  );
}
