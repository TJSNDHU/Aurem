/**
 * ReRoots AI PWA Orders Tab
 * Displays OLD app order history in NEW luxury UI
 */

import React, { useState, useEffect } from 'react';
import { Package, Truck, CheckCircle, Clock, ChevronRight, Loader2, ArrowLeft, MapPin, Calendar, CreditCard } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Safe auth hook
const useSafeAuth = () => {
  try {
    const auth = useAuth();
    return auth || { user: null };
  } catch (e) {
    return { user: null };
  }
};

export function PWAOrders() {
  const { user } = useSafeAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedOrder, setSelectedOrder] = useState(null);

  // Fetch orders from OLD app endpoint
  useEffect(() => {
    const fetchOrders = async () => {
      if (!user) {
        setLoading(false);
        return;
      }

      try {
        const token = localStorage.getItem('reroots_token');
        const response = await fetch(`${API_URL}/api/orders/my-orders`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        if (response.ok) {
          const data = await response.json();
          setOrders(data.orders || data || []);
        } else {
          throw new Error('Failed to fetch orders');
        }
      } catch (error) {
        console.error('[PWA Orders] Fetch error:', error);
        toast.error('Failed to load orders');
      } finally {
        setLoading(false);
      }
    };

    fetchOrders();
  }, [user]);

  // Status badge styling
  const getStatusStyle = (status) => {
    switch (status?.toLowerCase()) {
      case 'delivered':
        return 'bg-green-500/20 text-green-400';
      case 'shipped':
      case 'in_transit':
        return 'bg-blue-500/20 text-blue-400';
      case 'processing':
      case 'pending':
        return 'bg-amber-500/20 text-amber-400';
      case 'cancelled':
        return 'bg-red-500/20 text-red-400';
      default:
        return 'bg-white/20 text-white/60';
    }
  };

  // Status icon
  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case 'delivered':
        return <CheckCircle className="w-5 h-5" />;
      case 'shipped':
      case 'in_transit':
        return <Truck className="w-5 h-5" />;
      default:
        return <Clock className="w-5 h-5" />;
    }
  };

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-CA', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  // If not logged in
  if (!user) {
    return (
      <div className="pb-28 px-4 pt-8 text-center">
        <Package className="w-16 h-16 text-white/20 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">Sign in to view orders</h2>
        <p className="text-white/60 text-sm">
          Your order history will appear here once you're logged in.
        </p>
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  // Order Detail View
  if (selectedOrder) {
    return (
      <div className="pb-28 px-4">
        {/* Back Button */}
        <button
          onClick={() => setSelectedOrder(null)}
          className="flex items-center gap-2 text-white/60 py-4"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back to Orders</span>
        </button>

        {/* Order Header */}
        <div className="mb-6">
          <h2 className="text-xl font-bold text-white">
            Order #{selectedOrder.order_number || selectedOrder._id?.slice(-6)}
          </h2>
          <p className="text-white/60 text-sm mt-1">
            Placed on {formatDate(selectedOrder.created_at)}
          </p>
          <span className={`inline-block mt-2 px-3 py-1 rounded-full text-sm ${getStatusStyle(selectedOrder.status)}`}>
            {selectedOrder.status || 'Processing'}
          </span>
        </div>

        {/* Order Items */}
        <div className="mb-6">
          <h3 className="font-semibold text-white mb-3">Items</h3>
          <div className="space-y-3">
            {(selectedOrder.items || []).map((item, idx) => (
              <div 
                key={idx}
                className="p-3 rounded-xl bg-white/5 border border-white/10 flex items-center gap-3"
              >
                <div className="w-16 h-16 rounded-lg bg-gradient-to-br from-white/10 to-white/5 overflow-hidden flex-shrink-0">
                  {item.product?.images?.[0] && (
                    <img 
                      src={item.product.images[0]} 
                      alt={item.product?.name}
                      className="w-full h-full object-cover"
                    />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white font-medium text-sm truncate">
                    {item.product?.name || item.name || 'Product'}
                  </p>
                  <p className="text-white/60 text-xs">
                    Qty: {item.quantity} × ${(item.price || item.product?.price || 0).toFixed(2)}
                  </p>
                </div>
                <p className="text-amber-500 font-semibold">
                  ${((item.price || item.product?.price || 0) * item.quantity).toFixed(2)}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Shipping Info */}
        {selectedOrder.shipping_address && (
          <div className="mb-6 p-4 rounded-xl bg-white/5 border border-white/10">
            <div className="flex items-center gap-2 mb-3">
              <MapPin className="w-5 h-5 text-amber-500" />
              <h3 className="font-semibold text-white">Shipping Address</h3>
            </div>
            <p className="text-white/80 text-sm">
              {selectedOrder.shipping_address.name || `${user.first_name} ${user.last_name}`}<br />
              {selectedOrder.shipping_address.address_line_1}<br />
              {selectedOrder.shipping_address.address_line_2 && `${selectedOrder.shipping_address.address_line_2}\n`}
              {selectedOrder.shipping_address.city}, {selectedOrder.shipping_address.province} {selectedOrder.shipping_address.postal_code}<br />
              {selectedOrder.shipping_address.country}
            </p>
          </div>
        )}

        {/* Order Summary */}
        <div className="p-4 rounded-xl bg-gradient-to-r from-amber-500/10 to-amber-600/10 border border-amber-500/20">
          <h3 className="font-semibold text-white mb-3">Order Summary</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-white/60">
              <span>Subtotal</span>
              <span>${(selectedOrder.subtotal || selectedOrder.total || 0).toFixed(2)}</span>
            </div>
            {selectedOrder.shipping_cost > 0 && (
              <div className="flex justify-between text-white/60">
                <span>Shipping</span>
                <span>${selectedOrder.shipping_cost.toFixed(2)}</span>
              </div>
            )}
            {selectedOrder.tax > 0 && (
              <div className="flex justify-between text-white/60">
                <span>Tax</span>
                <span>${selectedOrder.tax.toFixed(2)}</span>
              </div>
            )}
            {selectedOrder.discount > 0 && (
              <div className="flex justify-between text-green-400">
                <span>Discount</span>
                <span>-${selectedOrder.discount.toFixed(2)}</span>
              </div>
            )}
            <div className="flex justify-between text-white font-bold pt-2 border-t border-white/10">
              <span>Total</span>
              <span className="text-amber-500">${(selectedOrder.total || 0).toFixed(2)}</span>
            </div>
          </div>
        </div>

        {/* Tracking Info */}
        {selectedOrder.tracking_number && (
          <div className="mt-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/20">
            <div className="flex items-center gap-2 mb-2">
              <Truck className="w-5 h-5 text-blue-400" />
              <h3 className="font-semibold text-white">Tracking</h3>
            </div>
            <p className="text-white/80 text-sm font-mono">{selectedOrder.tracking_number}</p>
          </div>
        )}
      </div>
    );
  }

  // Orders List View
  return (
    <div className="pb-28 px-4">
      {/* Header */}
      <div className="pt-4 pb-6">
        <h2 className="text-xl font-bold text-white">My Orders</h2>
        <p className="text-white/60 text-sm">{orders.length} orders</p>
      </div>

      {/* Orders List */}
      {orders.length > 0 ? (
        <div className="space-y-3">
          {orders.map(order => (
            <button
              key={order._id || order.id || order.order_number}
              onClick={() => setSelectedOrder(order)}
              className="w-full p-4 rounded-xl bg-white/5 border border-white/10 text-left hover:bg-white/10 transition-colors"
            >
              <div className="flex items-start gap-4">
                <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${getStatusStyle(order.status)}`}>
                  {getStatusIcon(order.status)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-white font-medium">
                      Order #{order.order_number || order._id?.slice(-6)}
                    </p>
                    <ChevronRight className="w-5 h-5 text-white/40 flex-shrink-0" />
                  </div>
                  <p className="text-white/60 text-xs mb-2">
                    {formatDate(order.created_at)} • {order.items?.length || 0} items
                  </p>
                  <div className="flex items-center justify-between">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${getStatusStyle(order.status)}`}>
                      {order.status || 'Processing'}
                    </span>
                    <span className="text-amber-500 font-semibold">
                      ${(order.total || 0).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <Package className="w-16 h-16 text-white/20 mx-auto mb-4" />
          <h3 className="text-white font-semibold mb-2">No orders yet</h3>
          <p className="text-white/60 text-sm mb-6">
            Your order history will appear here once you make a purchase.
          </p>
          <Button className="bg-gradient-to-r from-amber-500 to-amber-600 text-black">
            Start Shopping
          </Button>
        </div>
      )}
    </div>
  );
}

export default PWAOrders;
