/**
 * AUREM Omnichannel Comm Hub
 * Unified inbox for WhatsApp, Email, SMS — all channels in one view
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Mail, MessageCircle, Phone, Send, Search, Filter, RefreshCw,
  Star, Archive, Trash2, Reply, ChevronRight, Clock, User,
  Paperclip, MoreHorizontal, CheckCheck, AlertCircle, Inbox,
  Hash, Tag, ArrowLeft, X, Plus, MessageSquare,
  Zap, Target, TrendingUp, Loader2, BarChart3, Shield, Link2
} from 'lucide-react';
import { EmptyInbox } from './EmptyStates';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const CHANNEL_CONFIG = {
  email: { icon: Mail, color: '#3b82f6', label: 'Email', bg: '#3b82f6' },
  whatsapp: { icon: MessageCircle, color: '#25D366', label: 'WhatsApp', bg: '#25D366' },
  sms: { icon: Phone, color: '#f59e0b', label: 'SMS', bg: '#f59e0b' },
  chat: { icon: MessageSquare, color: '#D4AF37', label: 'AI Chat', bg: '#D4AF37' }
};

const DEMO_CONVERSATIONS = [];

export default function OmnichannelHub({ token }) {
  const [conversations, setConversations] = useState([]);
  const [selectedConv, setSelectedConv] = useState(null);
  const [filterChannel, setFilterChannel] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [replyText, setReplyText] = useState('');
  const [loading, setLoading] = useState(false);

  // Recovery Campaigns
  const [hubView, setHubView] = useState('inbox'); // inbox | campaigns
  const [campaigns, setCampaigns] = useState([]);
  const [commStats, setCommStats] = useState(null);
  const [sentMessages, setSentMessages] = useState([]);
  const [campaignChannel, setCampaignChannel] = useState('email');
  const [campaignType, setCampaignType] = useState('abandoned_cart');
  const [campaignSource, setCampaignSource] = useState('all');
  const [campaignLimit, setCampaignLimit] = useState(50);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState(null);

  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const fetchCampaigns = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/comms/campaigns`, { headers });
      const data = await res.json();
      if (res.ok) setCampaigns(data.campaigns || []);
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchCommStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/comms/stats`, { headers });
      const data = await res.json();
      if (res.ok) setCommStats(data);
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchSentMessages = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/comms/sent-messages?limit=20`, { headers });
      const data = await res.json();
      if (res.ok) setSentMessages(data.messages || []);
    } catch (e) { console.error(e); }
  }, [headers]);

  useEffect(() => {
    fetchCampaigns();
    fetchCommStats();
    fetchSentMessages();
  }, [fetchCampaigns, fetchSentMessages, fetchCommStats]);

  const handleLaunchCampaign = async () => {
    setSending(true); setSendResult(null);
    try {
      const res = await fetch(`${API_URL}/api/comms/bulk-recovery`, {
        method: 'POST', headers,
        body: JSON.stringify({
          channel: campaignChannel,
          campaign_type: campaignType,
          source_filter: campaignSource,
          limit: campaignLimit,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Campaign failed');
      setSendResult(data);
      fetchCampaigns();
      fetchCommStats();
      fetchSentMessages();
    } catch (e) { setSendResult({ error: e.message }); }
    finally { setSending(false); }
  };

  const filteredConversations = conversations.filter(conv => {
    if (filterChannel !== 'all' && conv.channel !== filterChannel) return false;
    if (filterStatus === 'unread' && !conv.unread) return false;
    if (filterStatus === 'starred' && !conv.starred) return false;
    if (searchQuery && !conv.contact_name.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !conv.last_message.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const handleSendReply = () => {
    if (!replyText.trim() || !selectedConv) return;
    const newMessage = {
      id: Date.now(),
      from: 'agent',
      text: replyText,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setConversations(prev => prev.map(c =>
      c.id === selectedConv.id
        ? { ...c, messages: [...c.messages, newMessage], last_message: replyText, timestamp: 'Just now' }
        : c
    ));
    setSelectedConv(prev => ({
      ...prev,
      messages: [...prev.messages, newMessage]
    }));
    setReplyText('');
  };

  const handleToggleStar = (convId) => {
    setConversations(prev => prev.map(c =>
      c.id === convId ? { ...c, starred: !c.starred } : c
    ));
  };

  const unreadCount = conversations.filter(c => c.unread).length;
  const channelCounts = {
    all: conversations.length,
    email: conversations.filter(c => c.channel === 'email').length,
    whatsapp: conversations.filter(c => c.channel === 'whatsapp').length,
    sms: conversations.filter(c => c.channel === 'sms').length,
    chat: conversations.filter(c => c.channel === 'chat').length
  };

  return (
    <div className="flex-1 flex flex-col bg-white/60 overflow-hidden" data-testid="omnichannel-hub">
      {/* View Switcher */}
      <div className="flex items-center gap-1 px-4 pt-3 pb-0">
        <button onClick={() => setHubView('inbox')} data-testid="hub-view-inbox"
          className={`flex items-center gap-1.5 px-4 py-2 rounded-t-lg text-xs font-bold transition-all ${
            hubView === 'inbox' ? 'bg-white/80 text-[#1A1A2E] border border-b-0 border-[#FF6B00]/20' : 'text-[#888] hover:text-[#1A1A2E]'
          }`}>
          <Inbox className="size-3.5" /> Unified Inbox
        </button>
        <button onClick={() => setHubView('campaigns')} data-testid="hub-view-campaigns"
          className={`flex items-center gap-1.5 px-4 py-2 rounded-t-lg text-xs font-bold transition-all ${
            hubView === 'campaigns' ? 'bg-white/80 text-[#1A1A2E] border border-b-0 border-[#FF6B00]/20' : 'text-[#888] hover:text-[#1A1A2E]'
          }`}>
          <Target className="size-3.5" /> Recovery Campaigns
          {commStats?.total_sent > 0 && (
            <span className="px-1.5 py-0.5 text-[8px] font-bold bg-[#D4AF37]/10 text-[#D4AF37] rounded-full">{commStats.total_sent}</span>
          )}
        </button>
      </div>

      {/* CAMPAIGNS VIEW */}
      {hubView === 'campaigns' ? (
        <div className="flex-1 overflow-y-auto p-5" data-testid="campaigns-view">
          {/* Stats Bar */}
          {commStats && (
            <div className="grid grid-cols-4 gap-3 mb-5">
              {[
                { label: 'Messages Sent', value: commStats.total_sent, icon: Send, color: '#D4AF37' },
                { label: 'Delivery Rate', value: `${commStats.delivery_rate}%`, icon: CheckCheck, color: '#4ade80' },
                { label: 'Click Rate', value: `${commStats.click_rate}%`, icon: Link2, color: '#64C8FF' },
                { label: 'Campaigns', value: commStats.total_campaigns, icon: Target, color: '#B88759' },
              ].map((s, i) => {
                const Icon = s.icon;
                return (
                  <div key={i} className="p-3 rounded-xl border border-white/30 bg-white/50 backdrop-blur-sm">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Icon className="size-3" style={{ color: s.color }} />
                      <span className="text-[7px] text-[#888] uppercase tracking-wider font-bold">{s.label}</span>
                    </div>
                    <div className="text-lg font-bold text-[#1A1A2E]">{s.value}</div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Launch Campaign */}
          <div className="p-5 rounded-2xl border border-[#D4AF37]/15 bg-white/50 backdrop-blur-sm mb-5">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="size-5 text-[#D4AF37]" />
              <h3 className="text-sm font-bold text-[#1A1A2E] tracking-wider">LAUNCH RECOVERY CAMPAIGN</h3>
            </div>
            <p className="text-[10px] text-[#888] mb-4">
              Send attributed recovery messages to your customer vault. Every link carries a signed aurem_ref token for commission tracking.
            </p>

            <div className="grid grid-cols-3 gap-3 mb-4">
              {/* Channel */}
              <div>
                <label className="text-[8px] text-[#888] uppercase tracking-wider font-bold mb-1 block">Channel</label>
                <div className="flex gap-1">
                  {[
                    { id: 'email', label: 'Email', color: '#3b82f6' },
                    { id: 'whatsapp', label: 'WA', color: '#25D366' },
                    { id: 'sms', label: 'SMS', color: '#f59e0b' },
                  ].map(ch => (
                    <button key={ch.id} onClick={() => setCampaignChannel(ch.id)} data-testid={`campaign-channel-${ch.id}`}
                      className={`flex-1 py-2 rounded-lg text-[10px] font-bold transition-all border ${
                        campaignChannel === ch.id ? `text-white border-transparent` : 'text-[#888] border-white/30 hover:border-[#D4AF37]/20'
                      }`}
                      style={campaignChannel === ch.id ? { background: ch.color } : {}}>
                      {ch.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Campaign Type */}
              <div>
                <label className="text-[8px] text-[#888] uppercase tracking-wider font-bold mb-1 block">Type</label>
                <select value={campaignType} onChange={e => setCampaignType(e.target.value)} data-testid="campaign-type-select"
                  className="w-full py-2 px-2 rounded-lg border border-white/30 bg-white/60 text-[10px] text-[#1A1A2E] focus:outline-none focus:border-[#D4AF37]">
                  <option value="abandoned_cart">Abandoned Cart</option>
                  <option value="win_back">Win Back</option>
                  <option value="new_offer">New Offer</option>
                </select>
              </div>

              {/* Source Filter */}
              <div>
                <label className="text-[8px] text-[#888] uppercase tracking-wider font-bold mb-1 block">Audience</label>
                <select value={campaignSource} onChange={e => setCampaignSource(e.target.value)} data-testid="campaign-source-select"
                  className="w-full py-2 px-2 rounded-lg border border-white/30 bg-white/60 text-[10px] text-[#1A1A2E] focus:outline-none focus:border-[#D4AF37]">
                  <option value="all">All Customers</option>
                  <option value="shopify_sync">Shopify</option>
                  <option value="hubspot_sync">HubSpot</option>
                  <option value="salesforce_sync">Salesforce</option>
                  <option value="web_scrape">Web Mined</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 flex-1">
                <label className="text-[8px] text-[#888] uppercase tracking-wider font-bold">Limit:</label>
                <input type="number" value={campaignLimit} onChange={e => setCampaignLimit(Number(e.target.value))} min={1} max={500}
                  className="w-20 py-1.5 px-2 rounded-lg border border-white/30 bg-white/60 text-[10px] text-[#1A1A2E] focus:outline-none focus:border-[#D4AF37]"
                  data-testid="campaign-limit-input" />
              </div>
              <button onClick={handleLaunchCampaign} disabled={sending} data-testid="launch-campaign-btn"
                className="px-6 py-2.5 rounded-lg font-bold text-sm text-white transition-all disabled:opacity-50 flex items-center gap-2"
                style={{ background: 'linear-gradient(135deg, #D4AF37, #8B7355)' }}>
                {sending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
                {sending ? 'Sending...' : 'Launch Campaign'}
              </button>
            </div>
          </div>

          {/* Send Result */}
          {sendResult && !sendResult.error && (
            <div className="p-4 rounded-xl border border-[#4ade80]/20 bg-[#4ade80]/5 mb-5" data-testid="campaign-result">
              <div className="flex items-center gap-2 mb-2">
                <CheckCheck className="size-4 text-[#4ade80]" />
                <span className="text-sm font-bold text-[#FF6B00]">Campaign Launched</span>
              </div>
              <div className="grid grid-cols-4 gap-3 text-center">
                <div><div className="text-lg font-bold text-[#1A1A2E]">{sendResult.total_targeted}</div><div className="text-[8px] text-[#888]">Targeted</div></div>
                <div><div className="text-lg font-bold text-[#4ade80]">{sendResult.sent}</div><div className="text-[8px] text-[#888]">Sent</div></div>
                <div><div className="text-lg font-bold text-red-400">{sendResult.failed}</div><div className="text-[8px] text-[#888]">Failed</div></div>
                <div><div className="text-lg font-bold text-[#888]">{sendResult.skipped}</div><div className="text-[8px] text-[#888]">Skipped</div></div>
              </div>
            </div>
          )}
          {sendResult?.error && (
            <div className="p-3 mb-5 rounded-lg border border-red-200/50 bg-red-50/80 text-red-600 text-sm">
              {sendResult.error}
            </div>
          )}

          {/* Campaign History */}
          <div className="rounded-xl border border-white/30 bg-white/40 backdrop-blur-sm overflow-hidden mb-5">
            <div className="px-3 py-2 border-b border-white/20 flex items-center justify-between">
              <span className="text-[9px] text-[#888] uppercase tracking-wider font-bold flex items-center gap-2">
                <BarChart3 className="size-3" /> Campaign History
              </span>
              <button onClick={fetchCampaigns} className="text-[#888] hover:text-[#D4AF37] transition-colors">
                <RefreshCw className="size-3" />
              </button>
            </div>
            <div className="divide-y divide-white/10">
              {campaigns.length > 0 ? campaigns.map(c => (
                <div key={c.campaign_id} className="px-3 py-2.5 flex items-center justify-between hover:bg-white/30 transition-all">
                  <div className="flex items-center gap-2">
                    <div className="size-2 rounded-full" style={{
                      background: c.channel === 'email' ? '#3b82f6' : c.channel === 'whatsapp' ? '#25D366' : '#f59e0b'
                    }} />
                    <span className="text-xs font-bold text-[#1A1A2E]">{c.name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-[9px] text-[#888]">
                    <span className="text-[#4ade80] font-bold">{c.sent} sent</span>
                    <span>{c.failed} failed</span>
                    <span>{new Date(c.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              )) : (
                <div className="p-6 text-center text-sm text-[#888]">
                  No campaigns yet. Launch your first recovery campaign above.
                </div>
              )}
            </div>
          </div>

          {/* Recent Sent Messages */}
          {sentMessages.length > 0 && (
            <div className="rounded-xl border border-white/30 bg-white/40 backdrop-blur-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-white/20 text-[9px] text-[#888] uppercase tracking-wider font-bold flex items-center gap-2">
                <Send className="size-3" /> Recent Messages
              </div>
              <div className="max-h-[250px] overflow-y-auto divide-y divide-white/10">
                {sentMessages.slice(0, 10).map(m => (
                  <div key={m.message_id} className="px-3 py-2 flex items-center justify-between text-[10px]">
                    <div className="flex items-center gap-2">
                      <div className="size-2 rounded-full" style={{
                        background: m.delivery_status === 'delivered' ? '#4ade80' : '#ef4444'
                      }} />
                      <span className="text-[#1A1A2E] font-bold">{m.customer_email}</span>
                    </div>
                    <span className="text-[#888]">{m.channel}</span>
                    <span className="text-[#888]">{m.campaign_type?.replace('_', ' ')}</span>
                    <span className={m.delivery_status === 'delivered' ? 'text-[#4ade80]' : 'text-red-400'}>{m.delivery_status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
      /* INBOX VIEW */
      <div className="flex-1 flex overflow-hidden" data-testid="inbox-view">
      {/* Conversation List Sidebar */}
      <div className="w-80 border-r border-[#FF6B00]/20 flex flex-col bg-white/80 backdrop-blur-sm">
        {/* Header */}
        <div className="p-4 border-b border-[#FF6B00]/20">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-sm font-semibold text-[#e2c97e] tracking-wider">Comm Hub</h1>
            <div className="flex items-center gap-1.5">
              {unreadCount > 0 && (
                <span className="px-2 py-0.5 text-[10px] font-bold bg-[#D4AF37] text-[#050505] rounded-full">
                  {unreadCount}
                </span>
              )}
              <button data-testid="new-conversation-btn" onClick={() => { /* Start new conversation placeholder */ }} className="p-1.5 text-[#555] hover:text-[#D4AF37] transition-colors">
                <Plus className="size-4" />
              </button>
            </div>
          </div>

          {/* Search */}
          <div className="relative mb-3">
            <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[#555]" />
            <input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              data-testid="hub-search-input"
              className="w-full pl-8 pr-3 py-2 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-[11px] text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50"
            />
          </div>

          {/* Channel Filters */}
          <div className="flex gap-1 overflow-x-auto">
            {[
              { id: 'all', label: 'All', count: channelCounts.all },
              { id: 'email', label: 'Email', count: channelCounts.email, color: '#3b82f6' },
              { id: 'whatsapp', label: 'WA', count: channelCounts.whatsapp, color: '#25D366' },
              { id: 'sms', label: 'SMS', count: channelCounts.sms, color: '#f59e0b' },
              { id: 'chat', label: 'Chat', count: channelCounts.chat, color: '#D4AF37' }
            ].map(ch => (
              <button
                key={ch.id}
                onClick={() => setFilterChannel(ch.id)}
                data-testid={`filter-${ch.id}`}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[10px] whitespace-nowrap transition-all ${
                  filterChannel === ch.id
                    ? 'bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/30'
                    : 'text-[#666] hover:text-[#555] border border-transparent'
                }`}
              >
                {ch.label}
                <span className="text-[9px] opacity-60">{ch.count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-auto">
          {filteredConversations.length > 0 ? (
            <div className="divide-y divide-[#141414]">
              {filteredConversations.map(conv => {
                const channelCfg = CHANNEL_CONFIG[conv.channel];
                const ChannelIcon = channelCfg.icon;
                const isSelected = selectedConv?.id === conv.id;
                return (
                  <div
                    key={conv.id}
                    onClick={() => { setSelectedConv(conv); setConversations(prev => prev.map(c => c.id === conv.id ? {...c, unread: false} : c)); }}
                    data-testid={`conversation-${conv.id}`}
                    className={`p-3 cursor-pointer transition-all ${
                      isSelected ? 'bg-[#D4AF37]/5 border-l-2 border-l-[#D4AF37]' : 'hover:bg-white/40 border-l-2 border-l-transparent'
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      <div className="relative flex-shrink-0">
                        <div className="size-9 rounded-full bg-[#1A1A1A] flex items-center justify-center text-[11px] font-semibold text-[#1A1A2E]">
                          {conv.contact_name.split(' ').map(n => n[0]).join('')}
                        </div>
                        <div
                          className="absolute -bottom-0.5 -right-0.5 size-4 rounded-full flex items-center justify-center"
                          style={{ backgroundColor: channelCfg.color }}
                        >
                          <ChannelIcon className="size-2.5 text-white" />
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className={`text-xs ${conv.unread ? 'font-semibold text-[#1A1A2E]' : 'text-[#1A1A2E]'}`}>
                            {conv.contact_name}
                          </span>
                          <span className="text-[9px] text-[#555] whitespace-nowrap">{conv.timestamp}</span>
                        </div>
                        <p className={`text-[11px] mt-0.5 truncate ${conv.unread ? 'text-[#555]' : 'text-[#5a5a72]'}`}>
                          {conv.last_message}
                        </p>
                      </div>
                      {conv.unread && (
                        <div className="size-2 rounded-full bg-[#D4AF37] mt-1.5 flex-shrink-0" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-8 text-center">
              <Inbox className="size-6 text-[#333] mx-auto mb-2" />
              <p className="text-[11px] text-[#555]">No conversations found</p>
              <EmptyInbox />
            </div>
          )}
        </div>
      </div>

      {/* Conversation Detail */}
      {selectedConv ? (
        <div className="flex-1 flex flex-col">
          {/* Conversation Header */}
          <div className="px-5 py-3 border-b border-[#FF6B00]/20 flex items-center justify-between bg-white/80 backdrop-blur-sm">
            <div className="flex items-center gap-3">
              <div className="size-9 rounded-full bg-[#1A1A1A] flex items-center justify-center text-[11px] font-semibold text-[#1A1A2E]">
                {selectedConv.contact_name.split(' ').map(n => n[0]).join('')}
              </div>
              <div>
                <h3 className="text-xs font-medium text-[#1A1A2E]">{selectedConv.contact_name}</h3>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-[#5a5a72]">{selectedConv.contact_email}</span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ backgroundColor: `${CHANNEL_CONFIG[selectedConv.channel].color}15`, color: CHANNEL_CONFIG[selectedConv.channel].color }}>
                    {CHANNEL_CONFIG[selectedConv.channel].label}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleToggleStar(selectedConv.id)}
                className={`p-2 rounded-lg transition-colors ${selectedConv.starred ? 'text-[#D4AF37]' : 'text-[#555] hover:text-[#D4AF37]'}`}
              >
                <Star className={`size-4 ${selectedConv.starred ? 'fill-current' : ''}`} />
              </button>
              <button onClick={() => { /* Archive conversation */ }} className="p-2 text-[#555] hover:text-[#555] rounded-lg transition-colors" data-testid="archive-conversation-btn">
                <Archive className="size-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-auto p-5 space-y-4">
            {selectedConv.messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.from === 'agent' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[65%] px-4 py-2.5 rounded-2xl ${
                  msg.from === 'agent'
                    ? 'bg-[#D4AF37]/10 text-[#1A1A2E] rounded-br-sm'
                    : 'bg-white/50 text-[#1A1A2E] rounded-bl-sm'
                }`}>
                  <p className="text-xs leading-relaxed">{msg.text}</p>
                  <div className={`flex items-center gap-1 mt-1 ${msg.from === 'agent' ? 'justify-end' : ''}`}>
                    <span className="text-[9px] text-[#555]">{msg.time}</span>
                    {msg.from === 'agent' && <CheckCheck className="size-3 text-[#D4AF37]" />}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Reply Box */}
          <div className="p-4 border-t border-[#FF6B00]/20 bg-white/80 backdrop-blur-sm">
            <div className="flex items-end gap-3">
              <div className="flex-1 relative">
                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendReply(); } }}
                  placeholder={`Reply via ${CHANNEL_CONFIG[selectedConv.channel].label}...`}
                  data-testid="reply-input"
                  rows={1}
                  className="w-full px-4 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-xl text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50 resize-none"
                />
              </div>
              <button
                onClick={handleSendReply}
                disabled={!replyText.trim()}
                data-testid="send-reply-btn"
                className="p-2.5 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-xl text-[#050505] hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                <Send className="size-4" />
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center" data-testid="no-conversation-selected">
          <div className="text-center">
            <Inbox className="size-12 text-[#222] mx-auto mb-4" />
            <h3 className="text-sm text-[#555] mb-1">Select a conversation</h3>
            <p className="text-[11px] text-[#444]">Choose from your unified inbox to start responding</p>
          </div>
        </div>
      )}
    </div>
    )}
    </div>
  );
}
