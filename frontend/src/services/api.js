/**
 * ReRoots API Service Layer
 * Connects to reroots.ca Python backend
 *
 * Base URL: Uses REACT_APP_BACKEND_URL for environment flexibility
 * Auth: JWT Bearer token stored in localStorage
 */

const BASE_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

/* ── TOKEN HELPERS ──────────────────────────────────────────────────────── */
export const getToken = () => localStorage.getItem("rr_token");
export const setToken = (t) => localStorage.setItem("rr_token", t);
export const clearToken = () => localStorage.removeItem("rr_token");

const authHeaders = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${getToken()}`,
});

/* ── CORE REQUEST ───────────────────────────────────────────────────────── */
async function req(method, path, body, isFormData = false) {
  const headers = isFormData
    ? { Authorization: `Bearer ${getToken()}` }
    : authHeaders();

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: isFormData ? body : body ? JSON.stringify(body) : undefined,
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(data?.detail || data?.message || `Error ${res.status}`);
  }
  return data;
}

/* ══════════════════════════════════════════════════════════════════════════
   AUTH  —  /api/auth/*
══════════════════════════════════════════════════════════════════════════ */

/**
 * POST /api/auth/login
 * Body: { email, password }
 * Returns: { access_token, user: { id, name, email, tier, points, skin_type, role } }
 */
export async function login(email, password) {
  const data = await req("POST", "/api/auth/login", { email, password });
  setToken(data.token || data.access_token);
  return normalizeUser(data.user);
}

/**
 * POST /api/auth/register
 * Body: { first_name, last_name, email, password, skin_type, birthday, offers_opt_in }
 * Returns: { access_token, user }
 */
export async function register(form) {
  const data = await req("POST", "/api/auth/register", {
    first_name: form.firstName,
    last_name: form.lastName,
    email: form.email,
    password: form.password,
    skin_type: form.skinType,
    birthday: form.birthday || null,
    offers_opt_in: form.offers,
  });
  setToken(data.token || data.access_token);
  return normalizeUser(data.user);
}

/**
 * GET /api/auth/me
 * Returns current authenticated user profile
 */
export async function getMe() {
  const data = await req("GET", "/api/auth/me");
  return normalizeUser(data);
}

/**
 * POST /api/auth/logout
 */
export async function logout() {
  try { await req("POST", "/api/auth/logout"); } catch (_) {}
  clearToken();
}

function normalizeUser(u) {
  return {
    id: u.id,
    name: u.name || `${u.first_name || ""} ${u.last_name || ""}`.trim(),
    email: u.email,
    role: u.role || (u.is_admin ? "admin" : "customer"),
    tier: u.tier || "Silver",
    points: u.loyalty_points ?? u.points ?? 500,
    skinType: u.skin_type || u.skinType || "",
    birthday: u.birthday || "",
    offers: u.offers_opt_in ?? u.offers ?? true,
    signupDate: u.created_at ? new Date(u.created_at).toLocaleDateString("en-CA") : "",
  };
}

/* ══════════════════════════════════════════════════════════════════════════
   PRODUCTS  —  /api/products/*
══════════════════════════════════════════════════════════════════════════ */

/**
 * GET /api/products
 * Returns: array of products
 */
export async function getProducts() {
  const data = await req("GET", "/api/products");
  return data.map(normalizeProduct);
}

/**
 * POST /api/products
 * Creates a new product. Uploads image to Cloudinary if provided.
 */
export async function createProduct(product) {
  let imageUrl = product.image;

  // If image is a base64 data URL, upload to Cloudinary first
  if (product.image && product.image.startsWith("data:")) {
    imageUrl = await uploadImage(product.image, `product_${Date.now()}`);
  }

  const data = await req("POST", "/api/products", {
    name: product.name,
    subtitle: product.subtitle,
    sku: product.sku,
    price: parseFloat(product.price),
    cost: parseFloat(product.cost),
    size: product.size,
    tag: product.tag,
    description: product.desc,
    ingredients: product.ingredients,
    stock: parseInt(product.stock),
    reorder_point: parseInt(product.reorder),
    batch_code: product.batch,
    accent_color: product.accent,
    accent_dim: product.accentDim,
    bottle_shape: product.shape,
    background_hue: product.hue,
    image_url: imageUrl,
    status: computeStatus(parseInt(product.stock), parseInt(product.reorder)),
  });
  return normalizeProduct(data);
}

/**
 * PUT /api/products/:id
 * Updates an existing product.
 */
export async function updateProduct(id, product) {
  let imageUrl = product.image;

  if (product.image && product.image.startsWith("data:")) {
    imageUrl = await uploadImage(product.image, `product_${id}`);
  }

  const data = await req("PUT", `/api/products/${id}`, {
    name: product.name,
    subtitle: product.subtitle,
    sku: product.sku,
    price: parseFloat(product.price),
    cost: parseFloat(product.cost),
    size: product.size,
    tag: product.tag,
    description: product.desc,
    ingredients: product.ingredients,
    stock: parseInt(product.stock),
    reorder_point: parseInt(product.reorder),
    batch_code: product.batch,
    accent_color: product.accent,
    accent_dim: product.accentDim,
    bottle_shape: product.shape,
    background_hue: product.hue,
    image_url: imageUrl,
    status: computeStatus(parseInt(product.stock), parseInt(product.reorder)),
  });
  return normalizeProduct(data);
}

/**
 * DELETE /api/products/:id
 */
export async function deleteProduct(id) {
  await req("DELETE", `/api/products/${id}`);
}

function normalizeProduct(p) {
  return {
    id: p.id,
    name: p.name,
    subtitle: p.subtitle || "",
    sku: p.sku || "",
    price: p.price,
    cost: p.cost || 0,
    size: p.size || "",
    tag: p.tag || "",
    desc: p.description || p.desc || "",
    ingredients: p.ingredients || "",
    stock: p.stock,
    reorder: p.reorder_point ?? p.reorder ?? 15,
    batch: p.batch_code || p.batch || "",
    accent: p.accent_color || p.accent || "#6BAED6",
    accentDim: p.accent_dim || p.accentDim || "#2a4a6a",
    shape: p.bottle_shape || p.shape || "dropper",
    hue: p.background_hue || p.hue || "linear-gradient(160deg,#0a1020,#060c18)",
    image: p.image_url || p.image || null,
    rating: p.rating || 5.0,
    reviews: p.review_count || p.reviews || 0,
    status: p.status || computeStatus(p.stock, p.reorder_point ?? p.reorder ?? 15),
  };
}

function computeStatus(stock, reorder) {
  if (stock <= 0) return "Out";
  if (stock <= reorder) return stock < reorder * 0.7 ? "Critical" : "Low";
  return "OK";
}

/* ══════════════════════════════════════════════════════════════════════════
   IMAGE UPLOAD  —  /api/upload  (proxies to Cloudinary)
══════════════════════════════════════════════════════════════════════════ */

/**
 * POST /api/upload
 * Accepts multipart/form-data with field "file"
 * Returns: { url: "https://res.cloudinary.com/..." }
 */
export async function uploadImage(base64DataUrl, publicId = "") {
  // Convert base64 to Blob
  const [header, data] = base64DataUrl.split(",");
  const mime = header.match(/:(.*?);/)[1];
  const binary = atob(data);
  const arr = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
  const blob = new Blob([arr], { type: mime });

  const formData = new FormData();
  formData.append("file", blob, `${publicId || "upload"}.${mime.split("/")[1]}`);
  if (publicId) formData.append("public_id", publicId);

  const res = await fetch(`${BASE_URL}/api/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
    body: formData,
  });
  const result = await res.json();
  if (!res.ok) throw new Error(result?.detail || "Upload failed");
  return result.url;
}

/* ══════════════════════════════════════════════════════════════════════════
   SUBSCRIBERS / CRM  —  /api/crm/*
══════════════════════════════════════════════════════════════════════════ */

/**
 * GET /api/crm/subscribers
 * Returns list of subscribers with offer opt-in status
 */
export async function getSubscribers() {
  const data = await req("GET", "/api/crm/subscribers");
  return data.map(normalizeSubscriber);
}

/**
 * PATCH /api/crm/subscribers/:id
 * Toggle offers opt-in or update status
 */
export async function updateSubscriber(id, changes) {
  const data = await req("PATCH", `/api/crm/subscribers/${id}`, {
    offers_opt_in: changes.offers,
    status: changes.status,
  });
  return normalizeSubscriber(data);
}

/**
 * GET /api/crm/customers
 * Full CRM customer list with LTV, health score, tier
 */
export async function getCustomers() {
  return req("GET", "/api/crm/customers");
}

function normalizeSubscriber(s) {
  return {
    id: s.id,
    name: s.name || `${s.first_name || ""} ${s.last_name || ""}`.trim(),
    email: s.email,
    skinType: s.skin_type || s.skinType || "",
    birthday: s.birthday || "",
    tier: s.tier || "Silver",
    offers: s.offers_opt_in ?? s.offers ?? true,
    signupDate: s.created_at
      ? new Date(s.created_at).toLocaleDateString("en-CA")
      : s.signupDate || "",
    status: s.offers_opt_in === false ? "Opted Out" : "Active",
  };
}

/* ══════════════════════════════════════════════════════════════════════════
   MARKETING / OFFERS  —  /api/marketing/*
   Uses SendGrid via your Python backend
══════════════════════════════════════════════════════════════════════════ */

/**
 * POST /api/marketing/send-offer
 * Body: { subject, body, discount_code, recipient_filter }
 * Backend iterates active subscribers and sends via SendGrid
 * Supports personalization tokens: {{name}}, {{tier}}, {{points}}
 * Returns: { sent_count, message_id }
 */
export async function sendOffer({ subject, body, discountCode, filter = "active" }) {
  return req("POST", "/api/marketing/send-offer", {
    subject,
    body,
    discount_code: discountCode || null,
    recipient_filter: filter, // "active" | "all" | "gold_plus"
    template_tokens: ["{{name}}", "{{tier}}", "{{points}}"],
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   ORDERS  —  /api/orders/*
══════════════════════════════════════════════════════════════════════════ */

/**
 * GET /api/orders
 * Query params: status, limit, offset
 */
export async function getOrders({ status = null, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit, offset });
  if (status) params.set("status", status);
  return req("GET", `/api/orders?${params}`);
}

/**
 * GET /api/orders/my
 * Returns orders for the currently authenticated customer
 */
export async function getMyOrders() {
  return req("GET", "/api/orders/my");
}

/* ══════════════════════════════════════════════════════════════════════════
   LOYALTY  —  /api/loyalty/*
══════════════════════════════════════════════════════════════════════════ */

/**
 * GET /api/loyalty/me
 * Returns { points, tier, tier_progress, next_tier, next_tier_threshold }
 */
export async function getLoyalty() {
  return req("GET", "/api/loyalty/me");
}

/**
 * POST /api/loyalty/redeem
 * Body: { points }
 */
export async function redeemPoints(points) {
  return req("POST", "/api/loyalty/redeem", { points });
}

/* ══════════════════════════════════════════════════════════════════════════
   ACCOUNTING  —  /api/accounting/*
══════════════════════════════════════════════════════════════════════════ */

/**
 * GET /api/accounting/transactions
 * Query params: start_date, end_date, type
 */
export async function getTransactions({ startDate, endDate, type } = {}) {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  if (type) params.set("type", type);
  return req("GET", `/api/accounting/transactions?${params}`);
}

/**
 * GET /api/accounting/summary
 * Returns { revenue, expenses, refunds, net, period }
 */
export async function getAccountingSummary() {
  return req("GET", "/api/accounting/summary");
}

/* ══════════════════════════════════════════════════════════════════════════
   ANALYTICS  —  /api/analytics/*
══════════════════════════════════════════════════════════════════════════ */

/**
 * GET /api/analytics/dashboard
 * Returns KPIs: revenue_mtd, active_customers, avg_order_value, refund_rate
 */
export async function getDashboardStats() {
  return req("GET", "/api/analytics/dashboard");
}

/**
 * GET /api/analytics/revenue?period=6m
 */
export async function getRevenueChart(period = "6m") {
  return req("GET", `/api/analytics/revenue?period=${period}`);
}

export default {
  // Auth
  login,
  register,
  getMe,
  logout,
  getToken,
  setToken,
  clearToken,
  // Products
  getProducts,
  createProduct,
  updateProduct,
  deleteProduct,
  // Upload
  uploadImage,
  // CRM
  getSubscribers,
  updateSubscriber,
  getCustomers,
  // Marketing
  sendOffer,
  // Orders
  getOrders,
  getMyOrders,
  // Loyalty
  getLoyalty,
  redeemPoints,
  // Accounting
  getTransactions,
  getAccountingSummary,
  // Analytics
  getDashboardStats,
  getRevenueChart,
};
