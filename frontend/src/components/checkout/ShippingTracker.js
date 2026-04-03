import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Package, Truck, CheckCircle, Clock, MapPin, RefreshCw, ExternalLink } from 'lucide-react';
import { Button } from '../ui/button';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Shipping status steps
const SHIPPING_STEPS = [
  { id: 'confirmed', label: 'Order Confirmed', icon: CheckCircle },
  { id: 'processing', label: 'Label Created', icon: Package },
  { id: 'shipped', label: 'Shipped', icon: Truck },
  { id: 'in_transit', label: 'In Transit', icon: MapPin },
  { id: 'delivered', label: 'Delivered', icon: CheckCircle },
];

const ShippingTracker = ({ orderId, initialOrder = null }) => {
  const [order, setOrder] = useState(initialOrder);
  const [trackingInfo, setTrackingInfo] = useState(null);
  const [loading, setLoading] = useState(!initialOrder); // Only show loading if no initial order
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [hasInitialLoad, setHasInitialLoad] = useState(!!initialOrder);

  // Fetch order and tracking info
  const fetchOrderStatus = async (showLoading = false) => {
    if (!orderId) return;
    
    // Only show loading on initial fetch, not on refresh
    if (showLoading && !hasInitialLoad) {
      setLoading(true);
    }
    setError(null);
    
    try {
      // Fetch order details
      const orderRes = await axios.get(`${API}/orders/${orderId}`);
      setOrder(orderRes.data);
      setHasInitialLoad(true);
      
      // If order has tracking number, fetch tracking info
      if (orderRes.data?.tracking_number) {
        try {
          const trackingRes = await axios.get(`${API}/shipping/track/${orderRes.data.tracking_number}`);
          setTrackingInfo(trackingRes.data);
        } catch (trackError) {
          console.log('Tracking info not available:', trackError);
        }
      }
      
      setLastRefresh(new Date());
    } catch (err) {
      setError('Unable to fetch order status');
      console.error('Order fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (orderId && !initialOrder) {
      fetchOrderStatus(true); // Show loading on initial fetch
    }
    
    // Auto-refresh every 60 seconds if order is in transit (reduced from 30s)
    const interval = setInterval(() => {
      if (order?.order_status === 'shipped' || order?.order_status === 'in_transit') {
        fetchOrderStatus(false); // Don't show loading on refresh
      }
    }, 60000);
    
    return () => clearInterval(interval);
  }, [orderId]);

  // Determine current step based on order status
  const getCurrentStep = () => {
    if (!order) return 0;
    
    const status = order.order_status?.toLowerCase() || 'pending';
    const paymentStatus = order.payment_status?.toLowerCase();
    
    // Map order status to step index
    if (status === 'delivered') return 4;
    if (status === 'in_transit') return 3;
    if (status === 'shipped') return 2;
    if (status === 'processing' || order.tracking_number) return 1;
    if (paymentStatus === 'paid' || status === 'confirmed') return 0;
    
    return 0;
  };

  const currentStep = getCurrentStep();

  // Format date for display
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-CA', { 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Get status message
  const getStatusMessage = () => {
    if (!order) return 'Loading order details...';
    
    if (order.order_status === 'delivered') {
      return 'Your order has been delivered!';
    }
    
    if (order.order_status === 'shipped' || order.order_status === 'in_transit') {
      return `Your package is on the way with ${order.shipping_carrier || 'the courier'}`;
    }
    
    if (order.tracking_number) {
      return 'Shipping label created - awaiting pickup';
    }
    
    if (order.payment_status === 'paid') {
      return 'Payment confirmed - preparing your order';
    }
    
    return 'Order received - processing payment';
  };

  // Get estimated delivery
  const getEstimatedDelivery = () => {
    if (trackingInfo?.estimated_delivery) {
      return formatDate(trackingInfo.estimated_delivery);
    }
    
    if (order?.shipped_at) {
      // Estimate 5-8 business days from ship date
      const shipDate = new Date(order.shipped_at);
      const minDelivery = new Date(shipDate);
      minDelivery.setDate(minDelivery.getDate() + 5);
      const maxDelivery = new Date(shipDate);
      maxDelivery.setDate(maxDelivery.getDate() + 8);
      return `${minDelivery.toLocaleDateString('en-CA', { month: 'short', day: 'numeric' })} - ${maxDelivery.toLocaleDateString('en-CA', { month: 'short', day: 'numeric' })}`;
    }
    
    return '5-8 business days';
  };

  if (error && !order) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
        <p className="text-red-600 text-sm">{error}</p>
        <Button 
          variant="ghost" 
          size="sm" 
          className="mt-2"
          onClick={() => fetchOrderStatus(true)}
        >
          <RefreshCw className="h-4 w-4 mr-1" /> Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden" data-testid="shipping-tracker">
      {/* Header */}
      <div className="bg-gradient-to-r from-[#2D2A2E] to-[#4A4548] p-4 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Truck className="h-5 w-5" />
            <h3 className="font-semibold">Shipping Status</h3>
          </div>
          <Button 
            variant="ghost" 
            size="sm" 
            className="text-white hover:bg-white/20 h-8"
            onClick={() => fetchOrderStatus(false)}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        <p className="text-white/80 text-sm mt-1">{getStatusMessage()}</p>
      </div>

      {/* Progress Steps */}
      <div className="p-4">
        <div className="relative">
          {/* Progress Line */}
          <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-gray-200">
            <div 
              className="w-full bg-gradient-to-b from-[#F8A5B8] to-[#D4AF37] transition-all duration-500"
              style={{ height: `${(currentStep / (SHIPPING_STEPS.length - 1)) * 100}%` }}
            />
          </div>

          {/* Steps */}
          <div className="space-y-6">
            {SHIPPING_STEPS.map((step, index) => {
              const isCompleted = index <= currentStep;
              const isCurrent = index === currentStep;
              const Icon = step.icon;
              
              return (
                <div key={step.id} className="flex items-start gap-4 relative">
                  {/* Icon Circle */}
                  <div className={`
                    w-10 h-10 rounded-full flex items-center justify-center z-10
                    transition-all duration-300
                    ${isCompleted 
                      ? 'bg-gradient-to-br from-[#F8A5B8] to-[#D4AF37] text-white' 
                      : 'bg-gray-100 text-gray-400'
                    }
                    ${isCurrent ? 'ring-4 ring-[#F8A5B8]/30 scale-110' : ''}
                  `}>
                    <Icon className="h-5 w-5" />
                  </div>
                  
                  {/* Step Info */}
                  <div className="flex-1 pt-1.5">
                    <p className={`font-medium ${isCompleted ? 'text-[#2D2A2E]' : 'text-gray-400'}`}>
                      {step.label}
                    </p>
                    
                    {/* Show additional info for current/completed steps */}
                    {isCompleted && (
                      <div className="text-sm text-gray-500 mt-1">
                        {step.id === 'confirmed' && order?.paid_at && (
                          <span>{formatDate(order.paid_at)}</span>
                        )}
                        {step.id === 'processing' && order?.tracking_number && (
                          <span className="font-mono">{order.tracking_number}</span>
                        )}
                        {step.id === 'shipped' && order?.shipped_at && (
                          <span>
                            {formatDate(order.shipped_at)}
                            {order.shipping_carrier && ` via ${order.shipping_carrier}`}
                          </span>
                        )}
                        {step.id === 'delivered' && trackingInfo?.delivered_at && (
                          <span>{formatDate(trackingInfo.delivered_at)}</span>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {/* Current Step Indicator */}
                  {isCurrent && index < SHIPPING_STEPS.length - 1 && (
                    <div className="absolute left-12 top-12 text-xs text-[#D4AF37] flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      <span>In Progress</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Tracking Info Footer */}
      {order?.tracking_number && (
        <div className="border-t bg-gray-50 p-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Tracking Number</p>
              <p className="font-mono font-semibold text-[#2D2A2E]">{order.tracking_number}</p>
              {order.shipping_carrier && (
                <p className="text-sm text-gray-600">{order.shipping_carrier}</p>
              )}
            </div>
            
            <div className="flex gap-2">
              {order.tracking_url && (
                <a 
                  href={order.tracking_url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-3 py-2 bg-[#2D2A2E] text-white text-sm rounded-lg hover:bg-[#2D2A2E]/90 transition-colors"
                >
                  Track Package
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
              
              {order.shipping_label_url && (
                <a 
                  href={order.shipping_label_url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-3 py-2 bg-gray-200 text-[#2D2A2E] text-sm rounded-lg hover:bg-gray-300 transition-colors"
                >
                  View Label
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </div>
          </div>
          
          {/* Estimated Delivery */}
          <div className="mt-3 pt-3 border-t border-gray-200">
            <div className="flex items-center gap-2 text-sm">
              <Clock className="h-4 w-4 text-[#D4AF37]" />
              <span className="text-gray-600">Estimated Delivery:</span>
              <span className="font-semibold text-[#2D2A2E]">{getEstimatedDelivery()}</span>
            </div>
          </div>
        </div>
      )}

      {/* Last Updated */}
      {lastRefresh && (
        <div className="px-4 pb-2 text-xs text-gray-400 text-right">
          Updated {formatDate(lastRefresh)}
        </div>
      )}
    </div>
  );
};

export default ShippingTracker;
