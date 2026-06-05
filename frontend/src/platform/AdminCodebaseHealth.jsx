/**
 * AdminCodebaseHealth.jsx — iter D-70
 * Live codebase-health dashboard. Auto-refreshes every 30s.
 * Route: /admin/codebase-health
 */
import { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw, AlertTriangle, FileCode, GitBranch, Activity, Loader2,
} from 'lucide-react';

const API = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');

const getTok = () =>
  sessionStorage.getItem('platform_token') ||
  localStorage.getItem('platform_token') ||
  localStorage.getItem('aurem_admin_token') ||
  sessionStorage.getItem('aurem_admin_token') || '';

const j = async (path, opts = {}) => {
  const r = await fetch(`${API}${path}`, {
    ...opts,
    headers: { Authorization: `Bearer ${getTok()}`, ...(opts.headers || {}) },
  });
  if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`);
  return r.json();
};

const scoreColor = (s) =>
  s >= 8 ? 'text-emerald-400' : s >= 5 ? 'text-amber-400' : 'text-rose-400';

const sizeColor = (n) =>
  n >= 1500 ? 'text-rose-400' : n >= 800 ? 'text-orange-400'
  : n >= 300 ? 'text-yellow-400' : 'text-zinc-400';

export default function AdminCodebaseHealth() {
  const [snap, setSnap]     = useState(null);
  const [trend, setTrend]   = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr]       = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [a, b] = await Promise.all([
        j('/api/admin/codebase-health/latest'),
        j('/api/admin/codebase-health/trend?days=7'),
      ]);
      setSnap(a.snapshot);
      setTrend(b.items || []);
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }, []);

  const forceRefresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await j('/api/admin/codebase-health/refresh', { method: 'POST' });
      setSnap(r.snapshot);
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 30000);  // auto-refresh every 30s
    return () => clearInterval(id);
  }, [fetchAll]);

  if (!snap && !err) {
    return <div className="p-8 text-zinc-400 flex items-center gap-2" data-testid="codebase-health-loading">
      <Loader2 className="animate-spin size-4" />
      Running first snapshot — give us 10s…
    </div>;
  }

  if (err) {
    return <div className="p-8 text-rose-400" data-testid="codebase-health-error">{err}</div>;
  }

  const { backend: be, frontend: fe, health_score, top_action, generated_at } = snap;
  const buckets_be = be.size_buckets;

  return (
    <div className="p-8 text-zinc-200 max-w-7xl" data-testid="codebase-health-page">
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="text-2xl font-light tracking-wide">Codebase Health</h1>
          <p className="text-xs text-zinc-500 mt-1">
            generated {new Date(generated_at).toLocaleString()} · scan took {snap.duration_sec}s · auto-refresh 30s
          </p>
        </div>
        <button
          onClick={forceRefresh}
          disabled={loading}
          data-testid="codebase-health-refresh"
          className="px-3 py-1.5 text-xs rounded bg-zinc-900 border border-zinc-700 hover:border-zinc-500 flex items-center gap-1.5 disabled:opacity-40"
        >
          {loading ? <Loader2 className="size-3.5 animate-spin"/> : <RefreshCw className="size-3.5"/>}
          Refresh now
        </button>
      </div>

      {/* HERO + top action */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="lg:col-span-1 p-6 rounded-lg bg-zinc-950 border border-zinc-800" data-testid="codebase-health-score">
          <div className="text-xs uppercase tracking-wider text-zinc-500 mb-1">Health Score</div>
          <div className={`text-6xl font-light ${scoreColor(health_score)}`}>{health_score}</div>
          <div className="text-xs text-zinc-500 mt-2">out of 10</div>
        </div>

        <div className="lg:col-span-2 p-6 rounded-lg bg-amber-950/30 border border-amber-900/50" data-testid="codebase-health-action">
          <div className="flex items-start gap-3">
            <AlertTriangle className="size-5 text-amber-400 mt-0.5"/>
            <div className="flex-1">
              <div className="text-xs uppercase tracking-wider text-amber-300/70 mb-1">Top Action</div>
              <div className="font-mono text-sm text-amber-100">{top_action.path}</div>
              <div className="text-xs text-amber-300/80 mt-1.5">{top_action.reason}</div>
            </div>
          </div>
        </div>
      </div>

      {/* SIZE BUCKETS */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <BucketCard label="≥ 1500 lines" count={buckets_be.ge_1500} tone="rose"   testid="bucket-red"/>
        <BucketCard label="800-1499"     count={buckets_be.ge_800}  tone="orange" testid="bucket-orange"/>
        <BucketCard label="300-799"      count={buckets_be.ge_300}  tone="yellow" testid="bucket-yellow"/>
        <BucketCard label="< 300 (safe)" count={buckets_be.lt_300}  tone="zinc"   testid="bucket-safe"/>
      </div>

      {/* TOTALS */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <TotalsCard scope="Backend"  totals={be.totals} testid="totals-backend"/>
        <TotalsCard scope="Frontend" totals={fe.totals} testid="totals-frontend"/>
      </div>

      {/* GOD FILES + CIRCULAR */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Panel title="God Files" icon={FileCode} testid="godfiles-panel">
          {be.god_files.length === 0 ? (
            <div className="text-xs text-zinc-500">None ✓</div>
          ) : be.god_files.map((g, i) => (
            <div key={i} className="flex justify-between text-xs py-1 border-b border-zinc-900/50 last:border-0">
              <span className="font-mono text-zinc-300 truncate" title={g.path}>{g.path}</span>
              <span className="text-zinc-500 whitespace-nowrap ml-2">
                {g.imports}↑ / {g.imported_by}↓ · {g.lines}L
              </span>
            </div>
          ))}
        </Panel>

        <Panel title="Circular Imports" icon={GitBranch} testid="circular-panel">
          {be.circular.length === 0 ? (
            <div className="text-xs text-emerald-400">None detected ✓</div>
          ) : be.circular.map((cyc, i) => (
            <div key={i} className="text-xs font-mono text-rose-300 py-1">
              {cyc.join(' → ')}
            </div>
          ))}
        </Panel>
      </div>

      {/* COMPLEXITY HOTSPOTS + BIGGEST FILES */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Panel title="Complexity Hotspots (top 10)" icon={Activity} testid="complexity-panel">
          {be.cc_top.slice(0,10).map((c, i) => (
            <div key={i} className="flex justify-between text-xs py-1 border-b border-zinc-900/50 last:border-0">
              <span className="font-mono truncate">
                <span className="text-zinc-300">{c.path}</span>
                <span className="text-zinc-500"> · {c.fn}</span>
              </span>
              <span className={`whitespace-nowrap ml-2 ${c.cc >= 30 ? 'text-rose-400' : 'text-amber-400'}`}>
                CC={c.cc}
              </span>
            </div>
          ))}
        </Panel>

        <Panel title="Biggest Files (backend, top 10)" icon={FileCode} testid="biggest-panel">
          {be.biggest.slice(0,10).map((f, i) => (
            <div key={i} className="flex justify-between text-xs py-1 border-b border-zinc-900/50 last:border-0">
              <span className="font-mono text-zinc-300 truncate">{f.path}</span>
              <span className={`whitespace-nowrap ml-2 ${sizeColor(f.lines)}`}>{f.lines} lines</span>
            </div>
          ))}
        </Panel>
      </div>

      {/* TREND */}
      {trend.length > 1 && (
        <Panel title={`Score Trend (last ${trend.length} snapshots)`} icon={Activity} testid="trend-panel">
          <div className="flex items-end gap-1 h-20">
            {[...trend].reverse().map((t, i) => (
              <div key={i} title={`${t.health_score} @ ${new Date(t.generated_at).toLocaleString()}`}
                className={`flex-1 rounded-t ${scoreColor(t.health_score).replace('text-','bg-')} opacity-70 hover:opacity-100`}
                style={{ height: `${(t.health_score / 10) * 100}%`, minHeight: 2 }} />
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function BucketCard({ label, count, tone, testid }) {
  const toneClass = {
    rose:   'border-rose-900/50 bg-rose-950/30 text-rose-300',
    orange: 'border-orange-900/50 bg-orange-950/30 text-orange-300',
    yellow: 'border-yellow-900/50 bg-yellow-950/30 text-yellow-300',
    zinc:   'border-zinc-800 bg-zinc-950 text-zinc-400',
  }[tone];
  return (
    <div data-testid={testid} className={`p-4 rounded-lg border ${toneClass}`}>
      <div className="text-3xl font-light">{count}</div>
      <div className="text-xs uppercase tracking-wider mt-1 opacity-80">{label}</div>
    </div>
  );
}

function TotalsCard({ scope, totals, testid }) {
  return (
    <div data-testid={testid} className="p-4 rounded-lg bg-zinc-950 border border-zinc-800">
      <div className="text-xs uppercase tracking-wider text-zinc-500 mb-1">{scope}</div>
      <div className="text-sm">
        <span className="text-zinc-200">{totals.files.toLocaleString()}</span>
        <span className="text-zinc-500"> files · </span>
        <span className="text-zinc-200">{totals.lines.toLocaleString()}</span>
        <span className="text-zinc-500"> lines</span>
      </div>
    </div>
  );
}

function Panel({ title, icon: Icon, children, testid }) {
  return (
    <div data-testid={testid} className="p-4 rounded-lg bg-zinc-950 border border-zinc-800">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-zinc-500 mb-3">
        <Icon className="size-3.5"/>
        {title}
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}
