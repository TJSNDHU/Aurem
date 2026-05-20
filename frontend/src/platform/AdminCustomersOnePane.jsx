/**
 * AdminCustomersOnePane — Iter 288.3
 * ---------------------------------
 * Unified founder-only Customers tab. Replaces the fragmented "All Customers"
 * + "Customer Detail" + cleanup confusion with one pane:
 *   - Auto-refreshing customer list (every 15s)
 *   - Inline detail panel on row click
 *   - Quick actions: Reonboard BIN, Relink Pixel, Wipe non-founders
 *   - Search / filter
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Users, RefreshCw, Trash2, Search, ExternalLink, Key, AlertTriangle } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function AdminCustomersOnePane({ token }) {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const r = await fetch(`${API}/api/admin/founder/customers/list?limit=100`,
        { headers: { Authorization: `Bearer ${token}` } });
      if (r.ok) {
        const d = await r.json();
        setCustomers(d.customers || []);
      }
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => {
    load();
    const itv = setInterval(load, 15000);
    return () => clearInterval(itv);
  }, [load]);

  const showToast = (msg, kind = 'success') => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 4000);
  };

  const handleWipe = async () => {
    if (!window.confirm('Type WIPE to delete ALL non-founder customers + BINs.\nFounder accounts are preserved. Continue?')) return;
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/admin/founder/customers/cleanup`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: 'WIPE', keep_pixel_keys: true }),
      });
      const d = await r.json();
      showToast(`Wiped ${d.total_deleted || 0} records. Pixel keys preserved.`);
      await load();
      setSelected(null);
    } catch (e) { showToast(`Wipe failed: ${e.message}`, 'error'); }
    setBusy(false);
  };

  const handleReonboard = async () => {
    if (!selected) return;
    if (!window.confirm(`Reonboard ${selected.email} with a fresh BIN?\nExisting pixel API key will be relinked automatically.`)) return;
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/admin/founder/customers/reonboard-bin`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: selected.email,
          full_name: selected.full_name,
          company_name: selected.company_name,
          website: selected.website,
          city: selected.city,
          industry: selected.industry,
          phone: selected.phone,
          relink_existing_pixel: true,
        }),
      });
      const d = await r.json();
      showToast(`New BIN: ${d.business_id}${d.linked_pixel_key ? ' · Pixel relinked' : ''}`);
      await load();
    } catch (e) { showToast(`Reonboard failed: ${e.message}`, 'error'); }
    setBusy(false);
  };

  const visible = customers.filter(c => {
    if (!filter) return true;
    const f = filter.toLowerCase();
    return (c.email || '').toLowerCase().includes(f)
        || (c.business_id || '').toLowerCase().includes(f)
        || (c.company_name || '').toLowerCase().includes(f)
        || (c.full_name || '').toLowerCase().includes(f)
        || (c.website || '').toLowerCase().includes(f);
  });

  return (
    <div data-testid="admin-customers-one-pane" className="flex h-full bg-[#0A0505]">
      {/* Left: list */}
      <div className="w-1/2 border-r border-[#1a1410] flex flex-col">
        <div className="p-4 border-b border-[#1a1410] flex items-center gap-3">
          <Users className="size-5 text-[#D4AF37]" />
          <h2 className="text-lg font-medium text-[#E8E0D0] tracking-wide flex-1">Customers · Live</h2>
          <span data-testid="customers-count" className="text-xs font-mono text-[#D4AF37]">{visible.length}/{customers.length}</span>
          <button data-testid="customers-refresh-btn" onClick={load} disabled={loading} className="p-1.5 rounded hover:bg-[#1a1410]" aria-label="Refresh">
            <RefreshCw className={`size-4 text-[#888] ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
        <div className="p-3 border-b border-[#1a1410]">
          <div className="relative">
            <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#666]" />
            <input
              data-testid="customers-search"
              value={filter}
              onChange={e => setFilter(e.target.value)}
              placeholder="Search email · BIN · company · website…"
              className="w-full bg-[#120A05] border border-[#2a1f15] rounded pl-9 pr-3 py-2 text-sm text-[#E8E0D0] placeholder-[#5a5040] focus:outline-none focus:border-[#D4AF37]/40"
            />
          </div>
        </div>
        <div className="flex-1 overflow-auto">
          {visible.length === 0 ? (
            <div className="p-8 text-center text-sm text-[#5a5040]">
              {loading ? 'Loading…' : customers.length === 0 ? 'No customers yet.' : 'No matches.'}
            </div>
          ) : visible.map((c, i) => (
            <button
              key={c.email}
              data-testid={`customer-row-${i}`}
              onClick={() => setSelected(c)}
              className={`w-full text-left p-3 border-b border-[#1a1410]/50 hover:bg-[#120A05] transition-colors ${selected?.email === c.email ? 'bg-[#1a1410]' : ''}`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs text-[#D4AF37] font-bold">{c.business_id}</span>
                <span className="text-[10px] font-light" style={{ color: c.wizard_complete ? '#4ADE80' : '#FFB347' }}>
                  {c.wizard_complete ? '✅ wizard' : '⏳ pending'}
                </span>
              </div>
              <div className="text-sm text-[#E8E0D0]">{c.company_name || c.full_name || c.email}</div>
              <div className="text-xs text-[#888]">{c.email}{c.city ? ` · ${c.city}` : ''}{c.industry ? ` · ${c.industry}` : ''}</div>
            </button>
          ))}
        </div>
        <div className="p-3 border-t border-[#1a1410]">
          <button
            data-testid="customers-wipe-btn"
            onClick={handleWipe}
            disabled={busy}
            className="w-full py-2 px-3 bg-[#3a1010] hover:bg-[#5a1818] border border-[#5a1818] rounded text-xs text-[#FFB4B4] flex items-center justify-center gap-2 disabled:opacity-40"
          >
            <Trash2 className="size-3.5" />
            Wipe non-founder accounts
          </button>
        </div>
      </div>

      {/* Right: detail */}
      <div className="flex-1 flex flex-col">
        {!selected ? (
          <div className="flex-1 flex items-center justify-center text-[#5a5040] text-sm">
            Select a customer to view details
          </div>
        ) : (
          <>
            <div className="p-5 border-b border-[#1a1410]">
              <div className="flex items-center justify-between mb-3">
                <span data-testid="detail-bin" className="font-mono text-lg text-[#D4AF37] font-bold">{selected.business_id}</span>
                <span className="text-xs px-2 py-0.5 rounded" style={{
                  background: selected.active ? 'rgba(74,222,128,0.1)' : 'rgba(255,179,71,0.1)',
                  color: selected.active ? '#4ADE80' : '#FFB347',
                }}>{selected.active ? 'Active' : 'Inactive'}</span>
              </div>
              <div className="text-xl text-[#F5F0E8] font-light tracking-wide">{selected.company_name || '(no company)'}</div>
              <div className="text-sm text-[#888] mt-1">{selected.full_name}</div>
            </div>
            <div className="flex-1 overflow-auto p-5 space-y-4">
              <DetailRow label="Email" value={selected.email} />
              <DetailRow label="Phone" value={selected.phone} />
              <DetailRow label="City / Industry" value={`${selected.city || '—'} · ${selected.industry || '—'}`} />
              <DetailRow label="Plan" value={selected.plan} />
              <DetailRow label="Joined" value={selected.joined_at} />
              <DetailRow label="Google OAuth" value={selected.google_oauth ? '✅ Yes' : 'No'} />
              {selected.website && (
                <DetailRow label="Website" value={
                  <a href={selected.website} target="_blank" rel="noreferrer" className="text-[#D4AF37] hover:underline inline-flex items-center gap-1">
                    {selected.website} <ExternalLink className="size-3" />
                  </a>
                } />
              )}
            </div>
            <div className="p-4 border-t border-[#1a1410] flex gap-2">
              <button
                data-testid="reonboard-btn"
                onClick={handleReonboard}
                disabled={busy}
                className="flex-1 py-2 px-3 bg-[#1a1410] hover:bg-[#2a1f15] border border-[#D4AF37]/30 rounded text-xs text-[#D4AF37] flex items-center justify-center gap-2 disabled:opacity-40"
              >
                <Key className="size-3.5" />
                Reissue Fresh BIN
              </button>
            </div>
          </>
        )}
      </div>

      {toast && (
        <div data-testid="customers-toast" className="fixed bottom-6 right-6 px-4 py-3 rounded-lg shadow-2xl flex items-center gap-2 z-50" style={{
          background: toast.kind === 'error' ? '#3a1010' : '#0a2a14',
          border: `1px solid ${toast.kind === 'error' ? '#5a1818' : '#1a5a3a'}`,
          color: toast.kind === 'error' ? '#FFB4B4' : '#4ADE80',
        }}>
          {toast.kind === 'error' && <AlertTriangle className="size-4" />}
          <span className="text-sm">{toast.msg}</span>
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] tracking-[0.15em] uppercase text-[#5a5040]">{label}</span>
      <span className="text-sm text-[#E8E0D0]">{value || '—'}</span>
    </div>
  );
}
