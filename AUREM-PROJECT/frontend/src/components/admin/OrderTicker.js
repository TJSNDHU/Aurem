/**
 * Real-Time Order Ticker Component
 * Shows live notifications when new orders come in
 * Works across all admin pages via WebSocket
 */
import React, { useEffect, useState, useRef } from 'react';
import { useWebSocket } from '../../contexts';
import { toast } from 'sonner';
import { DollarSign, ShoppingBag, TrendingUp } from 'lucide-react';

const OrderTicker = () => {
  const { lastMessage, subscribe } = useWebSocket();
  const [recentOrders, setRecentOrders] = useState([]);
  const [todayStats, setTodayStats] = useState({
    totalOrders: 0,
    totalRevenue: 0
  });
  const audioRef = useRef(null);

  // Initialize notification sound
  useEffect(() => {
    audioRef.current = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdHuJiYB7dnN2hY6QiYJ7d3p/h42PioaCf4GGi46OioeBf4GGi46OjImGg4OFiIqKiIaCgYGEh4mJiIaCgYGEh4mJiIaCgYGDhoeIh4WAf4CDhYeHhoSBgIGDhYaGhYOBgIGDhYaGhYOBgIGCg4SEg4GAgICCg4SEg4GAgICCg4SEg4GAgICA');
  }, []);

  // Play notification sound
  const playNotificationSound = () => {
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
      audioRef.current.volume = 0.3;
      audioRef.current.play().catch(() => {});
    }
  };

  // Listen for new orders
  useEffect(() => {
    if (lastMessage) {
      const { type, data } = lastMessage;
      
      if (type === 'new_order') {
        // Play sound
        playNotificationSound();
        
        // Add to recent orders
        setRecentOrders(prev => [{
          id: data.order_id,
          order_number: data.order_number,
          total: data.total,
          customer: data.customer_email?.split('@')[0] || 'Customer',
          timestamp: new Date()
        }, ...prev.slice(0, 4)]);
        
        // Update today's stats
        setTodayStats(prev => ({
          totalOrders: prev.totalOrders + 1,
          totalRevenue: prev.totalRevenue + (data.total || 0)
        }));
        
        // Show prominent toast
        toast.custom((t) => (
          <div className="bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-lg shadow-lg p-4 max-w-sm animate-pulse">
            <div className="flex items-center gap-3">
              <div className="bg-white/20 rounded-full p-2">
                <ShoppingBag className="w-6 h-6" />
              </div>
              <div>
                <p className="font-bold text-lg">New Order!</p>
                <p className="text-white/90">#{data.order_number}</p>
                <p className="text-2xl font-bold">${data.total?.toFixed(2)}</p>
              </div>
            </div>
          </div>
        ), {
          duration: 6000,
          position: 'top-right',
        });
      }
      
      if (type === 'payment_received') {
        toast.success(`💳 Payment confirmed for #${data.order_number}`, {
          duration: 4000,
        });
      }
      
      if (type === 'order_shipped') {
        toast.success(`📦 Order #${data.order_number} shipped!`, {
          duration: 4000,
        });
      }
      
      if (type === 'inventory_update') {
        // Inventory sync - show warning for low stock items
        const updates = data.updates || [];
        updates.forEach(update => {
          if (update.low_stock_warning || update.new_stock <= 5) {
            toast.warning(
              <div className="flex items-center gap-2">
                <span>⚠️</span>
                <div>
                  <p className="font-semibold">Low Stock Alert!</p>
                  <p className="text-sm">{update.product_name}: {update.new_stock} left</p>
                </div>
              </div>,
              { duration: 6000 }
            );
          }
        });
      }
    }
  }, [lastMessage]);

  // Don't render anything visible - just handles notifications
  return null;
};

// Mini stats display for header (optional)
export const OrderTickerStats = () => {
  const [stats, setStats] = useState({ orders: 0, revenue: 0 });
  const { lastMessage } = useWebSocket();

  useEffect(() => {
    if (lastMessage?.type === 'new_order') {
      setStats(prev => ({
        orders: prev.orders + 1,
        revenue: prev.revenue + (lastMessage.data?.total || 0)
      }));
    }
  }, [lastMessage]);

  if (stats.orders === 0) return null;

  return (
    <div className="flex items-center gap-2 bg-green-100 text-green-700 px-3 py-1 rounded-full text-sm font-medium animate-pulse">
      <TrendingUp className="w-4 h-4" />
      <span>+{stats.orders} orders</span>
      <span className="font-bold">${stats.revenue.toFixed(0)}</span>
    </div>
  );
};

export default OrderTicker;
