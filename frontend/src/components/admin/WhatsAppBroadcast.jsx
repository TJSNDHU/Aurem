import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  MessageCircle, Users, Send, Copy, ExternalLink, Filter, 
  CheckCircle2, Clock, Loader2, RefreshCcw, Search, Download
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Textarea } from '../ui/textarea';
import { useAdminBrand } from './useAdminBrand';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL);

// WhatsApp Business Number (Canada)
const WHATSAPP_BUSINESS_NUMBER = '16475551234'; // Replace with actual number

/**
 * WhatsAppBroadcast Component
 * 
 * Admin panel for managing WhatsApp broadcasts via wa.me links.
 * Lists all opted-in customers, generates wa.me links with pre-filled messages.
 */
const WhatsAppBroadcast = () => {
  const { name: brandName, activeBrand } = useAdminBrand();
  
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [messageTemplate, setMessageTemplate] = useState(`Hi {name}! 👋\n\nThank you for being a ${brandName} customer. We have exciting news about your skincare journey!\n\n{custom_message}\n\n- The ${brandName} Team 🌱`);
  const [customMessage, setCustomMessage] = useState('');
  const [selectedCustomers, setSelectedCustomers] = useState([]);
  const [generatedLinks, setGeneratedLinks] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    purchased: 0,
    quiz_only: 0,
    vip: 0
  });

  // Fetch opted-in customers with brand filter
  const fetchCustomers = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.get(`${API}/api/admin/whatsapp-broadcast/customers`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { filter, brand: activeBrand }
      });
      setCustomers(res.data.customers || []);
      setStats(res.data.stats || stats);
    } catch (error) {
      console.error('Failed to fetch customers:', error);
      toast.error('Failed to load customers');
      // Use sample data for demo
      setCustomers([]);
    } finally {
      setLoading(false);
    }
  }, [filter, activeBrand]);

  useEffect(() => {
    fetchCustomers();
  }, [fetchCustomers]);
  
  // Update message template when brand changes
  useEffect(() => {
    setMessageTemplate(`Hi {name}! 👋\n\nThank you for being a ${brandName} customer. We have exciting news about your skincare journey!\n\n{custom_message}\n\n- The ${brandName} Team 🌱`);
  }, [brandName]);

  // Generate wa.me link for a customer
  const generateLink = (customer, message) => {
    const phone = customer.whatsapp_phone || customer.phone;
    if (!phone) return null;
    
    // Clean phone number (remove spaces, dashes, parentheses, keep digits and +)
    let cleanPhone = phone.replace(/[^\d+]/g, '');
    // Remove leading + if present, wa.me doesn't need it
    cleanPhone = cleanPhone.replace(/^\+/, '');
    // If no country code, assume Canada (+1)
    if (cleanPhone.length === 10) {
      cleanPhone = '1' + cleanPhone;
    }
    
    // Personalize message
    const personalizedMessage = message
      .replace('{name}', customer.name || customer.first_name || 'there')
      .replace('{custom_message}', customMessage);
    
    return `https://wa.me/${cleanPhone}?text=${encodeURIComponent(personalizedMessage)}`;
  };

  // Generate links for all selected customers
  const handleGenerateLinks = () => {
    const targets = selectedCustomers.length > 0 
      ? customers.filter(c => selectedCustomers.includes(c.id || c.email))
      : customers;
    
    const links = targets
      .map(customer => {
        const link = generateLink(customer, messageTemplate);
        if (!link) return null;
        return {
          customer,
          link,
          status: 'pending'
        };
      })
      .filter(Boolean);
    
    setGeneratedLinks(links);
    toast.success(`Generated ${links.length} WhatsApp links`);
  };

  // Copy all links to clipboard
  const handleCopyAllLinks = () => {
    const linksText = generatedLinks.map(l => `${l.customer.name || l.customer.email}: ${l.link}`).join('\n\n');
    navigator.clipboard.writeText(linksText);
    toast.success('All links copied to clipboard');
  };

  // Open link in new tab
  const handleOpenLink = (link, index) => {
    window.open(link.link, '_blank');
    setGeneratedLinks(prev => 
      prev.map((l, i) => i === index ? { ...l, status: 'opened' } : l)
    );
  };

  // Filter customers based on search
  const filteredCustomers = customers.filter(c => {
    const searchLower = searchQuery.toLowerCase();
    return (
      (c.name || '').toLowerCase().includes(searchLower) ||
      (c.email || '').toLowerCase().includes(searchLower) ||
      (c.phone || '').includes(searchQuery)
    );
  });

  // Toggle customer selection
  const toggleCustomerSelection = (customerId) => {
    setSelectedCustomers(prev => 
      prev.includes(customerId) 
        ? prev.filter(id => id !== customerId)
        : [...prev, customerId]
    );
  };

  // Select all filtered customers
  const handleSelectAll = () => {
    if (selectedCustomers.length === filteredCustomers.length) {
      setSelectedCustomers([]);
    } else {
      setSelectedCustomers(filteredCustomers.map(c => c.id || c.email));
    }
  };

  return (
    <div className="space-y-6" data-testid="whatsapp-broadcast">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-xl">
              <MessageCircle className="h-6 w-6 text-green-600" />
            </div>
            WhatsApp Broadcast
          </h1>
          <p className="text-gray-500 mt-1">Send personalized messages to opted-in customers</p>
        </div>
        <Button onClick={fetchCustomers} variant="outline" className="gap-2">
          <RefreshCcw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-green-50 to-emerald-50 border-green-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Users className="h-8 w-8 text-green-600" />
              <div>
                <p className="text-2xl font-bold text-green-700">{stats.total}</p>
                <p className="text-sm text-green-600">Total Opted-In</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-8 w-8 text-blue-600" />
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats.purchased}</p>
                <p className="text-sm text-gray-500">Purchased</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Clock className="h-8 w-8 text-amber-600" />
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats.quiz_only}</p>
                <p className="text-sm text-gray-500">Quiz Only</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <span className="text-2xl">⭐</span>
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats.vip}</p>
                <p className="text-sm text-gray-500">VIP (3+ orders)</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Left: Customer List */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Customers</CardTitle>
              <div className="flex gap-2">
                {['all', 'purchased', 'quiz_only', 'vip'].map((f) => (
                  <Button
                    key={f}
                    variant={filter === f ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setFilter(f)}
                    className={filter === f ? 'bg-green-600 hover:bg-green-700' : ''}
                  >
                    {f === 'all' ? 'All' : f === 'purchased' ? 'Purchased' : f === 'quiz_only' ? 'Quiz' : 'VIP'}
                  </Button>
                ))}
              </div>
            </div>
            <div className="flex gap-2 mt-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search by name, email, or phone..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Button variant="outline" size="sm" onClick={handleSelectAll}>
                {selectedCustomers.length === filteredCustomers.length ? 'Deselect All' : 'Select All'}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="max-h-[400px] overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-green-600" />
              </div>
            ) : filteredCustomers.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Users className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                <p>No opted-in customers found</p>
                <p className="text-sm">Customers opt-in during checkout</p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredCustomers.map((customer, idx) => (
                  <div
                    key={customer.id || customer.email || idx}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      selectedCustomers.includes(customer.id || customer.email)
                        ? 'border-green-500 bg-green-50'
                        : 'border-gray-200 hover:border-green-300 hover:bg-green-50/50'
                    }`}
                    onClick={() => toggleCustomerSelection(customer.id || customer.email)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={selectedCustomers.includes(customer.id || customer.email)}
                          onChange={() => {}}
                          className="w-4 h-4 text-green-600 rounded"
                        />
                        <div>
                          <p className="font-medium text-gray-900">
                            {customer.name || customer.first_name || 'Unknown'}
                          </p>
                          <p className="text-sm text-gray-500">{customer.email}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-600">
                          {customer.whatsapp_phone || customer.phone || 'No phone'}
                        </p>
                        {customer.order_count > 0 && (
                          <Badge variant="outline" className="text-xs">
                            {customer.order_count} order{customer.order_count > 1 ? 's' : ''}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right: Message Composer */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Compose Message</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700 mb-2 block">
                Message Template
              </label>
              <Textarea
                value={messageTemplate}
                onChange={(e) => setMessageTemplate(e.target.value)}
                rows={5}
                className="resize-none"
                placeholder="Use {name} and {custom_message} as placeholders"
              />
              <p className="text-xs text-gray-500 mt-1">
                Use {'{name}'} for customer name, {'{custom_message}'} for your custom content
              </p>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700 mb-2 block">
                Custom Message Content
              </label>
              <Textarea
                value={customMessage}
                onChange={(e) => setCustomMessage(e.target.value)}
                rows={3}
                className="resize-none"
                placeholder="Your special announcement, promotion, or update..."
              />
            </div>

            <div className="flex gap-2">
              <Button
                onClick={handleGenerateLinks}
                className="flex-1 bg-green-600 hover:bg-green-700"
                disabled={customers.length === 0}
              >
                <Send className="h-4 w-4 mr-2" />
                Generate {selectedCustomers.length > 0 ? selectedCustomers.length : filteredCustomers.length} Links
              </Button>
            </div>

            {/* Generated Links */}
            {generatedLinks.length > 0 && (
              <div className="mt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium text-gray-900">Generated Links ({generatedLinks.length})</h4>
                  <Button variant="outline" size="sm" onClick={handleCopyAllLinks}>
                    <Copy className="h-4 w-4 mr-1" />
                    Copy All
                  </Button>
                </div>
                <div className="max-h-[200px] overflow-y-auto space-y-2">
                  {generatedLinks.map((link, idx) => (
                    <div
                      key={idx}
                      className={`p-2 rounded-lg border flex items-center justify-between ${
                        link.status === 'opened' ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        {link.status === 'opened' ? (
                          <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
                        ) : (
                          <Clock className="h-4 w-4 text-gray-400 flex-shrink-0" />
                        )}
                        <span className="text-sm text-gray-700 truncate">
                          {link.customer.name || link.customer.email}
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenLink(link, idx)}
                        className="text-green-600 hover:text-green-700"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Business Number Config */}
      <Card className="bg-amber-50 border-amber-200">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <MessageCircle className="h-5 w-5 text-amber-600 mt-0.5" />
            <div>
              <p className="font-medium text-amber-800">WhatsApp Business Number</p>
              <p className="text-sm text-amber-700 mt-1">
                Current number: <code className="bg-amber-100 px-2 py-0.5 rounded">+1 {WHATSAPP_BUSINESS_NUMBER.slice(1, 4)} {WHATSAPP_BUSINESS_NUMBER.slice(4, 7)} {WHATSAPP_BUSINESS_NUMBER.slice(7)}</code>
              </p>
              <p className="text-xs text-amber-600 mt-2">
                To change this number, update the WHATSAPP_BUSINESS_NUMBER constant in the component file.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default WhatsAppBroadcast;
