/**
 * safeFetchJson — defensive JSON fetch for admin consoles.
 *
 * Why this exists (iter 325v ROOT-CAUSE FIX):
 *   Production users on aurem.live saw "Fetch failed: Unexpected token '<',
 *   '<!DOCTYPE ' is not valid JSON" everywhere. Root cause: every admin
 *   console (OraDevConsole, AdminPillarsMap, …) used raw fetch().json()
 *   without checking Content-Type. When Cloudflare returned its HTML 520
 *   "Web server returned an unknown error" page, .json() threw a cryptic
 *   parse error and admins thought the endpoint was dead.
 *
 * What this helper guarantees:
 *   1. Returns { ok, status, data, error, isAuthError, isGatewayError }.
 *   2. NEVER throws on non-JSON bodies — instead surfaces a friendly
 *      "gateway returned non-JSON (upstream outage)" error string.
 *   3. Maps 401/403 → isAuthError so the caller can show "Admin login
 *      required" instead of a generic failure banner.
 *   4. Maps 5xx / network errors → isGatewayError so the caller can show
 *      "Backend temporarily unreachable" instead of a parse error.
 *
 * The function deliberately does NOT auto-retry — that's a UI policy
 * decision the caller can make (e.g. useLiveApi already debounces).
 */
export async function safeFetchJson(url, opts = {}) {
  let r;
  try {
    r = await fetch(url, opts);
  } catch (e) {
    return {
      ok: false,
      status: 0,
      data: null,
      error: `Network error: ${e?.message || e}`,
      isAuthError: false,
      isGatewayError: true,
    };
  }

  const status = r.status;
  const isAuthError = status === 401 || status === 403;
  const isGatewayError = status >= 500 && status <= 599;

  const ctype = (r.headers.get("content-type") || "").toLowerCase();
  const looksJson = ctype.includes("application/json")
                 || ctype.includes("application/problem+json");

  if (!looksJson) {
    // Non-JSON body (HTML error page, plain-text, empty). Read body
    // for debugging but never parse it as JSON.
    const bodyPeek = await r.text().catch(() => "");
    return {
      ok: false,
      status,
      data: null,
      error: status >= 500
        ? `Backend gateway returned non-JSON (HTTP ${status}). Origin likely down.`
        : `Unexpected ${ctype || "non-JSON"} response (HTTP ${status}).`,
      isAuthError,
      isGatewayError: isGatewayError || !r.ok,
      bodyPeek: bodyPeek.slice(0, 200),
    };
  }

  let data = null;
  try {
    data = await r.json();
  } catch (e) {
    return {
      ok: false,
      status,
      data: null,
      error: `Invalid JSON body (HTTP ${status}): ${e?.message || e}`,
      isAuthError,
      isGatewayError: true,
    };
  }

  if (!r.ok) {
    return {
      ok: false,
      status,
      data,
      error: data?.detail || data?.error || `HTTP ${status}`,
      isAuthError,
      isGatewayError,
    };
  }

  return { ok: true, status, data, error: null, isAuthError: false, isGatewayError: false };
}

export default safeFetchJson;
