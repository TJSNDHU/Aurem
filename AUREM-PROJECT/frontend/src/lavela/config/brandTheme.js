/**
 * La Vela Bianca Brand Theme Configuration
 * This file contains all brand-specific theming for La Vela Bianca.
 * For future platform separation, copy this entire /lavela folder.
 */

export const LAVELA_BRAND = {
  id: 'lavela',
  name: 'La Vela Bianca',
  shortName: 'LA VELA',
  fullName: 'La Vela Bianca Inc.',
  domain: 'lavelabianca.com',
  tagline: 'Luxury Teen Skincare',
  ageRange: '8-18',
};

export const LAVELA_COLORS = {
  // Primary palette
  bg: "#0D4D4D",
  surface: "#1A6B6B",
  surfaceAlt: "#1A6B6B40",
  surfaceHover: "#1A6B6B80",
  
  // Borders
  border: "#D4A57440",
  borderLight: "#D4A57430",
  borderBright: "#D4A57460",
  
  // Accent colors
  gold: "#D4A574",
  goldDim: "#E6BE8A",
  goldFaint: "rgba(212,165,116,0.15)",
  
  // Status colors
  green: "#72B08A",
  greenBright: "#72B08A",
  greenFaint: "rgba(114,176,138,0.15)",
  
  red: "#E07070",
  redBright: "#E07070",
  redFaint: "rgba(224,112,112,0.15)",
  
  amber: "#E8A860",
  amberFaint: "rgba(232,168,96,0.15)",
  
  blue: "#7AAEC8",
  blueBright: "#7AAEC8",
  blueFaint: "rgba(122,174,200,0.15)",
  
  purple: "#9878D0",
  purpleBright: "#9878D0",
  purpleFaint: "rgba(152,120,208,0.15)",
  
  teal: "#72B0B0",
  tealBright: "#72B0B0",
  
  // Text colors
  text: "#FDF8F5",
  textDim: "#D4A574",
  textMuted: "#E8C4B8",
  white: "#FDF8F5",
  
  // Gradients
  headerGradient: "linear-gradient(180deg, #0A3C3C 0%, transparent 100%)",
};

export const LAVELA_FONTS = {
  display: "'Cormorant Garamond', Georgia, serif",
  sans: "'Inter', system-ui, sans-serif",
  mono: "'JetBrains Mono', 'Courier New', monospace",
};

export const LAVELA_PRODUCTS = [
  { id: 'LV-001', name: 'Teen Glow Cleanser', price: 45, category: 'Cleanser' },
  { id: 'LV-002', name: 'Clear Skin Serum', price: 65, category: 'Treatment' },
  { id: 'LV-003', name: 'Daily Hydration SPF', price: 55, category: 'Moisturizer' },
  { id: 'LV-004', name: 'Acne Defense Gel', price: 35, category: 'Treatment' },
  { id: 'LV-005', name: 'Gentle Night Cream', price: 48, category: 'Moisturizer' },
];

export default {
  brand: LAVELA_BRAND,
  colors: LAVELA_COLORS,
  fonts: LAVELA_FONTS,
  products: LAVELA_PRODUCTS,
};
