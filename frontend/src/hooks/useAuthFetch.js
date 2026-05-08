/**
 * useAuthFetch — single source of truth for authenticated platform API calls.
 *
 * Every admin/platform component MUST use this hook instead of raw fetch to
 * prevent the recurring "401 Auth required" bug caused by components forgetting
 * to attach the Bearer token.
 *
 * Token resolution order (matches what AdminLogin / PlatformAuth actually use):
 *   1. sessionStorage.platform_token    (primary — set by setPlatformToken)
 *   2. sessionStorage.aurem_platform_token
 *   3. localStorage.aurem_jwt
 *   4. localStorage.platform_token      (legacy)
 *   5. localStorage.admin_token         (legacy)
 *   6. localStorage.aurem_token         (OraPWA)
 *
 * Usage:
 *   const { apiFetch, apiJson, token } = useAuthFetch();
 *   const data = await apiJson("/api/agents/status");
 *   await apiJson("/api/agents/hunter/hunt-now", { method: "POST", body: {...} });
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getPlatformToken } from "../utils/secureTokenStore";
import { BACKEND_URL } from "../lib/api";

// Use the smart resolver (`lib/api.js`) so stale baked-in
// REACT_APP_BACKEND_URL on aurem.live automatically falls back to
// window.location.origin instead of hitting a dead preview pod.
const API = BACKEND_URL;

export function resolveAuthToken() {
  try {
    return (
      getPlatformToken() ||
      sessionStorage.getItem("aurem_platform_token") ||
      localStorage.getItem("aurem_jwt") ||
      localStorage.getItem("platform_token") ||
      localStorage.getItem("admin_token") ||
      localStorage.getItem("aurem_token") ||
      ""
    );
  } catch {
    return "";
  }
}

export default function useAuthFetch() {
  // apiFetch: returns the raw Response — use when you need headers/status.
  const apiFetch = useCallback(async (path, opts = {}) => {
    const token = resolveAuthToken();
    const isForm = opts.body instanceof FormData;
    const headers = {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    };
    const url = path.startsWith("http") ? path : `${API}${path}`;
    return fetch(url, { credentials: "omit", ...opts, headers });
  }, []);

  // apiJson: the common path — POST/GET JSON, throw on non-2xx with parsed error.
  const apiJson = useCallback(
    async (path, opts = {}) => {
      const body =
        opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)
          ? JSON.stringify(opts.body)
          : opts.body;
      const r = await apiFetch(path, { ...opts, body });
      if (!r.ok) {
        let msg = `${r.status}`;
        try {
          const d = await r.json();
          msg = d.detail || d.error || msg;
        } catch {
          /* non-json error body */
        }
        const err = new Error(msg);
        err.status = r.status;
        throw err;
      }
      // 204 / empty body safe path
      const text = await r.text();
      if (!text) return null;
      try {
        return JSON.parse(text);
      } catch {
        return text;
      }
    },
    [apiFetch]
  );

  const token = useMemo(resolveAuthToken, []);

  return { apiFetch, apiJson, token, API_URL: API };
}

/**
 * useLiveApi — drop-in LIVE DATA fetcher with auto-refresh.
 * iter 272 — Every admin/dashboard tab using this hook now auto-refreshes
 * without any per-component changes.
 *
 * Behavior:
 *   • Fetches `path` on mount
 *   • Re-fetches every `intervalMs` (default 15s)
 *   • Pauses polling when tab is hidden (saves battery + API cost)
 *   • Instant re-fetch on visibility return, window focus, network reconnect
 *   • Overlap prevention — no duplicate in-flight requests
 *   • Skips polling if no auth token (prevents 401 spam before login)
 *
 * Usage:
 *   const { data, loading, error, refresh } = useLiveApi("/api/agents/status");
 *   const { data } = useLiveApi("/api/foo", { intervalMs: 30000 });
 *   const { data } = useLiveApi("/api/foo", { enabled: !!someId });
 *
 * Returns:
 *   data     — last successful response (null until first load)
 *   loading  — true on first load
 *   refreshing — true on subsequent polls
 *   error    — Error object from last failed fetch (stale data preserved)
 *   refresh  — manual re-fetch trigger
 */
export function useLiveApi(path, options = {}) {
  const {
    intervalMs = 15000,
    enabled = true,
    pauseWhenHidden = true,
    refetchOnFocus = true,
    refetchOnReconnect = true,
    requireAuth = true,
  } = options;

  const { apiJson } = useAuthFetch();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const inFlight = useRef(false);
  const timerRef = useRef(null);
  const mounted = useRef(true);
  const firstLoad = useRef(true);

  const pathRef = useRef(path);
  useEffect(() => { pathRef.current = path; }, [path]);

  const runOnce = useCallback(async () => {
    if (inFlight.current) return;
    if (!pathRef.current) return;
    if (requireAuth && !resolveAuthToken()) return;
    inFlight.current = true;
    if (firstLoad.current) setLoading(true); else setRefreshing(true);
    try {
      const result = await apiJson(pathRef.current);
      if (!mounted.current) return;
      setData(result);
      setError(null);
    } catch (e) {
      if (!mounted.current) return;
      setError(e);
    } finally {
      if (mounted.current) {
        setLoading(false);
        setRefreshing(false);
        firstLoad.current = false;
      }
      inFlight.current = false;
    }
  }, [apiJson, requireAuth]);

  useEffect(() => {
    mounted.current = true;
    if (!enabled) return;

    const start = () => {
      if (timerRef.current) return;
      runOnce();
      timerRef.current = setInterval(runOnce, intervalMs);
    };
    const stop = () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
    const onVisibility = () => {
      if (!pauseWhenHidden) return;
      if (document.visibilityState === "visible") start();
      else stop();
    };
    const onFocus = () => { if (refetchOnFocus) runOnce(); };
    const onReconnect = () => { if (refetchOnReconnect) runOnce(); };

    if (!pauseWhenHidden || document.visibilityState === "visible") start();
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", onFocus);
    window.addEventListener("online", onReconnect);

    return () => {
      mounted.current = false;
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("online", onReconnect);
    };
  }, [enabled, intervalMs, pauseWhenHidden, refetchOnFocus, refetchOnReconnect, runOnce]);

  return { data, loading, refreshing, error, refresh: runOnce };
}
