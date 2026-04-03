import { createContext, useContext } from 'react';

// Brand Context (Multi-tenant)
export { BrandProvider, useBrand, BRAND_CONFIGS } from './BrandContext';

// Auth Context
export const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

// Cart Context - Import from CartContext.js to get the actual context with all methods
export { CartContext, CartProvider, useCart } from './CartContext';

// Site Content Context
export const SiteContentContext = createContext(null);
export const useSiteContent = () => useContext(SiteContentContext);

// Store Settings Context
export const StoreSettingsContext = createContext(null);
export const useStoreSettings = () => useContext(StoreSettingsContext);

// Global Background Context
export const GlobalBackgroundContext = createContext(null);
export const useGlobalBackground = () => useContext(GlobalBackgroundContext);

// Typography Context
export const TypographyContext = createContext(null);
export const useTypography = () => useContext(TypographyContext);

// Currency Context
export const CurrencyContext = createContext(null);
export const useCurrency = () => useContext(CurrencyContext);

// Wishlist Context
export const WishlistContext = createContext(null);
export const useWishlist = () => useContext(WishlistContext);

// Translation Context
export const TranslationContext = createContext(null);
export const useTranslation = () => useContext(TranslationContext);

// Re-export WebSocket context for convenience
export { WebSocketProvider, useWebSocket, useWebSocketEvent } from './WebSocketContext';
