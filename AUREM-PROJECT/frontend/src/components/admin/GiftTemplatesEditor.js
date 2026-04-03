import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { 
  Mail, MessageSquare, Phone, Save, Loader2, 
  Eye, Palette, RefreshCw, Info, Gift, Sparkles
} from 'lucide-react';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const GiftTemplatesEditor = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [templates, setTemplates] = useState({
    email: {
      subject: '🎁 {sender_name} sent you a gift!',
      cta_text: '🛍️ Claim Points & Shop Now',
      cta_color: '#F8A5B8'
    },
    sms: {
      message: '🎁 {sender_name} sent you {points_amount} points ({points_value})! Claim & shop: {claim_link}'
    },
    whatsapp: {
      message: '🎁 *You received a gift!*\n\n{sender_name} sent you *{points_amount} points* (worth {points_value})!\n\n{personal_note}\n\n👉 Claim your points & shop: {claim_link}\n\n⏰ Expires in {expiry_days} days'
    }
  });
  const [previewTab, setPreviewTab] = useState('email');

  const availableVars = [
    { name: '{sender_name}', desc: "Sender's name" },
    { name: '{recipient_name}', desc: "Recipient's name" },
    { name: '{points_amount}', desc: 'Number of points' },
    { name: '{points_value}', desc: 'Dollar value (e.g., $15.00)' },
    { name: '{personal_note}', desc: "Sender's personal message" },
    { name: '{claim_link}', desc: 'Unique claim URL' },
    { name: '{expiry_days}', desc: 'Days until expiration' }
  ];

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.get(`${API}/admin/gift-templates`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTemplates(res.data);
    } catch (error) {
      console.error('Failed to load templates:', error);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.put(`${API}/admin/gift-templates`, templates, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Templates saved successfully!');
    } catch (error) {
      toast.error('Failed to save templates');
    }
    setSaving(false);
  };

  const updateTemplate = (channel, field, value) => {
    setTemplates(prev => ({
      ...prev,
      [channel]: {
        ...prev[channel],
        [field]: value
      }
    }));
  };

  // Preview with sample data
  const previewData = {
    sender_name: 'Sarah',
    recipient_name: 'John',
    points_amount: '300',
    points_value: '$15.00',
    personal_note: 'Happy Birthday! Treat yourself to some amazing skincare 💕',
    claim_link: 'https://reroots.ca/claim-gift/abc123',
    expiry_days: '30'
  };

  const renderPreview = (text) => {
    let result = text;
    Object.entries(previewData).forEach(([key, value]) => {
      result = result.replace(new RegExp(`\\{${key}\\}`, 'g'), value);
    });
    return result;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            <Gift className="h-6 w-6 text-[#F8A5B8]" />
            Gift Message Templates
          </h2>
          <p className="text-[#5A5A5A] text-sm mt-1">
            Customize the messages sent when someone receives a gift
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={fetchTemplates} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Reset
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={saving}
            className="bg-[#F8A5B8] hover:bg-[#E8959A] text-[#2D2A2E]"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Save Templates
          </Button>
        </div>
      </div>

      {/* Available Variables */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Info className="h-4 w-4 text-blue-500" />
            Available Variables
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {availableVars.map((v) => (
              <div key={v.name} className="group relative">
                <Badge 
                  variant="outline" 
                  className="cursor-help hover:bg-[#F8A5B8]/10 transition-colors"
                  onClick={() => navigator.clipboard.writeText(v.name)}
                >
                  {v.name}
                </Badge>
                <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 text-xs bg-gray-800 text-white rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
                  {v.desc} (click to copy)
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Editor */}
        <div className="space-y-4">
          <Tabs defaultValue="email" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="email" className="gap-2">
                <Mail className="h-4 w-4" />
                Email
              </TabsTrigger>
              <TabsTrigger value="sms" className="gap-2">
                <Phone className="h-4 w-4" />
                SMS
              </TabsTrigger>
              <TabsTrigger value="whatsapp" className="gap-2">
                <MessageSquare className="h-4 w-4" />
                WhatsApp
              </TabsTrigger>
            </TabsList>

            {/* Email Tab */}
            <TabsContent value="email">
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <div>
                    <Label htmlFor="email_subject">Subject Line</Label>
                    <Input
                      id="email_subject"
                      value={templates.email?.subject || ''}
                      onChange={(e) => updateTemplate('email', 'subject', e.target.value)}
                      placeholder="🎁 {sender_name} sent you a gift!"
                      className="mt-1"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="email_cta">Button Text</Label>
                    <Input
                      id="email_cta"
                      value={templates.email?.cta_text || ''}
                      onChange={(e) => updateTemplate('email', 'cta_text', e.target.value)}
                      placeholder="🛍️ Claim Points & Shop Now"
                      className="mt-1"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="email_color" className="flex items-center gap-2">
                      <Palette className="h-4 w-4" />
                      Button Color
                    </Label>
                    <div className="flex gap-2 mt-1">
                      <Input
                        id="email_color"
                        type="color"
                        value={templates.email?.cta_color || '#F8A5B8'}
                        onChange={(e) => updateTemplate('email', 'cta_color', e.target.value)}
                        className="w-16 h-10 p-1"
                      />
                      <Input
                        value={templates.email?.cta_color || '#F8A5B8'}
                        onChange={(e) => updateTemplate('email', 'cta_color', e.target.value)}
                        placeholder="#F8A5B8"
                        className="flex-1"
                      />
                    </div>
                  </div>
                  
                  <p className="text-xs text-[#5A5A5A]">
                    Note: Email body uses a branded HTML template with your gift info automatically included.
                  </p>
                </CardContent>
              </Card>
            </TabsContent>

            {/* SMS Tab */}
            <TabsContent value="sms">
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <Label htmlFor="sms_message">Message (160 char limit)</Label>
                      <span className={`text-xs ${(templates.sms?.message?.length || 0) > 160 ? 'text-red-500' : 'text-[#5A5A5A]'}`}>
                        {templates.sms?.message?.length || 0}/160
                      </span>
                    </div>
                    <Textarea
                      id="sms_message"
                      value={templates.sms?.message || ''}
                      onChange={(e) => updateTemplate('sms', 'message', e.target.value)}
                      placeholder="🎁 {sender_name} sent you {points_amount} points..."
                      rows={4}
                      className="mt-1"
                    />
                  </div>
                  
                  <p className="text-xs text-[#5A5A5A]">
                    Keep it short! SMS messages over 160 characters may be split into multiple texts.
                  </p>
                </CardContent>
              </Card>
            </TabsContent>

            {/* WhatsApp Tab */}
            <TabsContent value="whatsapp">
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <div>
                    <Label htmlFor="wa_message">Message</Label>
                    <Textarea
                      id="wa_message"
                      value={templates.whatsapp?.message || ''}
                      onChange={(e) => updateTemplate('whatsapp', 'message', e.target.value)}
                      placeholder="🎁 *You received a gift!*..."
                      rows={8}
                      className="mt-1 font-mono text-sm"
                    />
                  </div>
                  
                  <p className="text-xs text-[#5A5A5A]">
                    Tip: Use *text* for bold, _text_ for italic in WhatsApp formatting.
                  </p>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Live Preview */}
        <div>
          <Card className="sticky top-4">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Eye className="h-4 w-4 text-[#F8A5B8]" />
                Live Preview
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs value={previewTab} onValueChange={setPreviewTab}>
                <TabsList className="grid w-full grid-cols-3 mb-4">
                  <TabsTrigger value="email" className="text-xs">Email</TabsTrigger>
                  <TabsTrigger value="sms" className="text-xs">SMS</TabsTrigger>
                  <TabsTrigger value="whatsapp" className="text-xs">WhatsApp</TabsTrigger>
                </TabsList>

                <TabsContent value="email">
                  <div className="border rounded-lg overflow-hidden">
                    {/* Email Preview Header */}
                    <div className="bg-gray-100 px-3 py-2 border-b">
                      <p className="text-xs text-[#5A5A5A]">Subject:</p>
                      <p className="text-sm font-medium">
                        {renderPreview(templates.email?.subject || '')}
                      </p>
                    </div>
                    
                    {/* Email Preview Body */}
                    <div className="p-4 bg-white">
                      <div className="text-center mb-4">
                        <div className="text-4xl mb-2">🎁</div>
                        <h3 className="text-lg font-bold">You Received a Gift!</h3>
                        <p className="text-sm text-[#5A5A5A]">Sarah sent you something special</p>
                      </div>
                      
                      <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-lg p-4 text-center mb-4 border border-[#D4AF37]/30">
                        <div className="text-3xl font-bold text-[#D4AF37]">300 points</div>
                        <div className="text-sm">Worth <strong>$15.00</strong> off!</div>
                      </div>
                      
                      <div className="bg-[#FFF5F7] rounded-lg p-3 mb-4 border-l-4 border-[#F8A5B8]">
                        <p className="text-sm italic text-[#5A5A5A]">"{previewData.personal_note}"</p>
                        <p className="text-xs text-[#888] mt-1">— Sarah</p>
                      </div>
                      
                      <div className="text-center">
                        <button 
                          className="px-6 py-3 rounded-full font-semibold text-[#2D2A2E]"
                          style={{ background: templates.email?.cta_color || '#F8A5B8' }}
                        >
                          {templates.email?.cta_text || 'Claim Points'}
                        </button>
                      </div>
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="sms">
                  <div className="bg-gray-100 rounded-2xl p-4 max-w-[280px] mx-auto">
                    <div className="bg-green-500 text-white rounded-2xl rounded-tl-sm p-3 text-sm">
                      {renderPreview(templates.sms?.message || '')}
                    </div>
                    <p className="text-xs text-[#5A5A5A] mt-2 text-right">
                      {(renderPreview(templates.sms?.message || '')).length} characters
                    </p>
                  </div>
                </TabsContent>

                <TabsContent value="whatsapp">
                  <div className="bg-[#E5DDD5] rounded-lg p-4">
                    <div className="bg-white rounded-lg p-3 max-w-[280px] shadow-sm">
                      <div 
                        className="text-sm whitespace-pre-wrap"
                        dangerouslySetInnerHTML={{
                          __html: renderPreview(templates.whatsapp?.message || '')
                            .replace(/\*([^*]+)\*/g, '<strong>$1</strong>')
                            .replace(/_([^_]+)_/g, '<em>$1</em>')
                            .replace(/\n/g, '<br/>')
                        }}
                      />
                      <p className="text-xs text-[#5A5A5A] mt-2 text-right">12:34 PM ✓✓</p>
                    </div>
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default GiftTemplatesEditor;
