/**
 * IntelligenceWidget — Customer-facing Intelligence Merge surface (iter 322eh)
 *
 * Wires the previously frontend-orphaned `bin_intelligence` stack into the
 * customer dashboard so customers can actually USE the data the pipeline
 * already collects. Four panels:
 *
 *   1. SUMMARY        — counts-only snapshot (pixel / email / phone / invoice)
 *   2. 3-BUCKET VIEW  — verified / likely / unknown contact rollup
 *   3. CSV UPLOAD     — invoice CSV importer (unlocks cross-source matching)
 *   4. MERGE NOW      — admin trigger
 *
 * All PII stays server-side. Responses are hashes + counts only.
 */
import React, { useEffect, useState, useCallback } from "react";
import {
  Database, Upload, RefreshCw, Loader2, CheckCircle, AlertCircle,
  Users, Eye, Mail, Phone, FileText, TrendingUp,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const COLORS = {
  bg: "rgba(8,8,15,0.78)",
  border: "rgba(212,175,55,0.18)",
  text: "#F0EADC",
  textD: "#A8A08F",
  gold: "#D4AF37",
  ok: "#22C55E",
  warn: "#F59E0B",
  err: "#EF4444",
  accent: "#FF6B00",
};

function getToken() {
  return (
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("token") ||
    ""
  );
}

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function IntelligenceWidget() {
  const [summary, setSummary] = useState(null);
  const [buckets, setBuckets] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(async () => {
    setErr("");
    try {
      const [rs, rb] = await Promise.all([
        fetch(`${API}/api/customer/intelligence/summary`, { headers: authHeaders() }),
        fetch(`${API}/api/customer/intelligence/buckets`, { headers: authHeaders() }),
      ]);
      if (rs.ok) {
        // Backend returns `{ok, bin_id, summary: {pixel, email, phone, invoice, top_actions}}`
        // — unwrap to the inner `summary` so the rest of the widget can use it flat.
        const js = await rs.json();
        setSummary(js?.summary || js);
      }
      else if (rs.status === 403) setErr("Sign in to view your intelligence data.");
      else setErr(`Summary failed: HTTP ${rs.status}`);
      if (rb.ok) setBuckets(await rb.json());
    } catch (e) {
      setErr(String(e?.message || e));
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const showToast = (kind, msg) => {
    setToast({ kind, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const onMergeNow = async () => {
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/customer/intelligence/merge-now`, {
        method: "POST", headers: authHeaders(),
      });
      if (r.ok) {
        const j = await r.json();
        showToast("ok", `Merge complete: ${j.profiles_written || 0} profiles written, ${j.single_source_skipped || 0} skipped`);
        await load();
      } else {
        showToast("err", `HTTP ${r.status}`);
      }
    } catch (e) {
      showToast("err", String(e?.message || e));
    }
    setBusy(false);
  };

  const onCsvUpload = async (file) => {
    if (!file) return;
    if (!file.name.endsWith(".csv")) {
      showToast("err", "Please upload a .csv file");
      return;
    }
    // CASL/PIPEDA compliance — backend rejects uploads without consent.
    // Surface that requirement to the user explicitly. This is also why
    // the backend collection `dnc_list` exists (322eb regression test
    // proved its writer works).
    const accepted = window.confirm(
      "CASL Compliance Notice:\n\n" +
      "By uploading this CSV, you confirm these contacts are your existing " +
      "clients (existing business relationship) and you have a legal basis " +
      "to message them under CASL/PIPEDA.\n\n" +
      "AUREM will log this consent. Continue?"
    );
    if (!accepted) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("casl_accepted", "true");
      const r = await fetch(`${API}/api/customer/intelligence/import-csv`, {
        method: "POST", headers: authHeaders(), body: form,
      });
      if (r.ok) {
        const j = await r.json();
        showToast(
          "ok",
          `CSV imported: ${j.rows_seen ?? 0} rows seen, ${j.accepted ?? 0} contacts added`
        );
        await load();
      } else {
        const t = await r.text();
        showToast("err", `Upload failed: ${t.slice(0, 160)}`);
      }
    } catch (e) {
      showToast("err", String(e?.message || e));
    }
    setBusy(false);
  };

  if (loading) {
    return (
      <div data-testid="intel-widget-loading" style={cardStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, color: COLORS.textD, fontSize: 13 }}>
          <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />
          Loading intelligence…
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </div>
    );
  }

  if (err) {
    return (
      <div data-testid="intel-widget-error" style={{ ...cardStyle, borderColor: "rgba(239,68,68,0.3)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, color: COLORS.err, fontSize: 13 }}>
          <AlertCircle size={14} /> {err}
        </div>
      </div>
    );
  }

  const pixel = summary?.pixel || {};
  const email = summary?.email || {};
  const phone = summary?.phone || {};
  const invoice = summary?.invoice || {};
  const topActions = summary?.top_actions || [];

  const bk = buckets?.counts || {};
  // Backend ships counts under `counts:{verified,likely,unclear}` (note: 'unclear' not 'unknown')
  const verified = bk.verified ?? 0;
  const likely = bk.likely ?? 0;
  const unknown = bk.unclear ?? bk.unknown ?? 0;
  const totalBucketed = verified + likely + unknown;

  return (
    <div data-testid="intelligence-widget" style={cardStyle}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Database size={16} style={{ color: COLORS.gold }} />
          <span style={{ fontSize: 12, color: COLORS.text, fontWeight: 600, letterSpacing: 1.5, textTransform: "uppercase" }}>
            Contact Intelligence
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <label data-testid="intel-csv-upload-label" style={{ ...btnGhost, cursor: busy ? "wait" : "pointer", opacity: busy ? 0.5 : 1 }}>
            <Upload size={12} /> Upload CSV
            <input
              data-testid="intel-csv-upload-input"
              type="file" accept=".csv"
              style={{ display: "none" }}
              disabled={busy}
              onChange={(e) => onCsvUpload(e.target.files?.[0])}
            />
          </label>
          <button data-testid="intel-merge-now-btn" onClick={onMergeNow} disabled={busy} style={btnGold}>
            {busy ? <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} /> : <RefreshCw size={12} />}
            Merge Now
          </button>
        </div>
      </div>

      {/* SUMMARY tiles */}
      <div data-testid="intel-summary-grid" style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px,1fr))",
        gap: 8, marginBottom: 14,
      }}>
        <Tile icon={Eye}      label="Visitors today" value={pixel.visitors_today ?? 0} testid="intel-tile-visitors" />
        <Tile icon={FileText} label="Forms filled"    value={pixel.forms_today ?? 0}   testid="intel-tile-forms" />
        <Tile icon={Users}    label="Identified"      value={pixel.matched_contacts ?? 0}
              highlight={pixel.matched_contacts > 0} testid="intel-tile-identified" />
        <Tile icon={Mail}     label="Emails"          value={email.identified ?? 0}    testid="intel-tile-emails" />
        <Tile icon={Phone}    label="Phones"          value={phone.verified ?? 0}      testid="intel-tile-phones" />
        <Tile icon={Database} label="Past clients"    value={invoice.past_clients ?? 0}
              highlight={invoice.past_clients > 0}    testid="intel-tile-invoices" />
      </div>

      {/* 3-BUCKET VIEW */}
      <div data-testid="intel-buckets" style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 10, color: COLORS.textD, textTransform: "uppercase",
                       letterSpacing: 1, marginBottom: 6 }}>
          Contact Buckets ({totalBucketed} total)
        </div>
        <div style={{ display: "flex", gap: 6, height: 10, borderRadius: 6, overflow: "hidden",
                       background: "rgba(255,255,255,0.04)" }}>
          {totalBucketed > 0 ? (
            <>
              <div style={{ width: `${(verified / totalBucketed) * 100}%`, background: COLORS.ok }}
                   title={`Verified: ${verified}`} />
              <div style={{ width: `${(likely / totalBucketed) * 100}%`, background: COLORS.warn }}
                   title={`Likely: ${likely}`} />
              <div style={{ width: `${(unknown / totalBucketed) * 100}%`, background: COLORS.textD }}
                   title={`Unknown: ${unknown}`} />
            </>
          ) : null}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 11 }}>
          <span style={{ color: COLORS.ok }}>●  Verified <b style={{ color: COLORS.text }}>{verified}</b></span>
          <span style={{ color: COLORS.warn }}>●  Likely <b style={{ color: COLORS.text }}>{likely}</b></span>
          <span style={{ color: COLORS.textD }}>●  Unknown <b style={{ color: COLORS.text }}>{unknown}</b></span>
        </div>
      </div>

      {/* TOP ACTION callout */}
      {topActions.length > 0 && (
        <div data-testid="intel-top-action" style={{
          padding: "10px 12px", borderRadius: 10,
          background: `linear-gradient(135deg, rgba(212,175,55,0.10), rgba(255,107,0,0.04))`,
          border: `1px solid rgba(212,175,55,0.30)`,
          display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
            <TrendingUp size={14} style={{ color: COLORS.gold, flexShrink: 0 }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 10, color: COLORS.textD, textTransform: "uppercase", letterSpacing: 0.8 }}>
                Top Action
              </div>
              <div style={{ fontSize: 12, color: COLORS.text, marginTop: 2,
                             whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {topActions[0].recommended_action || "Engage contact"}
                <span style={{ color: COLORS.textD, marginLeft: 8 }}>
                  intent {topActions[0].intent_level || "—"}
                </span>
              </div>
            </div>
          </div>
          <span style={{ color: COLORS.gold, fontWeight: 700, fontFamily: "monospace", fontSize: 16 }}>
            {topActions[0].score ?? "—"}
          </span>
        </div>
      )}

      {totalBucketed === 0 && (pixel.visitors_today ?? 0) === 0 && (
        <div data-testid="intel-empty-state" style={{
          padding: 14, borderRadius: 10, background: "rgba(255,255,255,0.02)",
          border: `1px dashed ${COLORS.border}`, fontSize: 12, color: COLORS.textD,
          textAlign: "center", marginTop: 8,
        }}>
          Upload an invoice CSV to start matching pixel visitors with past clients.<br />
          Cross-source matching unlocks 2× lead quality.
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div data-testid="intel-toast" style={{
          marginTop: 12, padding: "8px 12px", borderRadius: 8, fontSize: 12,
          background: toast.kind === "ok" ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
          border: `1px solid ${toast.kind === "ok" ? "rgba(34,197,94,0.30)" : "rgba(239,68,68,0.30)"}`,
          color: toast.kind === "ok" ? COLORS.ok : COLORS.err,
          display: "flex", alignItems: "center", gap: 6,
        }}>
          {toast.kind === "ok" ? <CheckCircle size={13} /> : <AlertCircle size={13} />}
          {toast.msg}
        </div>
      )}
    </div>
  );
}

function Tile({ icon: Icon, label, value, highlight, testid }) {
  return (
    <div data-testid={testid} style={{
      padding: "10px 8px", borderRadius: 10,
      background: highlight ? "rgba(212,175,55,0.08)" : "rgba(255,255,255,0.03)",
      border: `1px solid ${highlight ? "rgba(212,175,55,0.30)" : COLORS.border}`,
      display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 3,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 4, color: highlight ? COLORS.gold : COLORS.textD }}>
        {Icon && <Icon size={11} />}
        <span style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: 0.8 }}>{label}</span>
      </div>
      <span style={{ fontSize: 20, fontWeight: 700, fontFamily: "monospace",
                     color: highlight ? COLORS.gold : COLORS.text, lineHeight: 1 }}>
        {value}
      </span>
    </div>
  );
}

const cardStyle = {
  background: "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))",
  backdropFilter: "blur(22px) saturate(160%)",
  WebkitBackdropFilter: "blur(22px) saturate(160%)",
  border: `1px solid ${COLORS.border}`,
  borderRadius: 18,
  padding: 18,
  boxShadow: "0 18px 44px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)",
};
const btnGhost = {
  display: "inline-flex", alignItems: "center", gap: 4,
  padding: "6px 10px", background: "rgba(255,255,255,0.04)",
  border: `1px solid ${COLORS.border}`, borderRadius: 8,
  color: COLORS.text, fontSize: 11, cursor: "pointer",
};
const btnGold = {
  ...btnGhost,
  background: `linear-gradient(135deg, ${COLORS.gold}, ${COLORS.accent})`,
  color: "#08080F", fontWeight: 700, border: "none",
};
