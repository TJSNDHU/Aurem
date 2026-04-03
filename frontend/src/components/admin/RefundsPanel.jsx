import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  RefreshCw, 
  CheckCircle, 
  XCircle, 
  CreditCard,
  AlertCircle,
  X,
  Clock,
  DollarSign,
  Image,
  FileText
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

const statusColors = {
  pending: { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-200' },
  approved: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200' },
  rejected: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200' },
  refunded: { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-200' },
  store_credit: { bg: 'bg-purple-100', text: 'text-purple-800', border: 'border-purple-200' }
};

const RefundsPanel = () => {
  const [refunds, setRefunds] = useState([]);
  const [filter, setFilter] = useState('pending');
  const [selected, setSelected] = useState(null);
  const [notes, setNotes] = useState('');
  const [partialAmount, setPartialAmount] = useState('');
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState(false);

  useEffect(() => {
    fetchRefunds();
  }, [filter]);

  const getAuthHeaders = () => ({
    Authorization: `Bearer ${localStorage.getItem('reroots_token')}`
  });

  const fetchRefunds = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/api/admin/refunds?status=${filter}`, {
        headers: getAuthHeaders()
      });
      setRefunds(response.data || []);
    } catch (error) {
      console.error('Failed to fetch refunds:', error);
    } finally {
      setLoading(false);
    }
  };

  const resolveRefund = async (action) => {
    if (!selected) return;
    
    setResolving(true);
    try {
      await axios.patch(`${API}/api/admin/refunds/${selected.id}`, {
        action,
        notes,
        partial_amount: partialAmount ? parseFloat(partialAmount) : null,
        admin_name: 'Admin'
      }, {
        headers: getAuthHeaders()
      });
      
      setSelected(null);
      setNotes('');
      setPartialAmount('');
      fetchRefunds();
    } catch (error) {
      console.error('Failed to resolve refund:', error);
      alert('Failed to resolve refund. Please try again.');
    } finally {
      setResolving(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleDateString('en-CA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  const stats = {
    pending: refunds.filter(r => r.status === 'pending').length,
    total: refunds.length
  };

  return (
    <div className="p-6" data-testid="refunds-panel">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E]">Refund & Return Management</h2>
          <p className="text-gray-500 text-sm mt-1">
            {stats.pending > 0 ? `${stats.pending} pending requests` : 'All caught up!'}
          </p>
        </div>
        <Button 
          variant="outline" 
          size="sm" 
          onClick={fetchRefunds}
          data-testid="refresh-refunds-btn"
        >
          <RefreshCw className="h-4 w-4 mr-2" /> Refresh
        </Button>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {['pending', 'approved', 'rejected', 'refunded', 'store_credit'].map(status => {
          const colors = statusColors[status] || statusColors.pending;
          return (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                filter === status 
                  ? 'bg-[#2D2A2E] text-white shadow-md' 
                  : `${colors.bg} ${colors.text} hover:opacity-80`
              }`}
              data-testid={`filter-${status}`}
            >
              {status.replace('_', ' ').toUpperCase()}
            </button>
          );
        })}
      </div>

      {/* Refunds Table */}
      <Card className="border-0 shadow-sm">
        <CardContent className="p-0">
          {loading ? (
            <div className="text-center py-12 text-gray-500">Loading refunds...</div>
          ) : refunds.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <AlertCircle className="h-12 w-12 mx-auto mb-3 opacity-50" />
              No {filter} refund requests
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-[#2D2A2E] text-white text-left text-sm">
                    <th className="px-4 py-3">Order</th>
                    <th className="px-4 py-3">Customer</th>
                    <th className="px-4 py-3">Amount</th>
                    <th className="px-4 py-3">Reason</th>
                    <th className="px-4 py-3">Requested</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {refunds.map((refund, i) => {
                    const colors = statusColors[refund.status] || statusColors.pending;
                    return (
                      <tr 
                        key={refund.id}
                        className={`text-sm border-b ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}
                      >
                        <td className="px-4 py-3 font-medium">
                          #{refund.order_number || refund.order_id}
                        </td>
                        <td className="px-4 py-3">
                          <div>{refund.customer_name || 'Customer'}</div>
                          <div className="text-xs text-gray-500">{refund.customer_email}</div>
                        </td>
                        <td className="px-4 py-3 text-red-600 font-semibold">
                          ${(refund.refund_amount || refund.original_order_total || 0).toFixed(2)}
                        </td>
                        <td className="px-4 py-3 max-w-[200px] truncate" title={refund.reason}>
                          {refund.reason || '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-500">
                          {formatDate(refund.requested_at)}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}>
                            {refund.status}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {refund.status === 'pending' && (
                            <Button
                              size="sm"
                              onClick={() => {
                                setSelected(refund);
                                setPartialAmount('');
                                setNotes('');
                              }}
                              className="bg-[#2D2A2E] hover:bg-[#3d393d]"
                              data-testid={`review-refund-${refund.id}`}
                            >
                              Review
                            </Button>
                          )}
                          {refund.status !== 'pending' && refund.resolved_by && (
                            <span className="text-xs text-gray-500">
                              by {refund.resolved_by}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Review Modal */}
      {selected && (
        <div 
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={(e) => e.target === e.currentTarget && setSelected(null)}
        >
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg m-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b flex items-start justify-between">
              <div>
                <h3 className="text-xl font-bold text-[#2D2A2E]">
                  Review Return Request
                </h3>
                <p className="text-gray-500 text-sm">
                  Order #{selected.order_number || selected.order_id}
                </p>
              </div>
              <button 
                onClick={() => setSelected(null)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Customer & Amount */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500 uppercase">Customer</label>
                  <p className="font-medium">{selected.customer_name || 'Customer'}</p>
                  <p className="text-sm text-gray-500">{selected.customer_email}</p>
                </div>
                <div>
                  <label className="text-xs text-gray-500 uppercase">Original Amount</label>
                  <p className="text-2xl font-bold text-red-600">
                    ${(selected.refund_amount || selected.original_order_total || 0).toFixed(2)}
                  </p>
                </div>
              </div>

              {/* Reason */}
              <div>
                <label className="text-xs text-gray-500 uppercase">Reason for Return</label>
                <p className="mt-1 p-3 bg-gray-50 rounded-lg text-sm">
                  {selected.reason || 'No reason provided'}
                </p>
              </div>

              {/* Photos if any */}
              {selected.photos?.length > 0 && (
                <div>
                  <label className="text-xs text-gray-500 uppercase">Photos Submitted</label>
                  <div className="flex gap-2 mt-2">
                    {selected.photos.map((photo, idx) => (
                      <a 
                        key={idx} 
                        href={photo} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="w-16 h-16 bg-gray-100 rounded flex items-center justify-center hover:bg-gray-200"
                      >
                        <Image className="h-6 w-6 text-gray-400" />
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* Partial Amount */}
              <div>
                <label className="text-xs text-gray-500 uppercase">
                  Partial Amount (leave blank for full refund)
                </label>
                <div className="relative mt-1">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="number"
                    step="0.01"
                    value={partialAmount}
                    onChange={(e) => setPartialAmount(e.target.value)}
                    placeholder={`${(selected.refund_amount || selected.original_order_total || 0).toFixed(2)}`}
                    className="w-full pl-9 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#F8A5B8]"
                  />
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="text-xs text-gray-500 uppercase">Notes to Customer</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Explain your decision..."
                  className="w-full mt-1 p-3 border rounded-lg h-20 resize-none focus:outline-none focus:ring-2 focus:ring-[#F8A5B8]"
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="p-6 border-t bg-gray-50 rounded-b-xl">
              <div className="grid grid-cols-3 gap-3">
                <Button
                  onClick={() => resolveRefund('approve')}
                  disabled={resolving}
                  className="bg-green-500 hover:bg-green-600 text-white"
                  data-testid="approve-refund-btn"
                >
                  <CheckCircle className="h-4 w-4 mr-1" />
                  Approve
                </Button>
                <Button
                  onClick={() => resolveRefund('store_credit')}
                  disabled={resolving}
                  className="bg-purple-500 hover:bg-purple-600 text-white"
                  data-testid="store-credit-btn"
                >
                  <CreditCard className="h-4 w-4 mr-1" />
                  Store Credit
                </Button>
                <Button
                  onClick={() => resolveRefund('reject')}
                  disabled={resolving}
                  variant="destructive"
                  data-testid="reject-refund-btn"
                >
                  <XCircle className="h-4 w-4 mr-1" />
                  Reject
                </Button>
              </div>
              <Button
                variant="ghost"
                onClick={() => setSelected(null)}
                className="w-full mt-3"
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RefundsPanel;
