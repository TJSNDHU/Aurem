/**
 * SecurityKeysBlock.jsx — iter D-46
 *
 * One-click "Generate security keys" card that lives on
 * /developers/settings. Mints JWT_SECRET + AUREM_ENCRYPTION_KEY +
 * CORS_ORIGINS, stores AES-256 encrypted, applies live to env, and
 * shows the plaintext exactly once with a copy button per row.
 */
import React, { useEffect, useState } from "react";
import { ShieldAlert, Sparkles, Copy, Check, Eye, EyeOff,
         AlertTriangle, CheckCircle2 } from "lucide-react";
import { devAuthHeaders } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";

const KEY_LABELS = {
  JWT_SECRET:            "JWT_SECRET",
  AUREM_ENCRYPTION_KEY:  "AUREM_ENCRYPTION_KEY",
  CORS_ORIGINS:          "CORS_ORIGINS",
};

function SecretCopyRow({ name, value }) {
  const [shown, setShown]   = useState(false);
  const [copied, setCopied] = useState(false);
  function doCopy() {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  }
  return (
    <div data-testid={`security-key-row-${name}`}
         style={{ display: "grid",
                  gridTemplateColumns: "180px 1fr auto auto",
                  gap: 10, alignItems: "center", padding: "10px 0",
                  borderTop: "1px solid var(--dash-divider)" }}>
      <span style={{ fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 11, color: "#FFB070",
                      letterSpacing: 0.3 }}>
        {KEY_LABELS[name] || name}
      </span>
      <span data-testid={`security-key-value-${name}`}
            style={{ fontFamily: "'JetBrains Mono', monospace",
                     fontSize: 11, color: "#F0EDE8",
                     wordBreak: "break-all" }}>
        {shown ? value : "•".repeat(Math.min(48, value.length))}
      </span>
      <button onClick={() => setShown(s => !s)}
              data-testid={`security-key-toggle-${name}`}
              title={shown ? "Hide" : "Show"}
              style={{ background: "transparent", border: "none",
                       color: "var(--dash-text-muted)",
                       cursor: "pointer", padding: 4 }}>
        {shown ? <EyeOff size={13} /> : <Eye size={13} />}
      </button>
      <button onClick={doCopy}
              data-testid={`security-key-copy-${name}`}
              title="Copy to clipboard"
              style={{ background: copied
                         ? "rgba(74,222,128,0.10)"
                         : "rgba(255,107,0,0.10)",
                       border: copied
                         ? "1px solid rgba(74,222,128,0.40)"
                         : "1px solid rgba(255,107,0,0.40)",
                       color: copied ? "var(--dash-green, #4ade80)"
                                     : "#FF8C35",
                       padding: "4px 9px", borderRadius: 4,
                       fontSize: 11, cursor: "pointer",
                       display: "inline-flex", alignItems: "center", gap: 4 }}>
        {copied ? <><Check size={11} /> Copied</> : <><Copy size={11} /> Copy</>}
      </button>
    </div>
  );
}


export default function SecurityKeysBlock() {
  const [status, setStatus] = useState(null);  // {configured, current}
  const [plain,  setPlain]  = useState(null);  // {JWT_SECRET, ...} (shown once)
  const [busy,   setBusy]   = useState(false);
  const [err,    setErr]    = useState(null);
  const [ackSaved, setAck]  = useState(false);

  async function loadStatus() {
    try {
      const r = await fetch(`${API}/api/developers/security/status`,
                              { headers: devAuthHeaders() });
      if (!r.ok) return;
      const j = await r.json();
      setStatus(j);
    } catch { /* ignore */ }
  }
  useEffect(() => { loadStatus(); }, []);

  async function generate() {
    if (status?.configured) {
      if (!window.confirm(
        "Rotate security keys?\n\n" +
        "The current keys will be marked 'rotated' and a fresh set " +
        "will become active. You'll need to save the new plaintext " +
        "now — AUREM will never reveal them again.")) return;
    }
    setBusy(true); setErr(null); setPlain(null); setAck(false);
    try {
      const r = await fetch(`${API}/api/developers/security/generate-keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ rotate: true }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "generate_failed");
      setPlain(j.plaintext_once || null);
      setStatus({ configured: true, current: j.summary });
    } catch (e) { setErr(String(e.message || e)); }
    finally   { setBusy(false); }
  }

  return (
    <div data-testid="security-keys-block"
         style={{ marginBottom: 32 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10,
                     marginBottom: 6 }}>
        <ShieldAlert size={20} style={{ color: "var(--dash-orange)" }} />
        <h2 style={{ fontFamily: "'Cinzel', serif",
                      fontSize: 18, fontWeight: 700, margin: 0,
                      color: "var(--dash-gold-bright)" }}>
          Security keys
        </h2>
        {status?.current?.status === "active" && (
          <span data-testid="security-keys-status-active"
                style={{ marginLeft: 8, fontSize: 10,
                         padding: "3px 8px", borderRadius: 999,
                         background: "rgba(74,222,128,0.12)",
                         color: "var(--dash-green, #4ade80)",
                         letterSpacing: 0.5,
                         textTransform: "uppercase" }}>
            <CheckCircle2 size={10} style={{ verticalAlign: -1 }} /> Active
          </span>
        )}
        {!status?.configured && (
          <span data-testid="security-keys-status-none"
                style={{ marginLeft: 8, fontSize: 10,
                         padding: "3px 8px", borderRadius: 999,
                         background: "rgba(255,96,96,0.12)",
                         color: "#FF6060",
                         letterSpacing: 0.5,
                         textTransform: "uppercase" }}>
            <AlertTriangle size={10} style={{ verticalAlign: -1 }} /> Not configured
          </span>
        )}
      </div>
      <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                   marginBottom: 14, lineHeight: 1.6 }}>
        One click generates a fresh <code>JWT_SECRET</code>,&nbsp;
        <code>AUREM_ENCRYPTION_KEY</code>, and <code>CORS_ORIGINS</code>.
        Values are AES-256 encrypted at rest and applied to the live
        process immediately — no restart needed.
      </p>

      {/* Action button + current-status meta */}
      <div style={{ display: "flex", gap: 12, alignItems: "center",
                     flexWrap: "wrap", marginBottom: 14 }}>
        <button data-testid="security-generate-btn"
                onClick={generate} disabled={busy}
                style={{ padding: "10px 18px",
                         background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                         color: "#fff", border: "none", borderRadius: 6,
                         fontSize: 13, fontWeight: 500,
                         cursor: busy ? "not-allowed" : "pointer",
                         opacity: busy ? 0.5 : 1,
                         display: "inline-flex", alignItems: "center", gap: 8 }}>
          <Sparkles size={13} />
          {busy ? "Generating…"
                : (status?.configured ? "Rotate security keys"
                                       : "Generate security keys")}
        </button>
        {status?.current?.generated_at && (
          <span style={{ fontSize: 11, color: "var(--dash-text-muted)",
                          fontFamily: "'JetBrains Mono', monospace" }}>
            last generated&nbsp;
            {new Date(status.current.generated_at).toLocaleString()}
            {status.current.ip_address
              ? ` · from ${status.current.ip_address}`
              : ""}
          </span>
        )}
      </div>

      {err && (
        <div data-testid="security-error"
             style={{ padding: 12, marginBottom: 12,
                      background: "rgba(255,96,96,0.08)",
                      border: "1px solid rgba(255,96,96,0.30)",
                      borderRadius: 4, fontSize: 12, color: "#FF6060" }}>
          {err}
        </div>
      )}

      {/* Plaintext-once panel — only present right after a generation */}
      {plain && (
        <div data-testid="security-keys-once-panel"
             style={{ padding: "14px 16px", marginBottom: 8,
                      background: "rgba(255,140,53,0.06)",
                      border: "1px solid rgba(255,140,53,0.40)",
                      borderRadius: 6 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-start",
                         marginBottom: 8 }}>
            <AlertTriangle size={14} style={{ color: "#FF8C35",
                                                marginTop: 2,
                                                flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <strong style={{ color: "#FFB070", fontSize: 13 }}>
                Save these now — shown once
              </strong>
              <div style={{ fontSize: 11, color: "var(--dash-text-muted)",
                             marginTop: 3, lineHeight: 1.5 }}>
                Copy each value to your password manager. AUREM will
                never reveal the plaintext again — only the masked tail.
              </div>
            </div>
          </div>
          {Object.entries(plain).map(([k, v]) => (
            <SecretCopyRow key={k} name={k} value={v} />
          ))}
          <div style={{ marginTop: 12, display: "flex", gap: 8,
                         alignItems: "center" }}>
            <input data-testid="security-ack-checkbox"
                    type="checkbox" id="ack-saved"
                    checked={ackSaved}
                    onChange={e => setAck(e.target.checked)}
                    style={{ accentColor: "#FF8C35" }} />
            <label htmlFor="ack-saved"
                    style={{ fontSize: 12, color: "var(--dash-text)",
                             cursor: "pointer" }}>
              I have saved these keys to a password manager.
            </label>
            <button data-testid="security-ack-dismiss"
                    onClick={() => setPlain(null)}
                    disabled={!ackSaved}
                    style={{ marginLeft: "auto",
                             padding: "6px 14px",
                             background: ackSaved
                               ? "rgba(74,222,128,0.12)"
                               : "rgba(255,255,255,0.04)",
                             border: ackSaved
                               ? "1px solid rgba(74,222,128,0.40)"
                               : "1px solid var(--dash-border)",
                             color: ackSaved
                               ? "var(--dash-green, #4ade80)"
                               : "var(--dash-text-faint)",
                             borderRadius: 4, fontSize: 12,
                             cursor: ackSaved ? "pointer" : "not-allowed",
                             display: "inline-flex", alignItems: "center",
                             gap: 5 }}>
              <CheckCircle2 size={12} /> Done
            </button>
          </div>
        </div>
      )}

      {/* Current key tails when no plaintext panel is showing */}
      {!plain && status?.configured && (
        <div data-testid="security-keys-summary"
             style={{ padding: "10px 14px",
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid var(--dash-divider)",
                      borderRadius: 6 }}>
          {Object.entries(status.current?.keys || {}).map(([k, meta]) => (
            <div key={k}
                 style={{ display: "grid",
                          gridTemplateColumns: "200px 1fr auto",
                          gap: 10, padding: "6px 0",
                          fontSize: 11,
                          fontFamily: "'JetBrains Mono', monospace" }}>
              <span style={{ color: "#FFB070" }}>{KEY_LABELS[k] || k}</span>
              <span style={{ color: "var(--dash-text-muted)" }}>
                ••••{meta.key_tail || "????"}
              </span>
              <span style={{ fontSize: 9, color: meta.encrypted
                                  ? "var(--dash-green, #4ade80)"
                                  : "#FF8C35",
                              letterSpacing: 0.5,
                              textTransform: "uppercase" }}>
                {meta.encrypted ? "encrypted" : "plaintext"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
