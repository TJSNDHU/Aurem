import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  CheckCircle, XCircle, Clock, AlertTriangle, Zap, FileText, 
  DollarSign, Shield, RefreshCw, Loader2, Eye, ChevronRight,
  Bot, Sparkles, MessageSquare, Package, Bell
} from 'lucide-react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL);

// Authority Level Badges
const AuthorityBadge = ({ level }) => {
  const config = {
    L1: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-300', label: 'L1: Auto-Execute' },
    L2: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-300', label: 'L2: Needs Approval' },
    L3: { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-300', label: 'L3: Admin Only' }
  };
  const c = config[level] || config.L2;
  return (
    <Badge variant="outline" className={`${c.bg} ${c.text} ${c.border} text-xs`}>
      {c.label}
    </Badge>
  );
};

// Action Type Icons
const ActionIcon = ({ type }) => {
  const icons = {
    price_fix: DollarSign,
    content_draft: FileText,
    fraud_flag: Shield,
    education_snippet: Sparkles,
    review_response: MessageSquare,
    inventory_alert: Package,
    admin_alert: Bell
  };
  const Icon = icons[type] || Zap;
  return <Icon className="h-4 w-4" />;
};

// Single Action Card - Color coded by type (concern vs win)
const ActionCard = ({ action, onApprove, onReject, onPreview, loading }) => {
  // Color coding: concern = red/amber, win = gold/pink
  const isWin = action.card_type === 'win' || action.action_type === 'social_proof';
  
  const statusColors = {
    pending: isWin ? 'border-amber-400 bg-gradient-to-br from-amber-50 to-yellow-50' : 'border-amber-300 bg-amber-50',
    approved: 'border-green-300 bg-green-50',
    rejected: 'border-red-300 bg-red-50',
    executed: 'border-blue-300 bg-blue-50'
  };

  const iconGradient = isWin 
    ? 'bg-gradient-to-br from-amber-400 to-pink-500' 
    : 'bg-gradient-to-br from-purple-500 to-pink-500';

  return (
    <div className={`p-4 rounded-lg border-2 ${statusColors[action.status] || 'border-gray-200'} transition-all hover:shadow-md`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full ${iconGradient} flex items-center justify-center text-white`}>
            <ActionIcon type={action.action_type} />
          </div>
          <div>
            <h4 className="font-semibold text-sm text-gray-800">{action.title}</h4>
            <div className="flex items-center gap-2">
              <p className="text-xs text-gray-500">{action.action_type?.replace(/_/g, ' ').toUpperCase()}</p>
              {isWin && <Badge className="bg-gradient-to-r from-amber-400 to-pink-400 text-white text-[10px] px-1">WIN</Badge>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <AuthorityBadge level={action.authority_level} />
          <Badge variant="outline" className={action.status === 'pending' ? 'bg-amber-50 text-amber-600' : 'bg-gray-50'}>
            {action.status}
          </Badge>
        </div>
      </div>

      {/* Customer Quote for Wins */}
      {action.customer_quote && (
        <div className="bg-gradient-to-r from-amber-100 to-pink-100 rounded-md p-3 mb-3 border border-amber-200">
          <p className="text-xs text-amber-800 font-medium mb-1">💬 Customer Quote:</p>
          <p className="text-sm text-gray-700 italic">"{action.customer_quote}"</p>
        </div>
      )}

      {/* Draft Content Preview */}
      <div className={`rounded-md p-3 mb-3 border ${isWin ? 'bg-white/80 border-amber-200' : 'bg-white/70 border-gray-200'}`}>
        <p className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-3">{action.draft_content}</p>
        {action.draft_content?.length > 150 && (
          <Button variant="link" size="sm" className="p-0 h-auto text-purple-600" onClick={() => onPreview(action)}>
            View Full Content <ChevronRight className="h-3 w-3 ml-1" />
          </Button>
        )}
      </div>

      {/* Trigger Info */}
      <div className="flex items-center gap-4 text-xs text-gray-500 mb-3">
        <span className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {new Date(action.created_at).toLocaleString()}
        </span>
        {action.trigger_source && (
          <span className="flex items-center gap-1">
            <Zap className="h-3 w-3" />
            Trigger: {action.trigger_source}
          </span>
        )}
      </div>

      {/* Action Buttons - Only for pending L2 actions */}
      {action.status === 'pending' && action.authority_level === 'L2' && (
        <div className="flex gap-2">
          <Button 
            size="sm" 
            className={`flex-1 ${isWin ? 'bg-gradient-to-r from-amber-500 to-pink-500 hover:from-amber-600 hover:to-pink-600' : 'bg-green-600 hover:bg-green-700'}`}
            onClick={() => onApprove(action.id)}
            disabled={loading === action.id}
          >
            {loading === action.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <><CheckCircle className="h-4 w-4 mr-1" /> {isWin ? 'Approve for Social' : 'Approve & Execute'}</>}
          </Button>
          <Button 
            size="sm" 
            variant="outline"
            className="flex-1 border-red-300 text-red-600 hover:bg-red-50"
            onClick={() => onReject(action.id)}
            disabled={loading === action.id}
          >
            <XCircle className="h-4 w-4 mr-1" /> Reject
          </Button>
        </div>
      )}

      {/* Execution Result for completed actions */}
      {action.execution_result && (
        <div className="mt-3 p-2 bg-blue-50 rounded text-xs text-blue-700">
          <strong>Result:</strong> {action.execution_result}
        </div>
      )}
    </div>
  );
};

// Simulate Review Component - For Testing the Watchdog (Both Defense & Offense)
const SimulateReviewPanel = ({ token, onReviewAdded }) => {
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    product_name: 'AURA-GEN Biotech Serum',
    rating: 3,
    tone: 'frustrated',
    review_type: 'concern',  // 'concern' or 'win'
    concern_type: 'texture',
    win_type: 'glass_skin',
    custom_text: ''
  });

  // Preset templates based on type and tone
  const generateReviewText = () => {
    // DEFENSE: Concern templates
    const concernTemplates = {
      texture: {
        frustrated: "I've been using this for 2 weeks and it's SO STICKY. Feels heavy on my skin and takes forever to absorb. Not what I expected from a 'biotech' product.",
        polite: "The serum is nice but I find it a bit tacky on my skin. Perhaps applying to damp skin would help? Would love tips on better absorption.",
        angry: "This is basically GLUE. Worst texture I've ever experienced. My skin feels like it's suffocating. Want my money back!"
      },
      efficacy: {
        frustrated: "Been using this for a month and honestly... nothing. No glow, no results. Starting to think this doesn't work at all.",
        polite: "I'm on week 4 and haven't noticed significant changes yet. Is this normal for the purging phase? Any timeline for results?",
        angry: "SCAM. Complete waste of money. This product does NOTHING. No results whatsoever. Total fake science nonsense."
      },
      packaging: {
        frustrated: "My bottle arrived with product leaked everywhere. The pump doesn't work properly. Really disappointing for a premium brand.",
        polite: "Unfortunately my package arrived with some damage. The seal was broken and some product had leaked. Would appreciate a replacement.",
        angry: "BROKEN on arrival! Box was soaked, bottle cracked, product everywhere. This is unacceptable for a $80+ serum!"
      }
    };
    
    // OFFENSE: Win templates (for Marketing Engine testing)
    const winTemplates = {
      glass_skin: {
        excited: "OMG obsessed with this serum! My skin has NEVER looked like this - literal glass skin! I woke up like this for the first time ever. Holy grail product!",
        calm: "Really impressed with the results. My skin looks poreless and plump, friends keep asking what I'm using. The biotech actually works.",
        influencer: "Ok this is not an ad but I'm literally obsessed. Glass skin era has officially begun 💎 Never switching from this holy grail serum!"
      },
      results: {
        excited: "This product actually works! Visible results in just 2 weeks - my acne scars are fading and my skin is glowing. Game changer!",
        calm: "I was skeptical but the biotech science is real. My skin healed faster than any other product I've tried. Worth every penny.",
        influencer: "Not me becoming a walking billboard for ReRoots 😭 This serum healed my skin and I'm never going back. Life changing!"
      },
      obsessed: {
        excited: "I'm so obsessed with this I bought backups! The glow is insane, my skin has never been this plump. This is THE holy grail serum.",
        calm: "Quietly obsessed with this formulation. The results speak for themselves - poreless, bouncy skin that looks lit from within.",
        influencer: "POV: You finally found the serum that makes your skin look like a filter 💫 Obsessed is an understatement. Game changer!"
      }
    };
    
    if (formData.custom_text) return formData.custom_text;
    
    if (formData.review_type === 'win') {
      return winTemplates[formData.win_type]?.[formData.tone] || winTemplates.glass_skin.excited;
    } else {
      return concernTemplates[formData.concern_type]?.[formData.tone] || concernTemplates.texture.frustrated;
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const reviewText = formData.custom_text || generateReviewText();
      const isWin = formData.review_type === 'win';
      
      await axios.post(`${API}/api/admin/ai/simulate-review`, {
        product_name: formData.product_name,
        rating: isWin ? (formData.rating >= 4 ? formData.rating : 5) : formData.rating,  // Wins default to high ratings
        title: `Test Review - ${isWin ? formData.win_type : formData.concern_type} (${formData.tone})`,
        comment: reviewText,
        is_simulation: true
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success(`${isWin ? '✨ Win' : '🔧 Concern'} review added! Run Watchdog Scan to detect patterns.`);
      setShowForm(false);
      onReviewAdded?.();
    } catch (err) {
      toast.error('Failed to add test review: ' + (err.response?.data?.detail || err.message));
    }
    setSubmitting(false);
  };

  return (
    <Card className="border-amber-200 bg-gradient-to-br from-amber-50 to-yellow-50">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-amber-800 text-lg">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          Stress Test - Simulate Reviews
        </CardTitle>
        <CardDescription>Add test reviews to verify Brand Guardian responses</CardDescription>
      </CardHeader>
      <CardContent>
        {!showForm ? (
          <Button 
            onClick={() => setShowForm(true)}
            variant="outline"
            className="w-full border-amber-300 text-amber-700 hover:bg-amber-100"
          >
            <Sparkles className="h-4 w-4 mr-2" /> Add Test Review
          </Button>
        ) : (
          <div className="space-y-4">
            {/* Review Type Toggle - Defense vs Offense */}
            <div>
              <label className="text-xs font-medium text-gray-700">Review Type</label>
              <div className="grid grid-cols-2 gap-2 mt-1">
                <button
                  className={`p-3 rounded-md border text-sm font-medium transition-all ${
                    formData.review_type === 'concern' 
                      ? 'bg-red-500 text-white border-red-500' 
                      : 'bg-white border-gray-200 hover:border-red-300'
                  }`}
                  onClick={() => setFormData({...formData, review_type: 'concern', rating: 2})}
                >
                  🛡️ Concern (Defense)
                </button>
                <button
                  className={`p-3 rounded-md border text-sm font-medium transition-all ${
                    formData.review_type === 'win' 
                      ? 'bg-gradient-to-r from-amber-400 to-pink-400 text-white border-amber-400' 
                      : 'bg-white border-gray-200 hover:border-amber-300'
                  }`}
                  onClick={() => setFormData({...formData, review_type: 'win', rating: 5})}
                >
                  ✨ Win (Marketing)
                </button>
              </div>
            </div>

            {/* Product Selection */}
            <div>
              <label className="text-xs font-medium text-gray-700">Product</label>
              <select 
                className="w-full h-9 px-3 rounded-md border text-sm mt-1"
                value={formData.product_name}
                onChange={(e) => setFormData({...formData, product_name: e.target.value})}
              >
                <option>AURA-GEN Biotech Serum</option>
                <option>Copper Peptide Recovery</option>
                <option>PDRN Power Duo</option>
                <option>Bakuchiol Night Complex</option>
              </select>
            </div>

            {/* Concern Type - Only for Defense mode */}
            {formData.review_type === 'concern' && (
              <div>
                <label className="text-xs font-medium text-gray-700">Concern Type</label>
                <div className="grid grid-cols-3 gap-2 mt-1">
                  {['texture', 'efficacy', 'packaging'].map(type => (
                    <button
                      key={type}
                      className={`p-2 rounded-md border text-xs font-medium transition-all ${
                        formData.concern_type === type 
                          ? 'bg-red-500 text-white border-red-500' 
                          : 'bg-white border-gray-200 hover:border-red-300'
                      }`}
                      onClick={() => setFormData({...formData, concern_type: type})}
                    >
                      {type === 'texture' && '💧 Texture'}
                      {type === 'efficacy' && '⚡ Efficacy'}
                      {type === 'packaging' && '📦 Packaging'}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Win Type - Only for Offense mode */}
            {formData.review_type === 'win' && (
              <div>
                <label className="text-xs font-medium text-gray-700">Win Category (Viral Trigger)</label>
                <div className="grid grid-cols-3 gap-2 mt-1">
                  {['glass_skin', 'results', 'obsessed'].map(type => (
                    <button
                      key={type}
                      className={`p-2 rounded-md border text-xs font-medium transition-all ${
                        formData.win_type === type 
                          ? 'bg-gradient-to-r from-amber-400 to-pink-400 text-white border-amber-400' 
                          : 'bg-white border-gray-200 hover:border-amber-300'
                      }`}
                      onClick={() => setFormData({...formData, win_type: type})}
                    >
                      {type === 'glass_skin' && '💎 Glass Skin'}
                      {type === 'results' && '📈 Results'}
                      {type === 'obsessed' && '💕 Obsessed'}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Tone Selection */}
            <div>
              <label className="text-xs font-medium text-gray-700">
                {formData.review_type === 'win' ? 'Tone (Social Style)' : 'Customer Tone'}
              </label>
              <div className="grid grid-cols-3 gap-2 mt-1">
                {formData.review_type === 'concern' ? (
                  <>
                    {['polite', 'frustrated', 'angry'].map(tone => (
                      <button
                        key={tone}
                        className={`p-2 rounded-md border text-xs font-medium transition-all ${
                          formData.tone === tone 
                            ? 'bg-purple-500 text-white border-purple-500' 
                            : 'bg-white border-gray-200 hover:border-purple-300'
                        }`}
                        onClick={() => setFormData({...formData, tone: tone})}
                      >
                        {tone === 'polite' && '😊 Polite'}
                        {tone === 'frustrated' && '😤 Frustrated'}
                        {tone === 'angry' && '😡 Angry'}
                      </button>
                    ))}
                  </>
                ) : (
                  <>
                    {['calm', 'excited', 'influencer'].map(tone => (
                      <button
                        key={tone}
                        className={`p-2 rounded-md border text-xs font-medium transition-all ${
                          formData.tone === tone 
                            ? 'bg-pink-500 text-white border-pink-500' 
                            : 'bg-white border-gray-200 hover:border-pink-300'
                        }`}
                        onClick={() => setFormData({...formData, tone: tone})}
                      >
                        {tone === 'calm' && '😌 Calm'}
                        {tone === 'excited' && '🤩 Excited'}
                        {tone === 'influencer' && '📱 Influencer'}
                      </button>
                    ))}
                  </>
                )}
              </div>
            </div>

            {/* Star Rating */}
            <div>
              <label className="text-xs font-medium text-gray-700">Rating</label>
              <div className="flex gap-1 mt-1">
                {[1, 2, 3, 4, 5].map(star => (
                  <button
                    key={star}
                    className={`text-2xl ${formData.rating >= star ? 'text-amber-400' : 'text-gray-300'}`}
                    onClick={() => setFormData({...formData, rating: star})}
                  >
                    ★
                  </button>
                ))}
                <span className="ml-2 text-sm text-gray-500">({formData.rating}/5)</span>
              </div>
            </div>

            {/* Preview */}
            <div>
              <label className="text-xs font-medium text-gray-700">Review Preview</label>
              <div className="mt-1 p-3 bg-white rounded-md border border-gray-200 text-sm text-gray-700">
                {generateReviewText()}
              </div>
            </div>

            {/* Or Custom Text */}
            <div>
              <label className="text-xs font-medium text-gray-700">Or Write Custom (optional)</label>
              <textarea 
                className="w-full p-2 rounded-md border text-sm mt-1"
                rows={2}
                placeholder="Write your own test review..."
                value={formData.custom_text}
                onChange={(e) => setFormData({...formData, custom_text: e.target.value})}
              />
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              <Button 
                onClick={handleSubmit}
                disabled={submitting}
                className="flex-1 bg-amber-600 hover:bg-amber-700"
              >
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <><CheckCircle className="h-4 w-4 mr-1" /> Add Test Review</>}
              </Button>
              <Button 
                variant="outline"
                onClick={() => setShowForm(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Review Watchdog Status Card - Dual Mode (Defense + Offense)
const WatchdogStatus = ({ token, onScanComplete }) => {
  const [scanning, setScanning] = useState(false);
  const [lastScan, setLastScan] = useState(null);
  const [concerns, setConcerns] = useState([]);
  const [wins, setWins] = useState([]);

  const runScan = async () => {
    setScanning(true);
    try {
      const res = await axios.post(`${API}/api/admin/ai/review-watchdog/scan`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setLastScan(new Date().toISOString());
      setConcerns(res.data.concerns || []);
      setWins(res.data.wins || []);
      
      const concernCount = res.data.concerns?.length || 0;
      const winCount = res.data.wins?.length || 0;
      toast.success(`Scan complete! ${concernCount} concerns, ${winCount} wins detected. ${res.data.actions_created || 0} actions created.`);
      onScanComplete?.();
    } catch (err) {
      toast.error('Scan failed: ' + (err.response?.data?.detail || err.message));
    }
    setScanning(false);
  };

  return (
    <Card className="border-purple-200 bg-gradient-to-br from-purple-50 to-indigo-50">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-purple-800 text-lg">
          <Bot className="h-5 w-5 text-purple-500" />
          Dual-Mode Watchdog
          <Badge variant="outline" className="text-xs bg-red-50 text-red-600 border-red-200">Defense</Badge>
          <Badge variant="outline" className="text-xs bg-amber-50 text-amber-600 border-amber-200">Offense</Badge>
        </CardTitle>
        <CardDescription>Detects problems AND viral moments from reviews</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            {lastScan ? (
              <span>Last scan: {new Date(lastScan).toLocaleTimeString()}</span>
            ) : (
              <span>No scans run yet</span>
            )}
          </div>
          <Button 
            onClick={runScan} 
            disabled={scanning}
            className="bg-purple-600 hover:bg-purple-700"
          >
            {scanning ? (
              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Scanning...</>
            ) : (
              <><RefreshCw className="h-4 w-4 mr-2" /> Run Watchdog Scan</>
            )}
          </Button>
        </div>

        {/* Detected Concerns (Defense) */}
        {concerns.length > 0 && (
          <div className="mt-4 space-y-2">
            <h4 className="text-sm font-medium text-red-700 flex items-center gap-1">
              🛡️ Defense: Concerns Detected
            </h4>
            {concerns.map((c, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-red-50 rounded border border-red-200">
                <span className="text-sm text-red-800">{c.keyword}: <strong>{c.count}</strong> mentions</span>
                {c.threshold_met && <Badge className="bg-red-500">Fix Drafted</Badge>}
              </div>
            ))}
          </div>
        )}

        {/* Detected Wins (Offense) */}
        {wins.length > 0 && (
          <div className="mt-4 space-y-2">
            <h4 className="text-sm font-medium text-amber-700 flex items-center gap-1">
              ✨ Offense: Viral Moments Detected
            </h4>
            {wins.map((w, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gradient-to-r from-amber-50 to-pink-50 rounded border border-amber-200">
                <span className="text-sm text-amber-800">
                  {w.keywords?.slice(0, 3).join(', ')}: <strong>{w.count}</strong> mentions
                  {w.high_value_quotes > 0 && <span className="text-pink-600 ml-1">({w.high_value_quotes} high-value)</span>}
                </span>
                {w.threshold_met && <Badge className="bg-gradient-to-r from-amber-400 to-pink-400">Content Drafted</Badge>}
              </div>
            ))}
          </div>
        )}

        {/* No results message */}
        {concerns.length === 0 && wins.length === 0 && lastScan && (
          <div className="mt-4 text-center text-sm text-gray-500">
            No patterns detected in recent reviews. Add more test reviews to see the watchdog in action!
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// AI Tools Reference Panel
const AIToolsPanel = ({ token }) => {
  const [tools, setTools] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showTools, setShowTools] = useState(false);

  const fetchTools = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/admin/ai/tools`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTools(res.data);
    } catch (err) {
      toast.error('Failed to load tools');
    }
    setLoading(false);
  };

  useEffect(() => {
    if (showTools && !tools) fetchTools();
  }, [showTools]);

  return (
    <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-cyan-50">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-blue-800 text-lg">
            <Zap className="h-5 w-5 text-blue-500" />
            AI Tool Definitions
          </span>
          <Button variant="ghost" size="sm" onClick={() => setShowTools(!showTools)}>
            {showTools ? 'Hide' : 'Show'} Tools
          </Button>
        </CardTitle>
        <CardDescription>The "Hands" of your AI - what it can do</CardDescription>
      </CardHeader>
      {showTools && (
        <CardContent>
          {loading ? (
            <div className="text-center py-4"><Loader2 className="h-6 w-6 animate-spin mx-auto" /></div>
          ) : tools ? (
            <div className="space-y-4">
              {['L1', 'L2', 'L3'].map(level => (
                <div key={level}>
                  <h4 className={`text-xs font-bold uppercase mb-2 ${
                    level === 'L1' ? 'text-green-600' : level === 'L2' ? 'text-amber-600' : 'text-red-600'
                  }`}>
                    {level}: {level === 'L1' ? 'Auto-Execute' : level === 'L2' ? 'Needs Approval' : 'Admin Only'}
                  </h4>
                  <div className="space-y-1">
                    {tools.by_level[level]?.map(tool => (
                      <div key={tool.name} className="p-2 bg-white/60 rounded border border-blue-100 text-xs">
                        <span className="font-medium">{tool.name}</span>
                        <span className="text-gray-500 ml-2">- {tool.description}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </CardContent>
      )}
    </Card>
  );
};

// Product Improvement Report Panel
const ImprovementReportPanel = ({ token }) => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchReport = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/admin/ai/improvement-report`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setReport(res.data);
      toast.success('Report generated!');
    } catch (err) {
      toast.error('Failed to generate report');
    }
    setLoading(false);
  };

  return (
    <Card className="border-green-200 bg-gradient-to-br from-green-50 to-emerald-50">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-green-800 text-lg">
            <FileText className="h-5 w-5 text-green-500" />
            Product Improvement Report
          </span>
          <Button 
            onClick={fetchReport} 
            disabled={loading}
            size="sm"
            className="bg-green-600 hover:bg-green-700"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Generate Report'}
          </Button>
        </CardTitle>
        <CardDescription>AI-aggregated feedback for Batch #2 formula adjustments</CardDescription>
      </CardHeader>
      {report && (
        <CardContent>
          <div className="space-y-4">
            {/* Summary Stats */}
            <div className="grid grid-cols-3 gap-2">
              <div className="p-3 bg-white/60 rounded-lg text-center">
                <div className="text-2xl font-bold text-green-600">{report.summary.total_snippets_approved}</div>
                <div className="text-xs text-gray-500">Tips Approved</div>
              </div>
              <div className="p-3 bg-white/60 rounded-lg text-center">
                <div className="text-2xl font-bold text-blue-600">{report.summary.total_insights_logged}</div>
                <div className="text-xs text-gray-500">Insights Logged</div>
              </div>
              <div className="p-3 bg-white/60 rounded-lg text-center">
                <div className="text-2xl font-bold text-purple-600">{report.summary.products_with_feedback}</div>
                <div className="text-xs text-gray-500">Products</div>
              </div>
            </div>

            {/* Products with Feedback */}
            {Object.keys(report.by_product).length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-green-800 mb-2">Products with Customer Feedback:</h4>
                {Object.entries(report.by_product).map(([pid, data]) => (
                  <div key={pid} className="p-2 bg-white/60 rounded border border-green-200 mb-2">
                    <div className="font-medium text-sm">{pid}</div>
                    <div className="text-xs text-gray-500">{data.tips_added} tips added</div>
                    {data.concerns.length > 0 && (
                      <div className="text-xs text-amber-600 mt-1">
                        Triggers: {data.concerns.join(', ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Note */}
            <div className="p-3 bg-green-100 rounded-lg text-xs text-green-800">
              <strong>💡 Viki Note:</strong> {report.note}
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
};

// L3 Alerts Panel - Critical Issues Requiring Founder Attention
const L3AlertsPanel = ({ token }) => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({ urgent: 0, critical: 0 });

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/admin/ai/alerts`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAlerts(res.data.alerts || []);
      setStats({
        urgent: res.data.pending_urgent || 0,
        critical: res.data.pending_critical || 0
      });
    } catch (err) {
      console.error('Failed to fetch alerts:', err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  const acknowledgeAlert = async (alertId) => {
    try {
      await axios.post(`${API}/api/admin/ai/alerts/${alertId}/acknowledge`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Alert acknowledged');
      fetchAlerts();
    } catch (err) {
      toast.error('Failed to acknowledge alert');
    }
  };

  const pendingAlerts = alerts.filter(a => a.status === 'pending');

  return (
    <Card className={`border-2 ${stats.critical > 0 ? 'border-red-400 bg-red-50' : stats.urgent > 0 ? 'border-amber-400 bg-amber-50' : 'border-gray-200 bg-gray-50'}`}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between">
          <span className={`flex items-center gap-2 text-lg ${stats.critical > 0 ? 'text-red-800' : stats.urgent > 0 ? 'text-amber-800' : 'text-gray-800'}`}>
            <Bell className={`h-5 w-5 ${stats.critical > 0 ? 'text-red-500 animate-pulse' : stats.urgent > 0 ? 'text-amber-500' : 'text-gray-500'}`} />
            L3 Escalator Alerts
            {(stats.urgent > 0 || stats.critical > 0) && (
              <Badge className={stats.critical > 0 ? 'bg-red-500' : 'bg-amber-500'}>
                {stats.critical > 0 ? `${stats.critical} CRITICAL` : `${stats.urgent} URGENT`}
              </Badge>
            )}
          </span>
          <Button variant="ghost" size="sm" onClick={fetchAlerts} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </CardTitle>
        <CardDescription>High-priority issues that require your immediate attention</CardDescription>
      </CardHeader>
      <CardContent>
        {pendingAlerts.length === 0 ? (
          <div className="text-center py-6 text-gray-500">
            <Shield className="h-10 w-10 mx-auto mb-2 text-green-400" />
            <p className="text-sm">All clear! No critical alerts pending.</p>
          </div>
        ) : (
          <div className="space-y-3 max-h-[300px] overflow-y-auto">
            {pendingAlerts.map(alert => (
              <div 
                key={alert.id} 
                className={`p-3 rounded-lg border-2 ${
                  alert.priority === 'CRITICAL' 
                    ? 'border-red-400 bg-red-100' 
                    : 'border-amber-400 bg-amber-100'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <Badge className={alert.priority === 'CRITICAL' ? 'bg-red-600' : 'bg-amber-600'}>
                    {alert.priority}
                  </Badge>
                  <span className="text-xs text-gray-500">
                    {new Date(alert.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="text-sm font-medium text-gray-800 mb-1">{alert.message}</p>
                {alert.suggested_action && (
                  <p className="text-xs text-gray-600 mb-2">
                    <strong>Suggested:</strong> {alert.suggested_action}
                  </p>
                )}
                <Button 
                  size="sm" 
                  variant="outline"
                  className="w-full"
                  onClick={() => acknowledgeAlert(alert.id)}
                >
                  <CheckCircle className="h-4 w-4 mr-1" /> Acknowledge & Dismiss
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Main Component
const PendingAIActions = ({ token }) => {
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [activeTab, setActiveTab] = useState('pending');
  const [previewAction, setPreviewAction] = useState(null);

  const fetchActions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/admin/ai/pending-actions`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { status: activeTab === 'all' ? undefined : activeTab }
      });
      setActions(res.data.actions || []);
    } catch (err) {
      console.error('Failed to fetch actions:', err);
    }
    setLoading(false);
  }, [token, activeTab]);

  useEffect(() => {
    fetchActions();
  }, [fetchActions]);

  const handleApprove = async (actionId) => {
    setActionLoading(actionId);
    try {
      await axios.post(`${API}/api/admin/ai/pending-actions/${actionId}/approve`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Action approved and executed!');
      fetchActions();
    } catch (err) {
      toast.error('Failed to approve: ' + (err.response?.data?.detail || err.message));
    }
    setActionLoading(null);
  };

  const handleReject = async (actionId) => {
    setActionLoading(actionId);
    try {
      await axios.post(`${API}/api/admin/ai/pending-actions/${actionId}/reject`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Action rejected');
      fetchActions();
    } catch (err) {
      toast.error('Failed to reject: ' + (err.response?.data?.detail || err.message));
    }
    setActionLoading(null);
  };

  const pendingCount = actions.filter(a => a.status === 'pending').length;

  return (
    <div className="space-y-6">
      {/* L3 Alerts Banner - Always visible at top if there are critical alerts */}
      <L3AlertsPanel token={token} />

      {/* Two-Column Layout: Simulate + Watchdog */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SimulateReviewPanel token={token} onReviewAdded={fetchActions} />
        <WatchdogStatus token={token} onScanComplete={fetchActions} />
      </div>

      {/* Two-Column Layout: Tools + Improvement Report */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AIToolsPanel token={token} />
        <ImprovementReportPanel token={token} />
      </div>

      {/* Actions Queue */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-amber-500" />
                AI Actions Queue
                {pendingCount > 0 && (
                  <Badge className="bg-amber-500 ml-2">{pendingCount} Pending</Badge>
                )}
              </CardTitle>
              <CardDescription>Review and approve AI-drafted actions before they go live</CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={fetchActions} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="pending" className="relative">
                Pending
                {pendingCount > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-amber-500 text-white text-xs rounded-full flex items-center justify-center">
                    {pendingCount}
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="approved">Approved</TabsTrigger>
              <TabsTrigger value="rejected">Rejected</TabsTrigger>
              <TabsTrigger value="all">All</TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab} className="mt-0">
              {loading ? (
                <div className="text-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto text-purple-500" />
                  <p className="text-sm text-gray-500 mt-2">Loading actions...</p>
                </div>
              ) : actions.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <Bot className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                  <p className="text-lg font-medium">No {activeTab !== 'all' ? activeTab : ''} actions</p>
                  <p className="text-sm">Run the Review Watchdog to detect patterns and generate drafts.</p>
                </div>
              ) : (
                <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2">
                  {actions.map(action => (
                    <ActionCard 
                      key={action.id} 
                      action={action}
                      onApprove={handleApprove}
                      onReject={handleReject}
                      onPreview={setPreviewAction}
                      loading={actionLoading}
                    />
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Full Content Preview Modal */}
      {previewAction && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setPreviewAction(null)}>
          <div className="bg-white rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">{previewAction.title}</h3>
              <Button variant="ghost" size="sm" onClick={() => setPreviewAction(null)}>
                <XCircle className="h-5 w-5" />
              </Button>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 whitespace-pre-wrap text-sm">
              {previewAction.draft_content}
            </div>
            {previewAction.status === 'pending' && previewAction.authority_level === 'L2' && (
              <div className="flex gap-3 mt-4">
                <Button className="flex-1 bg-green-600" onClick={() => { handleApprove(previewAction.id); setPreviewAction(null); }}>
                  <CheckCircle className="h-4 w-4 mr-2" /> Approve & Execute
                </Button>
                <Button variant="outline" className="flex-1 border-red-300 text-red-600" onClick={() => { handleReject(previewAction.id); setPreviewAction(null); }}>
                  <XCircle className="h-4 w-4 mr-2" /> Reject
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PendingAIActions;
