import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { 
  Package, 
  Truck, 
  CheckCircle, 
  Clock, 
  MapPin, 
  Receipt, 
  AlertCircle,
  ExternalLink,
  Download,
  Loader2,
  ArrowLeft,
  CreditCard,
  Calendar,
  Box,
  ChevronRight
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

// Dynamic API URL for custom domains
const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

const BACKEND_URL = getBackendUrl();
const API = `${BACKEND_URL}/api`;

// Status badge colors
const statusColors = {
  pending: 'bg-yellow-100 text-yellow-800',
  processing: 'bg-blue-100 text-blue-800',
  shipped: 'bg-purple-100 text-purple-800',
  delivered: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
  refunded: 'bg-gray-100 text-gray-800'
};

const TrackOrderPage = () => {
  const [searchParams] = useSearchParams();
  const [orderNumber, setOrderNumber] = useState(searchParams.get('order') || '');
  const [email, setEmail] = useState(searchParams.get('email') || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [trackingData, setTrackingData] = useState(null);
  const [downloadingReceipt, setDownloadingReceipt] = useState(false);

  // Auto-fetch if params are present
  useEffect(() => {
    const orderParam = searchParams.get('order');
    const emailParam = searchParams.get('email');
    if (orderParam && emailParam) {
      setOrderNumber(orderParam);
      setEmail(emailParam);
      fetchTracking(orderParam, emailParam);
    }
  }, [searchParams]);

  const fetchTracking = useCallback(async (order, emailAddr) => {
    if (!order || !emailAddr) {
      setError('Please enter both order number and email');
      return;
    }

    setLoading(true);
    setError('');
    setTrackingData(null);

    try {
      const response = await axios.get(`${API}/track`, {
        params: { order, email: emailAddr }
      });
      setTrackingData(response.data);
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Order not found. Please check your order number.');
      } else if (err.response?.status === 403) {
        setError('Email does not match this order. Please use the email from your order confirmation.');
      } else {
        setError('Unable to fetch tracking information. Please try again later.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    fetchTracking(orderNumber, email);
  };

  const handleDownloadReceipt = async () => {
    if (!trackingData?.order?.order_number || !email) return;

    setDownloadingReceipt(true);
    try {
      const response = await axios.get(
        `${API}/receipt/${trackingData.order.order_number}`,
        {
          params: { email },
          responseType: 'blob'
        }
      );
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `ReRoots_Receipt_${trackingData.order.order_number}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Unable to download receipt. Please try again.');
    } finally {
      setDownloadingReceipt(false);
    }
  };

  // Format date helper
  const formatDate = (dateString) => {
    if (!dateString) return 'Pending';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-CA', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#FFF5F7] to-white">
      {/* Header */}
      <div className="bg-[#2D2A2E] text-white py-6">
        <div className="max-w-4xl mx-auto px-4">
          <Link to="/" className="inline-flex items-center text-[#F8A5B8] hover:text-white transition-colors mb-4">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Store
          </Link>
          <h1 className="text-3xl font-bold" data-testid="track-order-title">Track Your Order</h1>
          <p className="text-gray-300 mt-2">Enter your order details to view shipping status</p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Search Form */}
        {!trackingData && (
          <Card className="mb-8 border-0 shadow-lg" data-testid="tracking-search-form">
            <CardContent className="p-6">
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="orderNumber">Order Number</Label>
                    <Input
                      id="orderNumber"
                      placeholder="e.g., RR-240301-ABC123"
                      value={orderNumber}
                      onChange={(e) => setOrderNumber(e.target.value)}
                      className="mt-1"
                      data-testid="order-number-input"
                    />
                  </div>
                  <div>
                    <Label htmlFor="email">Email Address</Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="your@email.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="mt-1"
                      data-testid="email-input"
                    />
                  </div>
                </div>
                
                <Button 
                  type="submit" 
                  className="w-full bg-[#F8A5B8] hover:bg-[#E88DA0] text-[#2D2A2E]"
                  disabled={loading}
                  data-testid="track-order-submit"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Package className="h-4 w-4 mr-2" />
                      Track Order
                    </>
                  )}
                </Button>
              </form>

              {error && (
                <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3" data-testid="tracking-error">
                  <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-red-700 font-medium">Unable to find order</p>
                    <p className="text-red-600 text-sm">{error}</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Loading State */}
        {loading && !trackingData && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="h-12 w-12 text-[#F8A5B8] animate-spin mb-4" />
            <p className="text-gray-500">Fetching your order details...</p>
          </div>
        )}

        {/* Tracking Results */}
        {trackingData && (
          <div className="space-y-6" data-testid="tracking-results">
            {/* Order Header */}
            <Card className="border-0 shadow-lg overflow-hidden">
              <div className="bg-gradient-to-r from-[#2D2A2E] to-[#3d393d] p-6 text-white">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div>
                    <p className="text-[#D4AF37] text-sm uppercase tracking-wide">Order Number</p>
                    <h2 className="text-2xl font-bold" data-testid="order-number-display">
                      {trackingData.order.order_number}
                    </h2>
                  </div>
                  <Badge 
                    className={`${statusColors[trackingData.order.order_status] || statusColors.pending} px-4 py-2 text-sm font-semibold`}
                    data-testid="order-status-badge"
                  >
                    {trackingData.order.order_status?.replace('_', ' ').toUpperCase() || 'PENDING'}
                  </Badge>
                </div>
              </div>
              
              <CardContent className="p-6">
                <div className="grid md:grid-cols-3 gap-6">
                  <div className="flex items-start gap-3">
                    <Calendar className="h-5 w-5 text-[#F8A5B8] flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm text-gray-500">Order Date</p>
                      <p className="font-medium">{formatDate(trackingData.order.created_at).split(',')[0]}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Box className="h-5 w-5 text-[#F8A5B8] flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm text-gray-500">Items</p>
                      <p className="font-medium">{trackingData.order.items_count} item(s)</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <CreditCard className="h-5 w-5 text-[#F8A5B8] flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm text-gray-500">Total</p>
                      <p className="font-bold text-[#F8A5B8]">${trackingData.order.total?.toFixed(2)} {trackingData.order.currency}</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Tracking Timeline */}
            <Card className="border-0 shadow-lg" data-testid="tracking-timeline">
              <CardHeader className="border-b">
                <CardTitle className="flex items-center gap-2">
                  <Truck className="h-5 w-5 text-[#F8A5B8]" />
                  Shipping Progress
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <div className="space-y-6">
                  {trackingData.timeline?.map((step, index) => (
                    <div key={index} className="flex gap-4">
                      <div className="flex flex-col items-center">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                          step.completed 
                            ? 'bg-green-100 text-green-600' 
                            : 'bg-gray-100 text-gray-400'
                        }`}>
                          {step.completed ? (
                            <CheckCircle className="h-5 w-5" />
                          ) : (
                            <Clock className="h-5 w-5" />
                          )}
                        </div>
                        {index < trackingData.timeline.length - 1 && (
                          <div className={`w-0.5 h-12 ${step.completed ? 'bg-green-200' : 'bg-gray-200'}`} />
                        )}
                      </div>
                      <div className="flex-1 pb-6">
                        <p className={`font-semibold ${step.completed ? 'text-[#2D2A2E]' : 'text-gray-400'}`}>
                          {step.status}
                        </p>
                        <p className="text-sm text-gray-500">{step.description}</p>
                        {step.timestamp && (
                          <p className="text-xs text-gray-400 mt-1">{formatDate(step.timestamp)}</p>
                        )}
                        {step.tracking_number && (
                          <p className="text-xs text-[#F8A5B8] mt-1">
                            Tracking: {step.tracking_number}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Carrier Tracking Link */}
                {trackingData.tracking?.tracking_url && (
                  <div className="mt-6 pt-6 border-t">
                    <a
                      href={trackingData.tracking.tracking_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-[#F8A5B8] hover:text-[#E88DA0] font-medium"
                      data-testid="carrier-tracking-link"
                    >
                      <ExternalLink className="h-4 w-4" />
                      Track on {trackingData.tracking.carrier || 'Carrier'} Website
                    </a>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Shipping Address */}
            <div className="grid md:grid-cols-2 gap-6">
              <Card className="border-0 shadow-lg">
                <CardHeader className="border-b">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <MapPin className="h-5 w-5 text-[#F8A5B8]" />
                    Shipping Address
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-6">
                  <p className="font-medium">{trackingData.shipping?.recipient || 'Customer'}</p>
                  <p className="text-gray-600">{trackingData.shipping?.address}</p>
                  <p className="text-gray-600">
                    {trackingData.shipping?.city}, {trackingData.shipping?.province} {trackingData.shipping?.postal_code}
                  </p>
                  <p className="text-gray-600">{trackingData.shipping?.country}</p>
                </CardContent>
              </Card>

              {/* Order Items */}
              <Card className="border-0 shadow-lg">
                <CardHeader className="border-b">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Package className="h-5 w-5 text-[#F8A5B8]" />
                    Order Items
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-6 space-y-4">
                  {trackingData.order.items?.slice(0, 3).map((item, index) => (
                    <div key={index} className="flex items-center gap-3">
                      {item.image ? (
                        <img 
                          src={item.image} 
                          alt={item.name}
                          className="w-12 h-12 rounded object-cover bg-gray-100"
                        />
                      ) : (
                        <div className="w-12 h-12 rounded bg-gray-100 flex items-center justify-center">
                          <Box className="h-6 w-6 text-gray-400" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{item.name}</p>
                        <p className="text-xs text-gray-500">Qty: {item.quantity}</p>
                      </div>
                      <p className="font-medium text-sm">${(item.price * item.quantity).toFixed(2)}</p>
                    </div>
                  ))}
                  {trackingData.order.items?.length > 3 && (
                    <p className="text-sm text-gray-500 text-center pt-2">
                      + {trackingData.order.items.length - 3} more items
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Actions */}
            <Card className="border-0 shadow-lg bg-gradient-to-r from-[#FFF5F7] to-[#FFF8E7]">
              <CardContent className="p-6">
                <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-[#2D2A2E]">Need Your Receipt?</h3>
                    <p className="text-sm text-gray-600">Download your official payment receipt as PDF</p>
                  </div>
                  <Button
                    onClick={handleDownloadReceipt}
                    disabled={downloadingReceipt}
                    className="bg-[#2D2A2E] hover:bg-[#3d393d] text-white"
                    data-testid="download-receipt-btn"
                  >
                    {downloadingReceipt ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      <>
                        <Download className="h-4 w-4 mr-2" />
                        Download Receipt
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Search Again Button */}
            <div className="text-center">
              <Button
                variant="ghost"
                onClick={() => {
                  setTrackingData(null);
                  setOrderNumber('');
                  setEmail('');
                }}
                className="text-gray-500 hover:text-[#2D2A2E]"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Track Another Order
              </Button>
            </div>
          </div>
        )}

        {/* Help Section */}
        {!trackingData && !loading && (
          <Card className="mt-8 border-0 shadow-md bg-[#F9F9F9]">
            <CardContent className="p-6">
              <h3 className="font-semibold text-[#2D2A2E] mb-3">Need Help?</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-start gap-2">
                  <ChevronRight className="h-4 w-4 text-[#F8A5B8] flex-shrink-0 mt-0.5" />
                  Your order number can be found in your confirmation email
                </li>
                <li className="flex items-start gap-2">
                  <ChevronRight className="h-4 w-4 text-[#F8A5B8] flex-shrink-0 mt-0.5" />
                  Use the same email address you provided during checkout
                </li>
                <li className="flex items-start gap-2">
                  <ChevronRight className="h-4 w-4 text-[#F8A5B8] flex-shrink-0 mt-0.5" />
                  Tracking information may take 24-48 hours to appear after shipping
                </li>
              </ul>
              <div className="mt-4 pt-4 border-t border-gray-200">
                <p className="text-sm text-gray-500">
                  Still having trouble? Contact us at{' '}
                  <a href="mailto:support@reroots.ca" className="text-[#F8A5B8] hover:underline">
                    support@reroots.ca
                  </a>
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default TrackOrderPage;
