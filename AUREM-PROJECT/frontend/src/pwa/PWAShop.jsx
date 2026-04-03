/**
 * ReRoots AI PWA Shop Component
 * Mobile-optimized product browsing - MERGED with OLD cart context
 */

import React, { useState, useEffect } from 'react';
import { Search, Filter, ShoppingBag, Heart, Star, Loader2, X, Plus, Minus, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useCart } from '@/contexts/CartContext';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Safe cart hook
const useSafeCart = () => {
  try {
    const cart = useCart();
    return cart || { cart: { items: [] }, itemCount: 0, addToCart: async () => {}, loading: false, setSideCartOpen: () => {} };
  } catch (e) {
    return { cart: { items: [] }, itemCount: 0, addToCart: async () => {}, loading: false, setSideCartOpen: () => {} };
  }
};

export function PWAShop() {
  // Use OLD cart context for unified cart state
  const { cart, addToCart, itemCount, loading: cartLoading, setSideCartOpen } = useSafeCart();
  
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedProduct, setSelectedProduct] = useState(null);

  // Fetch products
  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const response = await fetch(`${API_URL}/api/products`);
        if (response.ok) {
          const data = await response.json();
          setProducts(data.products || data || []);
          
          // Extract unique categories
          const cats = [...new Set((data.products || data || []).map(p => p.category).filter(Boolean))];
          setCategories(cats);
        }
      } catch (error) {
        console.error('[PWA Shop] Fetch error:', error);
        toast.error('Failed to load products');
      } finally {
        setLoading(false);
      }
    };
    
    fetchProducts();
  }, []);

  // Filter products
  const filteredProducts = products.filter(product => {
    const matchesSearch = !searchQuery || 
      product.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      product.description?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesCategory = selectedCategory === 'all' || product.category === selectedCategory;
    
    return matchesSearch && matchesCategory;
  });

  // Add to cart - uses OLD cart context (unified with main app)
  const handleAddToCart = async (product) => {
    const productId = product.id || product._id;
    await addToCart(productId, 1);
    // toast.success is handled by CartContext
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="pb-28 px-4">
      {/* Header */}
      <div className="pt-4 pb-6 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Shop</h2>
          <p className="text-white/60 text-sm">{products.length} products</p>
        </div>
        
        <button 
          onClick={() => setSideCartOpen(true)}
          className="relative w-12 h-12 rounded-full bg-white/10 flex items-center justify-center"
        >
          <ShoppingBag className="w-6 h-6 text-white" />
          {itemCount > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-amber-500 text-black text-xs font-bold flex items-center justify-center">
              {itemCount > 9 ? '9+' : itemCount}
            </span>
          )}
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
        <input
          type="text"
          placeholder="Search products..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full h-12 pl-12 pr-4 rounded-xl bg-white/10 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-amber-500/50"
        />
      </div>

      {/* Categories */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-hide">
        <button
          onClick={() => setSelectedCategory('all')}
          className={`px-4 py-2 rounded-full whitespace-nowrap text-sm font-medium transition-all ${
            selectedCategory === 'all'
              ? 'bg-amber-500 text-black'
              : 'bg-white/10 text-white/80'
          }`}
        >
          All
        </button>
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`px-4 py-2 rounded-full whitespace-nowrap text-sm font-medium transition-all ${
              selectedCategory === cat
                ? 'bg-amber-500 text-black'
                : 'bg-white/10 text-white/80'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Products Grid */}
      <div className="grid grid-cols-2 gap-3">
        {filteredProducts.map(product => (
          <div 
            key={product.id || product._id}
            className="rounded-2xl overflow-hidden bg-white/5 border border-white/10"
          >
            {/* Product Image */}
            <button
              onClick={() => setSelectedProduct(product)}
              className="w-full aspect-square bg-gradient-to-br from-white/10 to-white/5 relative"
            >
              {product.images?.[0] && (
                <img 
                  src={product.images[0]} 
                  alt={product.name}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
              )}
              
              {/* Badges */}
              <div className="absolute top-2 left-2 flex flex-col gap-1">
                {product.is_bestseller && (
                  <span className="px-2 py-0.5 rounded-full bg-amber-500 text-black text-[10px] font-semibold">
                    BESTSELLER
                  </span>
                )}
                {product.discount_percent > 0 && (
                  <span className="px-2 py-0.5 rounded-full bg-red-500 text-white text-[10px] font-semibold">
                    {product.discount_percent}% OFF
                  </span>
                )}
              </div>
              
              {/* Wishlist */}
              <button 
                className="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/50 flex items-center justify-center"
                onClick={(e) => {
                  e.stopPropagation();
                  toast.success('Added to wishlist');
                }}
              >
                <Heart className="w-4 h-4 text-white" />
              </button>
            </button>

            {/* Product Info */}
            <div className="p-3">
              <h3 className="text-white text-sm font-medium line-clamp-2 min-h-[2.5rem]">
                {product.name}
              </h3>
              
              {/* Rating */}
              {product.rating && (
                <div className="flex items-center gap-1 mt-1">
                  <Star className="w-3 h-3 text-amber-500 fill-amber-500" />
                  <span className="text-white/60 text-xs">{product.rating}</span>
                </div>
              )}
              
              {/* Price */}
              <div className="flex items-center justify-between mt-2">
                <div>
                  <span className="text-amber-500 font-bold">
                    ${product.discount_percent 
                      ? (product.price * (1 - product.discount_percent / 100)).toFixed(2)
                      : product.price?.toFixed(2)
                    }
                  </span>
                  {product.discount_percent > 0 && (
                    <span className="ml-2 text-white/40 text-xs line-through">
                      ${product.price?.toFixed(2)}
                    </span>
                  )}
                </div>
                
                <button
                  onClick={() => handleAddToCart(product)}
                  disabled={cartLoading}
                  className="w-8 h-8 rounded-full bg-amber-500 flex items-center justify-center disabled:opacity-50"
                >
                  <Plus className="w-4 h-4 text-black" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* No Results */}
      {filteredProducts.length === 0 && (
        <div className="text-center py-12">
          <p className="text-white/60">No products found</p>
        </div>
      )}

      {/* Product Detail Modal */}
      {selectedProduct && (
        <ProductDetailModal 
          product={selectedProduct} 
          onClose={() => setSelectedProduct(null)}
          onAddToCart={handleAddToCart}
          cartLoading={cartLoading}
        />
      )}
    </div>
  );
}

/**
 * Product Detail Modal
 */
function ProductDetailModal({ product, onClose, onAddToCart, cartLoading }) {
  const [quantity, setQuantity] = useState(1);
  const [isAdding, setIsAdding] = useState(false);
  
  const effectivePrice = product.discount_percent
    ? product.price * (1 - product.discount_percent / 100)
    : product.price;

  return (
    <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-xl">
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 z-10 w-10 h-10 rounded-full bg-white/10 flex items-center justify-center"
      >
        <X className="w-6 h-6 text-white" />
      </button>

      <div className="h-full overflow-y-auto pb-32">
        {/* Product Image */}
        <div className="aspect-square bg-gradient-to-br from-white/10 to-white/5">
          {product.images?.[0] && (
            <img 
              src={product.images[0]} 
              alt={product.name}
              className="w-full h-full object-cover"
            />
          )}
        </div>

        {/* Product Info */}
        <div className="p-6">
          <h1 className="text-2xl font-bold text-white">{product.name}</h1>
          
          {/* Rating */}
          {product.rating && (
            <div className="flex items-center gap-2 mt-2">
              <div className="flex items-center gap-0.5">
                {[...Array(5)].map((_, i) => (
                  <Star 
                    key={i}
                    className={`w-4 h-4 ${
                      i < Math.floor(product.rating) 
                        ? 'text-amber-500 fill-amber-500' 
                        : 'text-white/20'
                    }`}
                  />
                ))}
              </div>
              <span className="text-white/60 text-sm">
                {product.rating} ({product.review_count || 0} reviews)
              </span>
            </div>
          )}

          {/* Price */}
          <div className="mt-4 flex items-baseline gap-3">
            <span className="text-3xl font-bold text-amber-500">
              ${effectivePrice.toFixed(2)}
            </span>
            {product.discount_percent > 0 && (
              <span className="text-white/40 text-lg line-through">
                ${product.price?.toFixed(2)}
              </span>
            )}
          </div>

          {/* Description */}
          <p className="mt-4 text-white/70 leading-relaxed">
            {product.description || product.short_description}
          </p>

          {/* Benefits */}
          {product.benefits && product.benefits.length > 0 && (
            <div className="mt-6">
              <h3 className="font-semibold text-white mb-3">Key Benefits</h3>
              <ul className="space-y-2">
                {product.benefits.slice(0, 4).map((benefit, i) => (
                  <li key={i} className="flex items-start gap-2 text-white/70 text-sm">
                    <ChevronRight className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                    {benefit}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Ingredients */}
          {product.key_ingredients && product.key_ingredients.length > 0 && (
            <div className="mt-6">
              <h3 className="font-semibold text-white mb-3">Key Ingredients</h3>
              <div className="flex flex-wrap gap-2">
                {product.key_ingredients.slice(0, 6).map((ing, i) => (
                  <span 
                    key={i}
                    className="px-3 py-1 rounded-full bg-white/10 text-white/70 text-xs"
                  >
                    {typeof ing === 'string' ? ing : ing.name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black via-black/95 to-transparent">
        <div className="flex items-center gap-4">
          {/* Quantity */}
          <div className="flex items-center gap-2 bg-white/10 rounded-xl px-2">
            <button
              onClick={() => setQuantity(q => Math.max(1, q - 1))}
              className="w-10 h-10 flex items-center justify-center"
            >
              <Minus className="w-4 h-4 text-white" />
            </button>
            <span className="w-8 text-center text-white font-semibold">{quantity}</span>
            <button
              onClick={() => setQuantity(q => q + 1)}
              className="w-10 h-10 flex items-center justify-center"
            >
              <Plus className="w-4 h-4 text-white" />
            </button>
          </div>

          {/* Add to Cart */}
          <Button
            onClick={async () => {
              setIsAdding(true);
              for (let i = 0; i < quantity; i++) {
                await onAddToCart(product);
              }
              setIsAdding(false);
              onClose();
            }}
            disabled={isAdding || cartLoading}
            className="flex-1 h-12 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-black font-semibold rounded-xl disabled:opacity-50"
          >
            {isAdding ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              `Add to Cart — $${(effectivePrice * quantity).toFixed(2)}`
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default PWAShop;
