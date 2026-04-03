import React, { useState, useEffect, useCallback } from 'react';
import { 
  MessageSquare, Bot, Settings, Users, Upload, Play, Pause,
  Send, RefreshCw, Trash2, ChevronDown, ChevronRight, Loader2,
  Sparkles, Check, X, Clock, Zap, Brain, Building2, User
} from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

const WhatsAppAIAssistant = () => {
  // State
  const [activeTab, setActiveTab] = useState('overview');
  const [settings, setSettings] = useState(null);
  const [brandVoice, setBrandVoice] = useState(null);
  const [stats, setStats] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testMessage, setTestMessage] = useState('');
  const [testReply, setTestReply] = useState(null);
  const [testLoading, setTestLoading] = useState(false);
  const [selectedContact, setSelectedContact] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);

  // Fetch all data
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [settingsRes, statsRes, contactsRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/whatsapp-ai/settings`),
        fetch(`${API_URL}/api/admin/whatsapp-ai/stats`),
        fetch(`${API_URL}/api/admin/whatsapp-ai/conversations/contacts`)
      ]);

      if (settingsRes.ok) {
        const data = await settingsRes.json();
        setSettings(data.settings);
        setBrandVoice(data.brand_voice);
      }
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
      if (contactsRes.ok) {
        const data = await contactsRes.json();
        setContacts(data.contacts || []);
      }
    } catch (err) {
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Toggle assistant
  const toggleAssistant = async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/whatsapp-ai/toggle`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        setSettings(prev => ({ ...prev, enabled: data.enabled }));
      }
    } catch (err) {
      console.error('Error toggling assistant:', err);
    }
  };

  // Update settings
  const updateSettings = async (newSettings) => {
    try {
      setSaving(true);
      const res = await fetch(`${API_URL}/api/admin/whatsapp-ai/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings)
      });
      if (res.ok) {
        const data = await res.json();
        setSettings(data.settings);
      }
    } catch (err) {
      console.error('Error updating settings:', err);
    } finally {
      setSaving(false);
    }
  };

  // Update brand voice
  const updateBrandVoice = async (newConfig) => {
    try {
      setSaving(true);
      const res = await fetch(`${API_URL}/api/admin/whatsapp-ai/brand-voice`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      });
      if (res.ok) {
        const data = await res.json();
        setBrandVoice(data.brand_voice);
      }
    } catch (err) {
      console.error('Error updating brand voice:', err);
    } finally {
      setSaving(false);
    }
  };

  // Test reply
  const testReplyMessage = async () => {
    if (!testMessage.trim()) return;
    try {
      setTestLoading(true);
      setTestReply(null);
      const res = await fetch(`${API_URL}/api/admin/whatsapp-ai/test-reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: testMessage,
          provider: settings?.provider || 'openai',
          mode: settings?.mode || 'brand'
        })
      });
      if (res.ok) {
        const data = await res.json();
        setTestReply(data);
      }
    } catch (err) {
      console.error('Error testing reply:', err);
    } finally {
      setTestLoading(false);
    }
  };

  // Switch provider
  const switchProvider = async (provider) => {
    try {
      const res = await fetch(`${API_URL}/api/admin/whatsapp-ai/switch-provider?provider=${provider}`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        setSettings(prev => ({ ...prev, provider: data.provider, model: data.model }));
      }
    } catch (err) {
      console.error('Error switching provider:', err);
    }
  };

  // Load conversation
  const loadConversation = async (phone) => {
    try {
      setSelectedContact(phone);
      const res = await fetch(`${API_URL}/api/admin/whatsapp-ai/conversations?phone=${phone}&limit=100`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data.conversations || []);
      }
    } catch (err) {
      console.error('Error loading conversation:', err);
    }
  };

  // Clear conversation
  const clearConversation = async (phone) => {
    if (!window.confirm(`Delete all messages with ${phone}?`)) return;
    try {
      const res = await fetch(`${API_URL}/api/admin/whatsapp-ai/conversations/${phone}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setContacts(prev => prev.filter(c => c.phone !== phone));
        if (selectedContact === phone) {
          setSelectedContact(null);
          setConversations([]);
        }
      }
    } catch (err) {
      console.error('Error clearing conversation:', err);
    }
  };

  // Upload chat history
  const handleChatUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('is_closest_person', 'true');

    try {
      setUploadStatus('uploading');
      const res = await fetch(`${API_URL}/api/admin/whatsapp-ai/upload-chat-history`, {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        setUploadStatus('success');
        setTimeout(() => setUploadStatus(null), 3000);
        await fetchData();
      } else {
        setUploadStatus('error');
      }
    } catch (err) {
      console.error('Error uploading:', err);
      setUploadStatus('error');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-pink-500" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="whatsapp-ai-assistant">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl shadow-lg">
            <MessageSquare className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">WhatsApp AI Assistant</h1>
            <p className="text-gray-500">Auto-reply with AI-powered responses</p>
          </div>
        </div>
        
        {/* Master Toggle */}
        <button
          onClick={toggleAssistant}
          data-testid="toggle-assistant-btn"
          className={`flex items-center gap-3 px-6 py-3 rounded-full font-medium transition-all ${
            settings?.enabled 
              ? 'bg-green-500 text-white hover:bg-green-600 shadow-lg shadow-green-500/30' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
        >
          {settings?.enabled ? <Play className="w-5 h-5" /> : <Pause className="w-5 h-5" />}
          {settings?.enabled ? 'Active' : 'Inactive'}
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <MessageSquare className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{stats?.total_conversations || 0}</p>
              <p className="text-sm text-gray-500">Total Messages</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <Bot className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{stats?.total_ai_replies || 0}</p>
              <p className="text-sm text-gray-500">AI Replies</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Users className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{stats?.unique_contacts || 0}</p>
              <p className="text-sm text-gray-500">Unique Contacts</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-100 rounded-lg">
              <Zap className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{stats?.today_messages || 0}</p>
              <p className="text-sm text-gray-500">Today's Messages</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-gray-200">
        {[
          { id: 'overview', label: 'Overview', icon: Settings },
          { id: 'personality', label: 'Personality', icon: Brain },
          { id: 'conversations', label: 'Conversations', icon: MessageSquare },
          { id: 'whatsapp-web', label: 'WhatsApp Web', icon: Zap },
          { id: 'test', label: 'Test Mode', icon: Sparkles }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-${tab.id}`}
            className={`flex items-center gap-2 px-4 py-3 font-medium transition-all border-b-2 -mb-px ${
              activeTab === tab.id
                ? 'text-pink-600 border-pink-500'
                : 'text-gray-500 border-transparent hover:text-gray-700'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="p-6 space-y-6">
            {/* Mode Selection */}
            <div>
              <h3 className="text-lg font-semibold mb-4">Response Mode</h3>
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() => updateSettings({ ...settings, mode: 'brand' })}
                  data-testid="mode-brand-btn"
                  className={`p-4 rounded-xl border-2 transition-all ${
                    settings?.mode === 'brand' 
                      ? 'border-pink-500 bg-pink-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-2">
                    <Building2 className={`w-6 h-6 ${settings?.mode === 'brand' ? 'text-pink-500' : 'text-gray-400'}`} />
                    <span className="font-semibold">Brand Voice</span>
                    {settings?.mode === 'brand' && <Check className="w-5 h-5 text-pink-500 ml-auto" />}
                  </div>
                  <p className="text-sm text-gray-500 text-left">
                    Responds as your brand's official customer support with product knowledge
                  </p>
                </button>
                
                <button
                  onClick={() => updateSettings({ ...settings, mode: 'personal' })}
                  data-testid="mode-personal-btn"
                  className={`p-4 rounded-xl border-2 transition-all ${
                    settings?.mode === 'personal' 
                      ? 'border-purple-500 bg-purple-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-2">
                    <User className={`w-6 h-6 ${settings?.mode === 'personal' ? 'text-purple-500' : 'text-gray-400'}`} />
                    <span className="font-semibold">Digital Twin</span>
                    {settings?.mode === 'personal' && <Check className="w-5 h-5 text-purple-500 ml-auto" />}
                  </div>
                  <p className="text-sm text-gray-500 text-left">
                    Responds in your personal texting style (learned from chat exports)
                  </p>
                </button>
              </div>
            </div>

            {/* LLM Provider */}
            <div>
              <h3 className="text-lg font-semibold mb-4">AI Provider</h3>
              <div className="grid grid-cols-3 gap-3">
                <button
                  onClick={() => switchProvider('openai')}
                  data-testid="provider-openai-btn"
                  className={`p-4 rounded-xl border-2 transition-all ${
                    settings?.provider === 'openai' 
                      ? 'border-green-500 bg-green-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="text-left">
                      <p className="font-semibold">OpenAI GPT-4o</p>
                      <p className="text-sm text-gray-500">Natural conversations</p>
                    </div>
                    {settings?.provider === 'openai' && <Check className="w-5 h-5 text-green-500" />}
                  </div>
                </button>
                
                <button
                  onClick={() => switchProvider('anthropic')}
                  data-testid="provider-anthropic-btn"
                  className={`p-4 rounded-xl border-2 transition-all ${
                    settings?.provider === 'anthropic' 
                      ? 'border-orange-500 bg-orange-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="text-left">
                      <p className="font-semibold">Claude Sonnet</p>
                      <p className="text-sm text-gray-500">Thoughtful responses</p>
                    </div>
                    {settings?.provider === 'anthropic' && <Check className="w-5 h-5 text-orange-500" />}
                  </div>
                </button>
                
                <button
                  onClick={() => switchProvider('gemini')}
                  data-testid="provider-gemini-btn"
                  className={`p-4 rounded-xl border-2 transition-all ${
                    settings?.provider === 'gemini' 
                      ? 'border-blue-500 bg-blue-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="text-left">
                      <p className="font-semibold">Gemini Flash</p>
                      <p className="text-sm text-gray-500">Fast & cost-effective</p>
                    </div>
                    {settings?.provider === 'gemini' && <Check className="w-5 h-5 text-blue-500" />}
                  </div>
                </button>
              </div>
            </div>

            {/* Settings */}
            <div>
              <h3 className="text-lg font-semibold mb-4">Settings</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                  <div>
                    <p className="font-medium">Business Hours Only</p>
                    <p className="text-sm text-gray-500">Only reply during work hours</p>
                  </div>
                  <button
                    onClick={() => updateSettings({ ...settings, business_hours_only: !settings?.business_hours_only })}
                    data-testid="business-hours-toggle"
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      settings?.business_hours_only ? 'bg-green-500' : 'bg-gray-300'
                    }`}
                  >
                    <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                      settings?.business_hours_only ? 'translate-x-7' : 'translate-x-1'
                    }`} />
                  </button>
                </div>
                
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                  <div>
                    <p className="font-medium">Reply Delay</p>
                    <p className="text-sm text-gray-500">Simulate typing for realism</p>
                  </div>
                  <select
                    value={settings?.auto_reply_delay_ms || 1000}
                    onChange={(e) => updateSettings({ ...settings, auto_reply_delay_ms: parseInt(e.target.value) })}
                    data-testid="reply-delay-select"
                    className="px-3 py-2 border border-gray-200 rounded-lg bg-white"
                  >
                    <option value={500}>0.5 seconds</option>
                    <option value={1000}>1 second</option>
                    <option value={2000}>2 seconds</option>
                    <option value={3000}>3 seconds</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Webhook URL */}
            <div className="p-4 bg-gray-900 rounded-xl">
              <p className="text-gray-400 text-sm mb-2">WHAPI Webhook URL (configure in WHAPI dashboard)</p>
              <code className="text-green-400 text-sm break-all">
                {window.location.origin}/api/admin/whatsapp-ai/webhook
              </code>
            </div>
          </div>
        )}

        {/* Personality Tab */}
        {activeTab === 'personality' && (
          <div className="p-6 space-y-6">
            {/* Brand Voice Config */}
            <div>
              <h3 className="text-lg font-semibold mb-4">Brand Voice Configuration</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Brand Name</label>
                  <input
                    type="text"
                    value={brandVoice?.brand_name || ''}
                    onChange={(e) => setBrandVoice({ ...brandVoice, brand_name: e.target.value })}
                    data-testid="brand-name-input"
                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-pink-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Tone</label>
                  <input
                    type="text"
                    value={brandVoice?.tone || ''}
                    onChange={(e) => setBrandVoice({ ...brandVoice, tone: e.target.value })}
                    data-testid="tone-input"
                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-pink-500"
                    placeholder="e.g., friendly and professional"
                  />
                </div>
              </div>
            </div>

            {/* Personality Traits */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Personality Traits</label>
              <div className="flex flex-wrap gap-2 mb-2">
                {(brandVoice?.personality_traits || []).map((trait, idx) => (
                  <span key={idx} className="px-3 py-1 bg-pink-100 text-pink-700 rounded-full text-sm flex items-center gap-1">
                    {trait}
                    <button 
                      onClick={() => setBrandVoice({
                        ...brandVoice,
                        personality_traits: brandVoice.personality_traits.filter((_, i) => i !== idx)
                      })}
                      className="hover:text-pink-900"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
              <input
                type="text"
                placeholder="Add trait (press Enter)"
                data-testid="add-trait-input"
                className="w-full px-4 py-2 border border-gray-200 rounded-lg"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.target.value.trim()) {
                    setBrandVoice({
                      ...brandVoice,
                      personality_traits: [...(brandVoice?.personality_traits || []), e.target.value.trim()]
                    });
                    e.target.value = '';
                  }
                }}
              />
            </div>

            {/* Product Knowledge */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Product Knowledge</label>
              <textarea
                value={brandVoice?.product_knowledge || ''}
                onChange={(e) => setBrandVoice({ ...brandVoice, product_knowledge: e.target.value })}
                data-testid="product-knowledge-textarea"
                rows={6}
                className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-pink-500"
                placeholder="Add information about your products that the AI should know..."
              />
            </div>

            {/* Upload Chat Export */}
            <div className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center">
              <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
              <p className="font-medium mb-1">Upload WhatsApp Chat Export</p>
              <p className="text-sm text-gray-500 mb-4">For Digital Twin mode - learn your texting style</p>
              <label className="cursor-pointer">
                <input 
                  type="file" 
                  accept=".txt"
                  onChange={handleChatUpload}
                  className="hidden"
                  data-testid="chat-upload-input"
                />
                <span className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium transition-colors">
                  <Upload className="w-4 h-4" />
                  Select .txt File
                </span>
              </label>
              {uploadStatus === 'uploading' && <p className="mt-3 text-blue-500">Uploading...</p>}
              {uploadStatus === 'success' && <p className="mt-3 text-green-500">Style patterns learned!</p>}
              {uploadStatus === 'error' && <p className="mt-3 text-red-500">Upload failed</p>}
            </div>

            {/* Save Button */}
            <button
              onClick={() => updateBrandVoice(brandVoice)}
              disabled={saving}
              data-testid="save-brand-voice-btn"
              className="w-full py-3 bg-gradient-to-r from-pink-500 to-rose-500 text-white font-medium rounded-xl hover:from-pink-600 hover:to-rose-600 disabled:opacity-50 transition-all"
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        )}

        {/* Conversations Tab */}
        {activeTab === 'conversations' && (
          <div className="flex h-[600px]">
            {/* Contact List */}
            <div className="w-1/3 border-r border-gray-200 overflow-y-auto">
              <div className="p-4 border-b border-gray-200">
                <h3 className="font-semibold">Contacts ({contacts.length})</h3>
              </div>
              {contacts.length === 0 ? (
                <div className="p-6 text-center text-gray-500">
                  <MessageSquare className="w-10 h-10 mx-auto mb-2 opacity-30" />
                  <p>No conversations yet</p>
                </div>
              ) : (
                contacts.map((contact, idx) => (
                  <div
                    key={idx}
                    onClick={() => loadConversation(contact.phone)}
                    data-testid={`contact-${idx}`}
                    className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 ${
                      selectedContact === contact.phone ? 'bg-pink-50' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-green-400 to-emerald-500 rounded-full flex items-center justify-center">
                          <User className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">{contact.phone}</p>
                          <p className="text-sm text-gray-500">{contact.message_count} messages</p>
                        </div>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); clearConversation(contact.phone); }}
                        className="p-2 hover:bg-red-50 rounded-lg text-gray-400 hover:text-red-500"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    {contact.ai_replies > 0 && (
                      <div className="mt-2 flex items-center gap-1 text-xs text-green-600">
                        <Bot className="w-3 h-3" />
                        {contact.ai_replies} AI replies
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Conversation View */}
            <div className="flex-1 flex flex-col">
              {selectedContact ? (
                <>
                  <div className="p-4 border-b border-gray-200 bg-gray-50">
                    <p className="font-semibold">{selectedContact}</p>
                  </div>
                  <div className="flex-1 overflow-y-auto p-4 space-y-3">
                    {conversations.slice().reverse().map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex ${msg.direction === 'out' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div className={`max-w-[70%] p-3 rounded-2xl ${
                          msg.direction === 'out'
                            ? msg.ai_generated
                              ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white'
                              : 'bg-blue-500 text-white'
                            : 'bg-gray-100 text-gray-900'
                        }`}>
                          <p className="text-sm">{msg.message}</p>
                          <div className={`text-xs mt-1 flex items-center gap-1 ${
                            msg.direction === 'out' ? 'text-white/70' : 'text-gray-400'
                          }`}>
                            {msg.ai_generated && <Bot className="w-3 h-3" />}
                            <Clock className="w-3 h-3" />
                            {msg.timestamp?.slice(11, 16)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center text-gray-400">
                  <div className="text-center">
                    <MessageSquare className="w-16 h-16 mx-auto mb-3 opacity-30" />
                    <p>Select a contact to view conversation</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* WhatsApp Web Tab */}
        {activeTab === 'whatsapp-web' && (
          <div className="p-6 space-y-6">
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-4 border border-green-200">
              <div className="flex items-start gap-3">
                <Zap className="w-5 h-5 text-green-600 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Connect Personal WhatsApp</p>
                  <p className="text-sm text-gray-600">
                    Link your personal WhatsApp account to send and receive messages directly from this dashboard.
                  </p>
                </div>
              </div>
            </div>

            {/* WhatsApp Web Connection Options */}
            <div className="grid grid-cols-2 gap-6">
              {/* Option 1: Connect Business WhatsApp */}
              <div className="bg-white border-2 border-gray-200 rounded-xl p-6 hover:border-green-500 transition-all">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-3 bg-green-100 rounded-xl">
                    <MessageSquare className="w-6 h-6 text-green-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">Your Business WhatsApp</h3>
                    <p className="text-sm text-gray-500">Link your number</p>
                  </div>
                </div>
                <p className="text-sm text-gray-600 mb-3">
                  Enter your business WhatsApp number to quickly access it.
                </p>
                <div className="space-y-3">
                  <input
                    type="tel"
                    placeholder="Your WhatsApp number (e.g., +14165551234)"
                    id="business-whatsapp-input"
                    defaultValue={localStorage.getItem('reroots_business_whatsapp') || ''}
                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        const phone = document.getElementById('business-whatsapp-input')?.value;
                        if (phone) {
                          // Save to localStorage
                          localStorage.setItem('reroots_business_whatsapp', phone);
                          // Format phone for wa.me link (remove non-digits except +)
                          const cleanPhone = phone.replace(/[^\d+]/g, '').replace('+', '');
                          // Open WhatsApp Web with phone for QR scan
                          const url = `https://web.whatsapp.com/send?phone=${cleanPhone}`;
                          window.open(url, '_blank');
                        } else {
                          // Just open WhatsApp Web
                          window.open('https://web.whatsapp.com', '_blank');
                        }
                      }}
                      data-testid="whatsapp-web-link"
                      className="flex-1 flex items-center justify-center gap-2 py-3 bg-green-500 text-white font-medium rounded-xl hover:bg-green-600 transition-all cursor-pointer"
                    >
                      <MessageSquare className="w-5 h-5" />
                      Open WhatsApp Web
                    </button>
                  </div>
                  <p className="text-xs text-gray-400 text-center">
                    Scan QR code with your phone to connect
                  </p>
                </div>
              </div>

              {/* Option 2: Direct Message Link */}
              <div className="bg-white border-2 border-gray-200 rounded-xl p-6 hover:border-green-500 transition-all">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-3 bg-blue-100 rounded-xl">
                    <Send className="w-6 h-6 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">Quick Message</h3>
                    <p className="text-sm text-gray-500">Send to any number</p>
                  </div>
                </div>
                <p className="text-sm text-gray-600 mb-3">
                  Generate a WhatsApp link to message any phone number directly.
                </p>
                <div className="space-y-3">
                  <input
                    type="tel"
                    placeholder="Phone number (e.g., +1234567890)"
                    id="quick-phone-input"
                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  />
                  <input
                    type="text"
                    placeholder="Message (optional)"
                    id="quick-message-input"
                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  />
                  <button
                    onClick={() => {
                      const phone = document.getElementById('quick-phone-input')?.value?.replace(/\D/g, '');
                      const msg = document.getElementById('quick-message-input')?.value || '';
                      if (phone) {
                        const url = `https://wa.me/${phone}${msg ? `?text=${encodeURIComponent(msg)}` : ''}`;
                        // Use location.href for better mobile support
                        window.location.href = url;
                      } else {
                        alert('Please enter a phone number');
                      }
                    }}
                    data-testid="send-quick-message-btn"
                    className="w-full py-2 bg-blue-500 text-white font-medium rounded-lg hover:bg-blue-600 transition-all"
                  >
                    Open Chat
                  </button>
                </div>
              </div>
            </div>

            {/* Broadcast Message */}
            <div className="bg-white border border-gray-200 rounded-xl p-6">
              <h3 className="font-semibold text-gray-900 mb-4">Broadcast Message</h3>
              <p className="text-sm text-gray-600 mb-4">
                Send promotional messages or offers to multiple customers at once.
              </p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Message Template</label>
                  <textarea
                    rows={3}
                    placeholder="Hi {name}! Check out our latest offers..."
                    id="broadcast-message"
                    className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  />
                  <p className="text-xs text-gray-400 mt-1">Use {'{name}'} to personalize with customer name</p>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      const msg = document.getElementById('broadcast-message')?.value || '';
                      if (msg) {
                        const url = `https://wa.me/?text=${encodeURIComponent(msg)}`;
                        window.location.href = url;
                      } else {
                        alert('Please enter a message');
                      }
                    }}
                    data-testid="broadcast-btn"
                    className="flex-1 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-medium rounded-xl hover:from-green-600 hover:to-emerald-600 transition-all"
                  >
                    Open WhatsApp to Share
                  </button>
                </div>
              </div>
            </div>

            {/* Tips */}
            <div className="bg-gray-50 rounded-xl p-4">
              <h4 className="font-medium text-gray-700 mb-2">Tips for WhatsApp Marketing</h4>
              <ul className="text-sm text-gray-600 space-y-1">
                <li>• Keep messages concise and personal</li>
                <li>• Include clear call-to-action</li>
                <li>• Best times to send: 10am-12pm, 2pm-5pm</li>
                <li>• Always get consent before messaging customers</li>
              </ul>
            </div>
          </div>
        )}

        {/* Test Mode Tab */}
        {activeTab === 'test' && (
          <div className="p-6 space-y-6">
            <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl p-4 border border-purple-100">
              <div className="flex items-start gap-3">
                <Sparkles className="w-5 h-5 text-purple-500 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Test Mode</p>
                  <p className="text-sm text-gray-600">
                    Test how the AI will respond without actually sending messages via WhatsApp.
                    Using <span className="font-semibold">{
                      settings?.provider === 'anthropic' ? 'Claude Sonnet' : 
                      settings?.provider === 'gemini' ? 'Gemini Flash' : 'GPT-4o'
                    }</span> in 
                    <span className="font-semibold"> {settings?.mode === 'brand' ? 'Brand Voice' : 'Digital Twin'}</span> mode.
                  </p>
                </div>
              </div>
            </div>

            {/* Test Input */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Customer Message</label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={testMessage}
                  onChange={(e) => setTestMessage(e.target.value)}
                  placeholder="Type a message to test..."
                  data-testid="test-message-input"
                  className="flex-1 px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-pink-500 focus:border-pink-500"
                  onKeyDown={(e) => e.key === 'Enter' && testReplyMessage()}
                />
                <button
                  onClick={testReplyMessage}
                  disabled={testLoading || !testMessage.trim()}
                  data-testid="test-send-btn"
                  className="px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-medium rounded-xl hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 transition-all flex items-center gap-2"
                >
                  {testLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                  Test
                </button>
              </div>
            </div>

            {/* Test Results */}
            {testReply && (
              <div className="space-y-4">
                <div className="p-4 bg-gray-100 rounded-xl">
                  <p className="text-sm font-medium text-gray-500 mb-2">Customer Message:</p>
                  <p className="text-gray-900">{testReply.input}</p>
                </div>
                
                <div className="p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Bot className="w-4 h-4 text-green-600" />
                    <p className="text-sm font-medium text-green-700">AI Reply ({testReply.provider}):</p>
                  </div>
                  <p className="text-gray-900 whitespace-pre-wrap">{testReply.reply}</p>
                </div>
              </div>
            )}

            {/* Quick Test Messages */}
            <div>
              <p className="text-sm font-medium text-gray-500 mb-3">Quick Test Messages</p>
              <div className="flex flex-wrap gap-2">
                {[
                  'Hi, what products do you sell?',
                  'How much is the PDRN serum?',
                  'Do you ship to USA?',
                  'My order hasnt arrived yet',
                  'Can I get a discount?'
                ].map((msg, idx) => (
                  <button
                    key={idx}
                    onClick={() => setTestMessage(msg)}
                    data-testid={`quick-test-${idx}`}
                    className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-sm text-gray-700 transition-colors"
                  >
                    {msg}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WhatsAppAIAssistant;
