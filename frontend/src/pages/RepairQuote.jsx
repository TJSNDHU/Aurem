/**
 * Public Repair Quote Page (iter 281.4 / Phase 2.4)
 * ====================================================
 * Public, no-auth lead magnet at /repair-quote.
 * Visitor enters URL + email → free 6-point audit → scorecard + email follow-up.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, ShieldCheck, Zap, Globe2, Mail, Smartphone, Link2, FileSearch, CalendarDays, ArrowRight, Sparkles, Check } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const LEGEND = [
  { key: "ssl", label: "SSL Certificate", icon: ShieldCheck, max: 20 },
  { key: "pagespeed", label: "Page Speed", icon: Zap, max: 20 },
  { key: "mobile", label: "Mobile Ready", icon: Smartphone, max: 20 },
  { key: "broken_links", label: "Working Links", icon: Link2, max: 15 },
  { key: "contact_form", label: "Contact Form", icon: Mail, max: 10 },
  { key: "social_links", label: "Social Links", icon: Globe2, max: 10 },
  { key: "copyright_year", label: "Updated Year", icon: CalendarDays, max: 5 },
];

function scoreColor(score) {
  if (score == null) return "#666";
  if (score >= 80) return "#10B981"; // emerald
  if (score >= 60) return "#D4AF37"; // gold
  if (score >= 40) return "#F59E0B"; // amber
  return "#EF4444"; // red
}

const RepairQuote = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    url: "",
    email: "",
    business_name: "",
    contact_phone: "",
    consent: true,
  });
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState("");
  const progressTimerRef = useRef(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  // ── "I don't have a website" instant-builder flow (7-day trial) ───
  // iter 322ab — customer chooses their OWN password (no temp generation).
  // iter 322ad — added optional services + URL fields for retention.
  // iter 322ae — added optional reviews_url for direct Birdeye/Google scrape.
  const [showNoSite, setShowNoSite] = useState(false);
  const [nwsForm, setNwsForm] = useState({
    business_name: "",
    email: "",
    phone: "",
    city: "",
    category: "",
    password: "",
    confirm_password: "",
    customer_services: "",
    website_url: "",
    reviews_url: "",
    consent: true,
  });
  const [nwsLoading, setNwsLoading] = useState(false);
  const [nwsResult, setNwsResult] = useState(null);
  const [nwsError, setNwsError] = useState("");

  const onNwsChange = useCallback((k) => (e) => {
    const v = e?.target?.type === "checkbox" ? e.target.checked : e.target.value;
    setNwsForm((p) => ({ ...p, [k]: v }));
  }, []);

  const submitNws = useCallback(async (e) => {
    e?.preventDefault?.();
    setNwsError("");
    setNwsResult(null);
    if (!nwsForm.business_name.trim() || !nwsForm.email.trim()) {
      setNwsError("Business name aur email dono chahiye.");
      return;
    }
    if (!nwsForm.consent) {
      setNwsError("CASL consent mark karo.");
      return;
    }
    if (!nwsForm.password || nwsForm.password.length < 8) {
      setNwsError("Password kam-se-kam 8 characters ka rakho.");
      return;
    }
    if (nwsForm.password !== nwsForm.confirm_password) {
      setNwsError("Confirm password match nahi kar raha.");
      return;
    }
    setNwsLoading(true);
    try {
      const r = await fetch(`${API}/api/website-builder/no-website`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nwsForm),
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        setNwsError(body?.detail || `Failed (HTTP ${r.status})`);
      } else {
        // iter 322ab — auto-login: persist token so /dashboard opens
        // without bouncing through /login.
        // iter 322ac — also set `aurem_customer_token` (LuxeAuthContext
        // storage key) + `aurem_customer_remember=1` so when /dashboard
        // internally redirects non-admin to /my, the customer portal
        // recognizes the session and skips the login overlay.
        if (body?.token) {
          try {
            localStorage.setItem("token", body.token);
            localStorage.setItem("aurem_admin_token", body.token);
            localStorage.setItem("aurem_customer_token", body.token);
            localStorage.setItem("aurem_customer_remember", "1");
            sessionStorage.setItem("platform_token", body.token);
            sessionStorage.setItem("aurem_customer_token", body.token);
          } catch {
            // storage unavailable — token still in JSON; user can refresh
          }
        }
        setNwsResult(body);
        // iter 322ac — auto-redirect to /dashboard after 4s so customer
        // lands directly on their portal (no manual click, no login page).
        setTimeout(() => {
          try {
            navigate("/dashboard");
          } catch {
            window.location.href = "/dashboard";
          }
        }, 4000);
      }
    } catch (err) {
      setNwsError(err.message || "Network error");
    } finally {
      setNwsLoading(false);
    }
  }, [nwsForm, navigate]);

  // iter 282al-13 — synthetic 0→100 progress bar that mirrors the
  // 6-step audit (SSL → speed → mobile → links → contact → social).
  // Caps at 92 until the real response lands, then snaps to 100.
  const PROGRESS_STEPS = [
    { pct: 8,  label: "Resolving DNS…" },
    { pct: 22, label: "Checking SSL certificate…" },
    { pct: 38, label: "Running PageSpeed (mobile)…" },
    { pct: 54, label: "Scanning mobile readiness…" },
    { pct: 68, label: "Validating links & forms…" },
    { pct: 82, label: "Detecting social signals…" },
    { pct: 92, label: "Compiling report…" },
  ];

  useEffect(() => {
    if (!loading) {
      if (progressTimerRef.current) {
        clearInterval(progressTimerRef.current);
        progressTimerRef.current = null;
      }
      return;
    }
    let i = 0;
    setProgress(PROGRESS_STEPS[0].pct);
    setProgressLabel(PROGRESS_STEPS[0].label);
    progressTimerRef.current = setInterval(() => {
      i = Math.min(i + 1, PROGRESS_STEPS.length - 1);
      setProgress(PROGRESS_STEPS[i].pct);
      setProgressLabel(PROGRESS_STEPS[i].label);
    }, 3500);
    return () => {
      if (progressTimerRef.current) clearInterval(progressTimerRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  const onChange = useCallback((k) => (e) => {
    const v = e?.target?.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((p) => ({ ...p, [k]: v }));
  }, []);

  const submit = useCallback(async (e) => {
    e?.preventDefault?.();
    setError("");
    setReport(null);
    if (!form.url.trim() || !form.email.trim()) {
      setError("URL aur email dono chahiye boss.");
      return;
    }
    if (!form.consent) {
      setError("CASL consent mark karo (one click).");
      return;
    }
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/public/repair-quote/audit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(body?.detail || `Audit failed (HTTP ${r.status})`);
      } else {
        setProgress(100);
        setProgressLabel("Done.");
        setReport(body);
      }
    } catch (e) {
      setError(e.message || "Network error");
    } finally {
      setLoading(false);
    }
  }, [form]);

  const score = report?.overall_score;
  const breakdown = report?.score_breakdown || {};

  return (
    <div
      data-testid="repair-quote-page"
      className="min-h-screen bg-gradient-to-b from-zinc-950 via-black to-zinc-950 text-zinc-100"
    >
      <div className="max-w-3xl mx-auto px-5 py-12">
        {/* Top-bar with Log In option (P0: existing customers skip signup) */}
        <div className="mb-6 flex items-center justify-between text-[12px]">
          <button
            type="button"
            onClick={() => navigate("/")}
            data-testid="repair-quote-home-link"
            className="text-zinc-400 hover:text-amber-400 transition flex items-center gap-1"
          >
            ← AUREM Home
          </button>
          <div className="flex items-center gap-3">
            <span className="text-zinc-500">Already have an account?</span>
            <button
              type="button"
              onClick={() => navigate("/my")}
              data-testid="repair-quote-login-btn"
              className="px-4 py-2 rounded-md border border-amber-500/40 text-amber-400 hover:bg-amber-500/10 transition font-medium"
            >
              Log In →
            </button>
          </div>
        </div>

        <div className="mb-10">
          <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-widest text-amber-400 mb-3">
            <FileSearch className="w-3 h-3" /> AUREM Repair · Free Audit
          </div>
          <h1 className="text-4xl sm:text-5xl font-semibold leading-tight mb-3">
            Free 6-point audit of your website.
            <br />
            <span className="text-amber-400">In 30 seconds.</span>
          </h1>
          <p className="text-zinc-400 text-base">
            Drop your URL — we run SSL · speed · mobile · broken links · contact form ·
            social signals · copyright year. Report goes to your inbox + a fixed-price
            repair quote within 24h.
          </p>
        </div>

        {/* Form */}
        {!report && (
          <form
            onSubmit={submit}
            data-testid="repair-quote-form"
            className="rounded-2xl border border-zinc-800 bg-zinc-950/70 p-6 space-y-4"
          >
            <div>
              <label className="text-[11px] uppercase tracking-wider text-zinc-500">
                Website URL <span className="text-amber-400">*</span>
              </label>
              <input
                data-testid="repair-quote-url"
                type="text"
                placeholder="example.com"
                value={form.url}
                onChange={onChange("url")}
                className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
                required
              />
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-[11px] uppercase tracking-wider text-zinc-500">
                  Email <span className="text-amber-400">*</span>
                </label>
                <input
                  data-testid="repair-quote-email"
                  type="email"
                  placeholder="you@business.com"
                  value={form.email}
                  onChange={onChange("email")}
                  className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wider text-zinc-500">
                  Business Name (optional)
                </label>
                <input
                  data-testid="repair-quote-business"
                  type="text"
                  placeholder="Acme Corp"
                  value={form.business_name}
                  onChange={onChange("business_name")}
                  className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
                />
              </div>
            </div>

            <label className="flex items-start gap-3 text-[12px] text-zinc-400 select-none cursor-pointer">
              <input
                data-testid="repair-quote-consent"
                type="checkbox"
                checked={form.consent}
                onChange={onChange("consent")}
                className="mt-1 accent-amber-500"
              />
              <span>
                I agree to receive my audit + a one-time repair quote by email
                (CASL-compliant). Unsubscribe in one click.
              </span>
            </label>

            {error && (
              <div
                data-testid="repair-quote-error"
                className="rounded-lg border border-rose-900 bg-rose-950/40 p-3 text-[13px] text-rose-300"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              data-testid="repair-quote-submit"
              className="w-full mt-2 bg-gradient-to-r from-amber-500 to-amber-300 hover:from-amber-400 hover:to-amber-200 text-black font-semibold py-3.5 rounded-lg flex items-center justify-center gap-2 disabled:opacity-50 transition"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Auditing…
                </>
              ) : (
                <>
                  <FileSearch className="w-4 h-4" /> Run free audit
                </>
              )}
            </button>

            {/* iter 282al-13 — Progress bar (0-100%) during scan */}
            {loading && (
              <div data-testid="repair-quote-progress" className="mt-2 space-y-2">
                <div className="flex items-center justify-between text-[11px] uppercase tracking-widest">
                  <span className="text-zinc-400" data-testid="repair-quote-progress-label">
                    {progressLabel || "Initialising…"}
                  </span>
                  <span className="text-amber-300 font-mono" data-testid="repair-quote-progress-pct">
                    {progress}%
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-900 ring-1 ring-amber-500/20">
                  <div
                    className="h-full bg-gradient-to-r from-amber-500 to-amber-300 transition-[width] duration-700 ease-out"
                    style={{ width: `${progress}%` }}
                    data-testid="repair-quote-progress-fill"
                  />
                </div>
                <p className="text-[10.5px] text-zinc-500 text-center">
                  Real audit in flight — Playwright + Google PageSpeed.
                </p>
              </div>
            )}

            <p className="text-[11px] text-zinc-500 text-center">
              Real audit using Playwright + Google PageSpeed. No mock data.
            </p>
          </form>
        )}

        {/* ── NO-WEBSITE CTA — opens instant 7-day starter site flow ── */}
        {!report && !showNoSite && (
          <div data-testid="no-website-cta-wrap" className="mt-5 text-center">
            <button
              type="button"
              data-testid="no-website-cta"
              onClick={() => { setShowNoSite(true); setNwsResult(null); setNwsError(""); }}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-amber-500/40 bg-amber-500/5 hover:bg-amber-500/15 text-amber-300 text-[13px] font-medium transition"
            >
              <Sparkles className="w-3.5 h-3.5" />
              I don't have a website — build me a free one (7-day trial)
            </button>
          </div>
        )}

        {/* ── NO-WEBSITE FORM ── */}
        {!report && showNoSite && !nwsResult && (
          <form
            onSubmit={submitNws}
            data-testid="no-website-form"
            className="mt-6 rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-zinc-950/70 p-6 space-y-4"
          >
            <div className="flex items-start justify-between gap-3 mb-2">
              <div>
                <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-widest text-amber-400 mb-1">
                  <Sparkles className="w-3 h-3" /> Free Starter Site · 7-day Trial
                </div>
                <h3 className="text-xl font-semibold">Build my website now</h3>
                <p className="text-zinc-400 text-[13px] mt-1">
                  We'll instantly generate a live sample site, install AUREM pixels, and create your dashboard. Subscribe before day 7 to keep it.
                </p>
              </div>
              <button
                type="button"
                data-testid="no-website-cancel"
                onClick={() => setShowNoSite(false)}
                className="text-zinc-500 hover:text-zinc-300 text-sm"
              >
                ✕
              </button>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-[11px] uppercase tracking-wider text-zinc-500">
                  Business Name <span className="text-amber-400">*</span>
                </label>
                <input
                  data-testid="nws-business-name"
                  type="text"
                  placeholder="Acme Roofing"
                  value={nwsForm.business_name}
                  onChange={onNwsChange("business_name")}
                  className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wider text-zinc-500">
                  Email <span className="text-amber-400">*</span>
                </label>
                <input
                  data-testid="nws-email"
                  type="email"
                  placeholder="you@business.com"
                  value={nwsForm.email}
                  onChange={onNwsChange("email")}
                  className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
                  required
                />
              </div>
            </div>

            <div className="grid sm:grid-cols-3 gap-4">
              <div>
                <label className="text-[11px] uppercase tracking-wider text-zinc-500">Phone</label>
                <input
                  data-testid="nws-phone"
                  type="tel"
                  placeholder="(555) 123-4567"
                  value={nwsForm.phone}
                  onChange={onNwsChange("phone")}
                  className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wider text-zinc-500">City</label>
                <input
                  data-testid="nws-city"
                  type="text"
                  placeholder="Toronto, ON"
                  value={nwsForm.city}
                  onChange={onNwsChange("city")}
                  className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wider text-zinc-500">Industry</label>
                <input
                  data-testid="nws-category"
                  type="text"
                  placeholder="Roofing, HVAC, etc."
                  value={nwsForm.category}
                  onChange={onNwsChange("category")}
                  className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
                />
              </div>
            </div>

            {/* iter 322ad — retention fix #1: customer-supplied services */}
            <div>
              <label className="text-[11px] uppercase tracking-wider text-zinc-500">
                Your Top Services <span className="text-zinc-600 normal-case tracking-normal">(optional — helps personalise your site)</span>
              </label>
              <input
                data-testid="nws-services"
                type="text"
                maxLength={150}
                placeholder="e.g. Oil change, Brake repair, Engine diagnostics"
                value={nwsForm.customer_services}
                onChange={onNwsChange("customer_services")}
                className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
              />
              <div className="mt-1 text-[11px] text-zinc-600">
                Comma-separated, max 6 services. Leave blank to use industry defaults.
              </div>
            </div>

            {/* iter 322ad — retention fix #4: brand-color extraction URL */}
            <div>
              <label className="text-[11px] uppercase tracking-wider text-zinc-500">
                Existing Website or Facebook URL <span className="text-zinc-600 normal-case tracking-normal">(optional — we'll match your brand colors)</span>
              </label>
              <input
                data-testid="nws-website-url"
                type="text"
                inputMode="url"
                placeholder="yoursite.com  or  facebook.com/yourbusiness"
                value={nwsForm.website_url}
                onChange={onNwsChange("website_url")}
                className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
              />
            </div>

            {/* iter 322ae — direct review-source URL for instant real reviews */}
            <div>
              <label className="text-[11px] uppercase tracking-wider text-zinc-500">
                Your Google Business or Birdeye URL <span className="text-zinc-600 normal-case tracking-normal">(optional — we'll pull your real reviews)</span>
              </label>
              <input
                data-testid="nws-reviews-url"
                type="text"
                inputMode="url"
                placeholder="reviews.birdeye.com/your-biz  or  g.page/your-biz"
                value={nwsForm.reviews_url}
                onChange={onNwsChange("reviews_url")}
                className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
              />
              <div className="mt-1 text-[11px] text-zinc-600">
                Skip this and we'll auto-search. If we can't find it we'll write realistic sample reviews you can edit later.
              </div>
            </div>

            {/* iter 322ab — customer-chosen password (no temp generation) */}
            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] uppercase tracking-widest text-zinc-500">
                  Create Password<span className="text-rose-400 ml-0.5">*</span>
                </label>
                <input
                  data-testid="nws-password"
                  type="password"
                  placeholder="Min 8 characters"
                  autoComplete="new-password"
                  value={nwsForm.password}
                  onChange={onNwsChange("password")}
                  className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-widest text-zinc-500">
                  Confirm Password<span className="text-rose-400 ml-0.5">*</span>
                </label>
                <input
                  data-testid="nws-confirm-password"
                  type="password"
                  placeholder="Re-enter password"
                  autoComplete="new-password"
                  value={nwsForm.confirm_password}
                  onChange={onNwsChange("confirm_password")}
                  className="mt-1 w-full bg-black/60 border border-zinc-800 rounded-lg px-4 py-3 text-base focus:border-amber-500 outline-none"
                />
              </div>
            </div>

            <label className="flex items-start gap-3 text-[12px] text-zinc-400 select-none cursor-pointer">
              <input
                data-testid="nws-consent"
                type="checkbox"
                checked={nwsForm.consent}
                onChange={onNwsChange("consent")}
                className="mt-1 accent-amber-500"
              />
              <span>
                I agree to receive my login credentials + onboarding emails (CASL-compliant). Trial ends in 7 days unless I subscribe.
              </span>
            </label>

            {nwsError && (
              <div data-testid="nws-error" className="rounded-lg border border-rose-900 bg-rose-950/40 p-3 text-[13px] text-rose-300">
                {nwsError}
              </div>
            )}

            <button
              type="submit"
              disabled={nwsLoading}
              data-testid="nws-submit"
              className="w-full bg-gradient-to-r from-amber-500 to-amber-300 hover:from-amber-400 hover:to-amber-200 text-black font-semibold py-3.5 rounded-lg flex items-center justify-center gap-2 disabled:opacity-50 transition"
            >
              {nwsLoading ? (<><Loader2 className="w-4 h-4 animate-spin" /> Building your site…</>) : (<><Sparkles className="w-4 h-4" /> Build my free site</>)}
            </button>
          </form>
        )}

        {/* ── NO-WEBSITE SUCCESS — customer chose own password, JWT auto-stored,
             auto-redirect to /dashboard in 4s. ZERO temp-password leak. ── */}
        {nwsResult && (
          <div data-testid="nws-result" className="mt-6 rounded-2xl border border-amber-500/40 bg-gradient-to-br from-amber-500/10 to-zinc-950/70 p-6 space-y-5">
            <div>
              <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-widest text-amber-300 mb-2">
                <Check className="w-3 h-3" /> You're signed in
              </div>
              <h3 className="text-2xl font-semibold">Welcome to AUREM 👋</h3>
              <p className="text-zinc-400 text-sm mt-2">
                Your sample site is being built (live in 30–60s) and your <strong className="text-amber-300">7-day trial</strong> is active. Taking you to your dashboard…
              </p>
            </div>

            <div className="rounded-lg bg-black/40 border border-zinc-800 p-4 space-y-3 font-mono text-[13px]">
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Email</span>
                <span data-testid="nws-result-email" className="text-zinc-100">{nwsResult.email || nwsResult?.user?.email || nwsForm.email}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Business ID</span>
                <span data-testid="nws-result-bin" className="text-amber-300">{nwsResult.bin}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Trial ends</span>
                <span className="text-zinc-100">{nwsResult.trial_ends_human || (nwsResult.trial_ends_at ? new Date(nwsResult.trial_ends_at).toLocaleDateString() : "")}</span>
              </div>
            </div>

            <div className="text-[12px] text-zinc-500 flex items-center gap-2">
              <Loader2 className="w-3 h-3 animate-spin" />
              Auto-redirecting to your dashboard…
            </div>

            <div className="grid sm:grid-cols-2 gap-3">
              <a
                href={nwsResult.sample_url}
                target="_blank"
                rel="noopener noreferrer"
                data-testid="nws-view-site"
                className="inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-amber-500/40 bg-amber-500/5 hover:bg-amber-500/15 text-amber-300 font-medium transition"
              >
                <Globe2 className="w-4 h-4" /> View my sample site
              </a>
              <button
                type="button"
                onClick={() => navigate("/dashboard")}
                data-testid="nws-go-dashboard"
                className="inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-gradient-to-r from-amber-500 to-amber-300 hover:from-amber-400 hover:to-amber-200 text-black font-semibold transition"
              >
                Go to dashboard now <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Report */}
        {report && (
          <div data-testid="repair-quote-report" className="space-y-6">
            {/* Score donut */}
            <div className="rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-950 to-black p-8 text-center">
              <div className="text-[11px] uppercase tracking-widest text-zinc-500 mb-2">
                Overall Score
              </div>
              <div
                data-testid="repair-quote-score"
                className="text-7xl font-bold mb-1"
                style={{ color: scoreColor(score) }}
              >
                {score ?? "?"}
                <span className="text-3xl text-zinc-500">/100</span>
              </div>
              <div className="text-zinc-400 text-sm mt-2">
                {report.url}
              </div>
            </div>

            {/* Score breakdown */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 p-6">
              <h3 className="text-base font-semibold mb-4">Score breakdown</h3>
              <div className="grid sm:grid-cols-2 gap-3">
                {LEGEND.map(({ key, label, icon: Icon, max }) => {
                  const got = breakdown[key] ?? 0;
                  const pct = Math.round((got / max) * 100);
                  return (
                    <div
                      key={key}
                      data-testid={`repair-quote-breakdown-${key}`}
                      className="flex items-center gap-3 p-3 rounded-lg bg-black/40 border border-zinc-900"
                    >
                      <Icon className="w-4 h-4 text-amber-400 shrink-0" />
                      <div className="flex-1">
                        <div className="text-[12px] text-zinc-300">{label}</div>
                        <div className="h-1.5 rounded-full bg-zinc-900 overflow-hidden mt-1.5">
                          <div
                            className="h-full bg-amber-400"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                      <div className="text-[11px] text-zinc-500 w-10 text-right">
                        {got}/{max}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Issues */}
            {(report.issues || []).length > 0 && (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 p-6">
                <h3 className="text-base font-semibold mb-4">Top issues found</h3>
                <ul className="space-y-2">
                  {report.issues.map((i, idx) => (
                    <li
                      key={idx}
                      data-testid={`repair-quote-issue-${idx}`}
                      className="flex items-start gap-2 text-sm text-zinc-300"
                    >
                      <span
                        className={`text-[10px] uppercase mt-0.5 px-2 py-0.5 rounded border tracking-wider ${
                          i.severity === "high"
                            ? "border-rose-700 text-rose-300 bg-rose-950/40"
                            : i.severity === "medium"
                            ? "border-amber-700 text-amber-300 bg-amber-950/40"
                            : "border-zinc-700 text-zinc-400 bg-zinc-900"
                        }`}
                      >
                        {i.severity || "low"}
                      </span>
                      <span>
                        <strong>{i.title}</strong>
                        {i.detail ? <span className="text-zinc-500"> · {i.detail}</span> : null}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Diagnosis (Claude) */}
            {report.diagnosis && (
              <div className="rounded-2xl border border-amber-700/40 bg-gradient-to-br from-amber-950/30 to-zinc-950 p-6">
                <h3 className="text-base font-semibold mb-3 text-amber-300">
                  Diagnosis
                </h3>
                <pre
                  data-testid="repair-quote-diagnosis"
                  className="whitespace-pre-wrap text-sm text-zinc-200 font-sans"
                >
                  {report.diagnosis}
                </pre>
              </div>
            )}

            {/* CTA */}
            <div className="rounded-2xl border border-amber-500/40 bg-gradient-to-r from-amber-500/10 via-amber-300/5 to-amber-500/10 p-6 text-center">
              <div className="text-lg font-semibold mb-2">
                Get the full repair quote in 24h
              </div>
              <div className="text-sm text-zinc-300 mb-4">
                We've emailed your full report to <span className="text-amber-300">{form.email}</span>.
                Reply YES for a fixed-price repair plan.
              </div>

              {/* Post-audit → /my customer interface (signup mode pre-filled) */}
              <a
                href={`/my?signup=1&email=${encodeURIComponent(form.email || "")}&biz=${encodeURIComponent(form.business_name || "")}&from=repair-audit`}
                data-testid="repair-quote-next-btn"
                className="inline-flex items-center justify-center gap-2 w-full sm:w-auto px-6 py-3 rounded-lg bg-gradient-to-r from-amber-500 to-amber-300 hover:from-amber-400 hover:to-amber-200 text-black font-semibold transition shadow-lg shadow-amber-500/20"
              >
                Next — Open my AUREM dashboard
                <ArrowRight className="w-4 h-4" />
              </a>

              <div className="mt-3">
                <button
                  onClick={() => {
                    setReport(null);
                    setForm({ url: "", email: "", business_name: "", contact_phone: "", consent: true });
                  }}
                  data-testid="repair-quote-reset-btn"
                  className="text-[12px] underline text-amber-300 hover:text-amber-200"
                >
                  Audit another site
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="text-center mt-12 text-[11px] text-zinc-600">
          Powered by AUREM · No mocks, real Playwright + Claude diagnosis
        </div>
      </div>
    </div>
  );
};

export default RepairQuote;
