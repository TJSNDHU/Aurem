/**
 * /enterprise/admin — Overview (linchpin page)
 * Pulls live data from /api/enterprise/audit + summary endpoints.
 */
import React, { useEffect, useState } from "react";
import { Users, Activity, AlertTriangle, CreditCard } from "lucide-react";
import EnterpriseAdminShell, { ENT_API, adminHeaders } from "./EnterpriseAdminShell";

export default function EnterpriseAdminOverview() {
  const [audit, setAudit] = useState({ rows: [], total: 0 });
  const [stripe, setStripe] = useState({ ora: { calls: 0, usd: 0 } });

  useEffect(() => {
    let cancelled = false;
    fetch(`${ENT_API}/api/enterprise/audit?limit=15`, { headers: adminHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(j => { if (j && !cancelled) setAudit(j); })
      .catch(() => {});
    fetch(`${ENT_API}/api/admin/ora/specialist-cost-breakdown`, { headers: adminHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(j => { if (j && !cancelled) setStripe(j); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  return (
    <EnterpriseAdminShell
      eyebrow="ENTERPRISE / ADMIN"
      title="Tenant overview"
      sub="Live counters from your audit log, billing engine and security guards."
    >
      <div className="av2-grid-4">
        <Tile icon={Users} label="Audit events (24h)"
              value={audit.total || 0}
              testid="overview-audit-count" />
        <Tile icon={Activity} label="ORA calls (7d)"
              value={(stripe?.ora?.calls || 0) + (stripe?.emergent?.calls || 0)}
              testid="overview-ora-count" />
        <Tile icon={AlertTriangle} label="Security blocks (7d)"
              value={(audit.rows || []).filter(r => r.result === "blocked").length}
              testid="overview-blocks" />
        <Tile icon={CreditCard} label="Spend (7d)"
              value={`$${(stripe?.total_spent_usd || 0).toFixed(2)}`}
              testid="overview-spend" />
      </div>

      <div className="av2-card" data-testid="overview-audit-feed">
        <h3 style={{ fontSize: 14, fontWeight: 600,
                      color: "var(--dash-text)", marginBottom: 12 }}>
          Recent audit events
        </h3>
        {(!audit.rows || audit.rows.length === 0) && (
          <p style={{ fontSize: 13, color: "var(--dash-text-muted)" }}>
            No events yet.
          </p>
        )}
        <ul style={{ listStyle: "none", padding: 0, margin: 0,
                     fontFamily: "'JetBrains Mono', monospace",
                     fontSize: 12 }}>
          {(audit.rows || []).slice(0, 15).map((r, i) => (
            <li key={r.event_id || i}
                data-testid="audit-row"
                style={{ display: "grid",
                          gridTemplateColumns: "120px 120px 1fr 80px",
                          gap: 12, padding: "6px 0",
                          borderBottom: i < audit.rows.length - 1
                            ? "1px solid var(--dash-divider)" : "none",
                          alignItems: "center" }}>
              <span style={{ color: "var(--dash-text-muted)" }}>
                {(r.timestamp || "").slice(11, 19)}
              </span>
              <span style={{ color: "var(--dash-gold-bright)" }}>
                {(r.action || "").slice(0, 18)}
              </span>
              <span style={{ color: "var(--dash-text)" }}>
                {(r.resource || "—").slice(0, 60)}
              </span>
              <span style={{
                color: r.result === "ok"      ? "var(--dash-green)"
                     : r.result === "blocked" ? "var(--dash-red)"
                     :                          "var(--dash-amber)",
                fontWeight: 500,
              }}>{r.result}</span>
            </li>
          ))}
        </ul>
      </div>
    </EnterpriseAdminShell>
  );
}

function Tile({ icon: Icon, label, value, testid }) {
  return (
    <div data-testid={testid} className="av2-card">
      <div style={{ display: "flex", alignItems: "center", gap: 6,
                     fontFamily: "'JetBrains Mono', monospace",
                     fontSize: 10, letterSpacing: "0.18em",
                     textTransform: "uppercase",
                     color: "var(--dash-text-muted)", marginBottom: 10 }}>
        <Icon size={11} /> {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 600,
                     color: "var(--dash-text)" }}>{value}</div>
    </div>
  );
}
