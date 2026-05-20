import React, { useEffect, useState } from 'react';
import { CheckCircle2, ShieldAlert, AlertTriangle, Clock, Check } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function relativeTime(ts) {
  const delta = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (delta < 60) return `${delta}s ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return `${Math.floor(delta / 86400)}d ago`;
}

export default function FounderSaves() {
  const [summary, setSummary] = useState(null);
  const [filter, setFilter] = useState('all');
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);

  const token = localStorage.getItem('adminToken')
              || localStorage.getItem('aurem_admin_token')
              || localStorage.getItem('platform_token')
              || localStorage.getItem('token');

  useEffect(() => {
    const fetchSummary = async () => {
      const res = await fetch(`${BACKEND_URL}/api/admin/founder-saves/summary`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setSummary(data);
    };
    fetchSummary();
  }, [token]);

  useEffect(() => {
    const fetchTimeline = async () => {
      setLoading(true);
      const res = await fetch(
        `${BACKEND_URL}/api/admin/founder-saves/timeline?limit=50&kind=${filter}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const data = await res.json();
      setTimeline(data);
      setLoading(false);
    };
    fetchTimeline();
  }, [filter, token]);

  const metrics = [
    {
      key: 'commits_approved_24h',
      icon: CheckCircle2,
      color: 'emerald',
      label: 'Commits Approved'
    },
    {
      key: 'council_overrides_24h',
      icon: ShieldAlert,
      color: 'amber',
      label: 'Council Overrides'
    },
    {
      key: 'tool_failures_24h',
      icon: AlertTriangle,
      color: 'rose',
      label: 'Tool Failures'
    },
    {
      key: 'last_save',
      icon: Clock,
      color: 'slate',
      label: 'Last Save'
    }
  ];

  const filters = [
    { kind: 'all', label: 'All' },
    { kind: 'commit', label: 'Commits' },
    { kind: 'override', label: 'Overrides' },
    { kind: 'tool_fail', label: 'Tool fails' }
  ];

  const kindColors = {
    commit: 'bg-emerald-500',
    override: 'bg-amber-500',
    tool_fail: 'bg-rose-500'
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Founder Saves, Audit Ledger</h1>
          <div className="h-1 w-32 bg-amber-400"></div>
        </div>

        <div className="grid grid-cols-4 gap-6 mb-8">
          {metrics.map(({ key, icon: Icon, color, label }) => (
            <div
              key={key}
              data-testid={`metric-${key}`}
              className="bg-slate-900 rounded-xl p-6"
            >
              <div className="flex items-center gap-3 mb-3">
                <Icon className={`size-5 text-${color}-400`} />
                <div className={`text-sm text-${color}-400 font-medium`}>{label}</div>
              </div>
              <div className="text-3xl font-bold">
                {summary ? (key === 'last_save' && summary[key] ? relativeTime(summary[key]) : summary[key] || 0) : '—'}
              </div>
            </div>
          ))}
        </div>

        <div className="flex gap-3 mb-8">
          {filters.map(({ kind, label }) => (
            <button
              key={kind}
              data-testid={`pill-${kind}`}
              onClick={() => setFilter(kind)}
              className={`px-4 py-2 rounded-lg font-medium transition ${
                filter === kind
                  ? 'bg-amber-400/20 border border-amber-400 text-amber-300'
                  : 'bg-slate-900 text-slate-400 hover:text-slate-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div
                key={i}
                className="h-16 bg-slate-900 rounded-xl animate-pulse"
              ></div>
            ))}
          </div>
        ) : timeline.length === 0 ? (
          <div
            data-testid="empty-ledger"
            className="flex flex-col items-center justify-center py-16 text-slate-500"
          >
            <Check className="size-12 mb-4" />
            <div className="text-lg">Clean ledger, no founder saves yet.</div>
          </div>
        ) : (
          <div className="space-y-4">
            {timeline.map((item) => (
              <div
                key={item.ref_id}
                data-testid={`timeline-row-${item.ref_id}`}
                className="flex items-start gap-4 bg-slate-900 rounded-xl p-4"
              >
                <div
                  className={`size-3 rounded-full mt-1.5 flex-shrink-0 ${
                    kindColors[item.kind]
                  }`}
                ></div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-3 mb-1">
                    <span className="text-sm text-slate-400">
                      {relativeTime(item.ts)}
                    </span>
                    <span className="text-xs font-mono text-slate-500">
                      {item.actor}
                    </span>
                  </div>
                  <div className="text-slate-200 mb-1">{item.summary}</div>
                  <div className="text-xs font-mono text-slate-600 truncate">
                    {item.ref_id}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}