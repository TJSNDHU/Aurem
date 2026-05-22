/**
 * Secure Token Storage — dual-store wrapper (sessionStorage + localStorage).
 *
 * Security model:
 *  • sessionStorage is used as the PRIMARY write target (tab-scoped, clears on close).
 *  • localStorage is used as a PERSISTENT FALLBACK so that:
 *      - Opening a new tab stays logged in
 *      - Pasting a direct URL (e.g. /admin/brain-graph) works
 *      - Bookmarks + "Open in new tab" + /admin/links links work
 *
 * Writes go to BOTH stores. Reads prefer sessionStorage; fall back to localStorage
 * and re-hydrate sessionStorage from it on read (so subsequent code paths that
 * inspect sessionStorage directly still find the token).
 *
 * This is the common "fresh tab = still logged in" pattern used by Gmail, GitHub,
 * etc. The XSS surface increase is minimal because both stores are accessible
 * to page JS anyway — the real mitigation for XSS is CSP + input sanitation.
 *
 * iter 326o — ROLE-SEPARATED STORAGE
 * ──────────────────────────────────
 * Founder reported: "if admin logs out, customer login also breaks". Root
 * cause: both admin AND customer were saving their JWT to the SAME key
 * (`platform_token`). When admin logged out via `clearPlatformAuth()`, both
 * sessionStorage AND localStorage were wiped — including the customer's
 * still-valid session, which lived in the same slot in the same browser.
 *
 * Fix: per-role storage slots.
 *   Admin    → aurem_admin_token   / aurem_admin_user
 *   Customer → aurem_customer_token / aurem_customer_user
 *   Legacy   → platform_token       / platform_user   (read-only fallback)
 *
 * `setPlatformToken` / `getPlatformToken` / `clearPlatformAuth` remain as a
 * BACKWARDS-COMPATIBLE FACADE so old call sites still work. The facade now
 * routes writes into the right slot based on the JWT's role claim, and
 * reads check admin → customer → legacy in order. Admin's `clearAdminAuth`
 * and customer's `clearCustomerAuth` ONLY clear their own slot — they never
 * touch the other role, never touch the legacy slot.
 */

const PLATFORM_TOKEN_KEY = 'platform_token';   // legacy — kept for read-only fallback
const PLATFORM_USER_KEY  = 'platform_user';    // legacy — kept for read-only fallback
const ADMIN_TOKEN_KEY    = 'aurem_admin_token';
const ADMIN_USER_KEY     = 'aurem_admin_user';
const CUSTOMER_TOKEN_KEY = 'aurem_customer_token';
const CUSTOMER_USER_KEY  = 'aurem_customer_user';

function _readDual(key) {
  // Prefer session; fall back to localStorage and re-hydrate session for cross-tab UX.
  const sess = sessionStorage.getItem(key);
  if (sess) return sess;
  const local = localStorage.getItem(key);
  if (local) {
    try { sessionStorage.setItem(key, local); } catch { /* quota */ }
    return local;
  }
  return null;
}

function _writeDual(key, value) {
  try { sessionStorage.setItem(key, value); } catch { /* quota */ }
  try { localStorage.setItem(key, value); } catch { /* quota */ }
}

function _clearDual(key) {
  try { sessionStorage.removeItem(key); } catch { /* noop */ }
  try { localStorage.removeItem(key); } catch { /* noop */ }
}

function _decodeRole(token) {
  // Pull the role claim out of a JWT without verifying signature — this is
  // only used to PICK A STORAGE SLOT, not to grant any privilege. The server
  // re-verifies the token on every protected request.
  if (!token || typeof token !== 'string') return null;
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const payload = JSON.parse(atob(parts[1]));
    if (payload.is_super_admin || payload.role === 'super_admin') return 'admin';
    if (payload.is_admin || payload.role === 'admin') return 'admin';
    return 'customer';
  } catch {
    return null;
  }
}


/* ──────────────────────────────────────────────────────────────────────
 * Per-role API — preferred for new code (AdminLogin, AdminShell logout,
 * Customer login, Customer dashboard logout).
 * ────────────────────────────────────────────────────────────────────── */

export function setAdminToken(token) {
  _writeDual(ADMIN_TOKEN_KEY, token);
}
export function getAdminToken() {
  return _readDual(ADMIN_TOKEN_KEY) || _readDual(PLATFORM_TOKEN_KEY);  // legacy fallback
}
export function setAdminUser(user) {
  _writeDual(ADMIN_USER_KEY, JSON.stringify(user));
}
export function getAdminUser() {
  const raw = _readDual(ADMIN_USER_KEY) || _readDual(PLATFORM_USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}
export function clearAdminAuth() {
  // Critical: ONLY clear the admin slot. Customer session must survive an
  // admin logout. (This is the actual fix for the founder's bug.)
  _clearDual(ADMIN_TOKEN_KEY);
  _clearDual(ADMIN_USER_KEY);
  // iter 326nn — also wipe the legacy mirror slot if it currently
  // holds an admin token. `setPlatformToken()` mirrors writes there
  // for back-compat, so a stale admin JWT can survive logout and
  // bounce the founder right back to /admin/mission-control on the
  // next visit to /admin/login. Customer mirrors stay untouched.
  const legacy = _readDual(PLATFORM_TOKEN_KEY);
  if (legacy && _decodeRole(legacy) === 'admin') {
    _clearDual(PLATFORM_TOKEN_KEY);
    _clearDual(PLATFORM_USER_KEY);
  }
}

export function setCustomerToken(token) {
  _writeDual(CUSTOMER_TOKEN_KEY, token);
}
export function getCustomerToken() {
  return _readDual(CUSTOMER_TOKEN_KEY) || _readDual(PLATFORM_TOKEN_KEY);  // legacy fallback
}
export function setCustomerUser(user) {
  _writeDual(CUSTOMER_USER_KEY, JSON.stringify(user));
}
export function getCustomerUser() {
  const raw = _readDual(CUSTOMER_USER_KEY) || _readDual(PLATFORM_USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}
export function clearCustomerAuth() {
  // Critical: ONLY clear the customer slot. Admin session must survive a
  // customer logout in the same browser.
  _clearDual(CUSTOMER_TOKEN_KEY);
  _clearDual(CUSTOMER_USER_KEY);
  // iter 326nn — mirror cleanup for the legacy slot when it holds a
  // customer token (same rationale as clearAdminAuth above).
  const legacy = _readDual(PLATFORM_TOKEN_KEY);
  if (legacy && _decodeRole(legacy) === 'customer') {
    _clearDual(PLATFORM_TOKEN_KEY);
    _clearDual(PLATFORM_USER_KEY);
  }
}


/* ──────────────────────────────────────────────────────────────────────
 * Legacy facade — old call sites use these. They route to the correct
 * per-role slot based on the JWT's role claim, and the read side returns
 * whichever role is currently present (admin first, then customer, then
 * the actual legacy slot for users whose tokens were saved pre-326o).
 *
 * Existing code keeps working without modification.
 * ────────────────────────────────────────────────────────────────────── */

export function getPlatformToken() {
  return (
    _readDual(ADMIN_TOKEN_KEY)
    || _readDual(CUSTOMER_TOKEN_KEY)
    || _readDual(PLATFORM_TOKEN_KEY)
  );
}

export function setPlatformToken(token) {
  // Route write to the correct per-role slot so future reads from the
  // role-aware API hit the right place. Always write the legacy slot too
  // for any code that still reads `platform_token` directly.
  const role = _decodeRole(token);
  if (role === 'admin') {
    _writeDual(ADMIN_TOKEN_KEY, token);
  } else if (role === 'customer') {
    _writeDual(CUSTOMER_TOKEN_KEY, token);
  }
  _writeDual(PLATFORM_TOKEN_KEY, token);
}

export function getPlatformUser() {
  const raw = (
    _readDual(ADMIN_USER_KEY)
    || _readDual(CUSTOMER_USER_KEY)
    || _readDual(PLATFORM_USER_KEY)
  );
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    // One-time shape migration: legacy code stored the full login response
    // `{token, user}`. Downstream consumers expect the flat user object, so
    // auto-unwrap and re-persist the clean shape.
    if (parsed && parsed.user && parsed.token && !parsed.email && !parsed.is_admin) {
      const flatUser = parsed.user;
      _writeDual(PLATFORM_USER_KEY, JSON.stringify(flatUser));
      return flatUser;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function setPlatformUser(user) {
  // Mirror writes into both the per-role slot (chosen by user.role) and
  // the legacy slot so all readers see the same shape.
  const role = (user && (user.is_super_admin || user.is_admin
                          || user.role === 'admin'
                          || user.role === 'super_admin'))
    ? 'admin' : 'customer';
  const json = JSON.stringify(user);
  if (role === 'admin') {
    _writeDual(ADMIN_USER_KEY, json);
  } else {
    _writeDual(CUSTOMER_USER_KEY, json);
  }
  _writeDual(PLATFORM_USER_KEY, json);
}

export function clearPlatformAuth() {
  // iter 326o — Legacy behaviour DANGEROUSLY wiped everything for every
  // role, which is exactly what caused the founder's bug. We now infer
  // which role the caller meant by checking which slot is populated and
  // ONLY clear that one + the legacy slot. We do NOT clear the OTHER
  // role's slot. Callers that need a hard "logout everyone" should call
  // both `clearAdminAuth()` and `clearCustomerAuth()` explicitly.
  const adminPresent = !!_readDual(ADMIN_TOKEN_KEY);
  const customerPresent = !!_readDual(CUSTOMER_TOKEN_KEY);
  if (adminPresent && !customerPresent) {
    _clearDual(ADMIN_TOKEN_KEY);
    _clearDual(ADMIN_USER_KEY);
  } else if (customerPresent && !adminPresent) {
    _clearDual(CUSTOMER_TOKEN_KEY);
    _clearDual(CUSTOMER_USER_KEY);
  } else if (adminPresent && customerPresent) {
    // Both present — this is the "both logged in same browser" case.
    // Try to determine which one the caller meant by inspecting the
    // legacy slot's role claim (the legacy slot tracks the LAST writer).
    const legacyTok = _readDual(PLATFORM_TOKEN_KEY);
    const lastRole = _decodeRole(legacyTok);
    if (lastRole === 'admin') {
      _clearDual(ADMIN_TOKEN_KEY);
      _clearDual(ADMIN_USER_KEY);
    } else {
      _clearDual(CUSTOMER_TOKEN_KEY);
      _clearDual(CUSTOMER_USER_KEY);
    }
  }
  // Always clear the legacy slot.
  _clearDual(PLATFORM_TOKEN_KEY);
  _clearDual(PLATFORM_USER_KEY);
}
