import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Leaf, Check, Loader2, Info } from 'lucide-react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

/**
 * Roots Redemption Component for Checkout
 * Shows user's Roots balance and allows redemption at checkout
 * 
 * Props:
 * - subtotal: Order subtotal for calculating max discount
 * - onRedemptionApplied: Callback with { points, value, token } when redemption is applied
 * - onRedemptionRemoved: Callback when redemption is removed
 */
const RootsRedemption = ({ subtotal, onRedemptionApplied, onRedemptionRemoved }) => {
  const [loyaltyContext, setLoyaltyContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [redemptionApplied, setRedemptionApplied] = useState(null);

  // Fetch loyalty context when component mounts or subtotal changes
  useEffect(() => {
    const fetchLoyaltyContext = async () => {
      const token = localStorage.getItem('reroots_token');
      if (!token) {
        setLoyaltyContext({ logged_in: false, loyalty_balance: 0 });
        setLoading(false);
        return;
      }

      try {
        const res = await axios.get(`${API}/checkout/loyalty-context`, {
          params: { subtotal: subtotal || 0 },
          headers: { Authorization: `Bearer ${token}` }
        });
        setLoyaltyContext(res.data);
      } catch (error) {
        console.error('Failed to fetch loyalty context:', error);
        setLoyaltyContext({ logged_in: false, loyalty_balance: 0 });
      }
      setLoading(false);
    };

    fetchLoyaltyContext();
  }, [subtotal]);

  // Apply Roots redemption
  const applyRedemption = async () => {
    if (!loyaltyContext || loyaltyContext.points_to_redeem <= 0) return;

    setApplying(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.post(
        `${API}/loyalty/points/redeem`,
        {
          points: loyaltyContext.points_to_redeem,
          subtotal: subtotal
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      const redemption = {
        points: res.data.points,
        value: res.data.discount_value,
        token: res.data.redemption_token
      };

      setRedemptionApplied(redemption);
      onRedemptionApplied?.(redemption);
      toast.success(`Applied ${res.data.points} Roots - Save $${res.data.discount_value.toFixed(2)}!`);
    } catch (error) {
      console.error('Redemption failed:', error);
      toast.error(error.response?.data?.detail || 'Failed to apply Roots');
    }
    setApplying(false);
  };

  // Remove redemption
  const removeRedemption = () => {
    setRedemptionApplied(null);
    onRedemptionRemoved?.();
    toast.info('Roots redemption removed');
  };

  // Don't show if loading or no balance
  if (loading) {
    return (
      <div className="bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 rounded-lg p-4 mb-4" data-testid="roots-redemption-loading">
        <div className="flex items-center gap-2 text-emerald-700">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Loading Roots balance...</span>
        </div>
      </div>
    );
  }

  // Not logged in
  if (!loyaltyContext?.logged_in) {
    return (
      <div className="bg-gradient-to-r from-gray-50 to-slate-50 border border-gray-200 rounded-lg p-4 mb-4" data-testid="roots-redemption-login-prompt">
        <div className="flex items-center gap-2">
          <Leaf className="h-5 w-5 text-emerald-600" />
          <span className="font-medium text-gray-700">Have Roots?</span>
        </div>
        <p className="text-sm text-gray-500 mt-1">
          <a href="/login" className="text-emerald-600 hover:underline">Log in</a> to use your Roots balance at checkout
        </p>
      </div>
    );
  }

  // No balance
  if (loyaltyContext.loyalty_balance <= 0) {
    return null;
  }

  // Redemption already applied
  if (redemptionApplied) {
    return (
      <div className="bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-300 rounded-lg p-4 mb-4" data-testid="roots-redemption-applied">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-emerald-500 rounded-full flex items-center justify-center">
              <Check className="h-4 w-4 text-white" />
            </div>
            <div>
              <p className="font-medium text-emerald-800">
                {redemptionApplied.points} Roots Applied
              </p>
              <p className="text-sm text-emerald-600">
                Saving ${redemptionApplied.value.toFixed(2)}
              </p>
            </div>
          </div>
          <button
            onClick={removeRedemption}
            className="text-sm text-emerald-700 hover:text-emerald-900 hover:underline"
          >
            Remove
          </button>
        </div>
      </div>
    );
  }

  // Show redemption option
  return (
    <div className="bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 rounded-lg p-4 mb-4" data-testid="roots-redemption">
      <div className="flex items-center gap-2 mb-3">
        <Leaf className="h-5 w-5 text-emerald-600" />
        <span className="font-semibold text-emerald-800">Your Roots Balance</span>
      </div>

      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-2xl font-bold text-emerald-700">
            {loyaltyContext.loyalty_balance} Roots
          </p>
          <p className="text-sm text-emerald-600">
            ${loyaltyContext.balance_value.toFixed(2)} value
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-500 flex items-center gap-1">
            <Info className="h-3 w-3" />
            Max discount: {loyaltyContext.max_discount_pct}% off
          </p>
        </div>
      </div>

      {loyaltyContext.redeemable_amount > 0 && (
        <button
          onClick={applyRedemption}
          disabled={applying}
          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
          data-testid="apply-roots-btn"
        >
          {applying ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Applying...
            </>
          ) : (
            <>
              <Leaf className="h-4 w-4" />
              Apply {loyaltyContext.points_to_redeem} Roots — Save ${loyaltyContext.redeemable_amount.toFixed(2)}
            </>
          )}
        </button>
      )}

      {loyaltyContext.max_discount_amount && loyaltyContext.balance_value > loyaltyContext.max_discount_amount && (
        <p className="text-xs text-gray-500 mt-2 text-center">
          * Redemption capped at {loyaltyContext.max_discount_pct}% of order (${loyaltyContext.max_discount_amount.toFixed(2)})
        </p>
      )}
    </div>
  );
};

export default RootsRedemption;
