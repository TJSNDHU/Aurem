/**
 * AUREM Business Management
 * Manage multiple businesses and their AI agents
 */

import React, { useState, useEffect } from 'react';
import { 
  Building2, Bot, Plus, Settings, Trash2, Edit, 
  ChevronRight, Users, MessageSquare, BarChart3,
  Sparkles, Check, X, Loader2
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const BusinessCard = ({ business, onSelect, onEdit, isSelected }) => {
  const typeColors = {
    skincare: 'from-pink-500 to-rose-500',
    automotive: 'from-blue-500 to-cyan-500',
    saas: 'from-purple-500 to-indigo-500',
    ecommerce: 'from-green-500 to-emerald-500',
    default: 'from-[#D4AF37] to-[#8B7355]'
  };
  
  const gradientClass = typeColors[business.type] || typeColors.default;
  
  return (
    <div 
      onClick={() => onSelect(business)}
      className={`p-4 bg-[#0A0A0A] border rounded-xl cursor-pointer transition-all ${
        isSelected 
          ? 'border-[#D4AF37] shadow-lg shadow-[#D4AF37]/10' 
          : 'border-[#1A1A1A] hover:border-[#333]'
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${gradientClass} flex items-center justify-center`}>
          <Building2 className="w-5 h-5 text-white" />
        </div>
        <button 
          onClick={(e) => { e.stopPropagation(); onEdit(business); }}
          className="p-1 text-[#666] hover:text-[#D4AF37] transition-colors"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
      
      <h3 className="text-base font-medium text-[#F4F4F4] mb-1">{business.name}</h3>
      <p className="text-xs text-[#666] mb-3 line-clamp-2">{business.description}</p>
      
      <div className="flex items-center gap-2">
        <span className={`px-2 py-0.5 text-[10px] rounded-full bg-gradient-to-r ${gradientClass} text-white`}>
          {business.type.toUpperCase()}
        </span>
        <span className={`px-2 py-0.5 text-[10px] rounded-full ${
          business.is_active ? 'bg-[#4A4]/20 text-[#4A4]' : 'bg-[#666]/20 text-[#666]'
        }`}>
          {business.is_active ? 'ACTIVE' : 'INACTIVE'}
        </span>
      </div>
    </div>
  );
};

const AgentCard = ({ agent }) => {
  const roleColors = {
    scout: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30' },
    architect: { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/30' },
    envoy: { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/30' },
    closer: { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/30' },
    orchestrator: { bg: 'bg-[#D4AF37]/10', text: 'text-[#D4AF37]', border: 'border-[#D4AF37]/30' }
  };
  
  const colors = roleColors[agent.role] || roleColors.orchestrator;
  
  return (
    <div className={`p-3 rounded-lg border ${colors.bg} ${colors.border}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Bot className={`w-4 h-4 ${colors.text}`} />
          <span className={`text-sm font-medium ${colors.text}`}>{agent.name}</span>
        </div>
        <span className={`px-2 py-0.5 text-[10px] rounded-full ${colors.bg} ${colors.text} border ${colors.border}`}>
          {agent.role.toUpperCase()}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {agent.capabilities.slice(0, 3).map((cap, idx) => (
          <span key={idx} className="px-1.5 py-0.5 text-[9px] bg-[#1A1A1A] text-[#888] rounded">
            {cap.replace(/_/g, ' ')}
          </span>
        ))}
        {agent.capabilities.length > 3 && (
          <span className="px-1.5 py-0.5 text-[9px] bg-[#1A1A1A] text-[#666] rounded">
            +{agent.capabilities.length - 3}
          </span>
        )}
      </div>
    </div>
  );
};

const CreateBusinessModal = ({ onClose, onCreated, token }) => {
  const [formData, setFormData] = useState({
    name: '',
    type: 'custom',
    description: '',
    tone: 'professional',
    target_audience: '',
    products_services: '',
    unique_selling_points: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const businessTypes = [
    { id: 'skincare', label: 'Skincare/Beauty' },
    { id: 'automotive', label: 'Automotive' },
    { id: 'ecommerce', label: 'E-Commerce' },
    { id: 'saas', label: 'SaaS/Software' },
    { id: 'agency', label: 'Agency' },
    { id: 'healthcare', label: 'Healthcare' },
    { id: 'retail', label: 'Retail' },
    { id: 'custom', label: 'Other' }
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/api/business/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          ...formData,
          products_services: formData.products_services.split(',').map(s => s.trim()).filter(Boolean),
          unique_selling_points: formData.unique_selling_points.split(',').map(s => s.trim()).filter(Boolean)
        })
      });

      const data = await response.json();

      if (response.ok) {
        onCreated(data);
        onClose();
      } else {
        setError(data.detail || 'Failed to create business');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl overflow-hidden">
        <div className="p-6 border-b border-[#1A1A1A]">
          <h2 className="text-xl font-medium text-[#F4F4F4]">Create New Business</h2>
          <p className="text-sm text-[#666] mt-1">Set up AI agents for a new business</p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Business Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="ABC Company"
              className="w-full px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:border-[#D4AF37] focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Business Type</label>
            <div className="grid grid-cols-4 gap-2">
              {businessTypes.map((type) => (
                <button
                  key={type.id}
                  type="button"
                  onClick={() => setFormData({ ...formData, type: type.id })}
                  className={`p-2 text-xs rounded-lg border transition-all ${
                    formData.type === type.id
                      ? 'bg-[#D4AF37]/10 border-[#D4AF37] text-[#D4AF37]'
                      : 'bg-[#050505] border-[#1A1A1A] text-[#888] hover:border-[#333]'
                  }`}
                >
                  {type.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Brief description of the business..."
              rows={2}
              className="w-full px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:border-[#D4AF37] focus:outline-none resize-none"
            />
          </div>

          <div>
            <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Products/Services (comma separated)</label>
            <input
              type="text"
              value={formData.products_services}
              onChange={(e) => setFormData({ ...formData, products_services: e.target.value })}
              placeholder="Product A, Service B, Service C"
              className="w-full px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:border-[#D4AF37] focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Unique Selling Points (comma separated)</label>
            <input
              type="text"
              value={formData.unique_selling_points}
              onChange={(e) => setFormData({ ...formData, unique_selling_points: e.target.value })}
              placeholder="Fast delivery, 24/7 support, Premium quality"
              className="w-full px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:border-[#D4AF37] focus:outline-none"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-[#666] hover:text-[#AAA] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !formData.name}
              className="px-6 py-2 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              Create Business
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const BusinessManagement = ({ token }) => {
  const [businesses, setBusinesses] = useState([]);
  const [selectedBusiness, setSelectedBusiness] = useState(null);
  const [businessDetails, setBusinessDetails] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBusinesses();
  }, []);

  useEffect(() => {
    if (selectedBusiness) {
      fetchBusinessDetails(selectedBusiness.business_id);
    }
  }, [selectedBusiness]);

  const fetchBusinesses = async () => {
    try {
      const response = await fetch(`${API_URL}/api/business/list`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setBusinesses(data.businesses || []);
      
      if (data.businesses?.length > 0 && !selectedBusiness) {
        setSelectedBusiness(data.businesses[0]);
      }
    } catch (error) {
      console.error('Failed to fetch businesses:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchBusinessDetails = async (businessId) => {
    try {
      const response = await fetch(`${API_URL}/api/business/${businessId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setBusinessDetails(data);
    } catch (error) {
      console.error('Failed to fetch business details:', error);
    }
  };

  const handleBusinessCreated = (newBusiness) => {
    fetchBusinesses();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-[#D4AF37] animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-medium text-[#F4F4F4]">Business Management</h1>
          <p className="text-sm text-[#666] mt-1">Manage your businesses and AI agents</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] font-medium rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Business
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Business List */}
        <div className="col-span-1 space-y-3">
          <h2 className="text-sm font-medium text-[#666] uppercase tracking-wider">Your Businesses</h2>
          {businesses.map((business) => (
            <BusinessCard
              key={business.business_id}
              business={business}
              onSelect={setSelectedBusiness}
              onEdit={() => {}}
              isSelected={selectedBusiness?.business_id === business.business_id}
            />
          ))}
          
          {businesses.length === 0 && (
            <div className="text-center py-8 text-[#666]">
              <Building2 className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p className="text-sm">No businesses configured</p>
              <p className="text-xs mt-1">Click "Add Business" to get started</p>
            </div>
          )}
        </div>

        {/* Business Details */}
        <div className="col-span-2 space-y-4">
          {businessDetails ? (
            <>
              {/* Business Info */}
              <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-xl font-medium text-[#F4F4F4]">{businessDetails.business?.name}</h2>
                    <p className="text-sm text-[#666] mt-1">{businessDetails.business?.description}</p>
                  </div>
                  <span className="px-3 py-1 text-xs bg-[#D4AF37]/10 text-[#D4AF37] rounded-full border border-[#D4AF37]/30">
                    {businessDetails.business?.type?.toUpperCase()}
                  </span>
                </div>
                
                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-[#1A1A1A]">
                  <div className="text-center">
                    <div className="text-2xl font-semibold text-[#D4AF37]">{businessDetails.agent_count}</div>
                    <div className="text-xs text-[#666]">Active Agents</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-semibold text-[#4A4]">5</div>
                    <div className="text-xs text-[#666]">Channels</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-semibold text-[#F4F4F4]">OODA</div>
                    <div className="text-xs text-[#666]">Loop Active</div>
                  </div>
                </div>
              </div>

              {/* Agents */}
              <div className="p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl">
                <h3 className="text-sm font-medium text-[#666] uppercase tracking-wider mb-4">XYZ Agent Swarm</h3>
                <div className="grid grid-cols-2 gap-3">
                  {businessDetails.agents?.map((agent) => (
                    <AgentCard key={agent.agent_id} agent={agent} />
                  ))}
                </div>
              </div>

              {/* Quick Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl text-center">
                  <MessageSquare className="w-6 h-6 text-[#D4AF37] mx-auto mb-2" />
                  <div className="text-lg font-semibold text-[#F4F4F4]">1,247</div>
                  <div className="text-xs text-[#666]">Conversations</div>
                </div>
                <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl text-center">
                  <Users className="w-6 h-6 text-[#4A4] mx-auto mb-2" />
                  <div className="text-lg font-semibold text-[#F4F4F4]">342</div>
                  <div className="text-xs text-[#666]">Customers</div>
                </div>
                <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl text-center">
                  <BarChart3 className="w-6 h-6 text-purple-400 mx-auto mb-2" />
                  <div className="text-lg font-semibold text-[#F4F4F4]">94.2%</div>
                  <div className="text-xs text-[#666]">Resolution Rate</div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-64 bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl">
              <div className="text-center text-[#666]">
                <Sparkles className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p className="text-sm">Select a business to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create Business Modal */}
      {showCreateModal && (
        <CreateBusinessModal
          onClose={() => setShowCreateModal(false)}
          onCreated={handleBusinessCreated}
          token={token}
        />
      )}
    </div>
  );
};

export default BusinessManagement;
