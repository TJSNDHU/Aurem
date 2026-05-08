/**
 * AdminHunterTest — "Fire a Test Run" button panel
 * ═══════════════════════════════════════════════════════════════════════════
 * Route: /admin/hunter-test
 * Access: super_admin
 *
 * Ek simple form jisme:
 *   - Email + Phone input
 *   - 3 channel toggles (Email / SMS / WhatsApp)
 *   - Industry / Province / Count
 *   - "Fire Test Run" button
 * Click karte hi live trace dikhai deta hai with per-step ok/error.
 */
import React, { useState, useEffect, useCallback } from "react";
import useAuthFetch from "../hooks/useAuthFetch";
import { Zap, Mail, MessageCircle, Phone, CheckCircle2, XCircle, RefreshCw, History } from "lucide-react";

export default function AdminHunterTest() {
  const { apiJson } = useAuthFetch();
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [industry, setIndustry] = useState("salons");
  const [province, setProvince] = useState("Ontario");
  const [count, setCount] = useState(1);
  const [sendEmail, setSendEmail] = useState(true);
  const [sendSms, setSendSms] = useState(false);
  const [sendWa, setSendWa] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [toast, setToast] = useState(null);

  const G = "#C9A227";

  const push = useCallback((m, t = "info") => {
    setToast({ m, t });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const d = await apiJson("/api/agents/hunter/run-test/history?limit=10");
      setHistory(d.tests || []);
    } catch { /* silent */ }
  }, [apiJson]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // Pre-fill admin's own email on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem("platform_user") || localStorage.getItem("aurem_user");
      if (raw) {
        const u = JSON.parse(raw);
        const myEmail = u?.email || u?.user?.email;
        if (myEmail && !email) setEmail(myEmail);
      }
    } catch { /* ignore */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fire = async () => {
    if (!sendEmail && !sendSms && !sendWa) {
      return push("Pick at least one channel", "error");
    }
    if (sendEmail && !email) return push("Email required for email channel", "error");
    if ((sendSms || sendWa) && !phone) return push("Phone required for SMS/WhatsApp", "error");

    setBusy(true);
    setResult(null);
    try {
      const d = await apiJson("/api/agents/hunter/run-test", {
        method: "POST",
        body: {
          test_email: email || null,
          test_phone: phone || null,
          industry,
          province,
          count: Number(count),
          send_email: sendEmail,
          send_sms: sendSms,
          send_whatsapp: sendWa,
        },
      });
      setResult(d);
      if (d.ok) push("Test fired — check inbox + phone", "success");
      else push("Some steps failed — check trace below", "error");
      await loadHistory();
    } catch (e) {
      push(`Failed: ${e.message}`, "error");
    }
    setBusy(false);
  };

  const s = {
    root: { minHeight: "100vh", padding: "24px 28px", background: "#050507", color: "#E4DDD3", fontFamily: "'Jost', sans-serif" },
    title: { fontFamily: "'Cinzel', serif", fontSize: 22, color: G, letterSpacing: ".12em" },
    sub: { fontSize: 11, color: "#7a7a7a", letterSpacing: ".08em", textTransform: "uppercase", marginTop: 4 },
    card: { background: "rgba(15,18,28,0.6)", border: `1px solid rgba(201,162,39,0.18)`, borderRadius: 10, padding: 18, backdropFilter: "blur(16px)", marginTop: 18 },
    label: { fontSize: 9, letterSpacing: ".2em", textTransform: "uppercase", color: "#8a8a8a", fontWeight: 600, marginBottom: 5 },
    input: { width: "100%", background: "#0c0c0d", color: "#e4ddd3", border: "1px solid #222", borderRadius: 4, padding: "9px 11px", fontSize: 13, fontFamily: "'Jost', sans-serif" },
    row: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 },
    fireBtn: { background: G, color: "#0c0c0d", border: "none", padding: "14px 28px", borderRadius: 5, fontSize: 12, fontWeight: 700, letterSpacing: ".12em", textTransform: "uppercase", cursor: "pointer", width: "100%", marginTop: 14, boxShadow: `0 4px 20px ${G}55` },
    channel: (on) => ({
      padding: "12px 14px",
      borderRadius: 6,
      border: `1px solid ${on ? G : "rgba(255,255,255,0.08)"}`,
      background: on ? "rgba(201,162,39,0.08)" : "rgba(30,30,38,0.4)",
      color: on ? G : "#888",
      cursor: "pointer",
      display: "flex",
      alignItems: "center",
      gap: 8,
      fontSize: 12,
      fontWeight: 600,
      transition: "all 0.15s",
    }),
    step: (ok) => ({
      padding: "10px 14px",
      borderRadius: 4,
      background: "rgba(30,30,38,0.4)",
      border: `1px solid ${ok ? "rgba(126,200,160,0.25)" : "rgba(239,68,68,0.25)"}`,
      borderLeft: `3px solid ${ok ? "#7EC8A0" : "#EF4444"}`,
      marginBottom: 6,
      fontSize: 11,
      color: "#d4d4d4",
    }),
  };

  return (
    <div style={s.root} data-testid="admin-hunter-test">
      <div style={s.title}>⚡ Hunter · Live Test</div>
      <div style={s.sub}>Safe diagnostic · Sends ONE mock lead message to your own inbox/phone</div>

      {toast && (
        <div data-testid={`ht-toast-${toast.t}`} style={{ position: "fixed", top: 20, right: 20, zIndex: 1000,
          background: toast.t === "error" ? "#1a0808" : toast.t === "success" ? "#081508" : "#10101a",
          border: `1px solid ${toast.t === "error" ? "#7a2020" : "#2a5a2a"}`,
          padding: "10px 16px", borderRadius: 5, fontSize: 12 }}>
          {toast.m}
        </div>
      )}

      {/* FORM */}
      <div style={s.card}>
        <div style={s.row}>
          <div>
            <div style={s.label}>Your Email</div>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@yourdomain.com" style={s.input} data-testid="ht-email-input" />
          </div>
          <div>
            <div style={s.label}>Your Phone (E.164)</div>
            <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
              placeholder="+14155552671" style={s.input} data-testid="ht-phone-input" />
          </div>
        </div>

        <div style={s.row}>
          <div>
            <div style={s.label}>Industry</div>
            <input type="text" value={industry} onChange={(e) => setIndustry(e.target.value)} style={s.input} data-testid="ht-industry-input" />
          </div>
          <div>
            <div style={s.label}>Province</div>
            <input type="text" value={province} onChange={(e) => setProvince(e.target.value)} style={s.input} data-testid="ht-province-input" />
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <div style={s.label}>Channels</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            <div onClick={() => setSendEmail(!sendEmail)} style={s.channel(sendEmail)} data-testid="ht-channel-email">
              <Mail size={13} /> Email (Resend)
            </div>
            <div onClick={() => setSendSms(!sendSms)} style={s.channel(sendSms)} data-testid="ht-channel-sms">
              <Phone size={13} /> SMS (Twilio)
            </div>
            <div onClick={() => setSendWa(!sendWa)} style={s.channel(sendWa)} data-testid="ht-channel-whatsapp">
              <MessageCircle size={13} /> WhatsApp (WHAPI)
            </div>
          </div>
        </div>

        <div style={{ ...s.row, gridTemplateColumns: "100px 1fr" }}>
          <div>
            <div style={s.label}>Count</div>
            <select value={count} onChange={(e) => setCount(e.target.value)} style={s.input} data-testid="ht-count">
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={3}>3</option>
            </select>
          </div>
          <div>
            <div style={s.label}>Note</div>
            <div style={{ fontSize: 10.5, color: "#888", lineHeight: 1.5, padding: "8px 0" }}>
              Zero real businesses contacted · Synthetic lead data · Your inbox + phone only
            </div>
          </div>
        </div>

        <button onClick={fire} disabled={busy} data-testid="ht-fire-btn" style={{ ...s.fireBtn, opacity: busy ? 0.5 : 1 }}>
          <Zap size={14} style={{ display: "inline", marginRight: 8 }} />
          {busy ? "Firing…" : "Fire Test Run"}
        </button>
      </div>

      {/* RESULT */}
      {result && (
        <div style={{ ...s.card, background: result.ok ? "rgba(10,28,15,0.6)" : "rgba(28,10,10,0.6)", borderColor: result.ok ? "#2a5a2a" : "#7a2020" }} data-testid="ht-result">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            {result.ok
              ? <CheckCircle2 size={18} style={{ color: "#7EC8A0" }} />
              : <XCircle size={18} style={{ color: "#EF4444" }} />}
            <div style={{ fontFamily: "'Cinzel', serif", fontSize: 14, color: "#fff" }}>
              {result.ok ? "All channels fired successfully" : "Some channels had issues"}
            </div>
            <div style={{ fontSize: 10, color: "#888", marginLeft: "auto" }}>Test ID: <code>{result.hunt_id}</code></div>
          </div>

          <div style={{ marginBottom: 12, padding: "8px 12px", background: "rgba(0,0,0,0.3)", borderRadius: 4 }}>
            <div style={{ fontSize: 9, letterSpacing: "2px", color: "#888", marginBottom: 4, textTransform: "uppercase" }}>Sample Lead</div>
            <div style={{ fontSize: 12, color: "#e4ddd3" }}>
              <strong>{result.sample?.business_name}</strong> · {result.sample?.industry} · {result.sample?.city} · Score {result.sample?.score}/100
            </div>
          </div>

          {(result.trace?.steps || []).map((step, i) => (
            <div key={i} style={s.step(step.ok)}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {step.ok
                  ? <CheckCircle2 size={12} style={{ color: "#7EC8A0" }} />
                  : <XCircle size={12} style={{ color: "#EF4444" }} />}
                <strong style={{ fontSize: 11, color: "#fff", textTransform: "uppercase", letterSpacing: "1px" }}>{step.step}</strong>
                {step.provider && <span style={{ fontSize: 9, color: "#888", background: "#1a1a1e", padding: "1px 6px", borderRadius: 3 }}>{step.provider}</span>}
                {step.skipped && <span style={{ fontSize: 9, color: "#888" }}>(skipped)</span>}
              </div>
              {(step.error || step.resend_id || step.message_id || step.sid) && (
                <div style={{ fontSize: 10, color: "#888", marginTop: 4, fontFamily: "monospace" }}>
                  {step.error && <div style={{ color: "#ef9999" }}>error: {step.error}</div>}
                  {step.resend_id && <div>resend_id: {step.resend_id}</div>}
                  {step.message_id && <div>message_id: {step.message_id}</div>}
                  {step.sid && <div>sid: {step.sid}</div>}
                  {step.to && <div>to: {step.to}</div>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* HISTORY */}
      <div style={s.card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <div style={{ fontSize: 10, color: G, letterSpacing: ".15em", textTransform: "uppercase", fontWeight: 700 }}>
            <History size={11} style={{ display: "inline", marginRight: 4 }} /> Recent Test Runs
          </div>
          <button onClick={loadHistory} style={{ background: "transparent", border: `1px solid ${G}40`, color: G, padding: "4px 10px", borderRadius: 3, fontSize: 10, cursor: "pointer" }} data-testid="ht-refresh">
            <RefreshCw size={10} style={{ display: "inline", marginRight: 4 }} /> Refresh
          </button>
        </div>
        {history.map((h) => (
          <div key={h.test_id} style={{ padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: 11, color: "#bbb" }} data-testid={`ht-history-${h.test_id}`}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div>
                {h.ok ? <span style={{ color: "#7EC8A0" }}>✓</span> : <span style={{ color: "#EF4444" }}>✗</span>}{" "}
                <strong>{h.sample_lead_name}</strong> · {h.industry}/{h.province}
                <span style={{ marginLeft: 8, fontSize: 9, color: "#888", letterSpacing: 1 }}>[{(h.channels || []).join(", ")}]</span>
              </div>
              <div style={{ fontSize: 10, color: "#666" }}>{new Date(h.ran_at).toLocaleString("en-CA")}</div>
            </div>
          </div>
        ))}
        {history.length === 0 && <div style={{ fontSize: 11, color: "#555", textAlign: "center", padding: 14 }}>No test runs yet.</div>}
      </div>
    </div>
  );
}
