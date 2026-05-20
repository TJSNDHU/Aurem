/**
 * BuildLog — Public page at /build-log (iter 322au)
 * ══════════════════════════════════════════════════════════════════
 * Shows the AUREM build journal — every commit from Day 1 onward,
 * grouped by iteration, with file counts, lines changed, and category.
 * Pulls from /api/build-journal/feed and /api/build-journal/stats.
 * No auth — designed for "build in public" SEO + customer trust.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  GitBranch, FileText, Plus, Minus, Sparkles, ChevronLeft, ChevronRight,
  Filter, Activity,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const COLORS = {
  bg: '#0B0B0D', panel: 'rgba(15,18,28,0.55)', gold: '#D4AF37',
  text: '#E8E0D0', muted: '#8A8070', green: '#4ADE80', red: '#EF4444',
  blue: '#64C8FF', purple: '#8B5CF6',
};

const CATEGORY_COLOR = {
  feat: COLORS.green, fix: COLORS.red, refactor: COLORS.blue,
  docs: COLORS.muted, test: COLORS.purple, infra: COLORS.gold, chore: '#666',
};

export default function BuildLog() {
  const [stats, setStats] = useState(null);
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [category, setCategory] = useState('');
  const [loading, setLoading] = useState(true);
  const pageSize = 25;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, f] = await Promise.all([
        fetch(`${API}/api/build-journal/stats`).then(r => r.json()).catch(() => null),
        fetch(`${API}/api/build-journal/feed?page=${page}&page_size=${pageSize}${category ? `&category=${category}` : ''}`)
          .then(r => r.json()).catch(() => null),
      ]);
      if (s?.ok) setStats(s);
      if (f?.ok) { setItems(f.items || []); setTotal(f.total || 0); }
    } catch (_) {}
    setLoading(false);
  }, [page, category]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div data-testid="build-log-page" style={{
      minHeight: '100vh', background: COLORS.bg, color: COLORS.text,
      fontFamily: "'Jost',sans-serif", padding: '32px 24px',
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Jost:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
        .bl-card { transition: all 0.3s ease; }
        .bl-card:hover { transform: translateX(4px); border-color: rgba(212,175,55,0.35); }
      `}</style>

      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <Link to="/" style={{ color: COLORS.muted, fontSize: 12, textDecoration: 'none', letterSpacing: '0.15em', textTransform: 'uppercase' }}>
            ← Back to aurem.live
          </Link>
          <h1 data-testid="build-log-title" style={{
            fontFamily: "'Cinzel',serif", fontSize: 42, color: COLORS.text,
            marginTop: 8, marginBottom: 6, fontWeight: 700,
          }}>
            The AUREM <span style={{ color: COLORS.gold }}>Build Journal</span>
          </h1>
          <p style={{ color: COLORS.muted, fontSize: 14, maxWidth: 720, lineHeight: 1.6 }}>
            Every commit. Every iteration. From Day 1 to today. Automatically synced
            from git, fed into the ORA Learning Stack, mined for patterns. Built in
            public, Canada 🇨🇦.
          </p>
        </div>

        {/* Stats strip */}
        {stats && (
          <div data-testid="build-log-stats" style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: 10, marginBottom: 24,
          }}>
            <Stat label="Total commits"      value={stats.total_commits} color={COLORS.gold}  testid="stat-commits"  />
            <Stat label="Distinct iters"     value={stats.distinct_iters} color={COLORS.blue}  testid="stat-iters"     />
            <Stat label="Lines added"        value={`+${(stats.total_additions || 0).toLocaleString()}`} color={COLORS.green} testid="stat-add" />
            <Stat label="Lines removed"      value={`-${(stats.total_deletions || 0).toLocaleString()}`} color={COLORS.red}   testid="stat-del" />
            <Stat label="Days since Day 1"   value={stats.since}     color={COLORS.purple} testid="stat-since"  />
          </div>
        )}

        {/* Filter chips */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap', alignItems: 'center' }}>
          <Filter size={14} style={{ color: COLORS.muted }} />
          <span style={{ fontSize: 11, color: COLORS.muted, letterSpacing: '0.12em', textTransform: 'uppercase' }}>Filter</span>
          {['', 'feat', 'fix', 'refactor', 'docs', 'test', 'infra'].map(c => (
            <button key={c || 'all'} data-testid={`filter-${c || 'all'}`}
              onClick={() => { setCategory(c); setPage(1); }}
              style={{
                padding: '6px 14px', borderRadius: 999, fontSize: 11,
                fontWeight: 600, letterSpacing: '0.06em',
                background: category === c ? `${CATEGORY_COLOR[c] || COLORS.gold}22` : 'transparent',
                border: `1px solid ${category === c ? (CATEGORY_COLOR[c] || COLORS.gold) : 'rgba(255,255,255,0.08)'}`,
                color: category === c ? (CATEGORY_COLOR[c] || COLORS.gold) : COLORS.muted,
                cursor: 'pointer', textTransform: 'uppercase',
              }}>{c || 'all'}</button>
          ))}
        </div>

        {/* Feed */}
        {loading && <div style={{ color: COLORS.muted, padding: 40, textAlign: 'center' }}>Loading…</div>}
        {!loading && items.length === 0 && (
          <div data-testid="build-log-empty" style={{
            padding: 40, textAlign: 'center', color: COLORS.muted,
            background: COLORS.panel, borderRadius: 14,
            border: '1px dashed rgba(255,255,255,0.08)',
          }}>
            Build journal is being indexed, check back in a few seconds.
          </div>
        )}

        {!loading && items.length > 0 && (
          <div data-testid="build-log-feed" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {items.map(it => <CommitRow key={it.sha} item={it} />)}
          </div>
        )}

        {/* Paginator */}
        {totalPages > 1 && (
          <div data-testid="build-log-paginator" style={{
            marginTop: 24, display: 'flex', justifyContent: 'center',
            alignItems: 'center', gap: 12,
          }}>
            <button data-testid="page-prev" onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              style={pageBtn(page <= 1)}>
              <ChevronLeft size={14} /> Prev
            </button>
            <span style={{ fontSize: 12, color: COLORS.muted, fontFamily: "'JetBrains Mono',monospace" }}>
              Page {page} / {totalPages}
            </span>
            <button data-testid="page-next" onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              style={pageBtn(page >= totalPages)}>
              Next <ChevronRight size={14} />
            </button>
          </div>
        )}

        {/* Footer note */}
        <p style={{ fontSize: 11, color: COLORS.muted, textAlign: 'center', marginTop: 40, fontStyle: 'italic' }}>
          Auto-synced every 10 minutes · Daily digest 23:00 ET · Patterns mined nightly into ORA Learning Stack
        </p>
      </div>
    </div>
  );
}


function Stat({ label, value, color, testid }) {
  return (
    <div data-testid={testid} style={{
      padding: '14px 16px', background: COLORS.panel,
      border: `1px solid ${color}22`, borderRadius: 12,
      backdropFilter: 'blur(20px)',
    }}>
      <div style={{ fontSize: 22, color, fontWeight: 700, fontFamily: "'Cinzel',serif" }}>{value}</div>
      <div style={{ fontSize: 10, color: COLORS.muted, letterSpacing: '0.12em', textTransform: 'uppercase', marginTop: 2 }}>{label}</div>
    </div>
  );
}


function CommitRow({ item }) {
  const cat = item.category || 'feat';
  const color = CATEGORY_COLOR[cat] || COLORS.gold;
  const dt = new Date(item.ts || 0);
  const dateStr = isNaN(dt.getTime()) ? '—' : dt.toLocaleString('en-CA', { dateStyle: 'medium', timeStyle: 'short' });
  const testColor = item.test_status === 'pass' ? COLORS.green
                  : item.test_status === 'fail' ? COLORS.red
                  : COLORS.muted;

  return (
    <div className="bl-card" data-testid={`commit-${item.short}`} style={{
      padding: '14px 16px', background: COLORS.panel,
      border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12,
      display: 'flex', gap: 14, alignItems: 'flex-start',
    }}>
      <div style={{
        flexShrink: 0, padding: '4px 10px', borderRadius: 6,
        background: `${color}18`, border: `1px solid ${color}44`,
        color, fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
        textTransform: 'uppercase', minWidth: 60, textAlign: 'center',
      }}>{cat}</div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, color: COLORS.text, fontWeight: 500, marginBottom: 4, wordBreak: 'break-word' }}>
          {item.message}
        </div>
        <div style={{ display: 'flex', gap: 16, fontSize: 11, color: COLORS.muted, flexWrap: 'wrap', fontFamily: "'JetBrains Mono',monospace" }}>
          {item.iter && (
            <span style={{ color: COLORS.gold }} data-testid={`iter-${item.short}`}>
              <Sparkles size={11} style={{ verticalAlign: -2, marginRight: 3 }} />iter {item.iter}
            </span>
          )}
          <span><GitBranch size={11} style={{ verticalAlign: -2, marginRight: 3 }} />{item.short}</span>
          <span><FileText size={11} style={{ verticalAlign: -2, marginRight: 3 }} />{item.files_changed} file{item.files_changed === 1 ? '' : 's'}</span>
          <span style={{ color: COLORS.green }}><Plus size={11} style={{ verticalAlign: -2 }} />{item.additions}</span>
          <span style={{ color: COLORS.red }}><Minus size={11} style={{ verticalAlign: -2 }} />{item.deletions}</span>
          {item.test_status && item.test_status !== 'unknown' && (
            <span style={{ color: testColor }}>
              <Activity size={11} style={{ verticalAlign: -2, marginRight: 3 }} />tests {item.test_status}
            </span>
          )}
          <span>{dateStr}</span>
        </div>
        {item.shipped && item.shipped.length > 0 && (
          <div style={{ marginTop: 6, fontSize: 12, color: COLORS.text, opacity: 0.85 }}>
            <strong style={{ color: COLORS.gold }}>Shipped:</strong>{' '}
            {item.shipped.join(' · ')}
          </div>
        )}
      </div>

      {item.ora_learned && (
        <span data-testid={`ora-${item.short}`} title="Fed into ORA Learning Stack"
          style={{ fontSize: 9, color: COLORS.purple, letterSpacing: '0.1em' }}>
          ◉ ORA
        </span>
      )}
    </div>
  );
}


const pageBtn = (disabled) => ({
  padding: '8px 14px', borderRadius: 8, background: 'transparent',
  border: `1px solid ${disabled ? 'rgba(255,255,255,0.05)' : 'rgba(212,175,55,0.25)'}`,
  color: disabled ? COLORS.muted : COLORS.gold,
  fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase',
  cursor: disabled ? 'not-allowed' : 'pointer',
  display: 'inline-flex', alignItems: 'center', gap: 4,
  opacity: disabled ? 0.4 : 1,
});
