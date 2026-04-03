import React, { useState, useRef } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { 
  Share2, Copy, Check, Download, MessageCircle, 
  Instagram, Send, Smartphone, Crown, Sparkles,
  Image as ImageIcon, QrCode, Edit3
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";

// Lazy load html2canvas - only loads when user clicks download (~162KB savings)
const loadHtml2Canvas = () => import("html2canvas");

const ViralShareToolkit = ({ 
  referralCode,
  referralLink,
  userName = "Founding Member",
  referralCount = 0,
  isVIP = false,
  currentPrice = 100.00,
  goalPrice = 70.00  // FIXED: $70 Founding Member price
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState("quick");
  const [selectedMessage, setSelectedMessage] = useState(0);
  const [customMessage, setCustomMessage] = useState("");
  const [generatingImage, setGeneratingImage] = useState(false);
  const shareCardRef = useRef(null);
  
  // Pre-written share messages for different platforms - UPDATED PRICING
  const shareMessages = {
    casual: [
      `Okay so I found this Canadian skincare brand that uses the same PDRN tech from Korean clinics 🧬 AND they're doing a founding member deal - 30% off! Use my link to get the same price: ${referralLink}`,
      `Not sponsored but had to share - ReRoots is launching and their Founding Member pricing is amazing. $70 instead of $100! ${referralLink}`,
      `If you're into skincare, you NEED to check this out. Premium PDRN serum for $70. I'm not kidding. ${referralLink}`
    ],
    professional: [
      `I've joined the ReRoots Founding Member program - a Canadian biotech skincare brand launching PDRN technology serums. If you're interested in premium skincare at 30% off retail, here's my referral link: ${referralLink}`,
      `Sharing an opportunity I came across: ReRoots is offering Founding Member pricing on their biotech skincare line. Worth checking out if you're looking for clinical-grade products. ${referralLink}`
    ],
    urgency: [
      `⚠️ Only 1000 spots left for Founding Member pricing at ReRoots! $70 for a $100 serum. Grab yours before it's gone: ${referralLink}`,
      `🚨 Just got in on this - ReRoots PDRN serum for $70 (normally $100). Limited spots! ${referralLink}`
    ],
    story: [
      `So I've been looking for a good PDRN serum (the stuff they use in Korean clinics) and found this Canadian brand called ReRoots. They're doing a pre-launch thing where you get 30% off if you're a Founding Member. I signed up and wanted to share: ${referralLink}`,
      `Quick story: My dermatologist mentioned PDRN for skin regeneration. Found ReRoots - they're launching a serum with it AND doing Founding Member pricing at $70. Too good not to share: ${referralLink}`
    ]
  };
  
  // Platform-specific share handlers
  const shareHandlers = {
    whatsapp: () => {
      const message = customMessage || shareMessages.casual[selectedMessage];
      window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, "_blank");
    },
    sms: () => {
      const message = customMessage || shareMessages.casual[0];
      window.open(`sms:?body=${encodeURIComponent(message)}`, "_blank");
    },
    instagram: () => {
      // Instagram doesn't support direct URL sharing, so we copy the message
      const message = customMessage || shareMessages.casual[0];
      navigator.clipboard.writeText(message);
      toast.success("Message copied! Paste it in your Instagram story or DM", { duration: 4000 });
    },
    tiktok: () => {
      // TikTok - copy message for comments/bio
      const message = `Check out @reroots_skincare 🧬 Founding Member link in my bio! ${referralLink}`;
      navigator.clipboard.writeText(message);
      toast.success("Message copied! Add your link to your TikTok bio", { duration: 4000 });
    },
    facebook: () => {
      window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(referralLink)}&quote=${encodeURIComponent("Join me as a ReRoots Founding Member - 81% off premium PDRN skincare!")}`, "_blank");
    },
    twitter: () => {
      const message = `I just joined @ReRootsSkincare as a Founding Member! 🧬 Get almost 80% off premium PDRN biotech skincare. Limited spots!`;
      window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(message)}&url=${encodeURIComponent(referralLink)}`, "_blank");
    },
    telegram: () => {
      const message = customMessage || shareMessages.casual[0];
      window.open(`https://t.me/share/url?url=${encodeURIComponent(referralLink)}&text=${encodeURIComponent(message)}`, "_blank");
    },
    email: () => {
      const subject = "Join ReRoots - Get 81% OFF Premium PDRN Skincare";
      const body = customMessage || shareMessages.story[0];
      window.open(`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`, "_blank");
    }
  };
  
  const handleCopyLink = () => {
    navigator.clipboard.writeText(referralLink);
    setCopied(true);
    toast.success("Link copied!");
    setTimeout(() => setCopied(false), 2000);
  };
  
  const handleCopyMessage = (message) => {
    navigator.clipboard.writeText(message);
    toast.success("Message copied to clipboard!");
  };
  
  // Generate downloadable share graphic (lazy loads html2canvas)
  const generateShareGraphic = async () => {
    if (!shareCardRef.current) return;
    
    setGeneratingImage(true);
    try {
      // Dynamically import html2canvas only when needed
      const { default: html2canvas } = await loadHtml2Canvas();
      
      const canvas = await html2canvas(shareCardRef.current, {
        scale: 2,
        backgroundColor: null,
        logging: false
      });
      
      const link = document.createElement("a");
      link.download = `reroots-founding-member-${referralCode}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      toast.success("Share graphic downloaded!");
    } catch (err) {
      toast.error("Failed to generate image");
    }
    setGeneratingImage(false);
  };
  
  return (
    <>
      {/* Main Share Button */}
      <Button 
        onClick={() => setIsOpen(true)}
        className="w-full bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] hover:from-[#B8960F] hover:to-[#D4AF37] text-[#0a0a0a] font-bold py-6 rounded-xl"
        data-testid="open-share-toolkit"
      >
        <Share2 className="w-5 h-5 mr-2" />
        Share & Earn Referrals
        <Badge className="ml-2 bg-[#0a0a0a]/20 text-[#0a0a0a]">
          🔥 Viral Toolkit
        </Badge>
      </Button>
      
      {/* Share Toolkit Modal */}
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto bg-[#0a0a0a] border-[#333] text-white">
          <DialogHeader>
            <DialogTitle className="text-center text-2xl font-bold flex items-center justify-center gap-2">
              <Sparkles className="w-6 h-6 text-[#D4AF37]" />
              Viral Share Toolkit
            </DialogTitle>
            <p className="text-center text-white/60 text-sm">
              Share with friends and unlock the $70 Founding Member price
            </p>
          </DialogHeader>
          
          <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-4">
            <TabsList className="grid grid-cols-4 bg-[#1a1a1a] border border-[#333]">
              <TabsTrigger value="quick" className="data-[state=active]:bg-[#D4AF37] data-[state=active]:text-[#0a0a0a]">
                Quick Share
              </TabsTrigger>
              <TabsTrigger value="messages" className="data-[state=active]:bg-[#D4AF37] data-[state=active]:text-[#0a0a0a]">
                Messages
              </TabsTrigger>
              <TabsTrigger value="graphics" className="data-[state=active]:bg-[#D4AF37] data-[state=active]:text-[#0a0a0a]">
                Graphics
              </TabsTrigger>
              <TabsTrigger value="qr" className="data-[state=active]:bg-[#D4AF37] data-[state=active]:text-[#0a0a0a]">
                QR Code
              </TabsTrigger>
            </TabsList>
            
            {/* QUICK SHARE TAB */}
            <TabsContent value="quick" className="mt-4 space-y-4">
              {/* Copy Link */}
              <div className="bg-[#1a1a1a] rounded-xl p-4 border border-[#333]">
                <p className="text-sm text-white/60 mb-2">Your referral link:</p>
                <div className="flex gap-2">
                  <div className="flex-1 bg-[#2a2a2a] rounded-lg px-4 py-3 text-sm truncate text-white/80 font-mono">
                    {referralLink}
                  </div>
                  <Button
                    onClick={handleCopyLink}
                    className={copied ? "bg-green-600" : "bg-[#D4AF37] hover:bg-[#B8960F] text-[#0a0a0a]"}
                  >
                    {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </Button>
                </div>
              </div>
              
              {/* Social Buttons Grid */}
              <div className="grid grid-cols-4 gap-3">
                <button
                  onClick={shareHandlers.whatsapp}
                  className="flex flex-col items-center gap-2 p-4 bg-[#25D366]/10 border border-[#25D366]/30 rounded-xl hover:bg-[#25D366]/20 transition-all"
                  data-testid="share-whatsapp"
                >
                  <MessageCircle className="w-6 h-6 text-[#25D366]" />
                  <span className="text-xs text-white/70">WhatsApp</span>
                </button>
                
                <button
                  onClick={shareHandlers.instagram}
                  className="flex flex-col items-center gap-2 p-4 bg-gradient-to-br from-[#833AB4]/10 via-[#FD1D1D]/10 to-[#F77737]/10 border border-[#E1306C]/30 rounded-xl hover:from-[#833AB4]/20 hover:via-[#FD1D1D]/20 hover:to-[#F77737]/20 transition-all"
                  data-testid="share-instagram"
                >
                  <Instagram className="w-6 h-6 text-[#E1306C]" />
                  <span className="text-xs text-white/70">Instagram</span>
                </button>
                
                <button
                  onClick={shareHandlers.tiktok}
                  className="flex flex-col items-center gap-2 p-4 bg-[#000]/10 border border-white/20 rounded-xl hover:bg-white/10 transition-all"
                  data-testid="share-tiktok"
                >
                  <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-5.2 1.74 2.89 2.89 0 012.31-4.64 2.93 2.93 0 01.88.13V9.4a6.84 6.84 0 00-1-.05A6.33 6.33 0 005 20.1a6.34 6.34 0 0010.86-4.43v-7a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-1-.1z"/>
                  </svg>
                  <span className="text-xs text-white/70">TikTok</span>
                </button>
                
                <button
                  onClick={shareHandlers.sms}
                  className="flex flex-col items-center gap-2 p-4 bg-[#34C759]/10 border border-[#34C759]/30 rounded-xl hover:bg-[#34C759]/20 transition-all"
                  data-testid="share-sms"
                >
                  <Smartphone className="w-6 h-6 text-[#34C759]" />
                  <span className="text-xs text-white/70">SMS</span>
                </button>
                
                <button
                  onClick={shareHandlers.facebook}
                  className="flex flex-col items-center gap-2 p-4 bg-[#1877F2]/10 border border-[#1877F2]/30 rounded-xl hover:bg-[#1877F2]/20 transition-all"
                  data-testid="share-facebook"
                >
                  <svg className="w-6 h-6 text-[#1877F2]" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                  </svg>
                  <span className="text-xs text-white/70">Facebook</span>
                </button>
                
                <button
                  onClick={shareHandlers.twitter}
                  className="flex flex-col items-center gap-2 p-4 bg-[#1DA1F2]/10 border border-[#1DA1F2]/30 rounded-xl hover:bg-[#1DA1F2]/20 transition-all"
                  data-testid="share-twitter"
                >
                  <svg className="w-6 h-6 text-[#1DA1F2]" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                  </svg>
                  <span className="text-xs text-white/70">X (Twitter)</span>
                </button>
                
                <button
                  onClick={shareHandlers.telegram}
                  className="flex flex-col items-center gap-2 p-4 bg-[#0088cc]/10 border border-[#0088cc]/30 rounded-xl hover:bg-[#0088cc]/20 transition-all"
                  data-testid="share-telegram"
                >
                  <Send className="w-6 h-6 text-[#0088cc]" />
                  <span className="text-xs text-white/70">Telegram</span>
                </button>
                
                <button
                  onClick={shareHandlers.email}
                  className="flex flex-col items-center gap-2 p-4 bg-white/5 border border-white/20 rounded-xl hover:bg-white/10 transition-all"
                  data-testid="share-email"
                >
                  <svg className="w-6 h-6 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  <span className="text-xs text-white/70">Email</span>
                </button>
              </div>
              
              {/* Progress indicator */}
              <div className="bg-[#1a1a1a] rounded-xl p-4 border border-[#333]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-white/60">Your Progress</span>
                  <span className="text-sm font-bold text-[#D4AF37]">{referralCount}/10 referrals</span>
                </div>
                <div className="h-2 bg-[#2a2a2a] rounded-full overflow-hidden">
                  <div 
                    className="h-full rounded-full transition-all"
                    style={{ 
                      width: `${Math.min((referralCount / 10) * 100, 100)}%`,
                      background: isVIP ? 'linear-gradient(90deg, #D4AF37, #F4D03F)' : 'linear-gradient(90deg, #F8A5B8, #FFB6C1)'
                    }}
                  />
                </div>
                <p className="text-xs text-white/40 mt-2">
                  {isVIP ? "🏆 You've unlocked the $70 Founding Member price!" : `${10 - referralCount} more to unlock $70 pricing`}
                </p>
              </div>
            </TabsContent>
            
            {/* PRE-WRITTEN MESSAGES TAB */}
            <TabsContent value="messages" className="mt-4 space-y-4">
              <p className="text-sm text-white/60">Choose a message style and customize if needed:</p>
              
              {/* Message Categories */}
              {Object.entries(shareMessages).map(([category, messages]) => (
                <div key={category} className="space-y-2">
                  <h4 className="text-sm font-semibold text-[#D4AF37] capitalize flex items-center gap-2">
                    {category === "casual" && "😊 Casual & Friendly"}
                    {category === "professional" && "💼 Professional"}
                    {category === "urgency" && "⚡ Urgency"}
                    {category === "story" && "📖 Story-based"}
                  </h4>
                  {messages.map((message, idx) => (
                    <div 
                      key={idx}
                      className="bg-[#1a1a1a] border border-[#333] rounded-lg p-3 hover:border-[#D4AF37]/50 transition-all cursor-pointer group"
                      onClick={() => handleCopyMessage(message)}
                    >
                      <p className="text-sm text-white/80 line-clamp-3">{message}</p>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-xs text-white/40">{message.length} characters</span>
                        <Button size="sm" variant="ghost" className="text-[#D4AF37] opacity-0 group-hover:opacity-100 transition-opacity">
                          <Copy className="w-3 h-3 mr-1" /> Copy
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
              
              {/* Custom Message Editor */}
              <div className="bg-[#1a1a1a] border border-[#333] rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Edit3 className="w-4 h-4 text-[#D4AF37]" />
                  <h4 className="text-sm font-semibold text-white">Write Your Own</h4>
                </div>
                <Textarea
                  value={customMessage}
                  onChange={(e) => setCustomMessage(e.target.value)}
                  placeholder="Write your custom message here..."
                  className="bg-[#2a2a2a] border-[#444] text-white min-h-[100px]"
                />
                <div className="flex justify-between items-center mt-2">
                  <span className="text-xs text-white/40">{customMessage.length} characters</span>
                  <Button 
                    size="sm" 
                    onClick={() => handleCopyMessage(customMessage)}
                    disabled={!customMessage}
                    className="bg-[#D4AF37] text-[#0a0a0a]"
                  >
                    <Copy className="w-3 h-3 mr-1" /> Copy Message
                  </Button>
                </div>
              </div>
            </TabsContent>
            
            {/* SHARE GRAPHICS TAB */}
            <TabsContent value="graphics" className="mt-4 space-y-4">
              <p className="text-sm text-white/60">Download and share this graphic on social media:</p>
              
              {/* Shareable Card Preview */}
              <div className="flex justify-center">
                <div 
                  ref={shareCardRef}
                  className="w-[340px] rounded-2xl overflow-hidden"
                  style={{
                    background: "linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%)"
                  }}
                >
                  {/* Card Header */}
                  <div 
                    className="p-6 text-center"
                    style={{
                      background: "linear-gradient(135deg, rgba(212, 175, 55, 0.2) 0%, rgba(212, 175, 55, 0.05) 100%)"
                    }}
                  >
                    <div className="flex justify-center mb-3">
                      <div 
                        className="w-16 h-16 rounded-full flex items-center justify-center"
                        style={{
                          background: "linear-gradient(135deg, #D4AF37 0%, #F4D03F 100%)"
                        }}
                      >
                        {isVIP ? (
                          <Crown className="w-8 h-8 text-[#0a0a0a]" />
                        ) : (
                          <Sparkles className="w-8 h-8 text-[#0a0a0a]" />
                        )}
                      </div>
                    </div>
                    <h3 className="text-lg font-bold text-white mb-1">
                      {isVIP ? "VIP Founding Member" : "Founding Member"}
                    </h3>
                    <p className="text-sm text-[#D4AF37]">{userName}</p>
                  </div>
                  
                  {/* Card Body */}
                  <div className="p-6 text-center">
                    <p className="text-white/60 text-sm mb-4">
                      Join me and get premium PDRN skincare at
                    </p>
                    <div className="mb-4">
                      <span className="text-white/40 line-through text-lg">$100</span>
                      <span className="text-4xl font-bold text-[#D4AF37] mx-3">
                        ${isVIP ? goalPrice.toFixed(2) : currentPrice.toFixed(2)}
                      </span>
                    </div>
                    <Badge 
                      className="mb-4"
                      style={{
                        background: "linear-gradient(135deg, #D4AF37 0%, #F4D03F 100%)",
                        color: "#0a0a0a"
                      }}
                    >
                      {isVIP ? "81% OFF" : "62% OFF"} • Limited Spots
                    </Badge>
                    
                    {/* Referral Code */}
                    <div 
                      className="mt-4 p-3 rounded-lg"
                      style={{ background: "rgba(212, 175, 55, 0.1)" }}
                    >
                      <p className="text-xs text-white/50 mb-1">Use my referral code:</p>
                      <p className="text-lg font-mono font-bold text-[#D4AF37]">{referralCode}</p>
                    </div>
                    
                    {/* Brand */}
                    <p className="mt-4 text-xs text-white/30">
                      ReRoots • Canadian Biotech Skincare
                    </p>
                  </div>
                </div>
              </div>
              
              {/* Download Button */}
              <Button 
                onClick={generateShareGraphic}
                disabled={generatingImage}
                className="w-full bg-[#D4AF37] hover:bg-[#B8960F] text-[#0a0a0a] py-6"
              >
                {generatingImage ? (
                  <span className="animate-spin mr-2">⏳</span>
                ) : (
                  <Download className="w-5 h-5 mr-2" />
                )}
                Download Share Graphic
              </Button>
              
              <p className="text-xs text-white/40 text-center">
                💡 Perfect for Instagram Stories, WhatsApp Status, or Facebook posts
              </p>
            </TabsContent>
            
            {/* QR CODE TAB */}
            <TabsContent value="qr" className="mt-4 space-y-4">
              <p className="text-sm text-white/60 text-center">Scan to join as a Founding Member:</p>
              
              <div className="flex justify-center">
                <div className="bg-white p-6 rounded-2xl">
                  <QRCodeSVG
                    id="referral-qr-code"
                    value={referralLink}
                    size={200}
                    level="H"
                    includeMargin={true}
                    fgColor="#0a0a0a"
                    bgColor="#FFFFFF"
                  />
                </div>
              </div>
              
              <div className="text-center">
                <p className="text-sm text-white/60 mb-2">Your referral link:</p>
                <p className="text-xs font-mono text-[#D4AF37] break-all">{referralLink}</p>
              </div>
              
              <Button 
                onClick={() => {
                  const svg = document.getElementById("referral-qr-code");
                  if (svg) {
                    const svgData = new XMLSerializer().serializeToString(svg);
                    const canvas = document.createElement("canvas");
                    const ctx = canvas.getContext("2d");
                    const img = new Image();
                    img.onload = () => {
                      canvas.width = img.width;
                      canvas.height = img.height;
                      ctx.fillStyle = "white";
                      ctx.fillRect(0, 0, canvas.width, canvas.height);
                      ctx.drawImage(img, 0, 0);
                      const link = document.createElement("a");
                      link.download = `reroots-qr-${referralCode}.png`;
                      link.href = canvas.toDataURL("image/png");
                      link.click();
                      toast.success("QR Code downloaded!");
                    };
                    img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgData)));
                  }
                }}
                className="w-full bg-[#D4AF37] hover:bg-[#B8960F] text-[#0a0a0a]"
              >
                <Download className="w-4 h-4 mr-2" />
                Download QR Code
              </Button>
              
              <p className="text-xs text-white/40 text-center">
                💡 Print this QR code for in-person sharing at events or meetups
              </p>
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ViralShareToolkit;
