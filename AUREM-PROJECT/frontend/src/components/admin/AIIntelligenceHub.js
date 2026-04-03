import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { 
  Crown, AlertTriangle, Sparkles, MessageSquare, TrendingUp, 
  Shield, Users, Star, Gift, Copy, RefreshCw, Loader2, 
  Bell, DollarSign, Package, Brain, Zap, Target, Heart,
  FileText, BarChart3, Send, CheckCircle, XCircle, Eye
} from 'lucide-react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// =====================================================
// VIP SIGNAL COMPONENT - High-Value Customer Alerts
// =====================================================
const VIPSignalPanel = ({ token }) => {
  const [vipCustomers, setVipCustomers] = useState([]);
  const [vipAlerts, setVipAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [settings, setSettings] = useState({
    min_order_value_vip: 200,
    min_orders_count_vip: 3,
    social_follower_threshold: 10000,
    auto_thank_you_note: true
  });
  const [generatingNote, setGeneratingNote] = useState(null);

  const fetchVIPData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/ai/vip-signals`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setVipCustomers(res.data.vip_customers || []);
      setVipAlerts(res.data.recent_alerts || []);
    } catch (err) {
      console.error('Failed to fetch VIP data:', err);
    }
    setLoading(false);
  }, [token]);

  useEffect(() => {
    fetchVIPData();
  }, [fetchVIPData]);

  const generateThankYouNote = async (customer) => {
    setGeneratingNote(customer.id);
    try {
      const res = await axios.post(`${API}/admin/ai/generate-thank-you-note`, {
        customer_name: customer.name,
        order_total: customer.total_spent,
        products: customer.recent_products || [],
        is_repeat: customer.order_count > 1
      }, { headers: { Authorization: `Bearer ${token}` } });
      
      toast.success('Thank you note generated!');
      // Copy to clipboard
      navigator.clipboard.writeText(res.data.note);
      toast.info('Note copied to clipboard!');
    } catch (err) {
      toast.error('Failed to generate note');
    }
    setGeneratingNote(null);
  };

  return (
    <Card className="border-yellow-200 bg-gradient-to-br from-yellow-50 to-amber-50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-amber-800">
          <Crown className="h-5 w-5 text-amber-500" />
          VIP Signal - High-Value Customer Alerts
        </CardTitle>
        <CardDescription>
          Automatically identify VIP customers and generate personalized thank-you notes
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Settings */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-3 bg-white/50 rounded-lg">
          <div>
            <Label className="text-xs">Min Order Value ($)</Label>
            <Input 
              type="number" 
              value={settings.min_order_value_vip}
              onChange={(e) => setSettings({...settings, min_order_value_vip: parseInt(e.target.value)})}
              className="h-8"
            />
          </div>
          <div>
            <Label className="text-xs">Min Orders Count</Label>
            <Input 
              type="number" 
              value={settings.min_orders_count_vip}
              onChange={(e) => setSettings({...settings, min_orders_count_vip: parseInt(e.target.value)})}
              className="h-8"
            />
          </div>
          <div>
            <Label className="text-xs">Social Followers</Label>
            <Input 
              type="number" 
              value={settings.social_follower_threshold}
              onChange={(e) => setSettings({...settings, social_follower_threshold: parseInt(e.target.value)})}
              className="h-8"
            />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-xs">
              <Switch 
                checked={settings.auto_thank_you_note}
                onCheckedChange={(v) => setSettings({...settings, auto_thank_you_note: v})}
              />
              Auto Thank-You
            </label>
          </div>
        </div>

        {/* Recent VIP Alerts */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-sm flex items-center gap-2">
              <Bell className="h-4 w-4 text-amber-500" />
              Recent VIP Orders
            </h4>
            <Button size="sm" variant="ghost" onClick={fetchVIPData} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
          
          {vipAlerts.length === 0 ? (
            <div className="text-center py-6 text-gray-500 text-sm">
              <Crown className="h-8 w-8 mx-auto mb-2 text-gray-300" />
              No VIP orders detected yet
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {vipAlerts.map((alert, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-white rounded-lg border border-amber-200 shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-400 to-yellow-500 flex items-center justify-center text-white font-bold">
                      {alert.customer_name?.charAt(0) || '?'}
                    </div>
                    <div>
                      <p className="font-medium text-sm">{alert.customer_name}</p>
                      <div className="flex items-center gap-2 text-xs text-gray-500">
                        <span>${alert.order_total?.toFixed(2)}</span>
                        {alert.is_repeat && <Badge variant="outline" className="text-xs">Repeat</Badge>}
                        {alert.is_influencer && <Badge className="bg-purple-500 text-xs">Influencer</Badge>}
                      </div>
                    </div>
                  </div>
                  <Button 
                    size="sm" 
                    variant="outline"
                    className="border-amber-300 text-amber-700 hover:bg-amber-50"
                    onClick={() => generateThankYouNote(alert)}
                    disabled={generatingNote === alert.id}
                  >
                    {generatingNote === alert.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <><Gift className="h-4 w-4 mr-1" /> Thank You Note</>
                    )}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

// =====================================================
// FRAUD DETECTION COMPONENT
// =====================================================
const FraudDetectionPanel = ({ token }) => {
  const [flaggedOrders, setFlaggedOrders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [settings, setSettings] = useState({
    enabled: true,
    check_ip_mismatch: true,
    check_address_anomaly: true,
    check_velocity: true,
    auto_hold: false
  });

  const fetchFlaggedOrders = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/ai/fraud-detection`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setFlaggedOrders(res.data.flagged_orders || []);
    } catch (err) {
      console.error('Failed to fetch fraud data:', err);
    }
    setLoading(false);
  }, [token]);

  useEffect(() => {
    fetchFlaggedOrders();
  }, [fetchFlaggedOrders]);

  const reviewOrder = async (orderId, action) => {
    try {
      await axios.post(`${API}/admin/ai/fraud-review`, {
        order_id: orderId,
        action: action // 'approve' or 'reject'
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`Order ${action}d`);
      fetchFlaggedOrders();
    } catch (err) {
      toast.error('Failed to update order');
    }
  };

  return (
    <Card className="border-red-200 bg-gradient-to-br from-red-50 to-orange-50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-red-800">
          <Shield className="h-5 w-5 text-red-500" />
          Fraud & Chargeback Protection
        </CardTitle>
        <CardDescription>
          AI-powered fraud detection to protect against chargebacks
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Settings */}
        <div className="flex flex-wrap gap-4 p-3 bg-white/50 rounded-lg">
          <label className="flex items-center gap-2 text-xs">
            <Switch checked={settings.enabled} onCheckedChange={(v) => setSettings({...settings, enabled: v})} />
            Enabled
          </label>
          <label className="flex items-center gap-2 text-xs">
            <Switch checked={settings.check_ip_mismatch} onCheckedChange={(v) => setSettings({...settings, check_ip_mismatch: v})} />
            IP Mismatch
          </label>
          <label className="flex items-center gap-2 text-xs">
            <Switch checked={settings.check_address_anomaly} onCheckedChange={(v) => setSettings({...settings, check_address_anomaly: v})} />
            Address Anomaly
          </label>
          <label className="flex items-center gap-2 text-xs">
            <Switch checked={settings.auto_hold} onCheckedChange={(v) => setSettings({...settings, auto_hold: v})} />
            Auto-Hold Risky
          </label>
        </div>

        {/* Flagged Orders */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-sm flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              Flagged Orders ({flaggedOrders.length})
            </h4>
            <Button size="sm" variant="ghost" onClick={fetchFlaggedOrders} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>

          {flaggedOrders.length === 0 ? (
            <div className="text-center py-6 text-gray-500 text-sm">
              <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-400" />
              No suspicious orders detected
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {flaggedOrders.map((order, idx) => (
                <div key={idx} className="p-3 bg-white rounded-lg border border-red-200 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <p className="font-medium text-sm">Order #{order.order_number}</p>
                      <p className="text-xs text-gray-500">{order.customer_email}</p>
                    </div>
                    <Badge variant="outline" className="bg-red-50 text-red-700 border-red-300">
                      Risk: {order.risk_score}%
                    </Badge>
                  </div>
                  <div className="text-xs text-red-600 mb-2">
                    {order.risk_reasons?.map((r, i) => <span key={i} className="block">• {r}</span>)}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" className="flex-1 text-green-600 border-green-300" onClick={() => reviewOrder(order.id, 'approve')}>
                      <CheckCircle className="h-4 w-4 mr-1" /> Approve
                    </Button>
                    <Button size="sm" variant="outline" className="flex-1 text-red-600 border-red-300" onClick={() => reviewOrder(order.id, 'reject')}>
                      <XCircle className="h-4 w-4 mr-1" /> Reject
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

// =====================================================
// CONTENT FACTORY COMPONENT
// =====================================================
const ContentFactoryPanel = ({ token, products }) => {
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [contentType, setContentType] = useState('tiktok');
  const [generatedContent, setGeneratedContent] = useState([]);
  const [generating, setGenerating] = useState(false);

  const generateContent = async () => {
    if (!selectedProduct) {
      toast.error('Please select a product');
      return;
    }
    
    setGenerating(true);
    try {
      const res = await axios.post(`${API}/admin/ai/generate-ad-content`, {
        product_id: selectedProduct.id,
        content_type: contentType,
        variations: 5
      }, { headers: { Authorization: `Bearer ${token}` } });
      
      setGeneratedContent(res.data.content || []);
      toast.success(`Generated ${res.data.content?.length || 0} variations!`);
    } catch (err) {
      toast.error('Failed to generate content');
    }
    setGenerating(false);
  };

  const copyContent = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard!');
  };

  return (
    <Card className="border-purple-200 bg-gradient-to-br from-purple-50 to-pink-50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-purple-800">
          <Sparkles className="h-5 w-5 text-purple-500" />
          Content Factory - AI Ad Copy Generator
        </CardTitle>
        <CardDescription>
          Generate TikTok scripts, Instagram captions, and ad copy using your product data
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label className="text-xs">Select Product</Label>
            <select 
              className="w-full h-9 px-3 rounded-md border text-sm"
              value={selectedProduct?.id || ''}
              onChange={(e) => setSelectedProduct(products?.find(p => p.id === e.target.value))}
            >
              <option value="">Choose a product...</option>
              {products?.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <Label className="text-xs">Content Type</Label>
            <select 
              className="w-full h-9 px-3 rounded-md border text-sm"
              value={contentType}
              onChange={(e) => setContentType(e.target.value)}
            >
              <option value="tiktok">TikTok Script</option>
              <option value="instagram">Instagram Caption</option>
              <option value="meta_ad">Meta Ad Copy</option>
              <option value="email">Email Subject Lines</option>
              <option value="sms">SMS Marketing</option>
            </select>
          </div>
        </div>

        <Button 
          onClick={generateContent} 
          disabled={generating || !selectedProduct}
          className="w-full bg-purple-600 hover:bg-purple-700"
        >
          {generating ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Generating 5 Variations...</>
          ) : (
            <><Sparkles className="h-4 w-4 mr-2" /> Generate Ad Copy</>
          )}
        </Button>

        {/* Generated Content */}
        {generatedContent.length > 0 && (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {generatedContent.map((content, idx) => (
              <div key={idx} className="p-3 bg-white rounded-lg border border-purple-200">
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="outline" className="text-purple-600">Variation {idx + 1}</Badge>
                  <Button size="sm" variant="ghost" onClick={() => copyContent(content.text)}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-sm whitespace-pre-wrap">{content.text}</p>
                {content.hashtags && (
                  <p className="text-xs text-purple-500 mt-2">{content.hashtags}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// =====================================================
// SENTIMENT ANALYSIS COMPONENT
// =====================================================
const SentimentAnalysisPanel = ({ token }) => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [timeRange, setTimeRange] = useState('week');

  const generateReport = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/ai/sentiment-analysis?range=${timeRange}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setReport(res.data);
      toast.success('Vibe Check report generated!');
    } catch (err) {
      toast.error('Failed to generate report');
    }
    setLoading(false);
  };

  return (
    <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-cyan-50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-blue-800">
          <MessageSquare className="h-5 w-5 text-blue-500" />
          Sentiment Analysis - Weekly Vibe Check
        </CardTitle>
        <CardDescription>
          AI-powered analysis of customer reviews and feedback
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <Label className="text-xs">Time Range</Label>
            <select 
              className="w-full h-9 px-3 rounded-md border text-sm"
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
            >
              <option value="week">Last 7 Days</option>
              <option value="month">Last 30 Days</option>
              <option value="quarter">Last 90 Days</option>
            </select>
          </div>
          <Button onClick={generateReport} disabled={loading} className="bg-blue-600 hover:bg-blue-700">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <><BarChart3 className="h-4 w-4 mr-2" /> Generate Report</>}
          </Button>
        </div>

        {report && (
          <div className="space-y-4">
            {/* Overall Sentiment */}
            <div className="p-4 bg-white rounded-lg border border-blue-200">
              <h4 className="font-medium text-sm mb-3 flex items-center gap-2">
                <Heart className="h-4 w-4 text-red-500" />
                Overall Sentiment
              </h4>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex justify-between text-xs mb-1">
                    <span>Positive</span>
                    <span className="text-green-600">{report.positive_percent}%</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full">
                    <div className="h-2 bg-green-500 rounded-full" style={{width: `${report.positive_percent}%`}}></div>
                  </div>
                </div>
                <div className="flex-1">
                  <div className="flex justify-between text-xs mb-1">
                    <span>Neutral</span>
                    <span className="text-gray-600">{report.neutral_percent}%</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full">
                    <div className="h-2 bg-gray-400 rounded-full" style={{width: `${report.neutral_percent}%`}}></div>
                  </div>
                </div>
                <div className="flex-1">
                  <div className="flex justify-between text-xs mb-1">
                    <span>Negative</span>
                    <span className="text-red-600">{report.negative_percent}%</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full">
                    <div className="h-2 bg-red-500 rounded-full" style={{width: `${report.negative_percent}%`}}></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Key Insights */}
            <div className="p-4 bg-white rounded-lg border border-blue-200">
              <h4 className="font-medium text-sm mb-3">Key Insights</h4>
              <div className="space-y-2">
                {report.insights?.map((insight, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-sm">
                    <span className={insight.type === 'positive' ? 'text-green-500' : insight.type === 'negative' ? 'text-red-500' : 'text-blue-500'}>
                      {insight.type === 'positive' ? '👍' : insight.type === 'negative' ? '⚠️' : '💡'}
                    </span>
                    <span>{insight.text}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Recommendations */}
            {report.recommendations && (
              <div className="p-4 bg-gradient-to-r from-blue-100 to-cyan-100 rounded-lg border border-blue-300">
                <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
                  <Target className="h-4 w-4 text-blue-600" />
                  AI Recommendations
                </h4>
                <p className="text-sm text-blue-800">{report.recommendations}</p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// =====================================================
// MAIN AI INTELLIGENCE HUB
// =====================================================
import PendingAIActions from './PendingAIActions';

const AIIntelligenceHub = ({ products }) => {
  const token = localStorage.getItem('reroots_token');
  const [activeTab, setActiveTab] = useState('bridge');

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            <Brain className="h-6 w-6 text-purple-600" />
            AI Intelligence Hub
          </h1>
          <p className="text-sm text-gray-500">Autonomous systems for customer insights, fraud protection, and content generation</p>
        </div>
        <Badge className="bg-gradient-to-r from-purple-500 to-pink-500 text-white">
          <Zap className="h-3 w-3 mr-1" /> AI Powered
        </Badge>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-5 w-full">
          <TabsTrigger value="bridge" className="flex items-center gap-1">
            <Zap className="h-4 w-4" />
            <span className="hidden sm:inline">Bridge</span>
          </TabsTrigger>
          <TabsTrigger value="vip" className="flex items-center gap-1">
            <Crown className="h-4 w-4" />
            <span className="hidden sm:inline">VIP Signal</span>
          </TabsTrigger>
          <TabsTrigger value="fraud" className="flex items-center gap-1">
            <Shield className="h-4 w-4" />
            <span className="hidden sm:inline">Fraud</span>
          </TabsTrigger>
          <TabsTrigger value="content" className="flex items-center gap-1">
            <Sparkles className="h-4 w-4" />
            <span className="hidden sm:inline">Content</span>
          </TabsTrigger>
          <TabsTrigger value="sentiment" className="flex items-center gap-1">
            <MessageSquare className="h-4 w-4" />
            <span className="hidden sm:inline">Sentiment</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="bridge" className="mt-4">
          <PendingAIActions token={token} />
        </TabsContent>
        <TabsContent value="vip" className="mt-4">
          <VIPSignalPanel token={token} />
        </TabsContent>
        <TabsContent value="fraud" className="mt-4">
          <FraudDetectionPanel token={token} />
        </TabsContent>
        <TabsContent value="content" className="mt-4">
          <ContentFactoryPanel token={token} products={products} />
        </TabsContent>
        <TabsContent value="sentiment" className="mt-4">
          <SentimentAnalysisPanel token={token} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AIIntelligenceHub;
