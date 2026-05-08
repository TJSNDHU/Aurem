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
 */

const PLATFORM_TOKEN_KEY = 'platform_token';
const PLATFORM_USER_KEY = 'platform_user';

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

export function getPlatformToken() {
  return _readDual(PLATFORM_TOKEN_KEY);
}

export function setPlatformToken(token) {
  _writeDual(PLATFORM_TOKEN_KEY, token);
}

export function getPlatformUser() {
  const raw = _readDual(PLATFORM_USER_KEY);
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
  _writeDual(PLATFORM_USER_KEY, JSON.stringify(user));
}

export function clearPlatformAuth() {
  _clearDual(PLATFORM_TOKEN_KEY);
  _clearDual(PLATFORM_USER_KEY);
}
