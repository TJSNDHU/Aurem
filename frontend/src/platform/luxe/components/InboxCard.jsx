/**
 * InboxCard — full-width inbox empty/list state.
 * Real wiring already exists in CustomerResultsRow.jsx. This is the
 * V2 visual shell: empty state with icon + count badge.
 */
import React from 'react';
import { Inbox as InboxIcon } from 'lucide-react';

export const InboxCard = ({ threads = [], unread = 0 }) => (
  <section data-testid="inbox-card" className="av2-card"
           style={{ display: 'flex', flexDirection: 'column', gap: 14, minHeight: 200 }}>
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--dash-text)' }}>
        Inbox · All Channels
      </h3>
      <span className="av2-pill" data-testid="inbox-unread-badge">{unread} unread</span>
    </header>
    {threads.length === 0 ? (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
                    gap: 10, padding: '32px 0', color: 'var(--dash-text-faint)' }}>
        <InboxIcon size={32} />
        <div style={{ fontSize: 13, color: 'var(--dash-text-muted)' }}>No conversations yet</div>
        <div style={{ fontSize: 11 }}>Replies across email · SMS · WhatsApp · voice land here.</div>
      </div>
    ) : (
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {threads.slice(0, 6).map((t) => (
          <li key={t.thread_id || t.id}
              data-testid={`inbox-thread-${t.thread_id || t.id}`}
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                       padding: 12, borderRadius: 10, background: 'var(--dash-track)',
                       border: '1px solid var(--dash-divider)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 12, color: 'var(--dash-text)', fontWeight: 500 }}>
                {t.channel?.toUpperCase() || 'EMAIL'} · {(t.handle || '').slice(0, 24) || 'anonymous'}
              </span>
              <span style={{ fontSize: 11, color: 'var(--dash-text-muted)' }}>
                {(t.last_preview || '').slice(0, 72)}
              </span>
            </div>
            {Number(t.unread) > 0 && (
              <span className="av2-pill av2-pill-ent">{t.unread}</span>
            )}
          </li>
        ))}
      </ul>
    )}
  </section>
);

export default InboxCard;
