/**
 * ORA Notification Bell + Panel
 * Shows unread count badge and notification history
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Bell, X, Check } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function OraNotificationBell({ token }) {
  const [notifications, setNotifications] = useState([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API}/api/ora/notifications?limit=20`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.notifications || []);
        setUnread(data.unread_count || 0);
      }
    } catch {}
  }, [token]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [load]);

  const markRead = async () => {
    if (!token || unread === 0) return;
    try {
      await fetch(`${API}/api/ora/notifications/read`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      setUnread(0);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch {}
  };

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) markRead();
  };

  useEffect(() => {
    const handler = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const fmtTime = (ts) => {
    if (!ts) return '';
    const d = new Date(ts);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  };

  const typeColors = {
    vip_lead: '#4FC3F7',
    invoice_paid: '#4ADE80',
    approval_needed: '#FFB347',
    morning_brief: '#CE93D8',
    website_issue: '#60A5FA',
    anomaly_detected: '#EF4444',
    pipeline_completed: '#FF6B00',
  };

  return (
    <div ref={panelRef} style={{ position: 'relative' }}>
      {/* Bell Button */}
      <button
        data-testid="ora-notification-bell"
        onClick={toggle}
        style={{
          width: 32, height: 32, borderRadius: '50%',
          border: `1px solid ${unread > 0 ? 'rgba(255,107,0,0.3)' : 'rgba(255,107,0,0.12)'}`,
          background: unread > 0 ? 'rgba(255,107,0,0.08)' : 'transparent',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', position: 'relative', transition: 'all 0.3s',
        }}
      >
        <Bell size={14} color={unread > 0 ? '#FF6B00' : '#8A8070'} />
        {unread > 0 && (
          <div data-testid="notification-badge" style={{
            position: 'absolute', top: -3, right: -3,
            minWidth: 16, height: 16, borderRadius: 8,
            background: '#FF6B00', display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '0 4px', border: '2px solid #08080F',
          }}>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, fontWeight: 700, color: '#FFF' }}>
              {unread > 9 ? '9+' : unread}
            </span>
          </div>
        )}
      </button>

      {/* Notification Panel */}
      {open && (
        <div
          data-testid="notification-panel"
          style={{
            position: 'absolute', top: 40, right: 0, zIndex: 300,
            width: 320, maxHeight: 400, overflowY: 'auto',
            background: 'rgba(12,12,20,0.98)', border: '1px solid rgba(255,107,0,0.15)',
            borderRadius: 14, backdropFilter: 'blur(24px)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.8)',
            animation: 'oraMsgIn 0.2s ease',
          }}
          className="ora-hide-scroll"
        >
          {/* Header */}
          <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(255,107,0,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 13, fontWeight: 600, color: '#E8E0D0' }}>Notifications</span>
            <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}>
              <X size={14} color="#6A6070" />
            </button>
          </div>

          {/* Notification List */}
          {notifications.length === 0 ? (
            <div style={{ padding: '30px 14px', textAlign: 'center' }}>
              <Bell size={24} color="#3A3A4A" style={{ margin: '0 auto 8px' }} />
              <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 12, color: '#6A6070' }}>No notifications yet</div>
            </div>
          ) : (
            <div style={{ padding: '4px 0' }}>
              {notifications.map((n, i) => (
                <div
                  key={i}
                  data-testid={`notification-item-${i}`}
                  style={{
                    padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.03)',
                    background: n.read ? 'transparent' : 'rgba(255,107,0,0.03)',
                    cursor: 'pointer', transition: 'background 0.2s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%', marginTop: 4, flexShrink: 0,
                      background: typeColors[n.type] || '#FF6B00',
                      opacity: n.read ? 0.3 : 1,
                    }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 12, fontWeight: n.read ? 400 : 600, color: '#E8E0D0', marginBottom: 2 }}>
                        {n.title}
                      </div>
                      <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#8A8070', lineHeight: 1.4 }}>
                        {n.body}
                      </div>
                      <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, color: '#5A5468', marginTop: 4 }}>
                        {fmtTime(n.sent_at)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
