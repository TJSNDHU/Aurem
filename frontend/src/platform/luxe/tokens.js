// Luxe design tokens — shared across customer portal pages.
export const GOLD     = '#D4A373';
export const GOLD_HI  = '#F7E7CE';
export const GOLD_DK  = '#8B6F44';
export const INK      = '#0A0A0F';
export const PANEL    = 'rgba(22,24,28,0.55)';
export const PANEL_HI = 'rgba(36,38,44,0.45)';
export const STROKE   = 'rgba(212,163,115,0.18)';
export const TEXT_HI  = '#E8E4DE';
export const TEXT_MD  = '#9A9590';
export const TEXT_LO  = '#6A6560';
export const GRADIENT_ORANGE_CTA =
  'linear-gradient(135deg, #FF6B00 0%, #FF8E3C 100%)';

export const fontDisplay = "'Cinzel', 'Montserrat', serif";
export const fontBody    = "'Jost', 'Inter', system-ui, sans-serif";
export const fontMono    = "'JetBrains Mono', ui-monospace, monospace";

export const labelStyle = {
  display: 'block', marginBottom: 6,
  fontFamily: fontMono, fontSize: 10, color: TEXT_MD,
  letterSpacing: '0.16em', textTransform: 'uppercase',
};

export const fieldStyle = {
  width: '100%', padding: '11px 14px', borderRadius: 10,
  background: 'rgba(8,10,14,0.7)',
  border: `1px solid ${STROKE}`,
  color: TEXT_HI, fontFamily: fontBody, fontSize: 14,
  outline: 'none',
};

export const buttonGold = {
  padding: '11px 22px', borderRadius: 10,
  background: GRADIENT_ORANGE_CTA, color: '#fff',
  fontFamily: fontDisplay, fontSize: 12, fontWeight: 700,
  letterSpacing: '0.20em', textTransform: 'uppercase',
  border: 'none', cursor: 'pointer',
  boxShadow: '0 8px 22px rgba(255,107,0,0.25)',
};
