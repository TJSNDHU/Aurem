/**
 * Admin Business IDs Management Page
 * Shows all tenants with Business IDs, connected devices, and actions.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Copy, Check, QrCode, Mail, RefreshCw, Users, Search, X, ExternalLink } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function AdminBusinessIds() {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [qrModal, setQrModal] = useState(null);
  const [copied, setCopied] = useState('');
  const [actionStatus, setActionStatus] = useState({});
  const token = getPlatformToken();

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/admin/business-ids`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setTenants(data.tenants || []);
      }
    } catch (err) { console.warn('Failed to load business IDs:', err.message); }
    setLoading(false);
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const copyBid = (bid) => {
    navigator.clipboard?.writeText(bid);
    setCopied(bid);
    setTimeout(() => setCopied(''), 2000);
  };

  const showQR = async (email) => {
    try {
      const res = await fetch(`${API}/api/admin/business-id/qr/${email}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setQrModal(data);
      }
    } catch {}
  };

  const resendWelcome = async (email) => {
    setActionStatus(prev => ({ ...prev, [email]: 'sending' }));
    try {
      await fetch(`${API}/api/admin/business-id/resend/${email}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      setActionStatus(prev => ({ ...prev, [email]: 'sent' }));
      setTimeout(() => setActionStatus(prev => ({ ...prev, [email]: '' })), 3000);
    } catch {
      setActionStatus(prev => ({ ...prev, [email]: 'error' }));
    }
  };

  const regenerateId = async (email) => {
    if (!window.confirm(`Regenerate Business ID for ${email}? This will disconnect all their devices.`)) return;
    setActionStatus(prev => ({ ...prev, [`regen_${email}`]: 'regenerating' }));
    try {
      const res = await fetch(`${API}/api/admin/business-id/regenerate/${email}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        setActionStatus(prev => ({ ...prev, [`regen_${email}`]: 'done' }));
        load(); // Refresh
      }
    } catch {
      setActionStatus(prev => ({ ...prev, [`regen_${email}`]: 'error' }));
    }
  };

  const generateAll = async () => {
    try {
      const res = await fetch(`${API}/api/admin/business-id/generate-all`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        alert(`Generated: ${data.generated}, Skipped: ${data.skipped}`);
        load();
      }
    } catch {}
  };

  const filtered = tenants.filter(t =>
    t.email?.toLowerCase().includes(search.toLowerCase()) ||
    t.business_name?.toLowerCase().includes(search.toLowerCase()) ||
    t.business_id?.toLowerCase().includes(search.toLowerCase())
  );

  const fmtDate = (d) => d ? new Date(d).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' }) : '---';

  return (
    <div data-testid="admin-business-ids" style={{ padding: '24px', maxWidth: 1200, margin: '0 auto' }}>
      <style>{`
        .admin-bid-table { width: 100%; border-collapse: collapse; }
        .admin-bid-table th { text-align: left; padding: 10px 12px; font-size: 10px; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: #6A6070; border-bottom: 1px solid rgba(255,255,255,0.06); font-family: 'Jost', sans-serif; }
        .admin-bid-table td { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.03); font-family: 'Jost', sans-serif; font-size: 13px; color: #E8E0D0; vertical-align: middle; }
        .admin-bid-table tr:hover td { background: rgba(255,107,0,0.02); }
        .abid-btn { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.03); color: #9A9490; font-size: 11px; cursor: pointer; transition: all 0.2s; font-family: 'Jost', sans-serif; }
        .abid-btn:hover { border-color: rgba(255,107,0,0.2); color: #FF6B00; background: rgba(255,107,0,0.04); }
      `}</style>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontFamily: "'Cinzel',serif", fontSize: 20, fontWeight: 700, color: '#E8E0D0', margin: 0 }}>Business IDs</h1>
          <p style={{ fontFamily: "'Jost',sans-serif", fontSize: 12, color: '#6A6070', margin: '4px 0 0' }}>
            {tenants.length} tenants with Business IDs
          </p>
        </div>
        <button onClick={generateAll} className="abid-btn" style={{ padding: '8px 16px', background: 'rgba(255,107,0,0.08)', borderColor: 'rgba(255,107,0,0.2)', color: '#FF6B00' }}>
          <RefreshCw size={12} /> Generate Missing IDs
        </button>
      </div>

      {/* Search */}
      <div style={{ marginBottom: 16, position: 'relative' }}>
        <Search size={14} color="#6A6070" style={{ position: 'absolute', left: 12, top: 10 }} />
        <input
          data-testid="admin-bid-search"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by name, email, or Business ID..."
          style={{
            width: '100%', padding: '8px 12px 8px 36px', borderRadius: 10,
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
            color: '#E8E0D0', fontSize: 13, fontFamily: "'Jost',sans-serif", outline: 'none',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', borderRadius: 14, border: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.01)' }}>
        <table className="admin-bid-table">
          <thead>
            <tr>
              <th>Tenant</th>
              <th>Business ID</th>
              <th>Devices</th>
              <th>Last ORA</th>
              <th>Welcome</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#6A6070' }}>Loading...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#6A6070' }}>No tenants found</td></tr>
            ) : (
              filtered.map((t, i) => (
                <tr key={i} data-testid={`admin-bid-row-${i}`}>
                  <td>
                    <Link
                      to={`/admin/customer/${encodeURIComponent(t.email)}`}
                      data-testid={`admin-bid-link-${i}`}
                      style={{textDecoration:'none',color:'inherit',display:'block'}}
                      title="Open Customer 360°"
                    >
                      <div style={{ fontWeight: 600, fontSize: 13, color: '#E8E0D0', display:'inline-flex', alignItems:'center', gap:6 }}>
                        {t.business_name || '---'}
                        <ExternalLink size={10} style={{opacity:0.5}}/>
                      </div>
                      <div style={{ fontSize: 11, color: '#6A6070' }}>{t.email}</div>
                    </Link>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Link
                        to={`/admin/customer/${encodeURIComponent(t.business_id)}`}
                        style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 13, fontWeight: 700, color: '#FF6B00', letterSpacing: '0.05em', textDecoration:'none' }}
                        title="Open Customer 360° by BIN"
                      >
                        {t.business_id}
                      </Link>
                      <button className="abid-btn" style={{ padding: '2px 6px' }} onClick={() => copyBid(t.business_id)}>
                        {copied === t.business_id ? <Check size={10} color="#4ADE80" /> : <Copy size={10} />}
                      </button>
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Users size={12} color="#6A6070" />
                      <span>{t.connected_devices}</span>
                    </div>
                  </td>
                  <td style={{ fontSize: 11, color: '#8A8070' }}>{fmtDate(t.last_ora_session)}</td>
                  <td>
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 6,
                      background: t.welcome_sent ? 'rgba(74,222,128,0.08)' : 'rgba(255,179,71,0.08)',
                      color: t.welcome_sent ? '#4ADE80' : '#FFB347',
                    }}>
                      {t.welcome_sent ? 'Sent' : 'Pending'}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      <button className="abid-btn" onClick={() => showQR(t.email)}><QrCode size={10} /> QR</button>
                      <button className="abid-btn" onClick={() => resendWelcome(t.email)}>
                        <Mail size={10} /> {actionStatus[t.email] === 'sending' ? '...' : actionStatus[t.email] === 'sent' ? 'Sent!' : 'Resend'}
                      </button>
                      <button className="abid-btn" onClick={() => regenerateId(t.email)}>
                        <RefreshCw size={10} /> Regen
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* QR Modal */}
      {qrModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setQrModal(null)}>
          <div data-testid="admin-qr-modal" style={{ background: '#0A0A14', borderRadius: 16, padding: 24, border: '1px solid rgba(201,168,76,0.2)', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 16, fontWeight: 700, color: '#FF6B00' }}>{qrModal.business_id}</span>
              <button onClick={() => setQrModal(null)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}><X size={16} color="#6A6070" /></button>
            </div>
            <img src={`data:image/png;base64,${qrModal.qr_base64}`} alt="QR" style={{ width: 280, height: 280, borderRadius: 8 }} />
            <p style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: '#6A6070', marginTop: 12 }}>{qrModal.url_encoded}</p>
          </div>
        </div>
      )}
    </div>
  );
}
