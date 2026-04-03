import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAdminBrand } from './useAdminBrand';

// UI Components
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { ScrollArea } from '../ui/scroll-area';
import { Switch } from '../ui/switch';

// Icons
import { 
  Loader2, Send, MessageCircle, Users, Tag, Check, X, 
  RefreshCw, Percent, Sparkles, CheckCheck, Phone, 
  MessageSquare, Shield
} from 'lucide-react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Source color mapping for visual distinction (same as email offers)
const SOURCE_COLORS = {
  newsletter: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-300', dot: 'bg-blue-500' },
  bio_scan: { bg: 'bg-purple-100', text: 'text-purple-700', border: 'border-purple-300', dot: 'bg-purple-500' },
  waitlist: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-300', dot: 'bg-amber-500' },
  partner: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-300', dot: 'bg-emerald-500' },
  customer: { bg: 'bg-pink-100', text: 'text-pink-700', border: 'border-pink-300', dot: 'bg-pink-500' }
};

const SMSOffersManager = () => {
  const { name: brandName, shortName } = useAdminBrand();
  
  const [recipients, setRecipients] = useState([]);
  const [sourceCounts, setSourceCounts] = useState({});
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showCreateOffer, setShowCreateOffer] = useState(false);
  const [selectedPhones, setSelectedPhones] = useState(new Set());
  const [filterSource, setFilterSource] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [verifiedCount, setVerifiedCount] = useState(0);
  
  // Offer form state
  const [offerForm, setOfferForm] = useState({
    message: `Hey! We have a special offer just for you at ${brandName}. Check out our latest skincare products!`,
    discount_code: '',
    discount_percent: 15,
    brand_prefix: '',
    message_type: 'whatsapp'  // 'whatsapp' or 'sms'
  });

  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [recipientsRes, campaignsRes] = await Promise.all([
        axios.get(`${API}/admin/sms-offers/recipients`, { headers }),
        axios.get(`${API}/admin/sms-offers/campaigns`, { headers }).catch(() => ({ data: { campaigns: [] } }))
      ]);
      
      setRecipients(recipientsRes.data?.recipients || []);
      setSourceCounts(recipientsRes.data?.source_counts || {});
      setVerifiedCount(recipientsRes.data?.verified_count || 0);
      setCampaigns(campaignsRes.data?.campaigns || []);
    } catch (error) {
      console.error('Failed to load SMS offers data:', error);
      toast.error('Failed to load phone numbers');
    } finally {
      setLoading(false);
    }
  };

  // Filter recipients based on search and source filter
  const filteredRecipients = recipients.filter(r => {
    const matchesSearch = !searchQuery || 
      r.phone.includes(searchQuery) ||
      r.display_phone.includes(searchQuery) ||
      (r.name && r.name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (r.email && r.email.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesSource = filterSource === 'all' || r.source === filterSource;
    return matchesSearch && matchesSource;
  });

  // Toggle single phone selection
  const togglePhone = (phone) => {
    const newSelected = new Set(selectedPhones);
    if (newSelected.has(phone)) {
      newSelected.delete(phone);
    } else {
      newSelected.add(phone);
    }
    setSelectedPhones(newSelected);
  };

  // Select/Deselect all visible phones
  const toggleSelectAll = () => {
    if (selectedPhones.size === filteredRecipients.length) {
      setSelectedPhones(new Set());
    } else {
      setSelectedPhones(new Set(filteredRecipients.map(r => r.phone)));
    }
  };

  // Generate random discount code
  const generateCode = () => {
    const prefix = offerForm.brand_prefix?.toUpperCase() || shortName;
    const percent = offerForm.discount_percent || 15;
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    const random = Array.from({ length: 5 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    setOfferForm({ ...offerForm, discount_code: `${prefix}${percent}${random}` });
  };

  // Send SMS/WhatsApp offers
  const sendOffers = async () => {
    if (selectedPhones.size === 0) {
      toast.error('Please select at least one recipient');
      return;
    }

    if (!offerForm.message.trim()) {
      toast.error('Please enter a message');
      return;
    }

    setSending(true);
    try {
      const response = await axios.post(`${API}/admin/sms-offers/send`, {
        ...offerForm,
        recipient_phones: Array.from(selectedPhones)
      }, { headers });

      toast.success(`Sent to ${response.data.sent_count} recipients via ${offerForm.message_type === 'whatsapp' ? 'WhatsApp' : 'SMS'}!`);
      
      if (response.data.discount_code) {
        toast.success(`Discount code created: ${response.data.discount_code}`);
      }
      
      if (response.data.failed_count > 0) {
        toast.warning(`${response.data.failed_count} messages failed to send`);
      }
      
      setShowCreateOffer(false);
      setSelectedPhones(new Set());
      loadData();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Failed to send offers';
      toast.error(errorMsg);
    } finally {
      setSending(false);
    }
  };

  // Format phone for display
  const formatPhoneDisplay = (phone) => {
    if (!phone) return '';
    if (phone.length > 10) {
      return `+${phone.slice(0, -10)} ${phone.slice(-10, -7)} ${phone.slice(-7, -4)} ${phone.slice(-4)}`;
    }
    return phone;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12" data-testid="sms-offers-loading">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="sms-offers-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">SMS / WhatsApp Offers</h2>
          <p className="text-sm text-gray-500 mt-1">Send promotional messages to customers from all programs via WHAPI</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadData} className="text-[#2D2A2E] border-gray-300" data-testid="refresh-sms-recipients">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Dialog open={showCreateOffer} onOpenChange={setShowCreateOffer}>
            <DialogTrigger asChild>
              <Button className="bg-green-600 hover:bg-green-700 text-white" data-testid="create-sms-offer-btn">
                <MessageCircle className="h-4 w-4 mr-2" />
                Create SMS Offer
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <MessageCircle className="h-5 w-5 text-green-500" />
                  Create SMS / WhatsApp Offer
                </DialogTitle>
              </DialogHeader>
              
              <div className="space-y-5 py-2">
                {/* Message Type Toggle */}
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-5 w-5 text-gray-500" />
                    <span className="font-medium">Message Type</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <button
                      type="button"
                      onClick={() => setOfferForm({ ...offerForm, message_type: 'whatsapp' })}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors ${
                        offerForm.message_type === 'whatsapp' 
                          ? 'bg-green-500 text-white' 
                          : 'bg-gray-200 text-gray-600'
                      }`}
                      data-testid="msg-type-whatsapp"
                    >
                      <MessageCircle className="h-4 w-4" />
                      WhatsApp
                    </button>
                    <button
                      type="button"
                      onClick={() => setOfferForm({ ...offerForm, message_type: 'sms' })}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors ${
                        offerForm.message_type === 'sms' 
                          ? 'bg-blue-500 text-white' 
                          : 'bg-gray-200 text-gray-600'
                      }`}
                      data-testid="msg-type-sms"
                    >
                      <Phone className="h-4 w-4" />
                      SMS
                    </button>
                  </div>
                </div>
                
                {/* Message */}
                <div>
                  <Label>Message</Label>
                  <Textarea 
                    value={offerForm.message}
                    onChange={(e) => setOfferForm({ ...offerForm, message: e.target.value })}
                    placeholder="Hey! We have a special offer just for you..."
                    rows={4}
                    className="mt-1"
                    data-testid="sms-message-input"
                  />
                  <p className="text-xs text-gray-500 mt-1">{offerForm.message.length}/500 characters</p>
                </div>
                
                {/* Discount Settings */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Discount Code (optional)</Label>
                    <div className="flex gap-2 mt-1">
                      <Input 
                        value={offerForm.discount_code}
                        onChange={(e) => setOfferForm({ ...offerForm, discount_code: e.target.value.toUpperCase() })}
                        placeholder="Auto-generated"
                        className="flex-1"
                        data-testid="sms-discount-code-input"
                      />
                      <Button 
                        type="button" 
                        variant="outline" 
                        onClick={generateCode}
                        className="shrink-0"
                        data-testid="sms-generate-code-btn"
                      >
                        <Tag className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <div>
                    <Label>Discount %</Label>
                    <div className="relative mt-1">
                      <Input 
                        type="number"
                        min="0"
                        max="100"
                        value={offerForm.discount_percent}
                        onChange={(e) => setOfferForm({ ...offerForm, discount_percent: parseInt(e.target.value) || 0 })}
                        className="pr-8"
                        data-testid="sms-discount-percent-input"
                      />
                      <Percent className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                    </div>
                  </div>
                </div>
                
                {/* Brand Prefix */}
                <div>
                  <Label>Brand Prefix (for code generation)</Label>
                  <Input 
                    value={offerForm.brand_prefix}
                    onChange={(e) => setOfferForm({ ...offerForm, brand_prefix: e.target.value.toUpperCase() })}
                    placeholder={shortName}
                    className="mt-1"
                    data-testid="sms-brand-prefix-input"
                  />
                  <p className="text-xs text-gray-500 mt-1">Leave empty to use store name as prefix</p>
                </div>
                
                {/* Recipient Selection */}
                <div className="border-t pt-4">
                  <div className="flex items-center justify-between mb-3">
                    <Label className="flex items-center gap-2">
                      <Phone className="h-4 w-4" />
                      Select Recipients
                    </Label>
                    <div className="flex items-center gap-2">
                      <Button 
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={toggleSelectAll}
                        className="text-sm"
                        data-testid="sms-select-all-btn"
                      >
                        <CheckCheck className="h-4 w-4 mr-1" />
                        {selectedPhones.size === filteredRecipients.length ? 'Deselect All' : 'Select All'}
                      </Button>
                    </div>
                  </div>
                  
                  {/* Source filter */}
                  <div className="flex flex-wrap gap-2 mb-3">
                    <Button
                      type="button"
                      variant={filterSource === 'all' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setFilterSource('all')}
                      className={filterSource === 'all' ? 'bg-[#2D2A2E]' : ''}
                      data-testid="sms-filter-all"
                    >
                      All ({recipients.length})
                    </Button>
                    {Object.entries(sourceCounts).map(([source, count]) => {
                      const sourceKey = source.toLowerCase().replace('-', '_').replace(' ', '_');
                      const colors = SOURCE_COLORS[sourceKey] || SOURCE_COLORS.customer;
                      return (
                        <Button
                          key={source}
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setFilterSource(sourceKey === 'bio_age_scan' ? 'bio_scan' : sourceKey)}
                          className={`${filterSource === sourceKey ? colors.bg + ' ' + colors.text + ' ' + colors.border : ''}`}
                          data-testid={`sms-filter-${sourceKey}`}
                        >
                          <span className={`w-2 h-2 rounded-full mr-2 ${colors.dot}`}></span>
                          {source} ({count})
                        </Button>
                      );
                    })}
                  </div>
                  
                  {/* Search */}
                  <Input 
                    placeholder="Search phone numbers..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="mb-3"
                    data-testid="sms-search-recipients-input"
                  />
                  
                  {/* Recipient list */}
                  <ScrollArea className="h-[200px] border rounded-lg">
                    <div className="p-2 space-y-1">
                      {filteredRecipients.map((recipient) => {
                        const isSelected = selectedPhones.has(recipient.phone);
                        const colors = SOURCE_COLORS[recipient.source] || SOURCE_COLORS.customer;
                        
                        return (
                          <div 
                            key={recipient.id} 
                            className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all ${
                              isSelected 
                                ? 'bg-green-50 border border-green-300' 
                                : 'hover:bg-gray-50 border border-transparent'
                            }`}
                            onClick={() => togglePhone(recipient.phone)}
                            data-testid={`sms-recipient-${recipient.phone.slice(-4)}`}
                          >
                            <div className={`w-5 h-5 rounded flex items-center justify-center ${
                              isSelected ? 'bg-green-500' : 'bg-gray-200'
                            }`}>
                              {isSelected && <Check className="h-3 w-3 text-white" />}
                            </div>
                            
                            <span className={`w-2 h-2 rounded-full ${colors.dot}`}></span>
                            
                            <div className="flex-1 min-w-0">
                              <p className={`text-sm font-mono truncate ${isSelected ? 'text-green-700 font-medium' : 'text-gray-700'}`}>
                                {recipient.display_phone}
                              </p>
                              {recipient.name && (
                                <p className="text-xs text-gray-500 truncate">{recipient.name}</p>
                              )}
                            </div>
                            
                            {recipient.whatsapp_verified && (
                              <Shield className="h-4 w-4 text-green-500" title="WhatsApp Verified" />
                            )}
                            
                            <Badge variant="outline" className={`text-xs ${colors.bg} ${colors.text} ${colors.border}`}>
                              {recipient.source_label}
                            </Badge>
                          </div>
                        );
                      })}
                      
                      {filteredRecipients.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                          <Phone className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                          <p>No phone numbers found</p>
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                  
                  <p className={`text-sm mt-2 ${selectedPhones.size > 0 ? 'text-green-600 font-medium' : 'text-gray-500'}`}>
                    {selectedPhones.size} recipient{selectedPhones.size !== 1 ? 's' : ''} selected
                  </p>
                </div>
                
                {/* Send Button */}
                <Button 
                  onClick={sendOffers} 
                  disabled={sending || selectedPhones.size === 0}
                  className={`w-full h-12 ${
                    offerForm.message_type === 'whatsapp' 
                      ? 'bg-green-600 hover:bg-green-700' 
                      : 'bg-blue-600 hover:bg-blue-700'
                  } text-white`}
                  data-testid="send-sms-offer-btn"
                >
                  {sending ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4 mr-2" />
                      Send {offerForm.message_type === 'whatsapp' ? 'WhatsApp' : 'SMS'} to {selectedPhones.size} Recipient{selectedPhones.size !== 1 ? 's' : ''}
                    </>
                  )}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        {Object.entries(sourceCounts).map(([source, count]) => {
          const sourceKey = source.toLowerCase().replace('-', '_').replace(' ', '_');
          const colors = SOURCE_COLORS[sourceKey] || SOURCE_COLORS.customer;
          return (
            <Card key={source} className={`border-2 ${colors.border}`}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`w-3 h-3 rounded-full ${colors.dot}`}></span>
                  <span className="text-sm font-medium text-gray-600">{source}</span>
                </div>
                <p className={`text-2xl font-bold ${colors.text}`}>{count}</p>
              </CardContent>
            </Card>
          );
        })}
        <Card className="border-2 border-gray-300">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <Phone className="w-3 h-3 text-gray-500" />
              <span className="text-sm font-medium text-gray-600">Total</span>
            </div>
            <p className="text-2xl font-bold text-gray-700">{recipients.length}</p>
          </CardContent>
        </Card>
        <Card className="border-2 border-green-300">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <Shield className="w-3 h-3 text-green-500" />
              <span className="text-sm font-medium text-gray-600">Verified</span>
            </div>
            <p className="text-2xl font-bold text-green-600">{verifiedCount}</p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Campaigns */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-green-500" />
            Recent SMS Campaigns
          </CardTitle>
        </CardHeader>
        <CardContent>
          {campaigns.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <MessageCircle className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>No SMS campaigns sent yet</p>
              <p className="text-sm">Create your first offer to get started</p>
            </div>
          ) : (
            <div className="space-y-3">
              {campaigns.slice(0, 10).map((campaign) => (
                <div 
                  key={campaign.id} 
                  className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                  data-testid={`sms-campaign-${campaign.id}`}
                >
                  <div className="flex-1">
                    <p className="font-medium text-[#2D2A2E] line-clamp-1">{campaign.message}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="outline" className={campaign.message_type === 'whatsapp' ? 'bg-green-50 text-green-700' : 'bg-blue-50 text-blue-700'}>
                        {campaign.message_type === 'whatsapp' ? 'WhatsApp' : 'SMS'}
                      </Badge>
                      <span className="text-xs text-gray-400">
                        {new Date(campaign.created_at).toLocaleDateString()} at {new Date(campaign.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {campaign.discount_code && (
                      <Badge variant="outline" className="font-mono">
                        {campaign.discount_code}
                      </Badge>
                    )}
                    {campaign.discount_percent && (
                      <Badge className="bg-green-100 text-green-700">
                        {campaign.discount_percent}% OFF
                      </Badge>
                    )}
                    <div className="text-right">
                      <p className="text-sm font-medium text-green-600">
                        <Check className="h-3 w-3 inline mr-1" />
                        {campaign.sent_count} sent
                      </p>
                      {campaign.failed_count > 0 && (
                        <p className="text-xs text-red-500">
                          <X className="h-3 w-3 inline mr-1" />
                          {campaign.failed_count} failed
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default SMSOffersManager;
