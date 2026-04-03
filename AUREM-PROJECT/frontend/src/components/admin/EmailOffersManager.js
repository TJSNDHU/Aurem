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
import { Checkbox } from '../ui/checkbox';
import { ScrollArea } from '../ui/scroll-area';

// Icons
import { 
  Loader2, Send, Mail, Users, Tag, Check, X, 
  RefreshCw, Percent, Sparkles, Filter, CheckCheck, Phone
} from 'lucide-react';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Source color mapping for visual distinction
const SOURCE_COLORS = {
  newsletter: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-300', dot: 'bg-blue-500' },
  bio_scan: { bg: 'bg-purple-100', text: 'text-purple-700', border: 'border-purple-300', dot: 'bg-purple-500' },
  waitlist: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-300', dot: 'bg-amber-500' },
  partner: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-300', dot: 'bg-emerald-500' },
  customer: { bg: 'bg-pink-100', text: 'text-pink-700', border: 'border-pink-300', dot: 'bg-pink-500' }
};

const EmailOffersManager = () => {
  const { shortName } = useAdminBrand();
  
  const [recipients, setRecipients] = useState([]);
  const [sourceCounts, setSourceCounts] = useState({});
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showCreateOffer, setShowCreateOffer] = useState(false);
  const [selectedEmails, setSelectedEmails] = useState(new Set());
  const [filterSource, setFilterSource] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Manual entry state
  const [manualEntry, setManualEntry] = useState('');
  const [manualEmails, setManualEmails] = useState(new Set());
  
  // Offer form state
  const [offerForm, setOfferForm] = useState({
    subject: 'Special Offer Just For You!',
    title: 'Exclusive Discount',
    message: 'As a valued customer, we\'re giving you an exclusive discount!',
    discount_code: '',
    discount_percent: 15,
    brand_prefix: ''
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
        axios.get(`${API}/admin/email-offers/recipients`, { headers }),
        axios.get(`${API}/admin/email-offers/campaigns`, { headers }).catch(() => ({ data: { campaigns: [] } }))
      ]);
      
      setRecipients(recipientsRes.data?.recipients || []);
      setSourceCounts(recipientsRes.data?.source_counts || {});
      setCampaigns(campaignsRes.data?.campaigns || []);
    } catch (error) {
      console.error('Failed to load email offers data:', error);
      toast.error('Failed to load recipients');
    } finally {
      setLoading(false);
    }
  };

  // Filter recipients based on search and source filter
  const filteredRecipients = recipients.filter(r => {
    const matchesSearch = !searchQuery || 
      r.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.name && r.name.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesSource = filterSource === 'all' || r.source === filterSource;
    return matchesSearch && matchesSource;
  });

  // Toggle single email selection
  const toggleEmail = (email) => {
    const newSelected = new Set(selectedEmails);
    if (newSelected.has(email)) {
      newSelected.delete(email);
    } else {
      newSelected.add(email);
    }
    setSelectedEmails(newSelected);
  };

  // Select/Deselect all visible emails
  const toggleSelectAll = () => {
    if (selectedEmails.size === filteredRecipients.length) {
      setSelectedEmails(new Set());
    } else {
      setSelectedEmails(new Set(filteredRecipients.map(r => r.email)));
    }
  };

  // Validate email format
  const isValidEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  // Validate phone format (basic check for digits)
  const isValidPhone = (phone) => {
    const cleaned = phone.replace(/[\s\-\(\)\.+]/g, '');
    return /^\d{10,15}$/.test(cleaned);
  };

  // Add manual entry (email or phone)
  const addManualEntry = () => {
    const entry = manualEntry.trim();
    if (!entry) return;

    // Check if it's an email or phone
    if (isValidEmail(entry)) {
      // Add as email
      const newManualEmails = new Set(manualEmails);
      newManualEmails.add(entry.toLowerCase());
      setManualEmails(newManualEmails);
      
      // Also add to selected emails
      const newSelected = new Set(selectedEmails);
      newSelected.add(entry.toLowerCase());
      setSelectedEmails(newSelected);
      
      setManualEntry('');
      toast.success(`Added email: ${entry}`);
    } else if (isValidPhone(entry)) {
      // For phone, store with phone: prefix
      const phoneEntry = `phone:${entry.replace(/[\s\-\(\)\.]/g, '')}`;
      const newManualEmails = new Set(manualEmails);
      newManualEmails.add(phoneEntry);
      setManualEmails(newManualEmails);
      
      // Also add to selected
      const newSelected = new Set(selectedEmails);
      newSelected.add(phoneEntry);
      setSelectedEmails(newSelected);
      
      setManualEntry('');
      toast.success(`Added phone: ${entry}`);
    } else {
      toast.error('Please enter a valid email address or phone number');
    }
  };

  // Remove manual entry
  const removeManualEntry = (entry) => {
    const newManualEmails = new Set(manualEmails);
    newManualEmails.delete(entry);
    setManualEmails(newManualEmails);
    
    const newSelected = new Set(selectedEmails);
    newSelected.delete(entry);
    setSelectedEmails(newSelected);
  };

  // Generate random discount code
  const generateCode = () => {
    const prefix = offerForm.brand_prefix?.toUpperCase() || shortName;
    const percent = offerForm.discount_percent || 15;
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    const random = Array.from({ length: 5 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    setOfferForm({ ...offerForm, discount_code: `${prefix}${percent}${random}` });
  };

  // Send email offers
  const sendOffers = async () => {
    if (selectedEmails.size === 0 && manualEmails.size === 0) {
      toast.error('Please select at least one recipient or add a manual entry');
      return;
    }

    // Combine selected emails with manual entries
    const allRecipients = [...selectedEmails, ...manualEmails];
    
    // Separate emails from phone numbers
    const emails = allRecipients.filter(r => !r.startsWith('phone:'));
    const phones = allRecipients.filter(r => r.startsWith('phone:')).map(p => p.replace('phone:', ''));

    if (emails.length === 0 && phones.length === 0) {
      toast.error('Please select at least one recipient');
      return;
    }

    setSending(true);
    try {
      const response = await axios.post(`${API}/admin/email-offers/send`, {
        ...offerForm,
        recipient_emails: emails,
        recipient_phones: phones
      }, { headers });

      toast.success(`Sent to ${response.data.sent_count} recipients!`);
      
      if (response.data.discount_code) {
        toast.success(`Discount code created: ${response.data.discount_code}`);
      }
      
      setShowCreateOffer(false);
      setSelectedEmails(new Set());
      setManualEmails(new Set());
      loadData();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Failed to send offers';
      toast.error(errorMsg);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12" data-testid="email-offers-loading">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="email-offers-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">Email Offers</h2>
          <p className="text-sm text-gray-500 mt-1">Send promotional emails to customers from all programs</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadData} className="text-[#2D2A2E] border-gray-300" data-testid="refresh-recipients">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Dialog open={showCreateOffer} onOpenChange={setShowCreateOffer}>
            <DialogTrigger asChild>
              <Button className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white" data-testid="create-email-offer-btn">
                <Mail className="h-4 w-4 mr-2" />
                Create Email Offer
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-[#F8A5B8]" />
                  Create Email Offer
                </DialogTitle>
              </DialogHeader>
              
              <div className="space-y-5 py-2">
                {/* Subject Line */}
                <div>
                  <Label>Subject Line</Label>
                  <Input 
                    value={offerForm.subject}
                    onChange={(e) => setOfferForm({ ...offerForm, subject: e.target.value })}
                    placeholder="Special Offer Just For You!"
                    className="mt-1"
                    data-testid="offer-subject-input"
                  />
                </div>
                
                {/* Offer Title */}
                <div>
                  <Label>Offer Title</Label>
                  <Input 
                    value={offerForm.title}
                    onChange={(e) => setOfferForm({ ...offerForm, title: e.target.value })}
                    placeholder="Exclusive Discount"
                    className="mt-1"
                    data-testid="offer-title-input"
                  />
                </div>
                
                {/* Message */}
                <div>
                  <Label>Message</Label>
                  <Textarea 
                    value={offerForm.message}
                    onChange={(e) => setOfferForm({ ...offerForm, message: e.target.value })}
                    placeholder="As a valued customer, we're giving you an exclusive discount!"
                    rows={3}
                    className="mt-1"
                    data-testid="offer-message-input"
                  />
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
                        data-testid="offer-discount-code-input"
                      />
                      <Button 
                        type="button" 
                        variant="outline" 
                        onClick={generateCode}
                        className="shrink-0"
                        data-testid="generate-code-btn"
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
                        data-testid="offer-discount-percent-input"
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
                    data-testid="offer-brand-prefix-input"
                  />
                  <p className="text-xs text-gray-500 mt-1">Leave empty to use store name as prefix</p>
                </div>
                
                {/* Manual Entry Section */}
                <div className="border-t pt-4">
                  <Label className="flex items-center gap-2 mb-3">
                    <Mail className="h-4 w-4" />
                    Add Manual Recipient
                  </Label>
                  <p className="text-xs text-gray-500 mb-3">Enter an email address or phone number to add manually</p>
                  
                  <div className="flex gap-2">
                    <Input 
                      value={manualEntry}
                      onChange={(e) => setManualEntry(e.target.value)}
                      placeholder="email@example.com or +1234567890"
                      className="flex-1"
                      data-testid="manual-entry-input"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          addManualEntry();
                        }
                      }}
                    />
                    <Button 
                      type="button"
                      onClick={addManualEntry}
                      className="bg-[#F8A5B8] hover:bg-[#F8A5B8]/90 text-[#2D2A2E]"
                      data-testid="add-manual-entry-btn"
                    >
                      Add
                    </Button>
                  </div>
                  
                  {/* Show manually added entries */}
                  {manualEmails.size > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-gray-500 mb-2">Manually added ({manualEmails.size}):</p>
                      <div className="flex flex-wrap gap-2">
                        {[...manualEmails].map((entry) => {
                          const isPhone = entry.startsWith('phone:');
                          const displayValue = isPhone ? entry.replace('phone:', '') : entry;
                          return (
                            <Badge 
                              key={entry}
                              variant="outline"
                              className={`${isPhone ? 'bg-blue-50 text-blue-700 border-blue-300' : 'bg-green-50 text-green-700 border-green-300'} flex items-center gap-1 py-1 px-2`}
                            >
                              {isPhone ? '📱' : '✉️'} {displayValue}
                              <button 
                                type="button"
                                onClick={() => removeManualEntry(entry)}
                                className="ml-1 hover:text-red-500"
                                data-testid={`remove-${entry.replace(/[@.:+]/g, '-')}`}
                              >
                                <X className="h-3 w-3" />
                              </button>
                            </Badge>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
                
                {/* Recipient Selection */}
                <div className="border-t pt-4">
                  <div className="flex items-center justify-between mb-3">
                    <Label className="flex items-center gap-2">
                      <Users className="h-4 w-4" />
                      Select Recipients
                    </Label>
                    <div className="flex items-center gap-2">
                      <Button 
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={toggleSelectAll}
                        className="text-sm"
                        data-testid="select-all-btn"
                      >
                        <CheckCheck className="h-4 w-4 mr-1" />
                        {selectedEmails.size === filteredRecipients.length ? 'Deselect All' : 'Select All'}
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
                      data-testid="filter-all"
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
                          data-testid={`filter-${sourceKey}`}
                        >
                          <span className={`w-2 h-2 rounded-full mr-2 ${colors.dot}`}></span>
                          {source} ({count})
                        </Button>
                      );
                    })}
                  </div>
                  
                  {/* Search */}
                  <Input 
                    placeholder="Search emails..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="mb-3"
                    data-testid="search-recipients-input"
                  />
                  
                  {/* Recipient list */}
                  <ScrollArea className="h-[200px] border rounded-lg">
                    <div className="p-2 space-y-1">
                      {filteredRecipients.map((recipient) => {
                        const isSelected = selectedEmails.has(recipient.email);
                        const colors = SOURCE_COLORS[recipient.source] || SOURCE_COLORS.customer;
                        
                        return (
                          <div 
                            key={recipient.id} 
                            className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all ${
                              isSelected 
                                ? 'bg-green-50 border border-green-300' 
                                : 'hover:bg-gray-50 border border-transparent'
                            }`}
                            onClick={() => toggleEmail(recipient.email)}
                            data-testid={`recipient-${recipient.email.replace('@', '-').replace('.', '-')}`}
                          >
                            <div className={`w-5 h-5 rounded flex items-center justify-center ${
                              isSelected ? 'bg-green-500' : 'bg-gray-200'
                            }`}>
                              {isSelected && <Check className="h-3 w-3 text-white" />}
                            </div>
                            
                            <span className={`w-2 h-2 rounded-full ${colors.dot}`}></span>
                            
                            <div className="flex-1 min-w-0">
                              <p className={`text-sm truncate ${isSelected ? 'text-green-700 font-medium' : 'text-gray-700'}`}>
                                {recipient.email}
                              </p>
                              {recipient.name && (
                                <p className="text-xs text-gray-500 truncate">{recipient.name}</p>
                              )}
                            </div>
                            
                            <Badge variant="outline" className={`text-xs ${colors.bg} ${colors.text} ${colors.border}`}>
                              {recipient.source_label}
                            </Badge>
                          </div>
                        );
                      })}
                      
                      {filteredRecipients.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                          <Mail className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                          <p>No recipients found</p>
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                  
                  <p className={`text-sm mt-2 ${(selectedEmails.size + manualEmails.size) > 0 ? 'text-green-600 font-medium' : 'text-gray-500'}`}>
                    {selectedEmails.size + manualEmails.size} recipient{(selectedEmails.size + manualEmails.size) !== 1 ? 's' : ''} selected
                    {manualEmails.size > 0 && <span className="text-blue-600 ml-1">({manualEmails.size} manual)</span>}
                  </p>
                </div>
                
                {/* Send Button */}
                <Button 
                  onClick={sendOffers} 
                  disabled={sending || (selectedEmails.size === 0 && manualEmails.size === 0)}
                  className="w-full bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white h-12"
                  data-testid="send-offer-btn"
                >
                  {sending ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4 mr-2" />
                      Send Offer to {selectedEmails.size + manualEmails.size} Recipient{(selectedEmails.size + manualEmails.size) !== 1 ? 's' : ''}
                    </>
                  )}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
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
              <Users className="w-3 h-3 text-gray-500" />
              <span className="text-sm font-medium text-gray-600">Total</span>
            </div>
            <p className="text-2xl font-bold text-gray-700">{recipients.length}</p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Campaigns */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-[#F8A5B8]" />
            Recent Campaigns
          </CardTitle>
        </CardHeader>
        <CardContent>
          {campaigns.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Mail className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>No email campaigns sent yet</p>
              <p className="text-sm">Create your first offer to get started</p>
            </div>
          ) : (
            <div className="space-y-3">
              {campaigns.slice(0, 10).map((campaign) => (
                <div 
                  key={campaign.id} 
                  className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                  data-testid={`campaign-${campaign.id}`}
                >
                  <div className="flex-1">
                    <p className="font-medium text-[#2D2A2E]">{campaign.title}</p>
                    <p className="text-sm text-gray-500">{campaign.subject}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(campaign.created_at).toLocaleDateString()} at {new Date(campaign.created_at).toLocaleTimeString()}
                    </p>
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

export default EmailOffersManager;
