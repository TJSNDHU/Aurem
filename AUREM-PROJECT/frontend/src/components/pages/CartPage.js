import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShoppingBag, Plus, Minus, Trash2, ArrowLeft, Sparkles, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useCart, useTranslation } from "@/contexts";

// UI Translations fallback
const UI_TRANSLATIONS = {
  en: { cart: "Shopping Cart", checkout: "Checkout", continueShopping: "Continue Shopping", emptyCart: "Your cart is empty", subtotal: "Subtotal" }
};

const BackButton = ({ className = "", label = "Back" }) => {
  const navigate = useNavigate();
  
  const handleBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/');
    }
  };
  
  return (
    <Button 
      variant="ghost" 
      onClick={handleBack}
      className={`flex items-center gap-2 text-[#5A5A5A] hover:text-[#2D2A2E] ${className}`}
    >
      <ArrowLeft className="h-4 w-4" />
      {label}
    </Button>
  );
};

const CartPage = () => {
  const { cart, updateQuantity, removeItem, subtotal } = useCart();
  const navigate = useNavigate();
  const { currentLang } = useTranslation() || {};
  const lang = currentLang || "en";
  const t = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS.en;
  
  const tax = subtotal * 0.13;
  const shipping = subtotal >= 75 ? 0 : 10;
  const total = subtotal + tax + shipping;

  if (!cart.items?.length) {
    return (
      <div className="min-h-screen pt-24 bg-[#FDF9F9]">
        <div className="max-w-3xl mx-auto px-6 md:px-12 py-16 text-center">
          <ShoppingBag className="h-16 w-16 text-[#888888] mx-auto mb-4" />
          <h1 className="font-display text-3xl font-bold text-[#2D2A2E] mb-4" data-testid="empty-cart-title">{t.cart_empty || "Your Cart is Empty"}</h1>
          <p className="text-[#5A5A5A] mb-8">{t.discover_collection || "Discover our biotech skincare collection."}</p>
          <Link to="/products">
            <Button className="btn-primary" data-testid="continue-shopping">{t.continue_shopping || "Continue Shopping"}</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 bg-[#FDF9F9]">
      <div className="max-w-7xl mx-auto px-6 md:px-12 py-12">
        <BackButton className="mb-6" label="Continue Shopping" />
        
        <h1 className="font-display text-3xl font-bold text-[#2D2A2E] mb-8" data-testid="cart-title">{t.your_cart || "Shopping Cart"}</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
          <div className="lg:col-span-2 space-y-4">
            {cart.items.map(item => {
              // Check if this is a combo item (new structure)
              const isCombo = item.item_type === "combo";
              
              if (isCombo) {
                // Render COMBO as single line item
                const comboPrice = item.price || 0;
                return (
                  <div key={item.combo_id} className="p-4 bg-white border border-purple-200 rounded-lg" data-testid={`cart-combo-${item.combo_id}`}>
                    {/* Combo Header */}
                    <div className="flex items-center gap-2 mb-3">
                      <span className="inline-flex items-center gap-1 px-3 py-1 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-xs font-semibold rounded-full">
                        <Sparkles className="w-3 h-3" /> COMBO DEAL
                      </span>
                      <span className="text-xs text-green-600 font-medium">
                        Save {Number(item.discount_percent || 0).toFixed(0)}%
                      </span>
                    </div>
                    
                    <h3 className="font-display font-semibold text-[#2D2A2E] mb-3">
                      {item.combo_name}
                    </h3>
                    
                    {/* Products in Combo */}
                    <div className="space-y-2 mb-4">
                      {item.products?.map((product, idx) => (
                        <div key={product.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                          <img
                            src={product.images?.[0] || "/placeholder.png"}
                            alt={product.name}
                            className="w-12 h-12 object-cover rounded-lg"
                          />
                          <div className="flex-1">
                            <p className="text-sm font-medium">{product.name}</p>
                            <p className="text-xs text-gray-500">Step {idx + 1}</p>
                          </div>
                          <CheckCircle2 className="w-4 h-4 text-green-500" />
                        </div>
                      ))}
                    </div>
                    
                    {/* Price & Quantity */}
                    <div className="flex items-center justify-between pt-3 border-t">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8 rounded-full"
                          onClick={() => updateQuantity(item.product_id, item.quantity - 1)}
                        >
                          <Minus className="h-3 w-3" />
                        </Button>
                        <span className="w-8 text-center">{item.quantity}</span>
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8 rounded-full"
                          onClick={() => updateQuantity(item.product_id, item.quantity + 1)}
                        >
                          <Plus className="h-3 w-3" />
                        </Button>
                      </div>
                      
                      <div className="text-right">
                        <p className="font-semibold text-lg">${(comboPrice * item.quantity).toFixed(2)} CAD</p>
                        {item.original_price && (
                          <p className="text-sm text-gray-400 line-through">${(item.original_price * item.quantity).toFixed(2)}</p>
                        )}
                      </div>
                    </div>
                    
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeItem(item.product_id)}
                      className="mt-2 text-gray-400 hover:text-red-500"
                    >
                      <Trash2 className="h-4 w-4 mr-1" /> Remove combo
                    </Button>
                  </div>
                );
              }
              
              // Legacy combo item support (with combo_price field)
              const effectivePrice = item.combo_price !== undefined && item.combo_price !== null
                ? item.combo_price
                : item.product?.discount_percent 
                  ? (item.product.price * (1 - item.product.discount_percent / 100)) 
                  : item.product?.price || 0;
              const isLegacyCombo = item.combo_price !== undefined && item.combo_price !== null;
              
              // Render REGULAR product item
              return (
              <div key={item.product_id} className="flex gap-4 p-4 bg-white border border-gray-100" data-testid={`cart-item-${item.product_id}`}>
                <Link to={`/products/${item.product?.slug}`} className="flex-shrink-0">
                  <img
                    src={item.product?.images?.[0] || "https://via.placeholder.com/100"}
                    alt={item.product?.name}
                    className="w-24 h-24 object-cover"
                  />
                </Link>
                <div className="flex-1 min-w-0">
                  <Link to={`/products/${item.product?.slug}`}>
                    <h3 className="font-display font-semibold text-[#2D2A2E] hover:text-[#F8A5B8] transition-colors line-clamp-1">
                      {item.product?.name}
                    </h3>
                  </Link>
                  {item.combo_name && (
                    <p className="text-xs text-purple-600 font-medium">{item.combo_name}</p>
                  )}
                  {isLegacyCombo ? (
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-purple-600">${effectivePrice.toFixed(2)} CAD</span>
                      {item.original_price && item.original_price > effectivePrice && (
                        <span className="text-xs text-[#888888] line-through">${item.original_price.toFixed(2)}</span>
                      )}
                      <span className="text-xs bg-purple-500 text-white px-1.5 py-0.5 rounded">COMBO</span>
                    </div>
                  ) : item.product?.discount_percent ? (
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[#F8A5B8]">${effectivePrice.toFixed(2)} CAD</span>
                      <span className="text-xs text-[#888888] line-through">${item.product?.price?.toFixed(2)}</span>
                      <span className="text-xs bg-[#F8A5B8] text-white px-1.5 py-0.5 rounded">{item.product.discount_percent}% OFF</span>
                    </div>
                  ) : (
                    <p className="text-sm text-[#5A5A5A]">${item.product?.price?.toFixed(2)} CAD</p>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-8 w-8 rounded-full"
                      onClick={() => updateQuantity(item.product_id, item.quantity - 1)}
                      data-testid={`decrease-${item.product_id}`}
                    >
                      <Minus className="h-3 w-3" />
                    </Button>
                    <span className="w-8 text-center">{item.quantity}</span>
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-8 w-8 rounded-full"
                      onClick={() => updateQuantity(item.product_id, item.quantity + 1)}
                      data-testid={`increase-${item.product_id}`}
                    >
                      <Plus className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
                <div className="flex flex-col items-end justify-between">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeItem(item.product_id)}
                    className="text-[#888888] hover:text-red-500"
                    data-testid={`remove-${item.product_id}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                  <span className="font-bold text-[#2D2A2E]">
                    ${(effectivePrice * item.quantity).toFixed(2)}
                  </span>
                </div>
              </div>
            );})}
          </div>

          <div className="lg:col-span-1">
            <Card className="sticky top-32">
              <CardHeader>
                <CardTitle className="font-display">{t.order_summary || "Order Summary"}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(() => {
                  // Calculate original subtotal from original prices (before combo discounts)
                  const originalSubtotal = cart.items?.reduce((sum, item) => {
                    // If combo item, use original_price, otherwise use product price
                    const originalPrice = item.original_price || item.product?.price || 0;
                    return sum + originalPrice * item.quantity;
                  }, 0) || 0;
                  
                  // subtotal from context already uses combo_price when available
                  const productDiscount = originalSubtotal - subtotal;
                  const taxAmount = subtotal * 0.13;
                  const shippingAmount = subtotal >= 75 ? 0 : 10;
                  const finalTotal = subtotal + taxAmount + shippingAmount;
                  
                  return (
                    <>
                      <div className="flex justify-between">
                        <span className="text-[#5A5A5A]">Products Subtotal</span>
                        <span>${originalSubtotal.toFixed(2)}</span>
                      </div>
                      
                      {productDiscount > 0 && (
                        <div className="flex justify-between text-green-600">
                          <span>Product Discount</span>
                          <span>-${productDiscount.toFixed(2)}</span>
                        </div>
                      )}
                      
                      {productDiscount > 0 && (
                        <div className="flex justify-between font-medium">
                          <span className="text-[#5A5A5A]">After Discount</span>
                          <span>${subtotal.toFixed(2)}</span>
                        </div>
                      )}
                      
                      <div className="flex justify-between">
                        <span className="text-[#5A5A5A]">{t.tax || "Tax"} (13% HST)</span>
                        <span>${taxAmount.toFixed(2)}</span>
                      </div>
                      
                      <div className="flex justify-between">
                        <span className="text-[#5A5A5A]">{t.shipping || "Shipping"}</span>
                        <span>{shippingAmount === 0 ? <span className="text-green-600">{t.free || "FREE"}</span> : `$${shippingAmount.toFixed(2)}`}</span>
                      </div>
                      
                      <Separator />
                      
                      <div className="flex justify-between font-bold text-lg">
                        <span>{t.total || "Total"}</span>
                        <span>${finalTotal.toFixed(2)} CAD</span>
                      </div>
                      
                      {originalSubtotal < 75 && (
                        <p className="text-sm text-[#F8A5B8]">
                          {t.free_shipping_msg || `Add $${(75 - originalSubtotal).toFixed(2)} more for free shipping!`}
                        </p>
                      )}
                    </>
                  );
                })()}
                <Button className="w-full btn-primary" onClick={() => navigate("/checkout")} data-testid="checkout-btn">
                  Proceed to Checkout
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CartPage;
