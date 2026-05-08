/**
 * AUREM Sovereign-Status — Public trust page (iter 322m Day 5+)
 * ----------------------------------------------------------------
 * Renders the sanitized payload from `GET /api/public/status` on
 * `/status` for prospects and existing customers. Auto-refreshes
 * every 30 seconds. No auth, no sensitive data.
 *
 * Brand tokens (matched to AuremHomepage.jsx):
 *   --void:#050508  --orange:#FF6B00  --gold:#C9A84C  --gold2:#E8C86A
 */
import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Activity, Shield, Zap, Brain, Copy, Check } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const STATUS_CSS = `
:root{
  --void:#050508; --dark:#0A0A0F; --dark2:#0E0E16;
  --card:#0F0F1A; --orange:#FF6B00; --orange2:#FF8C35;
  --gold:#C9A84C; --gold2:#E8C86A;
  --white:#F0EDE8; --muted:#7A7590; --muted2:#4A4560;
  --border:rgba(255,107,0,0.10); --border-gold:rgba(201,168,76,0.18);
  --green:#3FCF8E; --yellow:#E8C86A; --red:#FF5A6B;
}
.aurem-status *{margin:0;padding:0;box-sizing:border-box;}
.aurem-status{background:var(--void);color:var(--white);font-family:'Jost',sans-serif;font-weight:300;min-height:100vh;line-height:1.6;}
.aurem-status a{color:inherit;text-decoration:none;}

.s-bgwrap{position:fixed;inset:0;z-index:0;pointer-events:none;
  background:
    radial-gradient(ellipse 70% 40% at 50% 0%,rgba(255,107,0,0.07) 0%,transparent 60%),
    radial-gradient(ellipse 50% 50% at 90% 80%,rgba(201,168,76,0.05) 0%,transparent 60%);}
.s-bggrid{position:fixed;inset:0;z-index:0;pointer-events:none;
  background-image:linear-gradient(rgba(255,107,0,0.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,107,0,0.025) 1px,transparent 1px);
  background-size:64px 64px;
  mask-image:radial-gradient(ellipse 100% 70% at 50% 0%,black 20%,transparent 80%);}

.s-shell{position:relative;z-index:1;max-width:1080px;margin:0 auto;padding:48px 5% 96px;}
.s-back{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:var(--gold);margin-bottom:32px;letter-spacing:0.06em;}
.s-back:hover{color:var(--gold2);}

.s-hero{text-align:left;margin-bottom:56px;}
.s-eyebrow{display:inline-flex;align-items:center;gap:10px;border:1px solid var(--border-gold);padding:7px 18px;border-radius:100px;margin-bottom:28px;font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:0.18em;color:var(--gold);text-transform:uppercase;}
.s-eyebrow .pill-dot{width:8px;height:8px;border-radius:50%;}
.pill-green{background:var(--green);box-shadow:0 0 12px rgba(63,207,142,0.6);}
.pill-yellow{background:var(--yellow);box-shadow:0 0 12px rgba(232,200,106,0.55);}
.pill-red{background:var(--red);box-shadow:0 0 12px rgba(255,90,107,0.6);}

.s-h1{font-family:'Cinzel',serif;font-size:clamp(36px,6vw,60px);font-weight:600;letter-spacing:0.01em;line-height:1.05;margin-bottom:18px;
  background:linear-gradient(180deg,#FFF8E7 0%,var(--gold2) 60%,var(--gold) 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;}
.s-sub{max-width:620px;color:var(--muted);font-size:15px;line-height:1.7;}

.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:18px;margin-bottom:48px;}
@media(min-width:768px){.tiles{grid-template-columns:repeat(4,1fr);}}
.tile{position:relative;background:linear-gradient(180deg,rgba(15,15,26,0.85) 0%,rgba(10,10,15,0.85) 100%);
  border:1px solid var(--border-gold);border-radius:14px;padding:22px 22px 24px;overflow:hidden;
  transition:transform .25s ease,border-color .25s ease;}
.tile:hover{transform:translateY(-2px);border-color:rgba(201,168,76,0.35);}
.tile::before{content:"";position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--gold),transparent);opacity:0.5;}
.tile-icon{width:36px;height:36px;border-radius:8px;display:flex;align-items:center;justify-content:center;background:rgba(255,107,0,0.10);color:var(--orange2);margin-bottom:14px;}
.tile-label{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.22em;color:var(--muted);text-transform:uppercase;margin-bottom:8px;}
.tile-value{font-family:'Cinzel',serif;font-size:34px;font-weight:600;color:var(--white);line-height:1;letter-spacing:-0.01em;}
.tile-value .unit{font-size:18px;color:var(--gold);margin-left:4px;letter-spacing:0;}
.tile-foot{margin-top:10px;font-size:12px;color:var(--muted);}

.spark-wrap{background:linear-gradient(180deg,rgba(15,15,26,0.85),rgba(10,10,15,0.85));border:1px solid var(--border-gold);border-radius:14px;padding:24px;margin-bottom:48px;}
.spark-head{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:18px;flex-wrap:wrap;gap:8px;}
.spark-title{font-family:'Cinzel',serif;font-size:18px;color:var(--gold2);}
.spark-sub{font-size:12px;color:var(--muted);}
.spark{display:flex;align-items:flex-end;gap:5px;height:90px;}
.spark-bar{flex:1;background:linear-gradient(180deg,var(--orange) 0%,rgba(255,107,0,0.2) 100%);border-radius:3px 3px 0 0;min-height:3px;transition:height .4s ease;}
.spark-bar.zero{background:rgba(122,117,144,0.18);}

.embed-wrap{background:linear-gradient(180deg,rgba(15,15,26,0.85),rgba(10,10,15,0.85));border:1px solid var(--border);border-radius:14px;padding:24px;margin-bottom:32px;}
.embed-title{font-family:'Cinzel',serif;font-size:16px;color:var(--gold2);margin-bottom:8px;}
.embed-desc{font-size:13px;color:var(--muted);margin-bottom:14px;}
.embed-code{position:relative;font-family:'JetBrains Mono',monospace;font-size:12px;background:#06060A;border:1px solid var(--border);border-radius:8px;padding:14px 50px 14px 16px;color:#FBE4B8;word-break:break-all;line-height:1.55;}
.embed-copy{position:absolute;top:10px;right:10px;background:rgba(255,107,0,0.10);color:var(--orange2);border:1px solid rgba(255,107,0,0.25);width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:all .2s;}
.embed-copy:hover{background:rgba(255,107,0,0.20);}

.s-foot{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--muted);flex-wrap:wrap;gap:8px;border-top:1px solid var(--border);padding-top:18px;}
.s-foot a{color:var(--gold);}
.s-foot a:hover{color:var(--gold2);}
`;

const COLOR_LABEL = {
  green: "All systems sovereign",
  yellow: "Auto-correcting",
  red: "Council escalation in progress",
};

function fmtRelative(iso) {
  if (!iso) return "no incidents on record";
  try {
    const then = new Date(iso).getTime();
    const diff = Date.now() - then;
    if (diff < 60_000) return "just now";
    if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h ago`;
    return `${Math.round(diff / 86_400_000)}d ago`;
  } catch {
    return "—";
  }
}

export default function PublicStatus() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = async () => {
    try {
      const r = await fetch(`${API}/api/public/status`, { cache: "no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setData(j);
      setError(null);
    } catch (e) {
      setError(String(e.message || e));
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, []);

  const sparkMax = useMemo(() => {
    if (!data?.heals_sparkline_24h) return 1;
    return Math.max(1, ...data.heals_sparkline_24h);
  }, [data]);

  const embedUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/api/public/status/badge.json`
      : "https://aurem.live/api/public/status/badge.json";
  const embedShield = `https://img.shields.io/endpoint?url=${encodeURIComponent(embedUrl)}`;
  const embedMarkdown = `![AUREM Autonomy](${embedShield})`;

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(embedMarkdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  };

  const color = data?.badge_color || "yellow";

  return (
    <div className="aurem-status" data-testid="public-status-page">
      <style>{STATUS_CSS}</style>
      <div className="s-bgwrap" />
      <div className="s-bggrid" />

      <div className="s-shell">
        <Link to="/" className="s-back" data-testid="public-status-back">
          <ArrowLeft className="w-4 h-4" /> Back to AUREM
        </Link>

        <div className="s-hero">
          <div className="s-eyebrow" data-testid="public-status-pill">
            <span className={`pill-dot pill-${color}`} />
            {COLOR_LABEL[color] || COLOR_LABEL.yellow}
            <span style={{ color: "var(--muted2)", marginLeft: 6 }}>
              · live
            </span>
          </div>
          <h1 className="s-h1">Sovereign Status</h1>
          <p className="s-sub">
            AUREM measures, scores, and self-corrects every part of its own
            system in real time. The numbers below are pulled live from the
            production Council — no marketing, no padding, no human in the
            loop.
          </p>
        </div>

        {error && !data && (
          <div
            style={{
              border: "1px solid var(--red)",
              padding: 18,
              borderRadius: 12,
              color: "var(--red)",
              marginBottom: 24,
              fontSize: 13,
            }}
            data-testid="public-status-error"
          >
            Status feed temporarily unavailable. Retrying every 30s…
          </div>
        )}

        <div className="tiles" data-testid="public-status-tiles">
          <div className="tile" data-testid="tile-autonomy">
            <div className="tile-icon">
              <Shield className="w-5 h-5" />
            </div>
            <div className="tile-label">System Autonomy · 24h</div>
            <div className="tile-value">
              {data ? data.system_autonomy_pct.toFixed(2) : "—"}
              <span className="unit">%</span>
            </div>
            <div className="tile-foot">no human intervention</div>
          </div>

          <div className="tile" data-testid="tile-heals">
            <div className="tile-icon">
              <Activity className="w-5 h-5" />
            </div>
            <div className="tile-label">Watchdog Heals · 24h</div>
            <div className="tile-value">
              {data ? data.watchdog_heals_24h : "—"}
            </div>
            <div className="tile-foot">auto-fixed by Sovereign</div>
          </div>

          <div className="tile" data-testid="tile-heal-time">
            <div className="tile-icon">
              <Zap className="w-5 h-5" />
            </div>
            <div className="tile-label">Avg Heal Time</div>
            <div className="tile-value">
              {data ? (data.avg_heal_time_ms / 1000).toFixed(1) : "—"}
              <span className="unit">s</span>
            </div>
            <div className="tile-foot">latency-guardian recovery</div>
          </div>

          <div className="tile" data-testid="tile-veracity">
            <div className="tile-icon">
              <Brain className="w-5 h-5" />
            </div>
            <div className="tile-label">Decision Veracity</div>
            <div className="tile-value">
              {data ? data.decision_veracity_pct.toFixed(1) : "—"}
              <span className="unit">%</span>
            </div>
            <div className="tile-foot">Memory Guard 2-stamp pass rate</div>
          </div>
        </div>

        <div className="spark-wrap" data-testid="public-status-sparkline">
          <div className="spark-head">
            <div>
              <div className="spark-title">Council Activity · last 24 hours</div>
              <div className="spark-sub">
                Heals per hour · oldest left · newest right
              </div>
            </div>
            <div className="spark-sub">
              Last incident: {data ? fmtRelative(data.last_incident_at) : "—"}
            </div>
          </div>
          <div className="spark">
            {(data?.heals_sparkline_24h || Array(24).fill(0)).map((v, i) => {
              const pct = (v / sparkMax) * 100;
              return (
                <div
                  key={i}
                  className={`spark-bar${v === 0 ? " zero" : ""}`}
                  style={{ height: `${Math.max(3, pct)}%` }}
                  title={`${v} heals · ${24 - i}h ago`}
                />
              );
            })}
          </div>
        </div>

        <div className="embed-wrap" data-testid="public-status-embed">
          <div className="embed-title">Embed the trust badge</div>
          <div className="embed-desc">
            Drop this into your README, sales deck, or proposal — it auto-updates
            from the same live feed.
          </div>
          <div className="embed-code">
            {embedMarkdown}
            <button
              onClick={onCopy}
              className="embed-copy"
              data-testid="public-status-copy-embed"
              aria-label="Copy embed snippet"
            >
              {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div className="s-foot">
          <span>
            Updated{" "}
            {data?.ts ? new Date(data.ts).toLocaleTimeString() : "—"} ·
            refreshes every 30s
          </span>
          <span>
            Powered by AUREM ·{" "}
            <a href="/" data-testid="public-status-home-link">
              aurem.live
            </a>
          </span>
        </div>
      </div>
    </div>
  );
}
