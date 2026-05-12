/**
 * OraSettings — iter 322es
 * Founder-facing platform settings for ORA CTO.
 * 5 sections: GitHub · Permissions · Council · Notifications · Audit & Logs
 * Route: /admin/ora-settings
 */
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Settings as SettingsIcon, GitBranch, Shield, Users, Bell, FileText,
  Save, RefreshCw, Loader2, AlertTriangle, CheckCircle, Trash2,
  Download, RotateCcw, Lock,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const GREEN = "#67E8A0";
const RED = "#FF7676";

const GLASS = {
  background: "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))",
  backdropFilter: "blur(22px) saturate(160%)",
  WebkitBackdropFilter: "blur(22px) saturate(160%)",
  border: `1px solid ${BORDER}`,
  borderRadius: 18,
  boxShadow: "0 18px 44px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)",
};

function authHeaders() {
  const token =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") ||
    "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function OraSettings() {
  const navigate = useNavigate();
  const [section, setSection] = useState("github");
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/admin/ora-settings/`, { headers: authHeaders() });
      const j = await r.json();
      if (j?.ok) {
        setSettings(j.settings);
        setDraft({});
      }
    } catch (e) {
      setToast({ kind: "err", text: String(e) });
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const patch = async (sec) => {
    setBusy(true);
    setToast(null);
    try {
      const data = draft[sec] || settings[sec];
      const r = await fetch(`${API}/api/admin/ora-settings/${sec}`, {
        method: "PATCH",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ data }),
      });
      const j = await r.json();
      if (j?.ok) {
        setSettings(j.settings);
        setDraft((d) => ({ ...d, [sec]: undefined }));
        setToast({ kind: "ok", text: "✓ Saved" });
      } else {
        setToast({ kind: "err", text: j?.detail || "save failed" });
      }
    } catch (e) {
      setToast({ kind: "err", text: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const updDraft = (sec, key, val) =>
    setDraft((d) => ({ ...d, [sec]: { ...(d[sec] || settings[sec] || {}), [key]: val } }));

  const ghTest = async () => {
    setBusy(true);
    setToast(null);
    try {
      const r = await fetch(`${API}/api/admin/ora-settings/github-test`,
                             { method: "POST", headers: authHeaders() });
      const j = await r.json();
      if (j?.ok) setToast({ kind: "ok", text: `✓ ${j.login || "ok"}` });
      else setToast({ kind: "err", text: j?.error || j?.detail || "github failed" });
    } catch (e) {
      setToast({ kind: "err", text: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const exportCsv = async () => {
    try {
      const r = await fetch(`${API}/api/admin/ora-settings/export-audit-csv?limit=5000`, {
        method: "POST", headers: authHeaders(),
      });
      const blob = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "ora-audit.csv";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setToast({ kind: "err", text: String(e) });
    }
  };

  if (!settings) {
    return (
      <div style={{ minHeight: "100vh", background: "#0A0A12", color: TEXT_DIM,
                    display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Loader2 size={32} color={GOLD} className="spin" />
        <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <div data-testid="ora-settings" style={{ minHeight: "100vh", background: "#0A0A12", color: TEXT, padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 22 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <SettingsIcon size={26} color={GOLD} />
            <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700 }}>ORA Settings</h1>
          </div>
          <p style={{ color: TEXT_DIM, fontSize: 13, marginTop: 6 }}>
            Founder-only configuration · saved to <code>platform_settings/ora_cto</code>
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button data-testid="reload-btn" onClick={load} style={btn(false)}>
            <RefreshCw size={14} /> Reload
          </button>
          <button data-testid="back-btn" onClick={() => navigate("/admin/ora-chat")} style={btn(false)}>← Back</button>
        </div>
      </div>

      {/* Section tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 18 }}>
        {[
          ["github",        "GitHub",        GitBranch],
          ["permissions",   "Permissions",   Lock],
          ["council",       "Council",       Users],
          ["notifications", "Notifications", Bell],
          ["audit",         "Audit & Logs",  FileText],
        ].map(([k, label, Icon]) => (
          <button data-testid={`tab-${k}`} key={k} onClick={() => setSection(k)}
                  style={tabBtn(section === k)}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {toast && (
        <div data-testid="toast" style={{
          ...GLASS, padding: 10, marginBottom: 14,
          color: toast.kind === "ok" ? GREEN : RED,
          borderColor: toast.kind === "ok" ? GREEN : RED,
        }}>
          {toast.text}
        </div>
      )}

      {/* GitHub */}
      {section === "github" && (
        <Card title="GitHub Integration" icon={GitBranch}>
          <Row label="Personal Access Token">
            <input data-testid="gh-pat" type="password"
                    placeholder={settings.github.pat_masked || "ghp_..."}
                    onChange={(e) => updDraft("github", "pat", e.target.value)}
                    style={inp} />
            <span style={{ color: TEXT_DIM, fontSize: 11, marginLeft: 8 }}>
              {settings.github.pat_masked ? `current: ${settings.github.pat_masked}` : "not set"}
            </span>
          </Row>
          <Row label="Repository (owner/repo)">
            <input data-testid="gh-repo"
                    defaultValue={settings.github.repo || ""}
                    onChange={(e) => updDraft("github", "repo", e.target.value)}
                    placeholder="manavarya09/aurem" style={inp} />
          </Row>
          <Row label="Default branch">
            <input data-testid="gh-branch"
                    defaultValue={settings.github.default_branch || "main"}
                    onChange={(e) => updDraft("github", "default_branch", e.target.value)}
                    style={inp} />
          </Row>
          <Row label="Branch protection">
            <ToggleBtn checked={!!(draft.github?.branch_protection ?? settings.github.branch_protection)}
                       onChange={(v) => updDraft("github", "branch_protection", v)} />
          </Row>
          <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
            <button data-testid="gh-test" onClick={ghTest} disabled={busy} style={btn(false, busy)}>
              {busy ? <Loader2 size={14} className="spin" /> : <CheckCircle size={14} />} Test connection
            </button>
            <button data-testid="gh-save" onClick={() => patch("github")} disabled={busy} style={btn(true, busy)}>
              <Save size={14} /> Save GitHub
            </button>
          </div>
        </Card>
      )}

      {/* Permissions */}
      {section === "permissions" && (
        <Card title="ORA CTO Permissions" icon={Lock}>
          <p style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 12 }}>
            Toggle individual ORA tools. Disabled tools refuse invocation at the gate.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
            {Object.keys(settings.permissions.tools_enabled || {}).sort().map((tname) => {
              const current = draft.permissions?.tools_enabled
                ? draft.permissions.tools_enabled[tname]
                : settings.permissions.tools_enabled[tname];
              return (
                <label data-testid={`tool-${tname}`} key={tname}
                       style={{ display: "flex", justifyContent: "space-between",
                                 padding: "8px 10px", border: `1px solid ${BORDER}`,
                                 borderRadius: 8, fontSize: 12.5 }}>
                  <code style={{ color: TEXT }}>{tname}</code>
                  <ToggleBtn checked={!!current} onChange={(v) => {
                    const next = {
                      ...(draft.permissions?.tools_enabled || settings.permissions.tools_enabled),
                      [tname]: v,
                    };
                    updDraft("permissions", "tools_enabled", next);
                  }} />
                </label>
              );
            })}
          </div>
          <Row label="Shell whitelist (one per line)">
            <textarea data-testid="shell-whitelist" rows={4}
                       defaultValue={(settings.permissions.shell_whitelist || []).join("\n")}
                       onChange={(e) => updDraft("permissions", "shell_whitelist",
                                                  e.target.value.split("\n").map((s) => s.trim()).filter(Boolean))}
                       style={{ ...inp, minHeight: 80, fontFamily: "ui-monospace,monospace" }} />
          </Row>
          <button data-testid="perm-save" onClick={() => patch("permissions")} disabled={busy} style={btn(true, busy)}>
            <Save size={14} /> Save Permissions
          </button>
        </Card>
      )}

      {/* Council */}
      {section === "council" && (
        <Card title="Council Settings" icon={Users}>
          <p style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 12 }}>
            Which peer roles ORA consults. Hard gate = REJECT edit on any dissent.
          </p>
          <Row label="Peer roles">
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {["security", "backend", "qa", "devops", "design", "finance", "marketing", "pricing"].map((role) => {
                const list = draft.council?.peer_roles ?? settings.council.peer_roles;
                const has = list.includes(role);
                return (
                  <button data-testid={`role-${role}`} key={role}
                          onClick={() => {
                            const cur = list || [];
                            const next = has ? cur.filter((r) => r !== role) : [...cur, role];
                            updDraft("council", "peer_roles", next);
                          }}
                          style={pillBtn(has)}>
                    {role}
                  </button>
                );
              })}
            </div>
          </Row>
          <Row label="Hard gate (block edit on dissent)">
            <ToggleBtn checked={!!(draft.council?.hard_gate ?? settings.council.hard_gate)}
                       onChange={(v) => updDraft("council", "hard_gate", v)} />
          </Row>
          <Row label="Vote threshold to BLOCK (# of dissenters)">
            <select data-testid="vote-threshold"
                     defaultValue={settings.council.vote_threshold}
                     onChange={(e) => updDraft("council", "vote_threshold", parseInt(e.target.value))}
                     style={inp}>
              <option value={1}>1 (any peer can block)</option>
              <option value={2}>2 (majority)</option>
              <option value={99}>all (unanimous block)</option>
            </select>
          </Row>
          <button data-testid="council-save" onClick={() => patch("council")} disabled={busy} style={btn(true, busy)}>
            <Save size={14} /> Save Council
          </button>
        </Card>
      )}

      {/* Notifications */}
      {section === "notifications" && (
        <Card title="Notifications" icon={Bell}>
          <Row label="WhatsApp critical alerts">
            <ToggleBtn checked={!!(draft.notifications?.whatsapp_critical ?? settings.notifications.whatsapp_critical)}
                       onChange={(v) => updDraft("notifications", "whatsapp_critical", v)} />
          </Row>
          <Row label="Email digest time (HH:MM Toronto)">
            <input data-testid="digest-time" type="time"
                    defaultValue={settings.notifications.email_digest_time}
                    onChange={(e) => updDraft("notifications", "email_digest_time", e.target.value)}
                    style={inp} />
          </Row>
          <Row label="Digest email">
            <input data-testid="digest-email" type="email"
                    defaultValue={settings.notifications.digest_email}
                    onChange={(e) => updDraft("notifications", "digest_email", e.target.value)}
                    placeholder="teji.ss1986@gmail.com" style={inp} />
          </Row>
          <button data-testid="notif-save" onClick={() => patch("notifications")} disabled={busy} style={btn(true, busy)}>
            <Save size={14} /> Save Notifications
          </button>
        </Card>
      )}

      {/* Audit & Logs */}
      {section === "audit" && (
        <Card title="Audit & Logs" icon={FileText}>
          <Row label="Retention (days)">
            <input data-testid="audit-retention" type="number" min={7} max={3650}
                    defaultValue={settings.audit.retention_days}
                    onChange={(e) => updDraft("audit", "retention_days", parseInt(e.target.value))}
                    style={inp} />
          </Row>
          <div style={{ display: "flex", gap: 10, marginTop: 10, flexWrap: "wrap" }}>
            <button data-testid="audit-save" onClick={() => patch("audit")} disabled={busy} style={btn(true, busy)}>
              <Save size={14} /> Save
            </button>
            <button data-testid="export-csv" onClick={exportCsv} style={btn(false)}>
              <Download size={14} /> Export CSV (5000 rows)
            </button>
            <button data-testid="view-cockpit" onClick={() => navigate("/admin/ora-cto")} style={btn(false)}>
              <FileText size={14} /> View Cockpit
            </button>
            <button data-testid="view-rollbacks" onClick={() => navigate("/admin/ora-chat")} style={btn(false)}>
              <RotateCcw size={14} /> Rollbacks (in CTO Mode)
            </button>
          </div>
        </Card>
      )}

      <div style={{ marginTop: 14, color: TEXT_DIM, fontSize: 11 }}>
        Last saved: {settings._updated_at?.slice(0, 19) || "—"} by {settings._updated_by || "—"}
      </div>
      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function Card({ title, icon: Icon, children }) {
  return (
    <div style={{ ...GLASS, padding: 22 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <Icon size={18} color={GOLD} />
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Row({ label, children }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 18, marginBottom: 14 }}>
      <div style={{ width: 280, color: TEXT_DIM, fontSize: 12, paddingTop: 6 }}>{label}</div>
      <div style={{ flex: 1 }}>{children}</div>
    </div>
  );
}

function ToggleBtn({ checked, onChange }) {
  return (
    <button data-testid="toggle-btn" onClick={() => onChange(!checked)}
             style={{
               background: checked ? GREEN : "rgba(255,255,255,0.06)",
               color: checked ? "#0A0A12" : TEXT,
               border: `1px solid ${checked ? GREEN : BORDER}`,
               borderRadius: 8, padding: "5px 12px", fontSize: 12,
               fontWeight: 700, cursor: "pointer", minWidth: 72,
             }}>
      {checked ? "ON" : "OFF"}
    </button>
  );
}

const inp = {
  flex: 1, background: "rgba(0,0,0,0.4)", color: TEXT,
  border: `1px solid ${BORDER}`, borderRadius: 8,
  padding: "8px 12px", fontSize: 13, minWidth: 250,
};
function btn(primary, disabled) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: primary ? GOLD : "rgba(255,255,255,0.06)",
    color: primary ? "#0A0A12" : TEXT,
    border: `1px solid ${primary ? GOLD : BORDER}`,
    borderRadius: 8, padding: "8px 14px", fontSize: 12.5,
    fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
  };
}
function tabBtn(active) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: active ? GOLD : "rgba(255,255,255,0.04)",
    color: active ? "#0A0A12" : TEXT,
    border: `1px solid ${active ? GOLD : BORDER}`,
    borderRadius: 10, padding: "8px 14px", fontSize: 12.5,
    fontWeight: 700, cursor: "pointer", textTransform: "uppercase",
  };
}
function pillBtn(active) {
  return {
    padding: "6px 12px",
    background: active ? "rgba(212,175,55,0.16)" : "rgba(255,255,255,0.04)",
    border: `1px solid ${active ? GOLD : BORDER}`,
    borderRadius: 999, fontSize: 12, fontWeight: 600,
    color: active ? GOLD : TEXT, cursor: "pointer",
  };
}
