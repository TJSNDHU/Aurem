import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

// UI Components
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';

// Icons
import { 
  Loader2, Users, Mail, Search, Download, 
  RefreshCw, Phone, Tag, Send, Gift
} from 'lucide-react';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const SubscribersSection = () => {
  const [subscribers, setSubscribers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [sources, setSources] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  
  // Send Offer State
  const [showSendOffer, setShowSendOffer] = useState(false);
  const [selectedSubscriber, setSelectedSubscriber] = useState(null);
  const [sendingOffer, setSendingOffer] = useState(false);
  const [offerData, setOfferData] = useState({
    subject: '🎁 Special Offer Just For You!',
    message: 'Hi there!\n\nWe have an exclusive offer just for you:\n\n• 20% OFF your next purchase\n• Use code: SPECIAL20\n• Valid for 7 days\n\nShop now at reroots.ca\n\nThank you for being part of our community!\n\n- ReRoots Aesthetics Team',
    discount_code: 'SPECIAL20',
    discount_percent: 20
  });
  
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    loadSubscribers();
  }, []);

  const loadSubscribers = async () => {
    setLoading(true);
    try {
      // Load all subscribers without pagination to ensure counts match filtered results
      const res = await axios.get(`${API}/admin/all-subscribers?limit=10000`, { headers });
      const data = res.data;
      setSubscribers(data.subscribers || []);
      setTotalCount(data.total || 0);
      setSources(data.sources || []);
    } catch (error) {
      console.error('Failed to load subscribers:', error);
      toast.error("Failed to load subscribers");
    } finally {
      setLoading(false);
    }
  };

  const exportSubscribers = () => {
    const csvContent = filteredSubscribers.map(s => 
      `${s.email || ''},${s.phone || ''},${s.name || ''},${s.source || ''}`
    ).join('\n');
    const header = 'email,phone,name,source\n';
    const blob = new Blob([header + csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'subscribers.csv';
    a.click();
    toast.success('Subscribers exported!');
  };

  const openSendOffer = (subscriber) => {
    setSelectedSubscriber(subscriber);
    setShowSendOffer(true);
  };

  const sendOfferToSubscriber = async () => {
    if (!selectedSubscriber?.email) {
      toast.error('This subscriber has no email address');
      return;
    }
    
    setSendingOffer(true);
    try {
      await axios.post(`${API}/admin/send-individual-offer`, {
        email: selectedSubscriber.email,
        name: selectedSubscriber.name || '',
        subject: offerData.subject,
        message: offerData.message,
        discount_code: offerData.discount_code,
        discount_percent: offerData.discount_percent
      }, { headers });
      
      toast.success(`Offer sent to ${selectedSubscriber.email}!`);
      setShowSendOffer(false);
      setSelectedSubscriber(null);
    } catch (error) {
      console.error('Failed to send offer:', error);
      toast.error(error.response?.data?.detail || 'Failed to send offer');
    } finally {
      setSendingOffer(false);
    }
  };

  const filteredSubscribers = subscribers.filter(s => {
    const matchesSearch = 
      (s.email || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.phone || '').includes(searchQuery) ||
      (s.name || '').toLowerCase().includes(searchQuery.toLowerCase());
    
    if (sourceFilter === "all") return matchesSearch;
    return matchesSearch && s.source === sourceFilter;
  });

  // Count subscribers with email vs phone only
  const emailCount = subscribers.filter(s => s.email).length;
  const phoneOnlyCount = subscribers.filter(s => s.phone && !s.email).length;

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Mail className="h-5 w-5" />
            All Subscribers ({totalCount})
          </CardTitle>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={loadSubscribers}>
              <RefreshCw className="h-4 w-4 mr-1" />
              Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={exportSubscribers}>
              <Download className="h-4 w-4 mr-1" />
              Export
            </Button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-pink-50 rounded-lg p-3 text-center">
            <p className="text-xs text-[#5A5A5A]">Total</p>
            <p className="text-xl font-bold text-[#F8A5B8]">{totalCount}</p>
          </div>
          <div className="bg-blue-50 rounded-lg p-3 text-center">
            <p className="text-xs text-[#5A5A5A]">Emails</p>
            <p className="text-xl font-bold text-blue-500">{emailCount}</p>
          </div>
          <div className="bg-green-50 rounded-lg p-3 text-center">
            <p className="text-xs text-[#5A5A5A]">Phone Only</p>
            <p className="text-xl font-bold text-green-500">{phoneOnlyCount}</p>
          </div>
        </div>

        {/* Source badges */}
        {sources.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {sources.filter(s => s.count > 0).map(source => {
              const isActive = sourceFilter === source.value;
              return (
                <Badge 
                  key={source.value} 
                  variant={isActive ? "default" : "outline"}
                  className={`cursor-pointer text-xs transition-colors ${
                    isActive 
                      ? 'bg-[#F8A5B8] hover:bg-[#e8959a] text-white border-[#F8A5B8]' 
                      : 'bg-white hover:bg-gray-50 text-[#2D2A2E] border-gray-300'
                  }`}
                  onClick={() => setSourceFilter(isActive ? "all" : source.value)}
                >
                  {source.label}: {source.count}
                </Badge>
              );
            })}
            {sourceFilter !== "all" && (
              <Badge 
                variant="outline" 
                className="cursor-pointer bg-gray-100 hover:bg-gray-200 text-[#2D2A2E] text-xs"
                onClick={() => setSourceFilter("all")}
              >
                Clear ×
              </Badge>
            )}
          </div>
        )}

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input 
            placeholder="Search by email, phone or name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Results count */}
        <div className="text-sm text-[#5A5A5A]">
          {sourceFilter !== "all" ? (
            <span>
              Showing {filteredSubscribers.length} {sources.find(s => s.value === sourceFilter)?.label || sourceFilter} contacts
            </span>
          ) : (
            <span>Showing {filteredSubscribers.length} of {totalCount} total contacts</span>
          )}
        </div>

        {/* Subscriber List */}
        {filteredSubscribers.length === 0 ? (
          <p className="text-center text-[#5A5A5A] py-8">No subscribers found</p>
        ) : (
          <div className="space-y-2 max-h-[400px] overflow-y-auto border rounded-lg p-2">
            {filteredSubscribers.map((subscriber, idx) => (
              <div 
                key={`${subscriber.email || subscriber.phone}-${idx}`} 
                className="flex flex-col sm:flex-row sm:items-center justify-between p-3 bg-gray-50 rounded-lg gap-2"
              >
                <div className="flex-1 min-w-0">
                  {subscriber.email && (
                    <p className="font-medium text-sm truncate">{subscriber.email}</p>
                  )}
                  {subscriber.phone && (
                    <p className="text-sm text-green-600 flex items-center gap-1">
                      <Phone className="h-3 w-3" /> {subscriber.phone}
                    </p>
                  )}
                  {subscriber.name && (
                    <p className="text-xs text-[#5A5A5A]">{subscriber.name}</p>
                  )}
                  {/* Influencer-specific info */}
                  {subscriber.source === 'influencer' && subscriber.extra_data && (
                    <div className="flex flex-wrap gap-2 mt-1">
                      {subscriber.extra_data.instagram && (
                        <span className="text-xs text-purple-600">@{subscriber.extra_data.instagram}</span>
                      )}
                      {subscriber.extra_data.referral_code && (
                        <span className="text-xs bg-blue-100 text-blue-700 px-1 rounded">Code: {subscriber.extra_data.referral_code}</span>
                      )}
                      {subscriber.extra_data.earnings > 0 && (
                        <span className="text-xs bg-green-100 text-green-700 px-1 rounded">${subscriber.extra_data.earnings} earned</span>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {subscriber.email && (
                    <Button
                      size="sm"
                      onClick={() => openSendOffer(subscriber)}
                      className="bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 text-white text-xs h-7 px-2"
                    >
                      <Gift className="h-3 w-3 mr-1" />
                      Send Offer
                    </Button>
                  )}
                  <Badge 
                    variant="outline" 
                    className={`text-xs ${subscriber.source === 'influencer' ? 'bg-purple-100 text-purple-700 border-purple-300' : ''}`}
                  >
                    {subscriber.source_display || subscriber.source}
                  </Badge>
                  <span className="text-xs text-[#5A5A5A]">
                    {subscriber.created_at ? new Date(subscriber.created_at).toLocaleDateString() : ''}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Send Offer Dialog */}
        <Dialog open={showSendOffer} onOpenChange={setShowSendOffer}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Gift className="h-5 w-5 text-pink-500" />
                Send Offer to {selectedSubscriber?.email}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label>Email Subject</Label>
                <Input
                  value={offerData.subject}
                  onChange={(e) => setOfferData({...offerData, subject: e.target.value})}
                  placeholder="Subject line..."
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Discount Code</Label>
                  <Input
                    value={offerData.discount_code}
                    onChange={(e) => setOfferData({...offerData, discount_code: e.target.value})}
                    placeholder="SAVE20"
                  />
                </div>
                <div>
                  <Label>Discount %</Label>
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={offerData.discount_percent}
                    onChange={(e) => setOfferData({...offerData, discount_percent: parseInt(e.target.value) || 0})}
                  />
                </div>
              </div>
              <div>
                <Label>Message</Label>
                <Textarea
                  value={offerData.message}
                  onChange={(e) => setOfferData({...offerData, message: e.target.value})}
                  rows={6}
                  placeholder="Your offer message..."
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => setShowSendOffer(false)}
                  className="flex-1 text-[#2D2A2E]"
                >
                  Cancel
                </Button>
                <Button
                  onClick={sendOfferToSubscriber}
                  disabled={sendingOffer}
                  className="flex-1 bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 text-white"
                >
                  {sendingOffer ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Sending...</>
                  ) : (
                    <><Send className="h-4 w-4 mr-2" /> Send Offer</>
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
};

export default SubscribersSection;
