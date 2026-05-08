/**
 * Shared glass + shimmer styles for Customer Portal sub-pages.
 * Consistent spatial-glass aesthetic across Website, Report, ORA, Billing,
 * Social, Reviews, Referrals, Settings tabs — matches Home treatment.
 */

export const glassCard = {
  borderRadius: 18,
  padding: 22,
  background: 'rgba(15, 18, 28, 0.55)',
  backdropFilter: 'blur(22px) saturate(150%)',
  WebkitBackdropFilter: 'blur(22px) saturate(150%)',
  border: '1px solid rgba(212, 175, 55, 0.14)',
  boxShadow: '0 16px 44px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(212, 175, 55, 0.08)',
  position: 'relative',
};

export const glassCardLite = {
  ...glassCard,
  padding: 16,
  borderRadius: 14,
  boxShadow: '0 10px 28px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(212, 175, 55, 0.06)',
};

export const title = {
  fontFamily: "'Cinzel', serif",
  fontSize: 26,
  fontWeight: 700,
  color: '#FFF',
  letterSpacing: '0.03em',
  marginBottom: 4,
};

export const sub = { fontSize: 13, color: '#8A8070', marginBottom: 20 };

export const sectionH = {
  fontFamily: "'Cinzel', serif",
  fontSize: 14,
  fontWeight: 700,
  color: '#D4AF37',
  letterSpacing: '0.1em',
  textTransform: 'uppercase',
  margin: 0,
};

export const label = {
  fontSize: 11,
  color: '#8A8070',
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
};

export const primaryBtn = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  padding: '10px 18px',
  borderRadius: 10,
  background: 'linear-gradient(135deg, #D4AF37 0%, #FF8A3D 100%)',
  color: '#0A0A0F',
  fontWeight: 600,
  fontSize: 13,
  border: 'none',
  cursor: 'pointer',
  letterSpacing: '0.04em',
  boxShadow: '0 8px 24px rgba(212,175,55,0.22)',
};
