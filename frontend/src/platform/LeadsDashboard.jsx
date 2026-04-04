/**
 * Leads Dashboard
 * Shows captured leads with today's impact metrics
 * Phase A: Lead Capture System
 */

import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';

const LeadsDashboard = () => {
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedLead, setSelectedLead] = useState(null);

  const API_URL = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    fetchLeads();
    fetchStats();
    // Refresh every 30 seconds
    const interval = setInterval(() => {
      fetchLeads();
      fetchStats();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchLeads = async () => {
    try {
      const response = await fetch(`${API_URL}/api/leads`);
      const data = await response.json();
      if (data.success) {
        setLeads(data.leads);
      }
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/leads/stats?period=today`);
      const data = await response.json();
      if (data.success) {
        setStats(data.stats);
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const updateLeadStatus = async (leadId, newStatus) => {
    try {
      const response = await fetch(`${API_URL}/api/leads/${leadId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
      
      if (response.ok) {
        // Refresh leads
        fetchLeads();
        fetchStats();
      }
    } catch (err) {
      console.error('Failed to update lead:', err);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      new: 'bg-blue-500',
      contacted: 'bg-yellow-500',
      converted: 'bg-green-500',
      lost: 'bg-gray-500'
    };
    return colors[status] || 'bg-gray-500';
  };

  const getIntentIcon = (intentType) => {
    const icons = {
      booking: '📅',
      purchase: '🛍️',
      inquiry: '💬'
    };
    return icons[intentType] || '💡';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading leads...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center text-red-600">
          <p>Error loading leads: {error}</p>
          <Button onClick={() => window.location.reload()} className="mt-4">
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900">Leads Dashboard</h1>
          <p className="text-gray-600 mt-2">AI-captured leads from your conversations</p>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-blue-100 text-sm">Total Leads Today</p>
                    <h3 className="text-3xl font-bold mt-2">{stats.total_leads}</h3>
                  </div>
                  <div className="text-4xl opacity-50">💰</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-green-500 to-green-600 text-white">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-green-100 text-sm">Converted</p>
                    <h3 className="text-3xl font-bold mt-2">{stats.converted}</h3>
                  </div>
                  <div className="text-4xl opacity-50">✅</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-purple-500 to-purple-600 text-white">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-purple-100 text-sm">Estimated Value</p>
                    <h3 className="text-3xl font-bold mt-2">${stats.total_value.toFixed(0)}</h3>
                  </div>
                  <div className="text-4xl opacity-50">💵</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-orange-500 to-orange-600 text-white">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-orange-100 text-sm">Conversion Rate</p>
                    <h3 className="text-3xl font-bold mt-2">{stats.conversion_rate}%</h3>
                  </div>
                  <div className="text-4xl opacity-50">📈</div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Leads List */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Recent Leads</span>
              <Badge variant="outline">{leads.length} total</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {leads.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <div className="text-6xl mb-4">🎯</div>
                <p className="text-lg">No leads captured yet</p>
                <p className="text-sm mt-2">Your AI will automatically capture leads from conversations</p>
              </div>
            ) : (
              <div className="space-y-4">
                {leads.map((lead) => (
                  <div
                    key={lead.lead_id}
                    className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => setSelectedLead(lead)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <span className="text-2xl">
                            {getIntentIcon(lead.interest?.intent_type)}
                          </span>
                          <div>
                            <h3 className="font-semibold text-lg">
                              {lead.customer?.name || 'Unknown'}
                            </h3>
                            <p className="text-sm text-gray-600">
                              {lead.interest?.intent_type || 'General inquiry'}
                            </p>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4 text-sm mt-3">
                          <div>
                            <span className="text-gray-500">Phone:</span>
                            <span className="ml-2 font-medium">
                              {lead.customer?.phone || 'Not provided'}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-500">Email:</span>
                            <span className="ml-2 font-medium">
                              {lead.customer?.email || 'Not provided'}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-500">Value:</span>
                            <span className="ml-2 font-medium text-green-600">
                              ${lead.value_estimate?.toFixed(2) || '0.00'}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-500">Captured:</span>
                            <span className="ml-2 font-medium">
                              {new Date(lead.captured_at).toLocaleString()}
                            </span>
                          </div>
                        </div>

                        {lead.interest?.preferred_time && (
                          <div className="mt-2 text-sm">
                            <span className="text-gray-500">Preferred time:</span>
                            <span className="ml-2 font-medium">
                              {lead.interest.preferred_time}
                            </span>
                          </div>
                        )}
                      </div>

                      <div className="ml-4">
                        <Badge className={`${getStatusColor(lead.status)} text-white`}>
                          {lead.status}
                        </Badge>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2 mt-4 pt-4 border-t">
                      {lead.status === 'new' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            updateLeadStatus(lead.lead_id, 'contacted');
                          }}
                        >
                          Mark Contacted
                        </Button>
                      )}
                      {(lead.status === 'new' || lead.status === 'contacted') && (
                        <Button
                          size="sm"
                          className="bg-green-600 hover:bg-green-700"
                          onClick={(e) => {
                            e.stopPropagation();
                            updateLeadStatus(lead.lead_id, 'converted');
                          }}
                        >
                          Mark Converted
                        </Button>
                      )}
                      {lead.customer?.phone && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(`tel:${lead.customer.phone}`);
                          }}
                        >
                          📞 Call
                        </Button>
                      )}
                      {lead.customer?.email && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(`mailto:${lead.customer.email}`);
                          }}
                        >
                          📧 Email
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Lead Detail Modal */}
        {selectedLead && (
          <div
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
            onClick={() => setSelectedLead(null)}
          >
            <div
              className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between mb-4">
                <h2 className="text-2xl font-bold">Lead Details</h2>
                <button
                  onClick={() => setSelectedLead(null)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">Customer Information</h3>
                  <div className="bg-gray-50 p-4 rounded">
                    <p><strong>Name:</strong> {selectedLead.customer?.name || 'Unknown'}</p>
                    <p><strong>Email:</strong> {selectedLead.customer?.email || 'Not provided'}</p>
                    <p><strong>Phone:</strong> {selectedLead.customer?.phone || 'Not provided'}</p>
                  </div>
                </div>

                <div>
                  <h3 className="font-semibold mb-2">Lead Information</h3>
                  <div className="bg-gray-50 p-4 rounded">
                    <p><strong>Intent:</strong> {selectedLead.interest?.intent_type || 'General'}</p>
                    <p><strong>Confidence:</strong> {(selectedLead.ai_confidence * 100).toFixed(0)}%</p>
                    <p><strong>Estimated Value:</strong> ${selectedLead.value_estimate?.toFixed(2)}</p>
                    <p><strong>Status:</strong> <Badge className={getStatusColor(selectedLead.status)}>{selectedLead.status}</Badge></p>
                  </div>
                </div>

                {selectedLead.transcript && selectedLead.transcript.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2">Conversation Transcript</h3>
                    <div className="bg-gray-50 p-4 rounded max-h-64 overflow-y-auto space-y-2">
                      {selectedLead.transcript.map((msg, idx) => (
                        <div
                          key={idx}
                          className={`p-2 rounded ${
                            msg.role === 'user' ? 'bg-blue-100' : 'bg-gray-200'
                          }`}
                        >
                          <p className="text-xs text-gray-600 mb-1">
                            {msg.role === 'user' ? 'Customer' : 'AI'}
                          </p>
                          <p className="text-sm">{msg.content}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-6 flex gap-2">
                <Button
                  className="flex-1"
                  onClick={() => {
                    if (selectedLead.customer?.phone) {
                      window.open(`tel:${selectedLead.customer.phone}`);
                    }
                  }}
                  disabled={!selectedLead.customer?.phone}
                >
                  📞 Call Customer
                </Button>
                <Button
                  className="flex-1"
                  variant="outline"
                  onClick={() => {
                    if (selectedLead.customer?.email) {
                      window.open(`mailto:${selectedLead.customer.email}`);
                    }
                  }}
                  disabled={!selectedLead.customer?.email}
                >
                  📧 Send Email
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LeadsDashboard;
