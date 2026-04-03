import React, { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { 
  Share2, 
  X, 
  Copy, 
  Check, 
  Download,
  MessageCircle,
  Facebook,
  Twitter,
  Linkedin,
  Mail,
  Send
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const ShareCard = ({ 
  url = typeof window !== 'undefined' ? window.location.origin : '',
  title = "ReRoots Beauty Enhancer",
  description = "Discover premium Korean skincare with PDRN technology. Transform your skin naturally.",
  buttonStyle = "floating", // "floating", "inline", "minimal"
  buttonPosition = "bottom-right" // for floating style
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  
  const shareUrl = url || window.location.origin;
  
  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      toast.success("Link copied to clipboard!");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      toast.error("Failed to copy link");
    }
  };
  
  const handleDownloadQR = () => {
    const svg = document.getElementById("share-qr-code");
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
        link.download = "reroots-qr-code.png";
        link.href = canvas.toDataURL("image/png");
        link.click();
        toast.success("QR Code downloaded!");
      };
      
      img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgData)));
    }
  };
  
  const shareLinks = [
    {
      name: "WhatsApp",
      icon: MessageCircle,
      color: "bg-green-500 hover:bg-green-600",
      url: `https://wa.me/?text=${encodeURIComponent(`${title} - ${description}\n${shareUrl}`)}`
    },
    {
      name: "Facebook",
      icon: Facebook,
      color: "bg-blue-600 hover:bg-blue-700",
      url: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`
    },
    {
      name: "Twitter",
      icon: Twitter,
      color: "bg-sky-500 hover:bg-sky-600",
      url: `https://twitter.com/intent/tweet?text=${encodeURIComponent(title)}&url=${encodeURIComponent(shareUrl)}`
    },
    {
      name: "LinkedIn",
      icon: Linkedin,
      color: "bg-blue-700 hover:bg-blue-800",
      url: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`
    },
    {
      name: "Email",
      icon: Mail,
      color: "bg-gray-600 hover:bg-gray-700",
      url: `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(`${description}\n\nVisit: ${shareUrl}`)}`
    },
    {
      name: "Telegram",
      icon: Send,
      color: "bg-sky-600 hover:bg-sky-700",
      url: `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(title)}`
    }
  ];
  
  const handleShare = (shareLink) => {
    window.open(shareLink.url, "_blank", "width=600,height=400");
  };
  
  // Native share if available
  const handleNativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: title,
          text: description,
          url: shareUrl
        });
      } catch (err) {
        if (err.name !== 'AbortError') {
          setIsOpen(true);
        }
      }
    } else {
      setIsOpen(true);
    }
  };
  
  // Floating button position classes
  const positionClasses = {
    "bottom-right": "bottom-6 right-6",
    "bottom-left": "bottom-6 left-6",
    "top-right": "top-24 right-6",
    "top-left": "top-24 left-6"
  };
  
  return (
    <>
      {/* Share Button */}
      {buttonStyle === "floating" && (
        <button
          onClick={handleNativeShare}
          className={`fixed ${positionClasses[buttonPosition]} z-40 bg-gradient-to-r from-[#C9A86C] to-[#D4AF37] text-white p-4 rounded-full shadow-lg hover:shadow-xl transform hover:scale-110 transition-all duration-300`}
          title="Share ReRoots"
        >
          <Share2 className="h-6 w-6" />
        </button>
      )}
      
      {buttonStyle === "inline" && (
        <Button
          onClick={handleNativeShare}
          className="bg-gradient-to-r from-[#C9A86C] to-[#D4AF37] text-white hover:opacity-90 gap-2"
        >
          <Share2 className="h-4 w-4" />
          Share
        </Button>
      )}
      
      {buttonStyle === "minimal" && (
        <button
          onClick={handleNativeShare}
          className="flex items-center gap-2 text-[#C9A86C] hover:text-[#D4AF37] transition-colors"
        >
          <Share2 className="h-5 w-5" />
          <span>Share</span>
        </button>
      )}
      
      {/* Share Modal */}
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-center font-display text-xl">Share ReRoots</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-6 py-4">
            {/* QR Code */}
            <div className="flex flex-col items-center">
              <div className="bg-white p-4 rounded-xl shadow-inner border-2 border-[#C9A86C]/20">
                <QRCodeSVG
                  id="share-qr-code"
                  value={shareUrl}
                  size={180}
                  level="H"
                  includeMargin={true}
                  fgColor="#2D2A2E"
                  bgColor="#FFFFFF"
                  imageSettings={{
                    src: "https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png",
                    x: undefined,
                    y: undefined,
                    height: 35,
                    width: 35,
                    excavate: true,
                  }}
                />
              </div>
              <p className="text-sm text-gray-500 mt-2">Scan to visit ReRoots</p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadQR}
                className="mt-2 gap-2"
              >
                <Download className="h-4 w-4" />
                Download QR Code
              </Button>
            </div>
            
            {/* Copy Link */}
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-gray-100 rounded-lg px-4 py-3 text-sm truncate text-gray-600">
                {shareUrl}
              </div>
              <Button
                onClick={handleCopyLink}
                variant="outline"
                className={`gap-2 ${copied ? 'bg-green-50 border-green-500 text-green-600' : ''}`}
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? "Copied!" : "Copy"}
              </Button>
            </div>
            
            {/* Social Share Buttons */}
            <div>
              <p className="text-sm text-gray-500 mb-3 text-center">Share via</p>
              <div className="grid grid-cols-3 gap-3">
                {shareLinks.map((link) => (
                  <button
                    key={link.name}
                    onClick={() => handleShare(link)}
                    className={`${link.color} text-white rounded-xl p-3 flex flex-col items-center gap-1 transition-all hover:scale-105`}
                  >
                    <link.icon className="h-5 w-5" />
                    <span className="text-xs">{link.name}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ShareCard;
