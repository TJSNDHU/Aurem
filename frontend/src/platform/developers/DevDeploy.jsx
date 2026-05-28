/**
 * DevDeploy.jsx — iter D-44
 *
 * /developers/deploy — deployment overview + history. Reads
 * /api/developers/deploy/config and /api/developers/deploy/history.
 * "Redeploy" button POSTs to /api/developers/deploy/run with mode=deploy.
 */
import React, { useEffect, useState } from "react";
import { Rocket, ExternalLink, RefreshCw, CheckCircle2, Circle,
         Loader2, AlertCircle } from "lucide-react";
import DeveloperShell, { devAuthHeaders } from "./DeveloperShell";
import { PageHeader, SectionTitle } from "./DevDashboard";

const API = process.env.REACT_APP_BACKEND_URL || "";

const STEPS = [
  "Environment Ready",
  "Building",
  "Migrate DB",
  "Export Secrets",
  "Deploy",
  "Health Check",
];

function DeployStep({ label, done, current }) {
  const Icon = done ? CheckCircle2 : current ? Loader2 : Circle;
  return (
    <div data-testid={`deploy-step-${label.toLowerCase().replace(/\s+/g, '-')}`}
         style={{ display: "flex", alignItems: "center", gap: 10,
                  padding: "8px 0",
                  color: done ? "var(--dash-green, #4ade80)"
                              : current ? "#FF8C35"
                                        : "var(--dash-text-faint)",
                  fontSize: 12 }}>
      <Icon size={14}
            className={current ? "aurem-spin" : ""}
            style={{ flexShrink: 0 }} />
      {label}
    </div>
  );
}

export default function DevDeploy() {
  const [cfg, setCfg]       = useState(null);
  const [history, setHist]  = useState([]);
  const [busy, setBusy]     = useState(false);
  const [err, setErr]       = useState(null);
  const [activeRun, setActive] = useState(null); // currently running run_id
  const [stepIdx, setStepIdx] = useState(-1);

  async function loadAll() {
    setErr(null);
    try {
      const [c, h] = await Promise.all([
        fetch(`${API}/api/developers/deploy/config`, { headers: devAuthHeaders() })
          .then(r => r.ok ? r.json() : null),
        fetch(`${API}/api/developers/deploy/history`, { headers: devAuthHeaders() })
          .then(r => r.ok ? r.json() : { runs: [] }),
      ]);
      setCfg(c);
      setHist(h.runs || []);
    } catch (e) { setErr(String(e.message || e)); }
  }
  useEffect(() => { loadAll(); }, []);

  async function redeploy() {
    setBusy(true); setErr(null); setStepIdx(0);
    try {
      const r = await fetch(`${API}/api/developers/deploy/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ mode: "deploy" }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "deploy_failed");
      setActive(j.run_id || null);
      // Naive progress animation while the run finishes server-side.
      let i = 0;
      const t = setInterval(() => {
        i++; setStepIdx(i);
        if (i >= STEPS.length - 1) clearInterval(t);
      }, 1200);
    } catch (e) {
      setErr(String(e.message || e));
      setStepIdx(-1);
    } finally {
      setBusy(false);
      setTimeout(loadAll, 800);
    }
  }

  const lastSuccess = history.find(r => r.status === "ok"
                                     && (r.mode === "deploy" || r.mode === "real_deploy"));

  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="DEPLOY" title="Deployment overview"
                  sub="Trigger a redeploy and see recent run history." />

      {/* Live preview card */}
      <div className="av2-card" data-testid="deploy-app-card"
           style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ width: 64, height: 64, borderRadius: 8,
                       background: "linear-gradient(135deg, #FF6B00, #E8C86A)",
                       display: "flex", alignItems: "center",
                       justifyContent: "center", flexShrink: 0 }}>
          <Rocket size={28} style={{ color: "#fff" }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#F0EDE8" }}>
            AUREM Platform
          </div>
          <div style={{ fontSize: 12, color: "var(--dash-text-muted)",
                         marginTop: 2 }}>
            {cfg?.configured ? `Server: ${cfg.host}` : "No deploy target configured yet."}
          </div>
          <a href="https://aurem.live" target="_blank" rel="noreferrer"
             data-testid="deploy-visit-link"
             style={{ display: "inline-flex", alignItems: "center", gap: 5,
                      fontSize: 12, color: "#FF8C35",
                      textDecoration: "none", marginTop: 6 }}>
            aurem.live <ExternalLink size={11} />
          </a>
        </div>
        <button data-testid="deploy-redeploy-btn"
                onClick={redeploy}
                disabled={busy || !cfg?.configured}
                style={{ padding: "10px 18px",
                         background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                         color: "#fff", border: "none", borderRadius: 6,
                         fontSize: 13, fontWeight: 500,
                         cursor: (busy || !cfg?.configured) ? "not-allowed" : "pointer",
                         opacity: (busy || !cfg?.configured) ? 0.5 : 1,
                         display: "inline-flex", alignItems: "center", gap: 6 }}>
          <RefreshCw size={13}
                     className={busy ? "aurem-spin" : ""} />
          {busy ? "Deploying…" : "Redeploy"}
        </button>
      </div>

      {/* Progress steps */}
      {(busy || stepIdx >= 0) && (
        <div className="av2-card" data-testid="deploy-progress">
          <SectionTitle title="Deploy progress" />
          {STEPS.map((s, i) => (
            <DeployStep key={s} label={s}
                         done={stepIdx > i}
                         current={stepIdx === i} />
          ))}
        </div>
      )}

      {err && (
        <div data-testid="deploy-error" className="av2-card"
             style={{ borderColor: "rgba(255,96,96,0.30)",
                       background: "rgba(255,96,96,0.05)",
                       color: "#FF6060", fontSize: 13,
                       display: "flex", gap: 8, alignItems: "center" }}>
          <AlertCircle size={14} /> {err}
        </div>
      )}

      {/* Deploy history */}
      <div className="av2-card" data-testid="deploy-history">
        <SectionTitle title="Recent deploys" />
        {history.length === 0 ? (
          <p style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>
            No deploys yet. Configure SSH on Connect, then click Redeploy.
          </p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {history.map((r, i) => (
              <li key={r.run_id || i}
                   data-testid={`deploy-history-row-${i}`}
                   style={{ display: "grid",
                            gridTemplateColumns: "auto 1fr auto auto",
                            gap: 14, alignItems: "center",
                            padding: "10px 0",
                            borderTop: i > 0
                              ? "1px solid var(--dash-divider)" : "none",
                            fontSize: 12,
                            fontFamily: "'JetBrains Mono', monospace",
                            color: "var(--dash-text)" }}>
                <span style={{ width: 8, height: 8, borderRadius: 999,
                                background: r.status === "ok"
                                  ? "var(--dash-green, #4ade80)"
                                  : r.status === "failed"
                                    ? "#FF6060"
                                    : "#FF8C35" }} />
                <span>#{(r.run_id || "").slice(-8) || "—"}</span>
                <span style={{ color: "var(--dash-text-muted)" }}>
                  {r.mode || "deploy"}
                </span>
                <span style={{ color: "var(--dash-text-muted)" }}>
                  {r.started_at
                    ? new Date(r.started_at).toLocaleString()
                    : "—"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <style>{`
        @keyframes aurem-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .aurem-spin { animation: aurem-spin 900ms linear infinite; }
      `}</style>
    </DeveloperShell>
  );
}
