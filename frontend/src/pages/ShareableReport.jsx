/**
 * Public Shareable Repair Report (iter 281.5 / Phase 2.5)
 * ==========================================================
 * Read-only viewer at /r/{quote_id} — no auth, safe to share via email
 * or social. Reads from /api/public/repair-quote/{quote_id}.
 */
import React, { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Loader2, ShieldCheck, Zap, Globe2, Mail, Smartphone, Link2, CalendarDays, Share2 } from "lucide-react";

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
  if (score >= 80) return "#10B981";
  if (score >= 60) return "#D4AF37";
  if (score >= 40) return "#F59E0B";
  return "#EF4444";
}

const ShareableReport = () => {
  const { quote_id } = useParams();
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [report, setReport] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API}/api/public/repair-quote/${encodeURIComponent(quote_id)}`);
        const body = await r.json().catch(() => ({}));
        if (!alive) return;
        if (!r.ok) {
          setErr(body?.detail || `HTTP ${r.status}`);
        } else {
          setReport(body.report || null);
        }
      } catch (e) {
        if (alive) setErr(e.message || "Network error");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [quote_id]);

  const onShare = useCallback(async () => {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({
          title: `Website Audit · ${report?.business_name || report?.url}`,
          text: `Free 6-point website audit by AUREM — score ${report?.overall_score}/100`,
          url,
        });
      } else {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch (_) {}
  }, [report]);

  return (
    <div
      data-testid="shareable-report-page"
      className="min-h-screen bg-gradient-to-b from-zinc-950 via-black to-zinc-950 text-zinc-100"
    >
      <div className="max-w-3xl mx-auto px-5 py-12">
        <div className="mb-6 flex items-center justify-between">
          <Link
            to="/"
            className="text-[11px] uppercase tracking-widest text-amber-400 hover:text-amber-300"
          >
            ← AUREM
          </Link>
          {report && (
            <button
              onClick={onShare}
              data-testid="shareable-report-share-btn"
              className="text-[12px] flex items-center gap-2 bg-zinc-900 border border-zinc-800 hover:border-amber-500 px-3 py-1.5 rounded-lg transition"
            >
              <Share2 className="size-3.5" />
              {copied ? "Copied!" : "Share"}
            </button>
          )}
        </div>

        {loading && (
          <div className="flex items-center justify-center gap-2 text-zinc-400 py-20">
            <Loader2 className="size-4 animate-spin" /> Loading report…
          </div>
        )}

        {err && (
          <div
            data-testid="shareable-report-error"
            className="rounded-lg border border-rose-900 bg-rose-950/40 p-4 text-sm text-rose-300"
          >
            {err === "Report not found"
              ? "This audit report doesn't exist or was removed. "
              : `${err} — `}
            <Link to="/repair-quote" className="underline text-amber-300">
              Run a fresh audit
            </Link>
          </div>
        )}

        {report && !loading && (
          <div className="space-y-6">
            <div>
              <div className="text-[11px] uppercase tracking-widest text-amber-400 mb-2">
                AUREM · Free Website Audit
              </div>
              <h1 className="text-3xl sm:text-4xl font-semibold leading-tight">
                {report.business_name || report.url}
              </h1>
              <div className="text-sm text-zinc-500 mt-1">{report.url}</div>
            </div>

            {/* Score card */}
            <div className="rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-950 to-black p-8 text-center">
              <div className="text-[11px] uppercase tracking-widest text-zinc-500 mb-2">
                Overall Score
              </div>
              <div
                data-testid="shareable-report-score"
                className="text-7xl font-bold"
                style={{ color: scoreColor(report.overall_score) }}
              >
                {report.overall_score ?? "?"}
                <span className="text-3xl text-zinc-500">/100</span>
              </div>
            </div>

            {/* Breakdown */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 p-6">
              <h3 className="text-base font-semibold mb-4">Score breakdown</h3>
              <div className="grid sm:grid-cols-2 gap-3">
                {LEGEND.map(({ key, label, icon: Icon, max }) => {
                  const got = (report.score_breakdown || {})[key] ?? 0;
                  const pct = Math.round((got / max) * 100);
                  return (
                    <div
                      key={key}
                      data-testid={`shareable-report-breakdown-${key}`}
                      className="flex items-center gap-3 p-3 rounded-lg bg-black/40 border border-zinc-900"
                    >
                      <Icon className="size-4 text-amber-400 shrink-0" />
                      <div className="flex-1">
                        <div className="text-[12px] text-zinc-300">{label}</div>
                        <div className="h-1.5 rounded-full bg-zinc-900 overflow-hidden mt-1.5">
                          <div className="h-full bg-amber-400" style={{ width: `${pct}%` }} />
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
                <h3 className="text-base font-semibold mb-4">Issues found</h3>
                <ul className="space-y-2">
                  {report.issues.map((i, idx) => (
                    <li
                      key={idx}
                      data-testid={`shareable-report-issue-${idx}`}
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

            {/* Diagnosis */}
            {report.diagnosis && (
              <div className="rounded-2xl border border-amber-700/40 bg-gradient-to-br from-amber-950/30 to-zinc-950 p-6">
                <h3 className="text-base font-semibold mb-3 text-amber-300">Diagnosis</h3>
                <pre
                  data-testid="shareable-report-diagnosis"
                  className="whitespace-pre-wrap text-sm text-zinc-200 font-sans"
                >
                  {report.diagnosis}
                </pre>
              </div>
            )}

            <div className="rounded-2xl border border-amber-500/40 bg-gradient-to-r from-amber-500/10 via-amber-300/5 to-amber-500/10 p-6 text-center">
              <div className="text-lg font-semibold mb-2">Want a fixed-price repair quote?</div>
              <Link
                to="/repair-quote"
                className="inline-block bg-gradient-to-r from-amber-500 to-amber-300 text-black font-semibold px-6 py-3 rounded-lg hover:from-amber-400"
              >
                Run audit on your site →
              </Link>
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

export default ShareableReport;
