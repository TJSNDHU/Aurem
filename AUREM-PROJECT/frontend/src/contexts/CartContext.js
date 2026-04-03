import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API, getSessionId } from "@/utils/api";
import { useAuth } from "./AuthContext";

export const CartContext = createContext(null);

// Cart Provider with enhanced persistence
export const CartProvider = ({ children }) => {
  const [cart, setCart] = useState(() => {
    // Try to restore cart from localStorage for immediate display
    try {
      const cachedCart = localStorage.getItem("reroots_cart_cache");
      if (cachedCart) {
        const parsed = JSON.parse(cachedCart);
        console.log("[Cart] Restored from localStorage:", parsed?.items?.length || 0, "items");
        return parsed;
      }
    } catch (e) {
      console.error("[Cart] Failed to restore from localStorage:", e);
    }
    return { items: [] };
  });
  const [loading, setLoading] = useState(false);
  const [sideCartOpen, setSideCartOpen] = useState(false);
  const sessionId = getSessionId();
  const { user, loading: authLoading, authChecked } = useAuth();
  const lastSyncedRef = useRef(null);
  const syncTimeoutRef = useRef(null);

  // Cache cart to localStorage whenever it changes - with debounce
  useEffect(() => {
    if (cart && cart.items) {
      // Clear any pending sync
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
      
      // Debounce localStorage save to avoid excessive writes
      syncTimeoutRef.current = setTimeout(() => {
        try {
          const cartData = JSON.stringify(cart);
          localStorage.setItem("reroots_cart_cache", cartData);
          localStorage.setItem("reroots_cart_timestamp", Date.now().toString());
          console.log("[Cart] Saved to localStorage:", cart.items?.length || 0, "items");
        } catch (e) {
          console.error("[Cart] Failed to save to localStorage:", e);
        }
      }, 100);
    }
    
    return () => {
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
    };
  }, [cart]);

  const fetchCart = useCallback(async () => {
    // Wait for auth to be checked first
    if (!authChecked) return;
    
    // Avoid duplicate fetches within 2 seconds
    const now = Date.now();
    if (lastSyncedRef.current && now - lastSyncedRef.current < 2000) {
      console.log("[Cart] Skipping fetch - too recent");
      return;
    }
    
    try {
      console.log("[Cart] Fetching cart for session:", sessionId);
      // Always fetch cart using sessionId (works for both guests and logged-in users)
      const res = await axios.get(`${API}/cart/${sessionId}`, { timeout: 10000 });
      const serverItems = res.data?.items || [];
      lastSyncedRef.current = now;
      
      // Check if we have cached items in localStorage
      let cachedItems = [];
      let cacheTimestamp = 0;
      try {
        const cachedCart = localStorage.getItem("reroots_cart_cache");
        const timestamp = localStorage.getItem("reroots_cart_timestamp");
        if (cachedCart) {
          const parsed = JSON.parse(cachedCart);
          cachedItems = parsed?.items || [];
          cacheTimestamp = parseInt(timestamp) || 0;
        }
      } catch (e) {}
      
      console.log(`[Cart] Server: ${serverItems.length} items, Cached: ${cachedItems.length} items`);
      
      // If server has items, always use server data
      if (serverItems.length > 0) {
        console.log(`[Cart] Using server data: ${serverItems.length} items`);
        setCart(res.data);
      } 
      // If server is empty but we have recent cache (within 1 hour), sync cache to server
      else if (cachedItems.length > 0 && (now - cacheTimestamp) < 3600000) {
        console.log("[Cart] Server empty, syncing cached items...");
        let syncedAny = false;
        
        for (const item of cachedItems) {
          const productId = item.product_id || item.product?.id;
          if (!productId) continue;
          
          try {
            await axios.post(`${API}/cart/${sessionId}/add`, { 
              product_id: productId, 
              quantity: item.quantity || 1
            }, { timeout: 5000 });
            syncedAny = true;
          } catch (syncError) {
            console.error("[Cart] Failed to sync item:", productId, syncError.message);
          }
        }
        
        // Fetch again after sync
        if (syncedAny) {
          const syncRes = await axios.get(`${API}/cart/${sessionId}`, { timeout: 10000 });
          setCart(syncRes.data);
          console.log("[Cart] Synced", syncRes.data?.items?.length || 0, "items to server");
        } else {
          // Keep local cache if sync failed
          setCart({ items: cachedItems, session_id: sessionId });
        }
      } else {
        // Server is empty and no valid cache - set empty cart
        console.log("[Cart] Both server and cache empty");
        setCart({ items: [], session_id: sessionId });
      }
    } catch (error) {
      console.error("[Cart] Failed to fetch cart:", error.message);
      // On network error, keep cached version but don't clear it
      // This ensures cart persists even when API is unreachable
    }
  }, [sessionId, authChecked]);

  useEffect(() => {
    fetchCart();
  }, [fetchCart]);

  // Refresh cart when user logs in (to merge any guest cart)
  useEffect(() => {
    if (authChecked && user) {
      fetchCart();
    }
  }, [user, authChecked, fetchCart]);

  const addToCart = async (productId, quantity = 1) => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/cart/${sessionId}/add`, { product_id: productId, quantity });
      setCart(res.data);
      // Open side cart
      setSideCartOpen(true);
      toast.success("Added to bag!");
    } catch (error) {
      console.error("Cart error:", error);
      toast.error("Failed to add to cart");
    }
    setLoading(false);
  };

  // Add a combo to cart with its discounted price
  const addComboToCart = async (comboId, quantity = 1) => {
    console.log('[CartContext] addComboToCart called');
    console.log('[CartContext] comboId:', comboId);
    console.log('[CartContext] sessionId:', sessionId);
    console.log('[CartContext] API URL:', `${API}/cart/${sessionId}/add-combo`);
    
    if (!sessionId) {
      console.error('[CartContext] No sessionId available!');
      toast.error("Session error. Please refresh the page.");
      return;
    }
    
    if (!comboId) {
      console.error('[CartContext] No comboId provided!');
      toast.error("Invalid combo. Please try again.");
      return;
    }
    
    setLoading(true);
    try {
      const payload = { combo_id: comboId, quantity };
      console.log('[CartContext] Sending payload:', JSON.stringify(payload));
      
      const res = await axios.post(`${API}/cart/${sessionId}/add-combo`, payload);
      console.log('[CartContext] Response:', res.data);
      
      setCart(res.data);
      setSideCartOpen(true);
      toast.success("Combo added to bag!");
    } catch (error) {
      console.error("[CartContext] Cart error:", error);
      console.error("[CartContext] Error response:", error?.response?.data);
      console.error("[CartContext] Error status:", error?.response?.status);
      toast.error("Failed to add combo to cart");
      throw error; // Re-throw so the caller can catch it
    }
    setLoading(false);
  };

  const updateQuantity = async (productId, quantity) => {
    setLoading(true);
    try {
      const res = await axios.put(`${API}/cart/${sessionId}/update`, { product_id: productId, quantity });
      setCart(res.data);
    } catch (error) {
      toast.error("Failed to update cart");
    }
    setLoading(false);
  };

  const removeItem = async (productId) => {
    setLoading(true);
    try {
      const res = await axios.delete(`${API}/cart/${sessionId}/item/${productId}`);
      setCart(res.data);
      toast.success("Item removed");
    } catch (error) {
      toast.error("Failed to remove item");
    }
    setLoading(false);
  };

  const clearCart = async () => {
    try {
      await axios.delete(`${API}/cart/${sessionId}`);
      setCart({ items: [] });
      localStorage.removeItem("reroots_cart_cache");
    } catch (error) {
      console.error("Failed to clear cart:", error);
    }
  };

  const itemCount = cart.items?.reduce((sum, item) => sum + item.quantity, 0) || 0;
  
  // Calculate effective price accounting for combo items or product discount_percent
  const getEffectivePrice = (item) => {
    // New combo structure: item_type === "combo" uses item.price
    if (item.item_type === "combo") {
      return item.price || 0;
    }
    // Legacy combo support: combo_price field
    if (item.combo_price !== undefined && item.combo_price !== null) {
      return item.combo_price;
    }
    // Regular product: use product price with discount
    const product = item.product;
    if (!product) return 0;
    const price = product.price || 0;
    const discount = product.discount_percent || 0;
    return discount > 0 ? price * (1 - discount / 100) : price;
  };
  
  const subtotal = cart.items?.reduce((sum, item) => sum + getEffectivePrice(item) * item.quantity, 0) || 0;

  return (
    <CartContext.Provider value={{ 
      cart, 
      addToCart,
      addComboToCart, 
      updateQuantity, 
      removeItem, 
      clearCart, 
      itemCount, 
      subtotal, 
      loading, 
      sessionId, 
      fetchCart, 
      sideCartOpen, 
      setSideCartOpen,
      getEffectivePrice
    }}>
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => useContext(CartContext);
