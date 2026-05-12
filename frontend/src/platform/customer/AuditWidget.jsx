/**
 * AuditWidget — SEO score + Ads waste detector card for /my dashboard.
 *
 * Fetches `/api/customer/audit/latest`. If no audit exists, shows a "Run
 * audit now" button. If an audit exists, shows the four Lighthouse scores,
 * top issues, and the estimated $/mo Google Ads waste with the option to
 * unlock full Ads optimisation for $49/mo (Stripe upsell).
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { Loader2, AlertTriangle, TrendingDown, Sparkles, ExternalLink } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const COLORS = {
  bg: "rgba(255,255,255,0.04)",
  border: "rgba(212,175,55,0.18)",
  accent: "#D4AF37",
  accent2: "#FF6B00",
  ok: "#22C55E",
  warn: "#F59E0B",
  bad: "#EF4444",
  text: "#F0EADC",
  textD: "#A8A08F",
};

const scoreColor = (s) => (s >= 90 ? COLORS.ok : s >= 60 ? COLORS.warn : COLORS.bad);

const ScorePill = ({ label, score }) => (
  <div data-testid={`audit-score-${label.toLowerCase()}`} style={{
    display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
    padding: "10px 14px", borderRadius: 12,
    background: "rgba(255,255,255,0.03)", border: `1px solid ${COLORS.border}`,
    minWidth: 84,
  }}>
    <div style={{ fontSize: 28, fontWeight: 800, color: scoreColor(score), lineHeight: 1 }}>{score}</div>
    <div style={{ fontSize: 9, color: COLORS.textD, textTransform: "uppercase", letterSpacing: 1 }}>{label}</div>
  </div>
);

export default function AuditWidget() {
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const token = localStorage.getItem("aurem_customer_token") || localStorage.getItem("aurem_platform_token") || "";
  const headers = { Authorization: `Bearer ${token}` };

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/api/customer/audit/latest`, { headers, timeout: 10000 });
      if (data && data.id) {
        setAudit(data);
      } else {
        setAudit(null);
      }
    } catch (e) {
      // 401 = no token; just show empty state
      setAudit(null);
    }
    setLoading(false);
  };

  useEffect(() => { load(); /* poll every 30s in case bg audit completes */
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
    // eslint-disable-next-line
  }, []);

  const run = async (url) => {
    if (!url) return;
    let u = url.trim();
    if (!/^https?:\/\//i.test(u)) u = "https://" + u;
    setRunning(true); setErr("");
    try {
      const { data } = await axios.post(`${API}/api/customer/audit/run`,
        { url: u, strategy: "mobile" }, { headers, timeout: 80000 });
      setAudit(data);
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message || "Audit failed");
    }
    setRunning(false);
  };

  // Empty state
  if (!loading && !audit) {
    return (
      <div data-testid="audit-widget-empty" style={shellStyle}>
        <Header />
        <div style={{ padding: "8px 0", color: COLORS.textD, fontSize: 13, lineHeight: 1.55 }}>
          AUREM ne abhi tak tumhari website scan nahi ki. Enter your URL — Performance, SEO,
          aur estimated Google Ads waste — 60 seconds me.
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <input
            data-testid="audit-url-input"
            type="text" placeholder="https://yourbusiness.com"
            value={urlInput} onChange={(e) => setUrlInput(e.target.value)}
            style={inputStyle}
          />
          <button data-testid="audit-run-btn" onClick={() => run(urlInput)} disabled={running || !urlInput.trim()}
            style={btnAccent}>
            {running ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : "Audit"}
          </button>
        </div>
        {err && <div style={{ color: COLORS.bad, fontSize: 11, marginTop: 8, fontFamily: "monospace" }}>error: {err}</div>}
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </div>
    );
  }

  if (loading) {
    return (
      <div data-testid="audit-widget-loading" style={shellStyle}>
        <Header />
        <div style={{ display: "flex", alignItems: "center", gap: 10, color: COLORS.textD }}>
          <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Loading audit…
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </div>
    );
  }

  const scores = audit.scores || {};
  const ads = audit.ads || {};
  const waste = ads.estimated_monthly_waste_usd || 0;
  const issues = audit.top_issues || [];

  return (
    <div data-testid="audit-widget" style={shellStyle}>
      <Header url={audit.url} runAgain={() => run(audit.url)} running={running} />

      {audit.psi_status && audit.psi_status !== "ok" && (
        <div data-testid="audit-psi-warning" style={{
          marginBottom: 10, padding: "8px 12px", borderRadius: 8,
          background: "rgba(245,158,11,0.08)", border: `1px solid rgba(245,158,11,0.35)`,
          fontSize: 11, color: COLORS.warn, lineHeight: 1.5,
        }}>
          {audit.psi_status === "psi_api_not_enabled" && "Lighthouse scores are off — enable the PageSpeed Insights API on your Google Cloud key."}
          {audit.psi_status === "no_api_key" && "Lighthouse scores are off — no PSI key configured."}
          {audit.psi_status === "rate_limited" && "PageSpeed rate limit hit — re-run in a few minutes."}
          {audit.psi_status === "network_error" && "PageSpeed unreachable — retry shortly."}
        </div>
      )}

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 4 }}>
        <ScorePill label="Perf" score={scores.performance ?? 0} />
        <ScorePill label="SEO" score={scores.seo ?? 0} />
        <ScorePill label="A11y" score={scores.accessibility ?? 0} />
        <ScorePill label="Best" score={scores.best_practices ?? 0} />
      </div>

      {/* Ads waste callout */}
      {waste > 0 && (
        <div data-testid="audit-waste-callout" style={{
          marginTop: 14, padding: "12px 14px", borderRadius: 12,
          background: `linear-gradient(135deg, rgba(239,68,68,0.12), rgba(245,158,11,0.06))`,
          border: `1px solid rgba(239,68,68,0.35)`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <TrendingDown size={16} style={{ color: COLORS.bad }} />
            <strong style={{ color: COLORS.text }}>~${waste}/mo Google Ads waste detected</strong>
            <span style={{ fontSize: 10, color: COLORS.textD, marginLeft: "auto" }}>confidence: {ads.confidence}</span>
          </div>
          <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12, color: COLORS.textD, lineHeight: 1.6 }}>
            {(ads.waste_signals || []).slice(0, 3).map((s, i) => <li key={i}>{s}</li>)}
          </ul>
          <a href="/billing?addon=audit_pro" data-testid="audit-upgrade-link"
            style={{ display: "inline-flex", alignItems: "center", gap: 6, marginTop: 10, fontSize: 12,
              color: COLORS.accent, textDecoration: "none", fontWeight: 600 }}>
            <Sparkles size={13} /> Unlock Ads Optimisation Pro — $49/mo →
          </a>
        </div>
      )}

      {/* Top issues */}
      {issues.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
            <AlertTriangle size={13} style={{ color: COLORS.warn }} />
            <span style={{ fontSize: 11, color: COLORS.textD, textTransform: "uppercase", letterSpacing: 1 }}>Top issues</span>
          </div>
          <ul data-testid="audit-issues-list" style={{ margin: 0, padding: "0 0 0 18px", fontSize: 12, color: COLORS.text, lineHeight: 1.65 }}>
            {issues.slice(0, 5).map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}

      {/* iter 322ed — Intelligence Signals (wired from bin_intelligence) */}
      {audit.intelligence && audit.intelligence.available && (
        <div data-testid="audit-intelligence-section" style={{
          marginTop: 16, paddingTop: 14, borderTop: `1px dashed ${COLORS.border}`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%",
                            background: COLORS.accent, boxShadow: `0 0 8px ${COLORS.accent}` }} />
            <span style={{ fontSize: 11, color: COLORS.textD, textTransform: "uppercase", letterSpacing: 1 }}>
              Intelligence signals
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            <IntelTile label="Visitors today"
                        value={audit.intelligence.pixel_visitors_today}
                        testid="intel-visitors" />
            <IntelTile label="Forms filled"
                        value={audit.intelligence.pixel_forms_today}
                        testid="intel-forms" />
            <IntelTile label="Identified"
                        value={audit.intelligence.pixel_matched_contacts}
                        testid="intel-matched"
                        highlight={audit.intelligence.pixel_matched_contacts > 0} />
            <IntelTile label="Emails on file"
                        value={audit.intelligence.email_identified}
                        testid="intel-emails" />
            <IntelTile label="Phones verified"
                        value={audit.intelligence.phone_verified}
                        testid="intel-phones" />
            <IntelTile label="Past clients (CSV)"
                        value={audit.intelligence.invoice_past_clients}
                        testid="intel-invoices" />
          </div>
          {audit.intelligence.top_actions && audit.intelligence.top_actions.length > 0 && (
            <div data-testid="intel-top-actions" style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, color: COLORS.textD, textTransform: "uppercase",
                             letterSpacing: 1, marginBottom: 6 }}>Top action</div>
              {audit.intelligence.top_actions.slice(0, 1).map((a, i) => (
                <div key={i} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "8px 10px", borderRadius: 8,
                  background: `linear-gradient(135deg, rgba(212,175,55,0.10), rgba(255,107,0,0.04))`,
                  border: `1px solid rgba(212,175,55,0.30)`, fontSize: 12,
                }}>
                  <span style={{ color: COLORS.text }}>
                    {a.recommended_action || "Engage"} ·
                    <span style={{ color: COLORS.textD, marginLeft: 4 }}>
                      intent {a.intent_level || "—"}
                    </span>
                  </span>
                  <span style={{ color: COLORS.accent, fontWeight: 700, fontFamily: "monospace" }}>
                    {a.score ?? "—"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}

function IntelTile({ label, value, testid, highlight }) {
  return (
    <div data-testid={testid} style={{
      padding: "8px 10px", borderRadius: 10,
      background: highlight ? "rgba(212,175,55,0.08)" : "rgba(255,255,255,0.03)",
      border: `1px solid ${highlight ? "rgba(212,175,55,0.30)" : COLORS.border}`,
      display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2,
    }}>
      <span style={{ fontSize: 18, fontWeight: 700,
                     color: highlight ? COLORS.accent : COLORS.text,
                     fontFamily: "monospace", lineHeight: 1 }}>{value ?? 0}</span>
      <span style={{ fontSize: 9, color: COLORS.textD,
                     textTransform: "uppercase", letterSpacing: 0.8 }}>{label}</span>
    </div>
  );
}

function Header({ url, runAgain, running }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
      <div>
        <div style={{ fontSize: 11, color: COLORS.textD, textTransform: "uppercase", letterSpacing: 1.2 }}>SEO + ADS AUDIT</div>
        {url && (
          <a href={url} target="_blank" rel="noopener noreferrer"
            style={{ display: "inline-flex", gap: 4, alignItems: "center", color: COLORS.accent, fontSize: 12, textDecoration: "none" }}>
            {url.replace(/^https?:\/\//, "").slice(0, 40)} <ExternalLink size={10} />
          </a>
        )}
      </div>
      {runAgain && (
        <button onClick={runAgain} disabled={running} data-testid="audit-rerun-btn"
          style={{ ...btnGhost, padding: "5px 10px", fontSize: 10 }}>
          {running ? <Loader2 size={11} style={{ animation: "spin 1s linear infinite" }} /> : "Re-run"}
        </button>
      )}
    </div>
  );
}

const shellStyle = {
  padding: 18,
  borderRadius: 18,
  background: COLORS.bg,
  border: `1px solid ${COLORS.border}`,
  color: COLORS.text,
  fontFamily: "system-ui,-apple-system,sans-serif",
  boxShadow: "0 18px 50px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.05)",
};
const inputStyle = {
  flex: 1, padding: "10px 12px", borderRadius: 10,
  background: "rgba(255,255,255,0.04)", border: `1px solid ${COLORS.border}`,
  color: COLORS.text, fontSize: 13, outline: "none",
};
const btnGhost = {
  display: "flex", alignItems: "center", gap: 6,
  padding: "8px 14px", background: "rgba(255,255,255,0.04)",
  border: `1px solid ${COLORS.border}`, borderRadius: 10,
  color: COLORS.text, fontSize: 12, cursor: "pointer",
};
const btnAccent = {
  ...btnGhost,
  background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.accent2})`,
  color: "#08080F", fontWeight: 700, border: "none",
};
