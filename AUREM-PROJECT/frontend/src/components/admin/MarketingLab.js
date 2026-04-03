import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  Upload, Sparkles, Image as ImageIcon, Download, Loader2, 
  Wand2, RefreshCw, Instagram, Megaphone, Square, RectangleVertical,
  Check, X, Package, Palette, Zap, FlaskConical, Leaf, Crown, Copy, FileText,
  Users, Target, TrendingUp, Eye, MessageCircle, Send, Phone, Rocket
} from "lucide-react";
import { useAdminBrand } from "./useAdminBrand";

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Dynamic brand presets
const getBrandPreset = (isLaVela, brandName) => isLaVela ? {
  brandName: "La Vela Bianca Teen Skincare",
  brandTone: "Youthful luxury meets clean beauty science",
  colorPalette: {
    primary: "#0D4D4D",      // Deep teal
    secondary: "#FDF8F5",    // Warm white
    accent: "#D4A574",       // Golden sand
    neutral: "#1A6B6B"       // Lighter teal
  },
  visualStyle: "Fresh, clean aesthetic with coastal luxury vibes. Light and airy compositions emphasizing purity and youthful energy. Gen-Z friendly with premium edge.",
  lighting: "Bright natural lighting with golden hour warmth. Clean whites with subtle teal shadows for depth.",
  productPlacement: "Product as hero with fresh, minimal styling. Ocean/beach-inspired props if any.",
  typography: "Modern clean fonts, minimal text. Let the product speak."
} : {
  brandName: `${brandName} Biotech Skincare`,
  brandTone: "Clinical luxury meets nature-inspired science",
  colorPalette: {
    primary: "#F8A5B8",      // Soft pink
    secondary: "#2D2A2E",    // Deep charcoal
    accent: "#E88DA0",       // Rose
    neutral: "#FDF9F9"       // Warm white
  },
  visualStyle: "Photorealistic product photography with cinematic lighting, emphasizing scientific precision and botanical elegance. Clean compositions with negative space. Premium skincare editorial aesthetic.",
  lighting: "Soft diffused studio lighting with subtle rim light to emphasize product contours. Warm undertones for organic feel, cool accents for clinical credibility.",
  productPlacement: "Product as hero, 60-70% frame presence, slight angle to show label and form. Contextual props should enhance, not distract.",
  typography: "Clean sans-serif, minimal text overlays. Let the product speak."
};

// Dynamic vibe options based on brand
const getVibeOptions = (isLaVela) => isLaVela ? [
  { 
    id: "coastal", 
    label: "Coastal", 
    icon: Leaf,
    description: "Ocean-inspired, fresh, blue/teal tones",
    prompt: `La Vela Bianca coastal aesthetic: pristine white sand beaches, soft teal (#0D4D4D) ocean tones, golden sand accents (#D4A574), morning light on Mediterranean waters. Fresh, clean, youthful luxury. Product positioned with natural textures.`
  },
  { 
    id: "fresh-clean", 
    label: "Fresh & Clean", 
    icon: FlaskConical,
    description: "Pure, minimal, white/gold tones",
    prompt: `La Vela Bianca clean beauty aesthetic: pure white backgrounds with warm gold (#D4A574) accents, natural light streaming in, minimalist elegance. Teen-friendly luxury skincare. Simple, sophisticated compositions.`
  },
  { 
    id: "golden-hour", 
    label: "Golden Hour", 
    icon: Crown,
    description: "Warm sunset, luxury, gold tones",
    prompt: `La Vela Bianca golden hour luxury: warm sunset lighting with deep teal (#0D4D4D) shadows, golden sand (#D4A574) highlights, Mediterranean villa aesthetic. Aspirational teen luxury skincare. Product bathed in warm light.`
  }
] : [
  { 
    id: "clinical", 
    label: "Clinical", 
    icon: FlaskConical,
    description: "Lab-inspired, scientific, white/blue tones",
    prompt: `ReRoots clinical laboratory aesthetic: pristine white surfaces with soft pink (#F8A5B8) accent lighting, DNA helix shadows, medical-grade precision, sterile elegance with warm undertones. Scientific credibility meets skincare luxury.`
  },
  { 
    id: "nature-tech", 
    label: "Nature-Tech", 
    icon: Leaf,
    description: "Biotech meets nature, green accents",
    prompt: `ReRoots biotech-nature fusion: organic botanical textures meeting high-tech elements, soft green accents with rose gold (#E88DA0) highlights, sustainable luxury aesthetic.`
  },
  { 
    id: "luxury", 
    label: "Luxury Spa", 
    icon: Crown,
    description: "Premium, gold/marble, soft lighting",
    prompt: `ReRoots luxury spa atmosphere: Carrara marble surfaces, soft golden hour lighting with pink (#F8A5B8) undertones, premium velvet textures, rose gold accents.`
  }
];

const MarketingLab = () => {
  // Brand context
  const { isLaVela, name: brandName, colors } = useAdminBrand();
  const BRAND_PRESET = getBrandPreset(isLaVela, brandName);
  const vibeOptions = getVibeOptions(isLaVela);
  
  // Dynamic colors based on brand
  const C = {
    primary: isLaVela ? '#0D4D4D' : '#F8A5B8',
    primaryHover: isLaVela ? '#1A6B6B' : '#E88DA0',
    bg: isLaVela ? '#0D4D4D' : '#FDF9F9',
    text: isLaVela ? '#FDF8F5' : '#2D2A2E',
    textDim: isLaVela ? '#D4A574' : '#5A5A5A',
    accent: isLaVela ? '#D4A574' : '#F8A5B8',
  };
  
  // Product selection
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [loadingProducts, setLoadingProducts] = useState(true);
  
  // Target Audience (Bio-Scan Leads)
  const [audienceData, setAudienceData] = useState({
    total: 0,
    concerns: {},
    highIntent: 0,
    recentLeads: []
  });
  const [loadingAudience, setLoadingAudience] = useState(true);
  
  // WhatsApp Marketing Integration
  const [whatsappContacts, setWhatsappContacts] = useState([]);
  const [loadingWhatsapp, setLoadingWhatsapp] = useState(false);
  const [scanInsights, setScanInsights] = useState(null);
  const [socialPosts, setSocialPosts] = useState([]);
  const [broadcastMessage, setBroadcastMessage] = useState("");
  const [sendingBroadcast, setSendingBroadcast] = useState(false);
  const [sendingLaunchInvites, setSendingLaunchInvites] = useState(false);
  const [selectedContacts, setSelectedContacts] = useState([]);
  const [broadcastChannel, setBroadcastChannel] = useState("whatsapp"); // 'whatsapp' or 'sms'
  const [sourceFilter, setSourceFilter] = useState("all"); // Filter by source
  
  // Custom inputs
  const [productName, setProductName] = useState("");
  const [tagline, setTagline] = useState("");
  const [uploadedImage, setUploadedImage] = useState(null);
  const [imageBase64, setImageBase64] = useState("");
  
  // Vibe/Style selection - default based on brand
  const [selectedVibe, setSelectedVibe] = useState(isLaVela ? "coastal" : "clinical");
  
  // Asset type selection
  const [generatePost, setGeneratePost] = useState(true);
  const [generateStory, setGenerateStory] = useState(true);
  const [generateAd, setGenerateAd] = useState(true);
  
  // Generated assets
  const [generatedAssets, setGeneratedAssets] = useState({
    instagramPost: null,
    instagramStory: null,
    adCreative: null
  });
  
  // SEO metadata for generated assets
  const [seoMetadata, setSeoMetadata] = useState({
    instagramPost: null,
    instagramStory: null,
    adCreative: null
  });
  
  // Loading states
  const [generating, setGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState("");
  
  const fileInputRef = useRef(null);
  const token = localStorage.getItem('reroots_token');
  const headers = { Authorization: `Bearer ${token}` };

  // Load products on mount
  useEffect(() => {
    loadProducts();
    loadAudienceData();
    loadWhatsappContacts();
    loadScanInsights();
    loadSocialPosts();
  }, []);

  const loadProducts = async () => {
    try {
      const res = await axios.get(`${API}/products`);
      setProducts(res.data || []);
    } catch (err) {
      console.error("Failed to load products:", err);
      toast.error("Failed to load products");
    }
    setLoadingProducts(false);
  };

  // Load target audience data from bio-scans
  const loadAudienceData = async () => {
    try {
      const res = await axios.get(`${API}/admin/marketing-audience`, { headers });
      if (res.data) {
        setAudienceData({
          total: res.data.total || 0,
          concerns: res.data.concerns || {},
          highIntent: res.data.high_intent || 0,
          recentLeads: res.data.recent_leads || []
        });
      }
    } catch (err) {
      console.error("Failed to load audience data:", err);
    }
    setLoadingAudience(false);
  };

  // Load WhatsApp contacts for broadcast
  const loadWhatsappContacts = async () => {
    setLoadingWhatsapp(true);
    try {
      const res = await axios.get(`${API}/admin/marketing-lab/whatsapp-contacts`, { headers });
      setWhatsappContacts(res.data.contacts || []);
    } catch (err) {
      console.error("Failed to load WhatsApp contacts:", err);
    }
    setLoadingWhatsapp(false);
  };

  // Load scan insights for AI content suggestions
  const loadScanInsights = async () => {
    try {
      const res = await axios.get(`${API}/admin/marketing-lab/scan-insights`, { headers });
      setScanInsights(res.data);
    } catch (err) {
      console.error("Failed to load scan insights:", err);
    }
  };

  // Load auto-generated social posts (from milestone unlocks)
  const loadSocialPosts = async () => {
    try {
      const res = await axios.get(`${API}/admin/marketing-lab/social-posts`, { headers });
      setSocialPosts(res.data.posts || []);
    } catch (err) {
      console.error("Failed to load social posts:", err);
    }
  };

  // Send WhatsApp or SMS broadcast to selected contacts
  const sendBroadcast = async () => {
    if (!broadcastMessage.trim()) {
      toast.error("Please enter a message");
      return;
    }
    setSendingBroadcast(true);
    try {
      const endpoint = broadcastChannel === 'sms' 
        ? `${API}/admin/marketing-lab/send-sms-broadcast`
        : `${API}/admin/marketing-lab/send-broadcast`;
      
      const res = await axios.post(endpoint, {
        message: broadcastMessage,
        contact_ids: selectedContacts.length > 0 ? selectedContacts : [],
        filters: sourceFilter !== 'all' ? { source: sourceFilter } : {}
      }, { headers });
      
      const channelName = broadcastChannel === 'sms' ? 'SMS' : 'WhatsApp';
      toast.success(`${channelName} sent! ${res.data.sent} delivered, ${res.data.failed} failed`);
      setBroadcastMessage("");
      setSelectedContacts([]);
      loadWhatsappContacts();
    } catch (err) {
      console.error("Broadcast error:", err);
      toast.error(err.response?.data?.detail || "Failed to send broadcast");
    }
    setSendingBroadcast(false);
  };

  // Send launch invites to existing leads
  const sendLaunchInvites = async () => {
    setSendingLaunchInvites(true);
    try {
      const res = await axios.post(`${API}/admin/marketing-lab/send-launch-invites`, {}, { headers });
      toast.success(`Launch invites sent! ${res.data.sent} delivered to new leads`);
      loadWhatsappContacts();
    } catch (err) {
      console.error("Launch invite error:", err);
      toast.error(err.response?.data?.detail || "Failed to send launch invites");
    }
    setSendingLaunchInvites(false);
  };

  // Mark social post as posted
  const markPostAsPosted = async (postId) => {
    try {
      await axios.post(`${API}/admin/marketing-lab/mark-post-posted`, { post_id: postId }, { headers });
      toast.success("Post marked as published!");
      loadSocialPosts();
    } catch (err) {
      console.error("Failed to mark post:", err);
    }
  };

  // Handle product selection
  const handleProductSelect = (productId) => {
    const product = products.find(p => p.id === productId);
    if (product) {
      setSelectedProduct(product);
      setProductName(product.name || "");
      setTagline(product.tagline || product.short_description || "");
      // If product has an image, we could pre-load it
      if (product.images && product.images.length > 0) {
        setUploadedImage(product.images[0]);
      }
    }
  };

  // Handle image upload
  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) {
        toast.error("Image too large. Max 10MB.");
        return;
      }
      
      const reader = new FileReader();
      reader.onloadend = () => {
        setUploadedImage(reader.result);
        setImageBase64(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  // Generate marketing assets
  const generateAssets = async () => {
    if (!imageBase64 && !uploadedImage) {
      toast.error("Please upload a product image first");
      return;
    }

    if (!generatePost && !generateStory && !generateAd) {
      toast.error("Please select at least one asset type to generate");
      return;
    }

    setGenerating(true);
    setGeneratedAssets({ instagramPost: null, instagramStory: null, adCreative: null });
    setSeoMetadata({ instagramPost: null, instagramStory: null, adCreative: null });

    const selectedVibeConfig = vibeOptions.find(v => v.id === selectedVibe);
    const assetTypes = [];
    if (generatePost) assetTypes.push("instagram_post");
    if (generateStory) assetTypes.push("instagram_story");
    if (generateAd) assetTypes.push("ad_creative");

    try {
      for (const assetType of assetTypes) {
        const assetLabel = assetType === "instagram_post" ? "Instagram Post" : 
                          assetType === "instagram_story" ? "Instagram Story" : "Ad Creative";
        setGenerationProgress(`Generating ${assetLabel}...`);

        const res = await axios.post(`${API}/admin/marketing-lab/generate`, {
          image_base64: imageBase64 || uploadedImage,
          product_name: productName || "Premium Skincare Product",
          tagline: tagline || "",
          vibe: selectedVibe,
          vibe_prompt: selectedVibeConfig?.prompt || "",
          asset_type: assetType,
          brand_preset: BRAND_PRESET
        }, { timeout: 120000 }); // 2 min timeout for image generation

        if (res.data.success) {
          const imageData = `data:image/png;base64,${res.data.image_base64}`;
          const assetKey = assetType === "instagram_post" ? "instagramPost" : 
                         assetType === "instagram_story" ? "instagramStory" : "adCreative";
          
          setGeneratedAssets(prev => ({
            ...prev,
            [assetKey]: imageData
          }));
          
          // Store SEO metadata
          if (res.data.seo_metadata) {
            setSeoMetadata(prev => ({
              ...prev,
              [assetKey]: res.data.seo_metadata
            }));
          }
          
          toast.success(`${assetLabel} generated!`);
        } else {
          toast.error(`Failed to generate ${assetLabel}: ${res.data.error}`);
        }
      }
      
      setGenerationProgress("");
      toast.success("Marketing pack complete!");
    } catch (err) {
      console.error("Generation error:", err);
      toast.error(err.response?.data?.detail || "Failed to generate assets");
    }
    
    setGenerating(false);
    setGenerationProgress("");
  };

  // Download single image
  const downloadImage = (dataUrl, filename) => {
    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success(`Downloaded ${filename}`);
  };

  // Download all generated images
  const downloadAll = () => {
    const timestamp = new Date().toISOString().split('T')[0];
    const safeName = (productName || "product").replace(/[^a-z0-9]/gi, '_').toLowerCase();
    
    if (generatedAssets.instagramPost) {
      downloadImage(generatedAssets.instagramPost, `${safeName}_instagram_post_${timestamp}.png`);
    }
    if (generatedAssets.instagramStory) {
      downloadImage(generatedAssets.instagramStory, `${safeName}_instagram_story_${timestamp}.png`);
    }
    if (generatedAssets.adCreative) {
      downloadImage(generatedAssets.adCreative, `${safeName}_ad_creative_${timestamp}.png`);
    }
  };

  // Copy text to clipboard
  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard!`);
  };

  // SEO Metadata display component
  const SeoMetadataPanel = ({ metadata, assetType }) => {
    if (!metadata) return null;
    
    return (
      <div className="mt-2 p-2 bg-gray-50 rounded-lg text-xs space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-[#5A5A5A] font-medium flex items-center gap-1">
            <FileText className="w-3 h-3" /> SEO Data
          </span>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-2"
            onClick={() => copyToClipboard(
              `Alt: ${metadata.alt_text}\n\nCaption: ${metadata.caption}\n\nHashtags: ${metadata.hashtags?.join(' ') || ''}`,
              'SEO metadata'
            )}
          >
            <Copy className="w-3 h-3" />
          </Button>
        </div>
        {metadata.alt_text && (
          <div className="text-[#5A5A5A]">
            <span className="font-medium">Alt:</span> {metadata.alt_text.slice(0, 60)}...
          </div>
        )}
        {metadata.hashtags && metadata.hashtags.length > 0 && (
          <div className="text-[#F8A5B8] truncate">
            {metadata.hashtags.slice(0, 3).join(' ')}
          </div>
        )}
      </div>
    );
  };

  const hasGeneratedAssets = generatedAssets.instagramPost || generatedAssets.instagramStory || generatedAssets.adCreative;

  return (
    <div className="space-y-6" data-testid="marketing-lab">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: C.text }}>Marketing Lab</h1>
          <p className="mt-1" style={{ color: C.textDim }}>AI-powered marketing asset generator for {brandName}</p>
        </div>
        {hasGeneratedAssets && (
          <Button onClick={downloadAll} style={{ backgroundColor: C.primary, color: C.bg }}>
            <Download className="w-4 h-4 mr-2" />
            Download All
          </Button>
        )}
      </div>

      {/* Target Audience Section - Bio-Scan Leads */}
      <Card className="border-[#F8A5B8]/20 bg-gradient-to-r from-[#FDF9F9] to-white">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-[#F8A5B8]" />
              <CardTitle className="text-lg">Target Audience</CardTitle>
              <Badge className="bg-green-100 text-green-700">High Intent Leads</Badge>
            </div>
            <Button variant="ghost" size="sm" onClick={loadAudienceData} disabled={loadingAudience}>
              <RefreshCw className={`w-4 h-4 ${loadingAudience ? 'animate-spin' : ''}`} />
            </Button>
          </div>
          <CardDescription>Bio-Age Scan completions ready for targeted marketing</CardDescription>
        </CardHeader>
        <CardContent>
          {loadingAudience ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="w-6 h-6 animate-spin text-[#F8A5B8]" />
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Total Leads */}
              <div className="bg-white rounded-xl p-4 border shadow-sm">
                <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
                  <Eye className="w-4 h-4" />
                  Total Leads
                </div>
                <p className="text-3xl font-bold text-[#2D2A2E]">{audienceData.total}</p>
              </div>
              
              {/* High Intent */}
              <div className="bg-white rounded-xl p-4 border shadow-sm">
                <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
                  <Target className="w-4 h-4 text-green-500" />
                  High Intent
                </div>
                <p className="text-3xl font-bold text-green-600">{audienceData.highIntent}</p>
              </div>
              
              {/* Top Concerns */}
              <div className="bg-white rounded-xl p-4 border shadow-sm col-span-2">
                <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
                  <TrendingUp className="w-4 h-4" />
                  Top Concerns (for asset targeting)
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(audienceData.concerns || {}).slice(0, 5).map(([concern, count]) => (
                    <Badge 
                      key={concern} 
                      className="bg-[#F8A5B8]/20 text-[#F8A5B8] cursor-pointer hover:bg-[#F8A5B8]/30"
                      onClick={() => setTagline(`Targets ${concern.replace('_', ' ')}`)}
                    >
                      {concern.replace('_', ' ')}: {count}
                    </Badge>
                  ))}
                  {Object.keys(audienceData.concerns || {}).length === 0 && (
                    <span className="text-gray-400 text-sm">Complete Bio-Age Scans to see concerns</span>
                  )}
                </div>
              </div>
            </div>
          )}
          
          {audienceData.total > 0 && (
            <div className="mt-4 pt-4 border-t">
              <p className="text-sm text-gray-600">
                💡 <strong>Pro Tip:</strong> Click on a concern above to auto-fill it as your tagline, then generate assets that speak directly to these {audienceData.highIntent} high-intent leads.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* WhatsApp & SMS Marketing Hub - Powered by Whapi.cloud & Twilio */}
      <Card className="border-green-200 bg-gradient-to-r from-green-50/50 to-white">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessageCircle className="w-5 h-5 text-green-600" />
              <CardTitle className="text-lg">Marketing Hub</CardTitle>
              <Badge className="bg-green-100 text-green-700">WhatsApp + SMS</Badge>
            </div>
            <Button variant="ghost" size="sm" onClick={() => { loadWhatsappContacts(); loadScanInsights(); loadSocialPosts(); }} disabled={loadingWhatsapp}>
              <RefreshCw className={`w-4 h-4 ${loadingWhatsapp ? 'animate-spin' : ''}`} />
            </Button>
          </div>
          <CardDescription>Send offers via WhatsApp (WHAPI) or SMS (Twilio) to contacts from Data Hub</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Source Filter Buttons */}
          <div className="flex flex-wrap gap-2">
            <Button 
              size="sm" 
              variant={sourceFilter === 'all' ? 'default' : 'outline'}
              onClick={() => setSourceFilter('all')}
              className={sourceFilter === 'all' ? 'bg-gray-800' : ''}
            >
              All Sources ({whatsappContacts.length})
            </Button>
            {[
              { id: 'bio_scans', label: 'Bio-Age Scans', color: 'purple' },
              { id: 'waitlist', label: 'Waitlist', color: 'amber' },
              { id: 'partners', label: 'Partners', color: 'emerald' },
              { id: 'customers', label: 'Customers', color: 'pink' },
              { id: 'sms_subscribers', label: 'SMS Signups', color: 'blue' },
            ].map(source => {
              const count = whatsappContacts.filter(c => c.source === source.id).length;
              if (count === 0) return null;
              return (
                <Button 
                  key={source.id}
                  size="sm" 
                  variant={sourceFilter === source.id ? 'default' : 'outline'}
                  onClick={() => setSourceFilter(source.id)}
                  className={sourceFilter === source.id ? `bg-${source.color}-600` : `border-${source.color}-300 text-${source.color}-700`}
                >
                  {source.label} ({count})
                </Button>
              );
            })}
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white rounded-lg p-3 border shadow-sm">
              <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
                <Phone className="w-3 h-3" />
                Total Contacts
              </div>
              <p className="text-2xl font-bold text-green-600">{whatsappContacts.length}</p>
            </div>
            <div className="bg-white rounded-lg p-3 border shadow-sm">
              <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
                <Target className="w-3 h-3" />
                Selected
              </div>
              <p className="text-2xl font-bold text-[#2D2A2E]">{selectedContacts.length || 'All'}</p>
            </div>
            <div className="bg-white rounded-lg p-3 border shadow-sm col-span-2">
              <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
                <TrendingUp className="w-3 h-3" />
                AI Content Suggestion
              </div>
              {scanInsights?.top_concern ? (
                <p className="text-sm font-medium text-[#2D2A2E]">
                  {scanInsights.top_concern.percentage}% have "{scanInsights.top_concern.concern}" - <span className="text-[#F8A5B8]">Focus your scripts here!</span>
                </p>
              ) : (
                <p className="text-sm text-gray-400">Complete more scans for insights</p>
              )}
            </div>
          </div>

          {/* Contacts Table */}
          {whatsappContacts.length > 0 && (
            <div className="border rounded-lg overflow-hidden">
              <div className="bg-gray-50 px-3 py-2 border-b flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">
                  📱 Phone Numbers ({sourceFilter === 'all' ? whatsappContacts.length : whatsappContacts.filter(c => c.source === sourceFilter).length} contacts)
                </span>
                <div className="flex gap-2">
                  <Button 
                    size="sm" 
                    variant="ghost" 
                    onClick={() => {
                      const filtered = sourceFilter === 'all' ? whatsappContacts : whatsappContacts.filter(c => c.source === sourceFilter);
                      if (selectedContacts.length === filtered.length) {
                        setSelectedContacts([]);
                      } else {
                        setSelectedContacts(filtered.map(c => c.phone));
                      }
                    }}
                    className="text-xs"
                  >
                    {selectedContacts.length > 0 ? 'Deselect All' : 'Select All'}
                  </Button>
                </div>
              </div>
              <div className="max-h-60 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left w-8"></th>
                      <th className="px-3 py-2 text-left">Phone</th>
                      <th className="px-3 py-2 text-left">Name</th>
                      <th className="px-3 py-2 text-left">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(sourceFilter === 'all' ? whatsappContacts : whatsappContacts.filter(c => c.source === sourceFilter)).map((contact, idx) => (
                      <tr 
                        key={idx} 
                        className={`border-t hover:bg-gray-50 cursor-pointer ${selectedContacts.includes(contact.phone) ? 'bg-green-50' : ''}`}
                        onClick={() => {
                          if (selectedContacts.includes(contact.phone)) {
                            setSelectedContacts(selectedContacts.filter(p => p !== contact.phone));
                          } else {
                            setSelectedContacts([...selectedContacts, contact.phone]);
                          }
                        }}
                      >
                        <td className="px-3 py-2">
                          <input 
                            type="checkbox" 
                            checked={selectedContacts.includes(contact.phone)}
                            onChange={() => {}}
                            className="rounded border-gray-300"
                          />
                        </td>
                        <td className="px-3 py-2 font-mono text-xs">{contact.phone}</td>
                        <td className="px-3 py-2 text-gray-700">{contact.name || contact.email || '-'}</td>
                        <td className="px-3 py-2">
                          <Badge 
                            variant="outline" 
                            className={`text-xs bg-${contact.source_color}-50 text-${contact.source_color}-700 border-${contact.source_color}-200`}
                          >
                            {contact.source_label}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Channel Selection */}
          <div className="flex gap-2 items-center">
            <Label className="text-sm font-medium">Send via:</Label>
            <Button 
              size="sm" 
              variant={broadcastChannel === 'whatsapp' ? 'default' : 'outline'}
              onClick={() => setBroadcastChannel('whatsapp')}
              className={broadcastChannel === 'whatsapp' ? 'bg-green-600 hover:bg-green-700' : ''}
            >
              <MessageCircle className="w-4 h-4 mr-1" /> WhatsApp
            </Button>
            <Button 
              size="sm" 
              variant={broadcastChannel === 'sms' ? 'default' : 'outline'}
              onClick={() => setBroadcastChannel('sms')}
              className={broadcastChannel === 'sms' ? 'bg-blue-600 hover:bg-blue-700' : ''}
            >
              <Phone className="w-4 h-4 mr-1" /> SMS (Twilio)
            </Button>
          </div>

          {/* Launch Invite Button */}
          <div className="bg-gradient-to-r from-green-100 to-emerald-100 rounded-lg p-4 border border-green-200">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-semibold text-green-800 flex items-center gap-2">
                  <Rocket className="w-4 h-4" />
                  Launch Campaign: Activate Your Leads
                </h4>
                <p className="text-sm text-green-700 mt-1">
                  Send initial invite to all leads to start their 10-referral journey to $70
                </p>
              </div>
              <Button 
                onClick={sendLaunchInvites} 
                disabled={sendingLaunchInvites || whatsappContacts.length === 0}
                className="bg-green-600 hover:bg-green-700 text-white"
                data-testid="send-launch-invites-btn"
              >
                {sendingLaunchInvites ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Sending...</>
                ) : (
                  <><Send className="w-4 h-4 mr-2" /> Send Launch Invites</>
                )}
              </Button>
            </div>
          </div>

          {/* Custom Broadcast */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Custom {broadcastChannel === 'sms' ? 'SMS' : 'WhatsApp'} Broadcast</Label>
            <div className="flex gap-2">
              <Textarea
                value={broadcastMessage}
                onChange={(e) => setBroadcastMessage(e.target.value)}
                placeholder={broadcastChannel === 'sms' 
                  ? "Write your SMS message... (160 chars recommended)"
                  : "Write your WhatsApp message... (supports *bold* formatting)"
                }
                className="min-h-[80px] flex-1"
                data-testid="broadcast-message-input"
              />
            </div>
            <div className="flex justify-between items-center">
              <p className="text-xs text-gray-500">
                Will send to {selectedContacts.length > 0 ? selectedContacts.length : (sourceFilter === 'all' ? whatsappContacts.length : whatsappContacts.filter(c => c.source === sourceFilter).length)} contacts via {broadcastChannel === 'sms' ? 'SMS (Twilio)' : 'WhatsApp (WHAPI)'}
              </p>
              <Button 
                onClick={sendBroadcast} 
                disabled={sendingBroadcast || !broadcastMessage.trim() || whatsappContacts.length === 0}
                className={broadcastChannel === 'sms' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-green-600 hover:bg-green-700'}
                data-testid="send-broadcast-btn"
              >
                {sendingBroadcast ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Sending...</>
                ) : (
                  <><Send className="w-4 h-4 mr-2" /> Send {broadcastChannel === 'sms' ? 'SMS' : 'WhatsApp'}</>
                )}
              </Button>
            </div>
          </div>

          {/* Auto-Generated Social Proof Posts */}
          {socialPosts.length > 0 && (
            <div className="pt-4 border-t">
              <h4 className="font-medium text-[#2D2A2E] mb-2 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" />
                Auto-Generated Social Proof ({socialPosts.filter(p => !p.posted).length} pending)
              </h4>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {socialPosts.filter(p => !p.posted).slice(0, 3).map(post => (
                  <div key={post.id} className="bg-white rounded-lg p-3 border text-sm">
                    <p className="text-gray-700 whitespace-pre-wrap line-clamp-3">{post.content}</p>
                    <div className="flex justify-between items-center mt-2">
                      <Badge className="bg-amber-100 text-amber-700">{post.type}</Badge>
                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          variant="ghost"
                          onClick={() => copyToClipboard(post.content, "Social post")}
                        >
                          <Copy className="w-3 h-3" />
                        </Button>
                        <Button 
                          size="sm" 
                          variant="ghost"
                          className="text-green-600"
                          onClick={() => markPostAsPosted(post.id)}
                        >
                          <Check className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Inputs */}
        <div className="lg:col-span-1 space-y-4">
          {/* Product Selection */}
          <Card className="border-[#F8A5B8]/20">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Package className="w-4 h-4 text-[#F8A5B8]" />
                Product
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-sm text-[#5A5A5A]">Select from inventory</Label>
                <Select onValueChange={handleProductSelect} disabled={loadingProducts}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder={loadingProducts ? "Loading..." : "Choose a product"} />
                  </SelectTrigger>
                  <SelectContent>
                    {products.map(product => (
                      <SelectItem key={product.id} value={product.id}>
                        {product.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="text-center text-xs text-[#5A5A5A]">or enter manually</div>

              <div>
                <Label className="text-sm text-[#5A5A5A]">Product Name</Label>
                <Input 
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  placeholder="e.g., Bioactive Serum"
                  className="mt-1"
                  data-testid="product-name-input"
                />
              </div>

              <div>
                <Label className="text-sm text-[#5A5A5A]">Tagline / Benefit</Label>
                <Textarea 
                  value={tagline}
                  onChange={(e) => setTagline(e.target.value)}
                  placeholder="e.g., Clinically proven to reduce fine lines by 47%"
                  className="mt-1 min-h-[60px]"
                  data-testid="tagline-input"
                />
              </div>
            </CardContent>
          </Card>

          {/* Image Upload */}
          <Card className="border-[#F8A5B8]/20">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-[#F8A5B8]" />
                Product Image
              </CardTitle>
            </CardHeader>
            <CardContent>
              <input 
                type="file" 
                ref={fileInputRef}
                onChange={handleImageUpload}
                accept="image/png, image/jpeg, image/jpg, image/webp"
                className="hidden"
                data-testid="image-upload-input"
              />
              
              {uploadedImage ? (
                <div className="relative group">
                  <img 
                    src={uploadedImage} 
                    alt="Product" 
                    className="w-full h-48 object-contain rounded-lg border border-[#F8A5B8]/20 bg-gray-50"
                  />
                  <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2">
                    <Button 
                      size="sm" 
                      variant="secondary"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      Change
                    </Button>
                    <Button 
                      size="sm" 
                      variant="destructive"
                      onClick={() => { setUploadedImage(null); setImageBase64(""); }}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full h-48 border-2 border-dashed border-[#F8A5B8]/40 rounded-lg flex flex-col items-center justify-center gap-2 hover:border-[#F8A5B8] hover:bg-[#F8A5B8]/5 transition-colors"
                  data-testid="upload-area"
                >
                  <Upload className="w-8 h-8 text-[#F8A5B8]" />
                  <span className="text-sm text-[#5A5A5A]">Click to upload product image</span>
                  <span className="text-xs text-[#5A5A5A]/60">PNG, JPG up to 10MB</span>
                </button>
              )}
            </CardContent>
          </Card>

          {/* Vibe Selection */}
          <Card className="border-[#F8A5B8]/20">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Palette className="w-4 h-4 text-[#F8A5B8]" />
                Visual Vibe
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {vibeOptions.map((vibe) => {
                  const Icon = vibe.icon;
                  const isSelected = selectedVibe === vibe.id;
                  return (
                    <button
                      key={vibe.id}
                      onClick={() => setSelectedVibe(vibe.id)}
                      className={`w-full p-3 rounded-lg border-2 transition-all text-left ${
                        isSelected 
                          ? "border-[#F8A5B8] bg-[#F8A5B8]/10" 
                          : "border-gray-200 hover:border-[#F8A5B8]/50"
                      }`}
                      data-testid={`vibe-${vibe.id}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${isSelected ? "bg-[#F8A5B8]" : "bg-gray-100"}`}>
                          <Icon className={`w-4 h-4 ${isSelected ? "text-white" : "text-[#5A5A5A]"}`} />
                        </div>
                        <div>
                          <div className={`font-medium ${isSelected ? "text-[#2D2A2E]" : "text-[#5A5A5A]"}`}>
                            {vibe.label}
                          </div>
                          <div className="text-xs text-[#5A5A5A]/70">{vibe.description}</div>
                        </div>
                        {isSelected && <Check className="w-4 h-4 text-[#F8A5B8] ml-auto" />}
                      </div>
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Asset Type Selection */}
          <Card className="border-[#F8A5B8]/20">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Zap className="w-4 h-4 text-[#F8A5B8]" />
                Generate Assets
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={generatePost}
                  onChange={(e) => setGeneratePost(e.target.checked)}
                  className="w-4 h-4 accent-[#F8A5B8]"
                  data-testid="checkbox-post"
                />
                <Square className="w-4 h-4 text-[#5A5A5A]" />
                <div>
                  <div className="text-sm font-medium text-[#2D2A2E]">Instagram Post</div>
                  <div className="text-xs text-[#5A5A5A]">1:1 square format</div>
                </div>
              </label>

              <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={generateStory}
                  onChange={(e) => setGenerateStory(e.target.checked)}
                  className="w-4 h-4 accent-[#F8A5B8]"
                  data-testid="checkbox-story"
                />
                <RectangleVertical className="w-4 h-4 text-[#5A5A5A]" />
                <div>
                  <div className="text-sm font-medium text-[#2D2A2E]">Instagram Story</div>
                  <div className="text-xs text-[#5A5A5A]">9:16 vertical format</div>
                </div>
              </label>

              <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={generateAd}
                  onChange={(e) => setGenerateAd(e.target.checked)}
                  className="w-4 h-4 accent-[#F8A5B8]"
                  data-testid="checkbox-ad"
                />
                <Megaphone className="w-4 h-4 text-[#5A5A5A]" />
                <div>
                  <div className="text-sm font-medium text-[#2D2A2E]">Ad Creative</div>
                  <div className="text-xs text-[#5A5A5A]">1:1 conversion-focused</div>
                </div>
              </label>

              <Button 
                onClick={generateAssets}
                disabled={generating || (!uploadedImage && !imageBase64)}
                className="w-full bg-gradient-to-r from-[#F8A5B8] to-[#E88DA0] hover:from-[#E88DA0] hover:to-[#d87d90] text-white mt-4"
                data-testid="generate-btn"
              >
                {generating ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    {generationProgress || "Generating..."}
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Generate Marketing Pack
                  </>
                )}
              </Button>

              {generating && (
                <p className="text-xs text-center text-[#5A5A5A]">
                  Each image takes ~30-60 seconds to generate
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Generated Assets */}
        <div className="lg:col-span-2">
          <Card className="border-[#F8A5B8]/20 h-full">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Wand2 className="w-4 h-4 text-[#F8A5B8]" />
                Generated Assets
              </CardTitle>
              <CardDescription>
                Your AI-generated marketing visuals will appear here
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!hasGeneratedAssets && !generating ? (
                <div className="h-96 flex flex-col items-center justify-center text-center border-2 border-dashed border-gray-200 rounded-lg">
                  <ImageIcon className="w-16 h-16 text-gray-300 mb-4" />
                  <p className="text-[#5A5A5A]">No assets generated yet</p>
                  <p className="text-sm text-[#5A5A5A]/60 mt-1">
                    Upload a product image and click Generate
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {/* Instagram Post */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="text-xs">
                        <Square className="w-3 h-3 mr-1" />
                        Instagram Post
                      </Badge>
                      {generatedAssets.instagramPost && (
                        <Button 
                          size="sm" 
                          variant="ghost"
                          onClick={() => downloadImage(generatedAssets.instagramPost, `${productName || 'product'}_instagram_post.png`)}
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                    <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden border border-gray-200">
                      {generatedAssets.instagramPost ? (
                        <img 
                          src={generatedAssets.instagramPost} 
                          alt={seoMetadata.instagramPost?.alt_text || "Instagram Post"} 
                          className="w-full h-full object-cover"
                          data-testid="generated-post"
                        />
                      ) : generating && generatePost ? (
                        <div className="w-full h-full flex items-center justify-center">
                          <Loader2 className="w-8 h-8 animate-spin text-[#F8A5B8]" />
                        </div>
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <Square className="w-8 h-8 text-gray-300" />
                        </div>
                      )}
                    </div>
                    <SeoMetadataPanel metadata={seoMetadata.instagramPost} assetType="post" />
                  </div>

                  {/* Instagram Story */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="text-xs">
                        <RectangleVertical className="w-3 h-3 mr-1" />
                        Instagram Story
                      </Badge>
                      {generatedAssets.instagramStory && (
                        <Button 
                          size="sm" 
                          variant="ghost"
                          onClick={() => downloadImage(generatedAssets.instagramStory, `${productName || 'product'}_instagram_story.png`)}
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                    <div className="aspect-[9/16] max-h-[400px] bg-gray-100 rounded-lg overflow-hidden border border-gray-200">
                      {generatedAssets.instagramStory ? (
                        <img 
                          src={generatedAssets.instagramStory} 
                          alt={seoMetadata.instagramStory?.alt_text || "Instagram Story"} 
                          className="w-full h-full object-cover"
                          data-testid="generated-story"
                        />
                      ) : generating && generateStory ? (
                        <div className="w-full h-full flex items-center justify-center">
                          <Loader2 className="w-8 h-8 animate-spin text-[#F8A5B8]" />
                        </div>
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <RectangleVertical className="w-8 h-8 text-gray-300" />
                        </div>
                      )}
                    </div>
                    <SeoMetadataPanel metadata={seoMetadata.instagramStory} assetType="story" />
                  </div>

                  {/* Ad Creative */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="text-xs">
                        <Megaphone className="w-3 h-3 mr-1" />
                        Ad Creative
                      </Badge>
                      {generatedAssets.adCreative && (
                        <Button 
                          size="sm" 
                          variant="ghost"
                          onClick={() => downloadImage(generatedAssets.adCreative, `${productName || 'product'}_ad_creative.png`)}
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                    <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden border border-gray-200">
                      {generatedAssets.adCreative ? (
                        <img 
                          src={generatedAssets.adCreative} 
                          alt={seoMetadata.adCreative?.alt_text || "Ad Creative"} 
                          className="w-full h-full object-cover"
                          data-testid="generated-ad"
                        />
                      ) : generating && generateAd ? (
                        <div className="w-full h-full flex items-center justify-center">
                          <Loader2 className="w-8 h-8 animate-spin text-[#F8A5B8]" />
                        </div>
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <Megaphone className="w-8 h-8 text-gray-300" />
                        </div>
                      )}
                    </div>
                    <SeoMetadataPanel metadata={seoMetadata.adCreative} assetType="ad" />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default MarketingLab;
