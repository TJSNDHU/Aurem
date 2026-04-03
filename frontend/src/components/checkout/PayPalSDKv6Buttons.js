import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Loader2 } from 'lucide-react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';
const PAYPAL_CLIENT_ID = process.env.REACT_APP_PAYPAL_CLIENT_ID;

/**
 * PayPal SDK v6 Buttons Component
 * Uses the official PayPal JS SDK with buttons for a native checkout experience
 */
const PayPalSDKv6Buttons = ({ 
  amount, 
  currency = "CAD", 
  onApprove, 
  onError, 
  onCancel,
  disabled = false,
  createOrderPayload
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sdkReady, setSdkReady] = useState(false);
  const buttonContainerRef = useRef(null);
  const buttonsRendered = useRef(false);

  // Load PayPal SDK script
  useEffect(() => {
    const loadPayPalScript = () => {
      // Check if already loaded
      if (window.paypal) {
        setSdkReady(true);
        setLoading(false);
        return;
      }

      // Check if script is already being loaded
      const existingScript = document.getElementById('paypal-sdk-script');
      if (existingScript) {
        existingScript.addEventListener('load', () => {
          setSdkReady(true);
          setLoading(false);
        });
        return;
      }

      // Create and load script
      const script = document.createElement('script');
      script.id = 'paypal-sdk-script';
      script.src = `https://www.paypal.com/sdk/js?client-id=${PAYPAL_CLIENT_ID}&currency=${currency}&intent=capture&components=buttons`;
      script.async = true;
      
      script.onload = () => {
        console.log('PayPal SDK loaded');
        setSdkReady(true);
        setLoading(false);
      };
      
      script.onerror = (err) => {
        console.error('Failed to load PayPal SDK:', err);
        setError('Failed to load PayPal. Please refresh and try again.');
        setLoading(false);
      };
      
      document.body.appendChild(script);
    };

    loadPayPalScript();
  }, [currency]);

  // Render PayPal buttons when SDK is ready
  useEffect(() => {
    if (!sdkReady || !window.paypal || !buttonContainerRef.current || buttonsRendered.current || disabled) {
      return;
    }

    // Clear container
    buttonContainerRef.current.innerHTML = '';
    
    try {
      window.paypal.Buttons({
        style: {
          layout: 'vertical',
          color: 'gold',
          shape: 'rect',
          label: 'paypal',
          height: 55
        },
        
        // Create order on PayPal
        createOrder: async (data, actions) => {
          try {
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

            // Step 2: Create PayPal order
            const paypalResponse = await axios.post(
              `${API}/payments/paypal/create-order`,
              { order_id: internalOrderId },
              { headers }
            );

            console.log('PayPal order created:', paypalResponse.data);

            // Store internal order ID for capture
            localStorage.setItem('pending_paypal_order', internalOrderId);
            localStorage.setItem('pending_paypal_id', paypalResponse.data.id);

            // Return PayPal order ID
            return paypalResponse.data.id;
          } catch (err) {
            console.error('Error creating PayPal order:', err);
            const msg = err.response?.data?.detail || err.message || 'Failed to create order';
            setError(msg);
            throw err;
          }
        },

        // Capture payment when approved
        onApprove: async (data, actions) => {
          try {
            console.log('PayPal payment approved:', data);
            
            const token = localStorage.getItem('reroots_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const pendingOrderId = localStorage.getItem('pending_paypal_order');

            // Capture the payment
            const captureResponse = await axios.post(
              `${API}/payments/paypal/capture`,
              { 
                orderID: data.orderID,
                order_id: pendingOrderId 
              },
              { headers }
            );

            console.log('Payment captured:', captureResponse.data);

            // Clear stored IDs
            localStorage.removeItem('pending_paypal_order');
            localStorage.removeItem('pending_paypal_id');

            // Call success callback
            if (onApprove) {
              onApprove({
                ...captureResponse.data,
                order_id: pendingOrderId
              });
            }
          } catch (err) {
            console.error('Error capturing PayPal payment:', err);
            const msg = err.response?.data?.detail || err.message || 'Failed to capture payment';
            setError(msg);
            if (onError) onError(err);
          }
        },

        onCancel: (data) => {
          console.log('PayPal payment cancelled:', data);
          if (onCancel) onCancel(data);
        },

        onError: (err) => {
          console.error('PayPal error:', err);
          setError('PayPal encountered an error. Please try again.');
          if (onError) onError(err);
        }
      }).render(buttonContainerRef.current);
      
      buttonsRendered.current = true;
      console.log('PayPal buttons rendered');
    } catch (err) {
      console.error('Error rendering PayPal buttons:', err);
      setError('Failed to initialize PayPal buttons.');
    }
  }, [sdkReady, disabled, createOrderPayload, onApprove, onCancel, onError]);

  // Reset buttons when amount changes significantly
  useEffect(() => {
    if (buttonsRendered.current && buttonContainerRef.current) {
      buttonsRendered.current = false;
      buttonContainerRef.current.innerHTML = '';
    }
  }, [amount]);

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-center">
        <p className="text-red-600 text-sm mb-2">{error}</p>
        <button 
          onClick={() => {
            setError(null);
            buttonsRendered.current = false;
            if (buttonContainerRef.current) {
              buttonContainerRef.current.innerHTML = '';
            }
          }}
          className="text-sm text-blue-600 hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {loading && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-6 w-6 animate-spin text-[#003087]" />
          <span className="ml-2 text-sm text-gray-600">Loading PayPal...</span>
        </div>
      )}
      
      <div 
        ref={buttonContainerRef} 
        className={loading || disabled ? 'opacity-50 pointer-events-none' : ''}
        style={{ minHeight: loading ? 0 : '55px' }}
      />
      
      {!loading && sdkReady && (
        <p className="text-xs text-center text-gray-500">
          Secure checkout powered by PayPal
        </p>
      )}
    </div>
  );
};

export default PayPalSDKv6Buttons;
