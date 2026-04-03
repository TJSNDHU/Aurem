/**
 * Admin Brand Theme Utility
 * Shared theme generation for all admin components.
 * Usage: const { C, shortName, fullName, isLaVela } = useAdminTheme();
 */

import { useAdminBrand } from './useAdminBrand';
import { LAVELA_COLORS, LAVELA_FONTS, LAVELA_BRAND } from '../../lavela/config';

// ReRoots (default) color palette
const REROOTS_COLORS = {
  bg: "#FDF9F9",
  surface: "#FFFFFF",
  surfaceAlt: "#FEF2F4",
  surfaceHover: "#FEF2F4",
  
  border: "#F0E8E8",
  borderLight: "#E8DEE0",
  borderBright: "#D8C8CC",
  
  gold: "#F8A5B8",
  goldDim: "#E8889A",
  goldFaint: "rgba(248,165,184,0.08)",
  
  green: "#72B08A",
  greenBright: "#72B08A",
  greenFaint: "rgba(114,176,138,0.08)",
  
  red: "#E07070",
  redBright: "#E07070",
  redFaint: "rgba(224,112,112,0.08)",
  
  amber: "#E8A860",
  amberFaint: "rgba(232,168,96,0.08)",
  
  blue: "#7AAEC8",
  blueBright: "#7AAEC8",
  blueFaint: "rgba(122,174,200,0.08)",
  
  purple: "#9B8ABF",
  purpleBright: "#9B8ABF",
  purpleFaint: "rgba(155,138,191,0.08)",
  
  teal: "#72B0B0",
  tealBright: "#72B0B0",
  
  text: "#2D2A2E",
  textDim: "#8A8490",
  textMuted: "#C4BAC0",
  white: "#2D2A2E",
  
  headerGradient: "linear-gradient(180deg, #0c0e14 0%, transparent 100%)",
};

const REROOTS_BRAND = {
  id: 'reroots',
  name: 'ReRoots Aesthetics',
  shortName: 'REROOTS',
  fullName: 'Reroots Aesthetics Inc.',
  domain: 'reroots.ca',
};

// Shared fonts
export const FONTS = {
  display: "'Cormorant Garamond', Georgia, serif",
  sans: "'Inter', system-ui, sans-serif",
  mono: "'JetBrains Mono', 'Courier New', monospace",
};

/**
 * Get theme colors based on brand
 * @param {boolean} isLaVela - Whether La Vela brand is active
 * @returns {object} Color palette
 */
export const getThemeColors = (isLaVela) => isLaVela ? LAVELA_COLORS : REROOTS_COLORS;

/**
 * Get brand info based on brand
 * @param {boolean} isLaVela - Whether La Vela brand is active
 * @returns {object} Brand information
 */
export const getBrandInfo = (isLaVela) => isLaVela ? LAVELA_BRAND : REROOTS_BRAND;

/**
 * Generate CSS for admin modules
 * @param {object} C - Color palette
 * @param {string} moduleClass - CSS class prefix (e.g., 'crm', 'orders')
 * @returns {string} CSS string
 */
export const generateModuleCss = (C, moduleClass) => `
  @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=JetBrains+Mono:wght@300;400;500&family=Inter:wght@300;400;500;600&display=swap');
  .${moduleClass}-module * { box-sizing: border-box; margin: 0; padding: 0; }
  .${moduleClass}-module ::-webkit-scrollbar { width: 3px; height: 3px; }
  .${moduleClass}-module ::-webkit-scrollbar-track { background: ${C.bg}; }
  .${moduleClass}-module ::-webkit-scrollbar-thumb { background: ${C.borderLight}; border-radius: 2px; }
  @keyframes ${moduleClass}FadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes ${moduleClass}Pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
  @keyframes ${moduleClass}SlideIn { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: translateX(0); } }
  .${moduleClass}-hover-row:hover { background: ${C.surfaceAlt} !important; }
  .${moduleClass}-hover-btn:hover { opacity: 0.75; transform: translateY(-1px); }
  .${moduleClass}-hover-card:hover { border-color: ${C.goldDim} !important; }
  .${moduleClass}-module input:focus, .${moduleClass}-module select:focus, .${moduleClass}-module textarea:focus { outline: none; border-color: ${C.goldDim} !important; }
  .${moduleClass}-tab-btn:hover { color: ${C.gold} !important; }
`;

/**
 * Generate common styles for inputs, buttons
 * @param {object} C - Color palette
 * @returns {object} Style objects
 */
export const getCommonStyles = (C) => ({
  input: {
    width: "100%",
    background: C.bg,
    border: `1px solid ${C.border}`,
    color: C.text,
    padding: "0.6rem 0.75rem",
    fontSize: "0.8rem",
    fontFamily: FONTS.mono,
  },
  btnPrimary: {
    background: C.gold,
    color: C.bg,
    border: "none",
    padding: "0.6rem 1.4rem",
    fontSize: "0.65rem",
    letterSpacing: "0.2em",
    textTransform: "uppercase",
    cursor: "pointer",
    fontFamily: FONTS.mono,
    transition: "all 0.2s",
  },
  btnSecondary: {
    background: "transparent",
    color: C.textDim,
    border: `1px solid ${C.border}`,
    padding: "0.6rem 1.4rem",
    fontSize: "0.65rem",
    letterSpacing: "0.2em",
    textTransform: "uppercase",
    cursor: "pointer",
    fontFamily: FONTS.mono,
    transition: "all 0.2s",
  },
  btnGhost: {
    background: "transparent",
    color: C.textDim,
    border: "none",
    padding: "0.3rem 0.6rem",
    fontSize: "0.6rem",
    cursor: "pointer",
    fontFamily: FONTS.mono,
    transition: "all 0.2s",
  },
  card: {
    background: C.surface,
    border: `1px solid ${C.border}`,
    padding: "1.25rem 1.5rem",
  },
  sectionTitle: {
    fontSize: "0.56rem",
    letterSpacing: "0.3em",
    color: C.textMuted,
    textTransform: "uppercase",
    fontFamily: FONTS.mono,
    marginBottom: "1rem",
  },
});

/**
 * Hook to get complete admin theme
 * @returns {object} Complete theme with colors, brand info, and styles
 */
export const useAdminTheme = () => {
  const { isLaVela, shortName, fullName } = useAdminBrand();
  const C = getThemeColors(isLaVela);
  const brand = getBrandInfo(isLaVela);
  const styles = getCommonStyles(C);
  
  return {
    C,
    colors: C,
    isLaVela,
    shortName,
    fullName,
    brand,
    styles,
    fonts: FONTS,
  };
};

export default useAdminTheme;
