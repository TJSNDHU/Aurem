import React, { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Gift, X, Copy, Check, Heart, Smartphone, Send, Loader2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useBrand } from '../contexts/BrandContext';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const ReferralWidget = () => {
  const location = useLocation();
  const { brand } = useBrand();
  const brandName = brand?.name || 'ReRoots';
  const isLaVela = brand?.id === 'lavela';
  const brandPrimaryColor = isLaVela ? '#0D4D4D' : '#F8A5B8'; // Teal for La Vela, Pink for ReRoots
  
  const [isOpen, setIsOpen] = useState(false);
  const [showWidget, setShowWidget] = useState(false); // TBT Optimization: Delay widget appearance
  const [settings, setSettings] = useState(null);
  const [referralCode, setReferralCode] = useState(null);
  const [emails, setEmails] = useState("");
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState(false);
  
  const token = localStorage.getItem("reroots_token");
  const user = token ? JSON.parse(atob(token.split('.')[1])) : null;

  // Hide on checkout, cart, bio-scan, OROÉ, LA VELA pages, auth pages, admin pages, and QR landing pages
  const hiddenPaths = ['/checkout', '/cart', '/mission-control', '/Bio-Age-Repair-Scan', '/quiz', '/skin-scan', '/oroe', '/ritual', '/la-vela-bianca', '/lavela', '/login', '/register', '/auth', '/forgot-password', '/protocol', '/welcome', '/skincare-dictionary', '/library', '/ingredients', '/qr-generator', '/qr', '/qrcode', '/admin', '/reroots-admin', '/new-admin', '/app'];
  const shouldHide = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));

  // TBT OPTIMIZATION: Delay widget appearance by 5 seconds
  // This prevents the widget from stealing main thread during initial page load
  useEffect(() => {
    const timer = setTimeout(() => {
      setShowWidget(true);
    }, 5000); // 5 second delay after page load
    
    // Also show immediately on user interaction (scroll/click)
    const showOnInteraction = () => {
      setShowWidget(true);
      window.removeEventListener('scroll', showOnInteraction);
      window.removeEventListener('click', showOnInteraction);
    };
    
    window.addEventListener('scroll', showOnInteraction, { passive: true, once: true });
    window.addEventListener('click', showOnInteraction, { once: true });
    
    return () => {
      clearTimeout(timer);
      window.removeEventListener('scroll', showOnInteraction);
      window.removeEventListener('click', showOnInteraction);
    };
  }, []);

  useEffect(() => {
    axios.get(`${API}/referral-program`)
      .then(res => setSettings(res.data))
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (user && isOpen && !referralCode) {
      axios.post(`${API}/referral/create`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
        .then(res => setReferralCode(res.data.referral_code))
        .catch(console.error);
    }
  }, [user, isOpen, referralCode, token]);

  // Hide on checkout/cart pages or if widget not enabled, or if widget shouldn't show yet
  if (!settings?.enabled || !settings?.widget?.enabled || shouldHide || !showWidget) return null;

  const widget = settings.widget;
  const referralLink = referralCode ? `${window.location.origin}/ref/${referralCode}` : "";

  const copyLink = () => {
    navigator.clipboard.writeText(referralLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success("Link copied!");
  };

  const sendInvites = async () => {
    if (!emails.trim()) return;
    setSending(true);
    try {
      const emailList = emails.split(/[,\n]/).map(e => e.trim()).filter(e => e);
      await axios.post(`${API}/referral/invite`, { emails: emailList }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Invitations sent!");
      setEmails("");
    } catch (error) {
      toast.error("Failed to send invitations");
    }
    setSending(false);
  };

  const shareWhatsApp = () => {
    const text = encodeURIComponent(`${widget.share_message} ${referralLink}`);
    window.open(`https://wa.me/?text=${text}`, '_blank');
  };

  return (
    <>
      {/* Floating Button */}
      <button
        className="fixed z-50 shadow-2xl rounded-full p-4 text-white font-semibold flex items-center gap-2 hover:scale-105 active:scale-95 transition-transform"
        style={{ 
          backgroundColor: brandPrimaryColor,
          [widget.position.includes('right') ? 'right' : 'left']: '20px',
          [widget.position.includes('bottom') ? 'bottom' : 'top']: '100px'
        }}
        onClick={() => setIsOpen(true)}
        data-testid="referral-widget-btn"
      >
        <Gift className="h-5 w-5" />
        <span className="hidden sm:inline">{`Get ${brandName} FREE`}</span>
      </button>

      {/* Popup Modal */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setIsOpen(false)}>
          <div 
            className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-in zoom-in-95 duration-200"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div 
              className="p-6 text-white text-center relative"
              style={{ background: isLaVela ? 'linear-gradient(to right, #0D4D4D, #D4A574)' : 'linear-gradient(to right, #F8A5B8, #D4AF37)' }}
            >
              <button 
                onClick={() => setIsOpen(false)}
                className="absolute top-4 right-4 text-white/80 hover:text-white"
                data-testid="referral-widget-close"
              >
                <X className="h-5 w-5" />
              </button>
              <h2 className="font-display text-2xl font-bold">{widget.popup_title}</h2>
              <p className="opacity-90">{widget.popup_subtitle}</p>
            </div>

            <div className="p-6 space-y-6">
              {!user ? (
                <div className="text-center py-4">
                  <p className="text-[#5A5A5A] mb-4">Sign in to start referring friends and earning rewards!</p>
                  <Link to="/login">
                    <Button className="btn-primary">Sign In to Refer</Button>
                  </Link>
                </div>
              ) : (
                <>
                  {/* Rewards Info */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-[#FAF8F5] rounded-xl p-4 text-center">
                      <Gift className="h-8 w-8 text-[#D4AF37] mx-auto mb-2" />
                      <p className="text-sm text-[#5A5A5A]">You Get</p>
                      <p className="font-bold text-[#2D2A2E]">{settings.rewards.referrer}</p>
                    </div>
                    <div className="bg-[#FAF8F5] rounded-xl p-4 text-center">
                      <Heart className="h-8 w-8 text-[#F8A5B8] mx-auto mb-2" />
                      <p className="text-sm text-[#5A5A5A]">They Get</p>
                      <p className="font-bold text-[#2D2A2E]">{settings.rewards.referee}</p>
                    </div>
                  </div>

                  {/* Your Link */}
                  <div>
                    <Label className="text-sm font-semibold text-[#2D2A2E]">Your Referral Link</Label>
                    <div className="flex gap-2 mt-1">
                      <Input 
                        value={referralLink} 
                        readOnly 
                        className="bg-[#FAF8F5] text-sm"
                      />
                      <Button 
                        variant="outline" 
                        onClick={copyLink}
                        className={copied ? "bg-green-50 text-green-600 border-green-200" : ""}
                      >
                        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>

                  {/* Share Options */}
                  <div className="flex gap-3">
                    <Button 
                      className="flex-1 bg-green-500 hover:bg-green-600 text-white"
                      onClick={shareWhatsApp}
                    >
                      <Smartphone className="h-4 w-4 mr-2" />
                      WhatsApp
                    </Button>
                    <Button 
                      variant="outline" 
                      className="flex-1"
                      onClick={copyLink}
                    >
                      <Copy className="h-4 w-4 mr-2" />
                      Copy Link
                    </Button>
                  </div>

                  {/* Email Invites */}
                  <div>
                    <Label className="text-sm font-semibold text-[#2D2A2E]">Invite by Email</Label>
                    <Textarea
                      value={emails}
                      onChange={(e) => setEmails(e.target.value)}
                      placeholder="Enter emails separated by comma or new line"
                      rows={2}
                      className="mt-1"
                    />
                    <Button 
                      className="w-full mt-2 btn-primary"
                      onClick={sendInvites}
                      disabled={sending || !emails.trim()}
                    >
                      {sending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                      Send Invitations
                    </Button>
                  </div>

                  {/* Milestones */}
                  {settings.rewards.milestones?.length > 0 && (
                    <div className="bg-[#FAF8F5] rounded-xl p-4">
                      <h4 className="font-semibold text-[#2D2A2E] mb-3 flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-[#D4AF37]" />
                        Milestone Rewards
                      </h4>
                      <div className="space-y-2">
                        {settings.rewards.milestones.map((m, i) => (
                          <div key={i} className="flex justify-between items-center text-sm">
                            <span className="text-[#5A5A5A]">{m.referrals} Referrals</span>
                            <span className="font-semibold text-[#D4AF37]">{m.reward}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ReferralWidget;
