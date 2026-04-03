import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, ExternalLink } from 'lucide-react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

/**
 * Simple PayPal Redirect Component
 * Creates order and redirects to PayPal for payment
 */
const PayPalSDKv6 = ({ 
  amount, 
  currency = "CAD", 
  orderId,
  onApprove, 
  onError, 
  onCancel,
  disabled = false,
  createOrderPayload
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handlePayPalClick = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const token = localStorage.getItem('reroots_token');
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      console.log('Creating order for PayPal...', createOrderPayload);

      // Step 1: Create internal order
      const orderResponse = await axios.post(`${API}/orders`, {
        ...createOrderPayload,
        payment_method: 'paypal_api'
      }, { headers });

      const internalOrderId = orderResponse.data.order_id;
      console.log('Internal order created:', internalOrderId);

      // Step 2: Create PayPal order and get redirect URL
      const paypalResponse = await axios.post(
        `${API}/payments/paypal/create-order`,
        { order_id: internalOrderId },
        { headers }
      );

      console.log('PayPal response:', paypalResponse.data);

      // Find the approval URL to redirect user
      const approvalUrl = paypalResponse.data.links?.find(l => l.rel === 'approve')?.href 
        || paypalResponse.data.approval_url;

      if (approvalUrl) {
        // Store order ID for when user returns
        localStorage.setItem('pending_paypal_order', internalOrderId);
        localStorage.setItem('pending_paypal_id', paypalResponse.data.id);
        
        // Redirect to PayPal
        window.location.href = approvalUrl;
      } else {
        throw new Error('No PayPal approval URL received');
      }

    } catch (err) {
      console.error('PayPal error:', err);
      setLoading(false);
      const msg = err.response?.data?.detail || err.message || 'Failed to start PayPal checkout';
      setError(msg);
      if (onError) onError(err);
    }
  };

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-center">
        <p className="text-red-600 text-sm mb-2">{error}</p>
        <button 
          onClick={() => setError(null)}
          className="text-sm text-blue-600 hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <button
        onClick={handlePayPalClick}
        disabled={disabled || loading || !amount}
        className="w-full bg-[#FFC439] hover:bg-[#F0B72F] text-[#003087] font-bold py-4 px-6 rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        style={{ minHeight: '55px' }}
      >
        {loading ? (
          <>
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Connecting to PayPal...</span>
          </>
        ) : (
          <>
            <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7.076 21.337H2.47a.641.641 0 0 1-.633-.74L4.944.901C5.026.382 5.474 0 5.998 0h7.46c2.57 0 4.578.543 5.69 1.81 1.01 1.15 1.304 2.42 1.012 4.287-.023.143-.047.288-.077.437-.983 5.05-4.349 6.797-8.647 6.797h-2.19c-.524 0-.968.382-1.05.9l-1.12 7.106zm14.146-14.42a3.35 3.35 0 0 0-.607-.541c1.013 4.34-1.625 7.936-6.733 7.936h-.663l-.857 5.433h2.165c.458 0 .85-.331.922-.788l.038-.2.728-4.614.047-.256a.93.93 0 0 1 .922-.788h.58c3.76 0 6.705-1.528 7.565-5.946.36-1.847.174-3.388-.827-4.236z"/>
            </svg>
            <span>Pay with PayPal</span>
            <ExternalLink className="h-4 w-4 ml-1" />
          </>
        )}
      </button>
      <p className="text-xs text-center text-gray-500">
        You'll be redirected to PayPal to complete your purchase securely
      </p>
    </div>
  );
};

export default PayPalSDKv6;
