/**
 * La Vela Bianca Configuration Index
 * Export all La Vela specific configurations from this file.
 */

export { default as brandTheme, LAVELA_BRAND, LAVELA_COLORS, LAVELA_FONTS, LAVELA_PRODUCTS } from './brandTheme';

// Feature flags for La Vela specific features
export const LAVELA_FEATURES = {
  teenSkinQuiz: true,
  parentalControls: true,
  ageVerification: true,
  schoolPartnership: true,
  socialSharing: false, // Disabled for teens
};

// La Vela specific routes
export const LAVELA_ROUTES = {
  home: '/la-vela-bianca',
  products: '/la-vela-bianca/products',
  quiz: '/la-vela-bianca/skin-quiz',
  about: '/la-vela-bianca/about',
};
