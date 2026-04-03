import React, { useState, useRef, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { 
  Sparkles, Image as ImageIcon, Video, MessageSquare, 
  Download, Loader2, Wand2, Copy, Check, RefreshCw, Zap, FlaskConical, Beaker,
  History, Trash2, ChevronDown, ChevronUp, Clock, Mic, Play, Pause, Instagram, Link, ExternalLink, Upload
} from "lucide-react";
import ScienceTab from "./ScienceTab";

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Media Library Items Component - now accepts refreshKey prop to force re-render
const MediaLibraryItems = ({ refreshKey }) => {
  const [items, setItems] = useState([]);
  const [expanded, setExpanded] = useState(false);
  
  // Reload items whenever refreshKey changes or on mount
  useEffect(() => {
    const loadItems = () => {
      const saved = localStorage.getItem('reel_media_library');
      if (saved) {
        try {
          setItems(JSON.parse(saved));
        } catch (e) {
          setItems([]);
        }
      }
    };
    loadItems();
  }, [refreshKey]);
  
  const deleteItem = (id) => {
    const updated = items.filter(item => item.id !== id);
    setItems(updated);
    localStorage.setItem('reel_media_library', JSON.stringify(updated));
    toast.success('Item deleted');
  };
  
  const downloadItem = (item) => {
    if (item.type === 'link') {
      window.open(item.data, '_blank');
      return;
    }
    if (item.type === 'video_preview') {
      // Download thumbnail image for video preview
      const link = document.createElement('a');
      link.href = item.data;
      link.download = item.name.replace('.mp4', '_thumbnail.jpg').replace('.mov', '_thumbnail.jpg');
      link.click();
      toast.info('Downloaded thumbnail. For full video, re-upload a smaller file (<3MB)');
      return;
    }
    const link = document.createElement('a');
    link.href = item.data;
    link.download = item.name;
    link.click();
    toast.success('Downloaded!');
  };
  
  if (items.length === 0) {
    return (
      <p className="text-xs text-gray-400 text-center py-2">
        No saved media yet. Upload files above to build your media library.
      </p>
    );
  }
  
  const displayItems = expanded ? items : items.slice(0, 4);
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-gray-600">Saved Media ({items.length})</p>
        {items.length > 4 && (
          <button 
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-purple-600 hover:underline flex items-center gap-1"
          >
            {expanded ? 'Show Less' : `Show All (${items.length})`}
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        )}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {displayItems.map(item => (
          <div key={item.id} className="relative group bg-white rounded-lg border p-2 hover:border-purple-300 transition-colors">
            <div className="flex items-center gap-2 mb-1">
              {item.type === 'image' && <ImageIcon className="w-3 h-3 text-pink-500" />}
              {(item.type === 'video' || item.type === 'video_preview') && <Video className="w-3 h-3 text-purple-500" />}
              {item.type === 'audio' && <Mic className="w-3 h-3 text-green-500" />}
              {item.type === 'link' && <Link className="w-3 h-3 text-blue-500" />}
              <span className="text-xs text-gray-700 truncate flex-1">{item.name}</span>
            </div>
            
            {item.type === 'image' && (
              <img src={item.data} alt={item.name} className="w-full h-12 object-cover rounded" />
            )}
            {item.type === 'video' && (
              <video src={item.data} className="w-full h-12 object-cover rounded" />
            )}
            {item.type === 'video_preview' && (
              <div className="relative">
                {item.data ? (
                  <img src={item.data} alt={item.name} className="w-full h-12 object-cover rounded" />
                ) : (
                  <div className="w-full h-12 bg-gradient-to-br from-purple-100 to-pink-100 rounded flex items-center justify-center">
                    <Video className="w-5 h-5 text-purple-500" />
                  </div>
                )}
                <span className="absolute bottom-0 right-0 bg-black/70 text-white text-xs px-1 rounded-tl">
                  {item.metadata?.duration}s
                </span>
                <span className="absolute top-0 left-0 bg-purple-500 text-white text-xs px-1 rounded-br">
                  Preview
                </span>
              </div>
            )}
            {item.type === 'audio' && (
              <audio src={item.data} controls className="w-full h-8" style={{height: '24px'}} />
            )}
            {item.type === 'link' && (
              <p className="text-xs text-blue-500 truncate">{item.data}</p>
            )}
            
            <div className="absolute top-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => downloadItem(item)}
                className="p-1 bg-white rounded shadow hover:bg-gray-50"
                title={item.type === 'link' ? 'Open Link' : 'Download'}
              >
                {item.type === 'link' ? <ExternalLink className="w-3 h-3 text-blue-500" /> : <Download className="w-3 h-3 text-gray-600" />}
              </button>
              <button
                onClick={() => deleteItem(item.id)}
                className="p-1 bg-white rounded shadow hover:bg-red-50"
                title="Delete"
              >
                <Trash2 className="w-3 h-3 text-red-500" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const AIContentStudio = () => {
  const [activeTab, setActiveTab] = useState("reel");
  const [uploadedImage, setUploadedImage] = useState(null);
  const [imageBase64, setImageBase64] = useState("");
  const [productName, setProductName] = useState("");
  const [productDescription, setProductDescription] = useState("");
  
  // Generated content
  const [analysis, setAnalysis] = useState("");
  const [ugcImage, setUgcImage] = useState(null);
  const [caption, setCaption] = useState("");
  const [hashtags, setHashtags] = useState([]);
  const [videoUrl, setVideoUrl] = useState("");
  
  // Loading states
  const [analyzing, setAnalyzing] = useState(false);
  const [generatingImage, setGeneratingImage] = useState(false);
  const [generatingCaption, setGeneratingCaption] = useState(false);
  const [generatingVideo, setGeneratingVideo] = useState(false);
  
  // Settings
  const [ugcStyle, setUgcStyle] = useState("natural");
  const [captionPlatform, setCaptionPlatform] = useState("instagram");
  const [captionTone, setCaptionTone] = useState("casual");
  const [videoDuration, setVideoDuration] = useState("4");
  const [videoPrompt, setVideoPrompt] = useState("");
  
  const [copied, setCopied] = useState(false);
  const fileInputRef = useRef(null);

  // Science Formulation state
  const [scienceQuery, setScienceQuery] = useState("");
  const [formulationType, setFormulationType] = useState("ingredient");
  const [scienceResponse, setScienceResponse] = useState("");
  const [generatingScience, setGeneratingScience] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  
  // Reel Creator state
  const [reelScript, setReelScript] = useState("");
  const [reelTone, setReelTone] = useState("founder");
  const [reelDuration, setReelDuration] = useState("30");
  const [reelLanguage, setReelLanguage] = useState("en");
  const [reelTopic, setReelTopic] = useState("");
  const [generatingScript, setGeneratingScript] = useState(false);
  const [voiceProvider, setVoiceProvider] = useState("openai"); // openai (free) or elevenlabs (paid)
  const [selectedVoice, setSelectedVoice] = useState("onyx"); // Onyx - Deep, authoritative (FREE)
  const [availableVoices, setAvailableVoices] = useState([]);
  const [voiceStability, setVoiceStability] = useState(0.5);
  const [voiceSimilarity, setVoiceSimilarity] = useState(0.75);
  const [generatingVoice, setGeneratingVoice] = useState(false);
  const [generatedAudio, setGeneratedAudio] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef(null);
  const [mediaRefreshKey, setMediaRefreshKey] = useState(0); // For refreshing media library
  
  // HeyGen Video Generation state
  const [avatarPhoto, setAvatarPhoto] = useState(null);
  const [avatarPhotoPreview, setAvatarPhotoPreview] = useState(null);
  const [generatingHeygenVideo, setGeneratingHeygenVideo] = useState(false);
  const [heygenVideoId, setHeygenVideoId] = useState(null);
  const [heygenVideoStatus, setHeygenVideoStatus] = useState(null);
  const [heygenVideoUrl, setHeygenVideoUrl] = useState(null);
  const [heygenPolling, setHeygenPolling] = useState(false);
  
  // Helper to refresh media library after upload
  const refreshMediaLibrary = () => setMediaRefreshKey(prev => prev + 1);
  
  // Update selected voice when provider changes
  useEffect(() => {
    if (voiceProvider === "openai") {
      setSelectedVoice("onyx");
    } else {
      setSelectedVoice("ODq5zmih8GrVes37Dizd"); // Patrick - ElevenLabs
    }
  }, [voiceProvider]);
  
  // Load available voices on mount
  useEffect(() => {
    const loadVoices = async () => {
      try {
        const res = await axios.get(`${API}/admin/ai-studio/voices`);
        if (res.data.success) {
          setAvailableVoices(res.data.voices);
        }
      } catch (err) {
        console.error("Failed to load voices:", err);
      }
    };
    loadVoices();
  }, []);
  
  // Load AI history from localStorage
  const [aiHistory, setAiHistory] = useState(() => {
    const saved = localStorage.getItem('reroots_ai_history');
    return saved ? JSON.parse(saved) : [];
  });
  
  // Save AI history to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('reroots_ai_history', JSON.stringify(aiHistory));
  }, [aiHistory]);
  
  // Add to history function
  const addToHistory = (type, query, response, metadata = {}) => {
    const historyItem = {
      id: Date.now(),
      type, // 'science', 'caption', 'image', 'video'
      query,
      response,
      metadata,
      timestamp: new Date().toISOString()
    };
    setAiHistory(prev => [historyItem, ...prev].slice(0, 50)); // Keep last 50 items
  };
  
  // Clear history
  const clearHistory = () => {
    if (window.confirm('Are you sure you want to clear all AI history?')) {
      setAiHistory([]);
      toast.success('History cleared');
    }
  };
  
  // Load from history
  const loadFromHistory = (item) => {
    if (item.type === 'science') {
      setScienceQuery(item.query);
      setFormulationType(item.metadata?.queryType || 'ingredient');
      setScienceResponse(item.response);
      setActiveTab('science');
    } else if (item.type === 'caption') {
      setCaption(item.response);
      setHashtags(item.metadata?.hashtags || []);
      setActiveTab('caption');
    }
    toast.success('Loaded from history');
  };

  const styleOptions = {
    natural: "Natural lighting, authentic UGC feel, lifestyle shot",
    luxury: "Premium aesthetic, soft golden lighting, elegant composition",
    minimal: "Clean minimalist style, white background, product focus",
    lifestyle: "Lifestyle context, bathroom/vanity setting, morning routine vibe",
    closeup: "Macro close-up, texture focus, product details highlighted"
  };

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

  const analyzeImage = async () => {
    if (!imageBase64) {
      toast.error("Please upload an image first");
      return;
    }
    
    setAnalyzing(true);
    try {
      const res = await axios.post(`${API}/admin/ai-studio/analyze-image`, {
        image_base64: imageBase64
      });
      
      if (res.data.success) {
        setAnalysis(res.data.analysis);
        toast.success("Image analyzed!");
      } else {
        toast.error(res.data.error || "Analysis failed");
      }
    } catch (err) {
      toast.error("Failed to analyze image");
    }
    setAnalyzing(false);
  };

  const generateUGCImage = async () => {
    if (!imageBase64) {
      toast.error("Please upload an image first");
      return;
    }
    
    setGeneratingImage(true);
    try {
      const res = await axios.post(`${API}/admin/ai-studio/generate-ugc-image`, {
        image_base64: imageBase64,
        product_name: productName || "skincare product",
        style: styleOptions[ugcStyle]
      });
      
      if (res.data.success) {
        setUgcImage(`data:${res.data.mime_type};base64,${res.data.ugc_image_base64}`);
        toast.success("UGC image generated!");
      } else {
        toast.error(res.data.error || "Generation failed");
      }
    } catch (err) {
      toast.error("Failed to generate UGC image");
    }
    setGeneratingImage(false);
  };

  const generateCaption = async () => {
    setGeneratingCaption(true);
    try {
      const res = await axios.post(`${API}/admin/ai-studio/generate-caption`, {
        product_name: productName || "skincare product",
        product_description: productDescription,
        platform: captionPlatform,
        tone: captionTone
      });
      
      if (res.data.success) {
        setCaption(res.data.caption);
        setHashtags(res.data.hashtags || []);
        // Save to history
        addToHistory('caption', `Caption for ${productName || 'product'} (${captionPlatform}, ${captionTone})`, res.data.caption, {
          platform: captionPlatform,
          tone: captionTone,
          hashtags: res.data.hashtags || []
        });
        toast.success("Caption generated!");
      } else {
        toast.error(res.data.error || "Caption generation failed");
      }
    } catch (err) {
      toast.error("Failed to generate caption");
    }
    setGeneratingCaption(false);
  };

  const generateVideo = async () => {
    if (!videoPrompt && !productName) {
      toast.error("Please enter a video prompt or product name");
      return;
    }
    
    setGeneratingVideo(true);
    toast.info("Generating video... This may take 2-5 minutes", { duration: 10000 });
    
    try {
      const res = await axios.post(`${API}/admin/ai-studio/generate-video`, {
        prompt: videoPrompt || `A person gently applying ${productName} to their face, soft natural lighting, UGC style, authentic skincare routine`,
        product_name: productName,
        duration: parseInt(videoDuration),
        size: "1280x720" // Landscape (most compatible with Sora 2)
      }, { timeout: 700000 }); // 10+ minute timeout
      
      if (res.data.success) {
        setVideoUrl(`${API}${res.data.video_url}`);
        toast.success("Video generated!");
      } else {
        toast.error(res.data.error || "Video generation failed");
      }
    } catch (err) {
      toast.error("Video generation failed or timed out");
    }
    setGeneratingVideo(false);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success("Copied to clipboard!");
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadImage = (dataUrl, filename) => {
    const link = document.createElement("a");
    link.href = dataUrl;
    link.download = filename;
    link.click();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-[#D4AF37]" />
            AI Content Studio
          </h2>
          <p className="text-[#5A5A5A] mt-1">Generate UGC images, videos & captions with AI</p>
        </div>
        <Badge className="bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#0a0a0a]">
          <Zap className="w-3 h-3 mr-1" /> Powered by AI
        </Badge>
      </div>

      {/* Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Step 1: Upload Product Photo</CardTitle>
          <CardDescription>Upload a clear photo of your product to get started</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-6">
            {/* Upload Area */}
            <div 
              className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-[#D4AF37] transition-colors cursor-pointer"
              onClick={() => fileInputRef.current?.click()}
            >
              {uploadedImage ? (
                <img src={uploadedImage} alt="Uploaded" className="max-h-64 mx-auto rounded-lg shadow-md" />
              ) : (
                <div className="space-y-4">
                  <Upload className="w-12 h-12 text-gray-400 mx-auto" />
                  <p className="text-gray-500">Click or drag to upload product photo</p>
                  <p className="text-xs text-gray-400">PNG, JPG up to 10MB</p>
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageUpload}
                className="hidden"
              />
            </div>
            
            {/* Product Details */}
            <div className="space-y-4">
              <div>
                <Label>Product Name</Label>
                <Input
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  placeholder="e.g., AURA-GEN PDRN Serum"
                />
              </div>
              <div>
                <Label>Product Description (optional)</Label>
                <Textarea
                  value={productDescription}
                  onChange={(e) => setProductDescription(e.target.value)}
                  placeholder="Brief description for caption generation..."
                  rows={3}
                />
              </div>
              
              {uploadedImage && (
                <Button 
                  onClick={analyzeImage} 
                  disabled={analyzing}
                  className="w-full"
                  variant="outline"
                >
                  {analyzing ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Analyzing...</>
                  ) : (
                    <><Wand2 className="w-4 h-4 mr-2" /> Analyze Image</>
                  )}
                </Button>
              )}
              
              {analysis && (
                <div className="p-4 bg-[#FDF9F9] rounded-lg text-sm text-[#5A5A5A]">
                  <p className="font-medium text-[#2D2A2E] mb-2">AI Analysis:</p>
                  <p className="whitespace-pre-wrap">{analysis}</p>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Generation Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-5 w-full max-w-2xl">
          <TabsTrigger value="reel" className="flex items-center gap-1 text-xs sm:text-sm">
            <Instagram className="w-4 h-4" /> <span className="hidden sm:inline">Reel</span> Creator
          </TabsTrigger>
          <TabsTrigger value="image" className="flex items-center gap-1 text-xs sm:text-sm">
            <ImageIcon className="w-4 h-4" /> <span className="hidden sm:inline">UGC</span> Image
          </TabsTrigger>
          <TabsTrigger value="caption" className="flex items-center gap-1 text-xs sm:text-sm">
            <MessageSquare className="w-4 h-4" /> Caption
          </TabsTrigger>
          <TabsTrigger value="video" className="flex items-center gap-1 text-xs sm:text-sm">
            <Video className="w-4 h-4" /> Video
          </TabsTrigger>
          <TabsTrigger value="science" className="flex items-center gap-1 text-xs sm:text-sm">
            <FlaskConical className="w-4 h-4" /> Science
          </TabsTrigger>
        </TabsList>

        {/* Reel Creator Tab - NEW */}
        <TabsContent value="reel">
          <Card className="border-2 border-pink-200">
            <CardHeader className="bg-gradient-to-r from-pink-50 to-purple-50">
              <CardTitle className="text-lg flex items-center gap-2">
                <Instagram className="w-5 h-5 text-pink-500" />
                Instagram Reel Creator
                <Badge className="bg-gradient-to-r from-pink-500 to-purple-500 text-white text-xs">ALL-IN-ONE</Badge>
              </CardTitle>
              <CardDescription>
                Generate script → Voice → Create talking video for Instagram Reels
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6 pt-6">
              {/* Progress Indicator */}
              <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-pink-50 via-purple-50 to-green-50 rounded-xl border border-pink-200">
                <div className="flex items-center gap-2">
                  <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all ${reelScript ? 'bg-green-500 text-white' : 'bg-pink-500 text-white animate-pulse'}`}>
                    {reelScript ? '✓' : '1'}
                  </span>
                  <span className={`text-sm ${reelScript ? 'text-green-600 font-medium' : 'text-pink-600 font-medium'}`}>Script</span>
                </div>
                <div className={`h-1 w-16 rounded ${reelScript ? 'bg-gradient-to-r from-green-400 to-purple-400' : 'bg-gray-200'}`}></div>
                <div className="flex items-center gap-2">
                  <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all ${generatedAudio ? 'bg-green-500 text-white' : reelScript ? 'bg-purple-500 text-white animate-pulse' : 'bg-gray-300 text-gray-500'}`}>
                    {generatedAudio ? '✓' : '2'}
                  </span>
                  <span className={`text-sm ${generatedAudio ? 'text-green-600 font-medium' : reelScript ? 'text-purple-600 font-medium' : 'text-gray-400'}`}>Voice</span>
                </div>
                <div className={`h-1 w-16 rounded ${generatedAudio ? 'bg-gradient-to-r from-green-400 to-emerald-400' : 'bg-gray-200'}`}></div>
                <div className="flex items-center gap-2">
                  <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all ${generatedAudio ? 'bg-green-500 text-white animate-pulse' : 'bg-gray-300 text-gray-500'}`}>
                    3
                  </span>
                  <span className={`text-sm ${generatedAudio ? 'text-green-600 font-medium' : 'text-gray-400'}`}>Video</span>
                </div>
              </div>

              {/* Step 1: Generate Script */}
              <div className="space-y-4 p-4 bg-gray-50 rounded-xl">
                <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                  <span className="w-6 h-6 rounded-full bg-pink-500 text-white flex items-center justify-center text-xs">1</span>
                  Generate Script
                </div>
                
                <div>
                  <Label>Topic / What do you want to talk about?</Label>
                  <Textarea
                    value={reelTopic}
                    onChange={(e) => setReelTopic(e.target.value)}
                    placeholder="e.g., Why PDRN is the future of skincare, The science behind salmon DNA in serums, 3 mistakes people make with retinol..."
                    rows={2}
                  />
                </div>
                
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label>Tone</Label>
                    <Select value={reelTone} onValueChange={setReelTone}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="founder">🚀 Founder/Tech</SelectItem>
                        <SelectItem value="professional">💼 Professional</SelectItem>
                        <SelectItem value="casual">😊 Casual</SelectItem>
                        <SelectItem value="scientific">🔬 Scientific</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Duration</Label>
                    <Select value={reelDuration} onValueChange={setReelDuration}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="15">15 sec</SelectItem>
                        <SelectItem value="30">30 sec</SelectItem>
                        <SelectItem value="60">60 sec</SelectItem>
                        <SelectItem value="90">90 sec</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Language</Label>
                    <Select value={reelLanguage} onValueChange={setReelLanguage}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="en">English</SelectItem>
                        <SelectItem value="hi">Hinglish</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                
                <Button
                  onClick={async () => {
                    if (!reelTopic.trim()) {
                      toast.error("Please enter a topic");
                      return;
                    }
                    setGeneratingScript(true);
                    try {
                      const res = await axios.post(`${API}/admin/ai-studio/generate-reel-script`, {
                        topic: reelTopic,
                        product_name: productName,
                        tone: reelTone,
                        duration: reelDuration,
                        language: reelLanguage
                      });
                      if (res.data.success) {
                        setReelScript(res.data.script);
                        toast.success(`Script generated! (~${res.data.estimated_duration_seconds}s)`);
                      } else {
                        toast.error(res.data.error || "Failed to generate script");
                      }
                    } catch (err) {
                      toast.error("Failed to generate script");
                    }
                    setGeneratingScript(false);
                  }}
                  disabled={generatingScript || !reelTopic.trim()}
                  className="w-full bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 text-white"
                >
                  {generatingScript ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating Script...</>
                  ) : (
                    <><Wand2 className="w-4 h-4 mr-2" /> Generate Script</>
                  )}
                </Button>
                
                {reelScript && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label>Your Script (edit if needed)</Label>
                      <Button size="sm" variant="ghost" onClick={() => copyToClipboard(reelScript)}>
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                    <Textarea
                      value={reelScript}
                      onChange={(e) => setReelScript(e.target.value)}
                      rows={4}
                      className="font-mono text-sm"
                    />
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-gray-500">{reelScript.split(' ').length} words • ~{Math.round(reelScript.split(' ').length / 2.5)}s</p>
                      <div className="flex items-center gap-2 text-green-600 text-sm font-medium animate-pulse">
                        <Check className="w-4 h-4" /> Script Ready
                      </div>
                    </div>
                    
                    {/* Continue to Step 2 Button */}
                    <Button 
                      onClick={() => {
                        // Scroll to Step 2 smoothly
                        document.getElementById('reel-step-2')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        toast.info('Script loaded! Now generate the voice.', { duration: 3000 });
                      }}
                      className="w-full bg-gradient-to-r from-purple-500 to-indigo-500 hover:from-purple-600 hover:to-indigo-600 text-white mt-2"
                    >
                      Next: Generate Voice <span className="ml-2">→</span>
                    </Button>
                  </div>
                )}
              </div>
              
              {/* Arrow connector */}
              {reelScript && (
                <div className="flex justify-center -my-3">
                  <div className="w-0.5 h-6 bg-gradient-to-b from-pink-400 to-purple-500"></div>
                </div>
              )}
              
              {/* Step 2: Generate Voice */}
              <div 
                id="reel-step-2"
                className={`space-y-4 p-4 rounded-xl transition-all ${reelScript ? 'bg-gradient-to-r from-purple-50 to-indigo-50 border-2 border-purple-200' : 'bg-gray-100 opacity-50 pointer-events-none'}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                    <span className="w-6 h-6 rounded-full bg-purple-500 text-white flex items-center justify-center text-xs">2</span>
                    Generate Voice from Script
                  </div>
                  {reelScript && <Badge variant="outline" className="text-xs bg-white">📝 {reelScript.split(' ').length} words ready</Badge>}
                </div>
                
                {/* AI Provider Selector */}
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => setVoiceProvider("openai")}
                    className={`p-3 rounded-lg border-2 transition-all ${
                      voiceProvider === "openai" 
                        ? "border-green-500 bg-green-50" 
                        : "border-gray-200 hover:border-green-300"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg flex items-center justify-center">
                        <span className="text-white font-bold text-xs">AI</span>
                      </div>
                      <div className="text-left">
                        <p className="font-semibold text-sm">OpenAI TTS</p>
                        <p className="text-xs text-green-600">FREE • 9 voices</p>
                      </div>
                    </div>
                  </button>
                  
                  <button
                    onClick={() => setVoiceProvider("elevenlabs")}
                    className={`p-3 rounded-lg border-2 transition-all ${
                      voiceProvider === "elevenlabs" 
                        ? "border-purple-500 bg-purple-50" 
                        : "border-gray-200 hover:border-purple-300"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-600 rounded-lg flex items-center justify-center">
                        <span className="text-white font-bold text-xs">11</span>
                      </div>
                      <div className="text-left">
                        <p className="font-semibold text-sm">ElevenLabs</p>
                        <p className="text-xs text-amber-600">PAID • Premium</p>
                      </div>
                    </div>
                  </button>
                </div>
                
                <div>
                  <Label>Select Voice</Label>
                  <Select value={selectedVoice} onValueChange={setSelectedVoice}>
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a voice..." />
                    </SelectTrigger>
                    <SelectContent>
                      {voiceProvider === "openai" ? (
                        <>
                          {availableVoices.filter(v => v.category?.includes('openai')).map(voice => (
                            <SelectItem key={voice.voice_id} value={voice.voice_id}>
                              <span className="flex items-center gap-2">
                                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                                {voice.name} - {voice.description}
                              </span>
                            </SelectItem>
                          ))}
                        </>
                      ) : (
                        <>
                          {availableVoices.filter(v => v.category?.includes('elevenlabs')).map(voice => (
                            <SelectItem key={voice.voice_id} value={voice.voice_id}>
                              <span className="flex items-center gap-2">
                                <span className="w-2 h-2 bg-purple-500 rounded-full"></span>
                                {voice.name} - {voice.description}
                              </span>
                            </SelectItem>
                          ))}
                        </>
                      )}
                    </SelectContent>
                  </Select>
                  {voiceProvider === "elevenlabs" && (
                    <p className="text-xs text-amber-600 mt-1">⚠️ Requires ElevenLabs paid subscription</p>
                  )}
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs">Stability: {voiceStability}</Label>
                    <Slider
                      value={[voiceStability]}
                      onValueChange={([v]) => setVoiceStability(v)}
                      min={0}
                      max={1}
                      step={0.1}
                      className="mt-2"
                    />
                    <p className="text-xs text-gray-400 mt-1">Lower = more expressive</p>
                  </div>
                  <div>
                    <Label className="text-xs">Clarity: {voiceSimilarity}</Label>
                    <Slider
                      value={[voiceSimilarity]}
                      onValueChange={([v]) => setVoiceSimilarity(v)}
                      min={0}
                      max={1}
                      step={0.1}
                      className="mt-2"
                    />
                    <p className="text-xs text-gray-400 mt-1">Higher = clearer voice</p>
                  </div>
                </div>
                
                <Button
                  onClick={async () => {
                    if (!reelScript.trim()) {
                      toast.error("Please generate or enter a script first");
                      return;
                    }
                    setGeneratingVoice(true);
                    try {
                      const res = await axios.post(`${API}/admin/ai-studio/generate-voice`, {
                        text: reelScript,
                        voice_id: selectedVoice,
                        stability: voiceStability,
                        similarity_boost: voiceSimilarity
                      });
                      if (res.data.success) {
                        setGeneratedAudio(`data:${res.data.mime_type};base64,${res.data.audio_base64}`);
                        toast.success(`Voice generated! (~${res.data.estimated_duration_seconds}s)`);
                      } else if (res.data.requires_api_key) {
                        toast.error("ElevenLabs API key required. Add ELEVENLABS_API_KEY to your environment.");
                      } else {
                        toast.error(res.data.error || "Failed to generate voice");
                      }
                    } catch (err) {
                      toast.error("Failed to generate voice");
                    }
                    setGeneratingVoice(false);
                  }}
                  disabled={generatingVoice || !reelScript.trim()}
                  className="w-full bg-gradient-to-r from-purple-500 to-indigo-500 hover:from-purple-600 hover:to-indigo-600 text-white"
                >
                  {generatingVoice ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating Voice...</>
                  ) : (
                    <><Mic className="w-4 h-4 mr-2" /> Generate Voice</>
                  )}
                </Button>
                
                {generatedAudio && (
                  <div className="p-4 bg-white rounded-lg border space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="font-medium text-sm">Generated Audio</p>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            if (audioRef.current) {
                              if (isPlaying) {
                                audioRef.current.pause();
                              } else {
                                audioRef.current.play();
                              }
                              setIsPlaying(!isPlaying);
                            }
                          }}
                        >
                          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            try {
                              const mediaItems = JSON.parse(localStorage.getItem('reel_media_library') || '[]');
                              mediaItems.push({
                                id: Date.now(),
                                type: 'audio',
                                name: '🎙️ Voice - ' + (reelTopic.substring(0, 20) || 'Reel') + '.mp3',
                                data: generatedAudio,
                                createdAt: new Date().toISOString()
                              });
                              localStorage.setItem('reel_media_library', JSON.stringify(mediaItems.slice(-10)));
                              toast.success('Audio saved to Media Library! ✅');
                              refreshMediaLibrary();
                            } catch (err) {
                              toast.error('Failed to save audio');
                            }
                          }}
                          className="bg-green-50 border-green-300 text-green-700 hover:bg-green-100"
                        >
                          <Check className="w-4 h-4 mr-1" /> Save
                        </Button>
                        <a href={generatedAudio} download={`reel_audio_${Date.now()}.mp3`}>
                          <Button size="sm" variant="outline">
                            <Download className="w-4 h-4" />
                          </Button>
                        </a>
                      </div>
                    </div>
                    <audio 
                      ref={audioRef} 
                      src={generatedAudio} 
                      onEnded={() => setIsPlaying(false)}
                      className="w-full"
                      controls
                    />
                    <p className="text-xs text-gray-500">💡 Click "Save" to add to Media Library, or "Download" to get the MP3 file</p>
                    
                    {/* Continue to Step 3 Button */}
                    <Button 
                      onClick={() => {
                        document.getElementById('reel-step-3')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        toast.info('Voice ready! Now create your talking video.', { duration: 3000 });
                      }}
                      className="w-full bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white mt-2"
                    >
                      Next: Create Video <span className="ml-2">→</span>
                    </Button>
                  </div>
                )}
              </div>
              
              {/* Arrow connector for Step 2 to Step 3 */}
              {generatedAudio && (
                <div className="flex justify-center -my-3">
                  <div className="w-0.5 h-6 bg-gradient-to-b from-purple-400 to-green-500"></div>
                </div>
              )}
              
              {/* Step 3: Create Video */}
              <div 
                id="reel-step-3"
                className={`space-y-4 p-4 rounded-xl transition-all ${generatedAudio ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-200' : 'bg-gray-100 opacity-60 pointer-events-none'}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                    <span className="w-6 h-6 rounded-full bg-green-500 text-white flex items-center justify-center text-xs">3</span>
                    Create Talking Video
                    <Badge className="bg-gradient-to-r from-green-500 to-emerald-500 text-white text-xs ml-2">AI POWERED</Badge>
                  </div>
                  {generatedAudio && <Badge variant="outline" className="text-xs bg-white">🎙️ Audio ready</Badge>}
                </div>
                
                <div className="space-y-4">
                  {/* Upload Your Photo for Avatar */}
                  <div className="p-4 bg-white rounded-xl border-2 border-dashed border-pink-300">
                    <p className="text-sm font-medium text-gray-700 mb-3">📸 Upload your photo (your face will talk!)</p>
                    <div className="flex items-center gap-4">
                      <label className="flex-1 flex items-center justify-center gap-3 p-4 bg-gradient-to-r from-pink-50 to-rose-50 rounded-lg border-2 border-dashed border-pink-300 cursor-pointer hover:border-pink-500 hover:bg-pink-100 transition-all">
                        <input
                          type="file"
                          accept="image/*"
                          className="hidden"
                          disabled={!generatedAudio}
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              const reader = new FileReader();
                              reader.onload = (event) => {
                                setAvatarPhoto(event.target.result);
                                setAvatarPhotoPreview(event.target.result);
                                toast.success('Photo uploaded! Ready to generate video.');
                              };
                              reader.readAsDataURL(file);
                            }
                          }}
                        />
                        <Upload className="w-6 h-6 text-pink-500" />
                        <div>
                          <p className="font-semibold text-sm text-pink-700">Choose Photo</p>
                          <p className="text-xs text-pink-500">Clear face, good lighting</p>
                        </div>
                      </label>
                      
                      {avatarPhotoPreview && (
                        <div className="relative">
                          <img 
                            src={avatarPhotoPreview} 
                            alt="Avatar preview" 
                            className="w-20 h-20 object-cover rounded-xl border-2 border-pink-400"
                          />
                          <button
                            onClick={() => {
                              setAvatarPhoto(null);
                              setAvatarPhotoPreview(null);
                            }}
                            className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-red-600"
                          >
                            ✕
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Generate Video Button */}
                  <Button
                    onClick={async () => {
                      if (!avatarPhoto) {
                        toast.error('Please upload your photo first');
                        return;
                      }
                      if (!generatedAudio) {
                        toast.error('Please generate voice audio first');
                        return;
                      }
                      
                      setGeneratingHeygenVideo(true);
                      setHeygenVideoStatus('uploading');
                      
                      try {
                        toast.loading('Creating your talking avatar video...', { id: 'heygen-video', duration: 60000 });
                        
                        const res = await axios.post(`${API}/admin/ai-studio/heygen/generate-video`, {
                          photo_base64: avatarPhoto,
                          audio_base64: generatedAudio,
                          script: reelScript
                        });
                        
                        if (res.data.success) {
                          setHeygenVideoId(res.data.video_id);
                          setHeygenVideoStatus('processing');
                          toast.loading('Video is being generated... This may take 1-3 minutes.', { id: 'heygen-video' });
                          
                          // Start polling for status
                          setHeygenPolling(true);
                          let pollCount = 0;
                          const maxPolls = 60; // 5 minutes max
                          
                          const pollStatus = async () => {
                            try {
                              const statusRes = await axios.get(`${API}/admin/ai-studio/heygen/status/${res.data.video_id}`);
                              
                              if (statusRes.data.success) {
                                const status = statusRes.data.status;
                                setHeygenVideoStatus(status);
                                
                                if (status === 'completed') {
                                  setHeygenVideoUrl(statusRes.data.video_url);
                                  setHeygenPolling(false);
                                  setGeneratingHeygenVideo(false);
                                  toast.success('Video generated successfully! 🎉', { id: 'heygen-video' });
                                  
                                  // Auto-save to media library
                                  const mediaItems = JSON.parse(localStorage.getItem('reel_media_library') || '[]');
                                  mediaItems.push({
                                    id: Date.now(),
                                    type: 'link',
                                    name: '🎬 AI Reel - ' + (reelTopic.substring(0, 20) || 'Video'),
                                    data: statusRes.data.video_url,
                                    createdAt: new Date().toISOString()
                                  });
                                  localStorage.setItem('reel_media_library', JSON.stringify(mediaItems.slice(-10)));
                                  refreshMediaLibrary();
                                  return;
                                }
                                
                                if (status === 'failed') {
                                  setHeygenPolling(false);
                                  setGeneratingHeygenVideo(false);
                                  toast.error('Video generation failed: ' + (statusRes.data.error || 'Unknown error'), { id: 'heygen-video' });
                                  return;
                                }
                                
                                // Continue polling if still processing
                                pollCount++;
                                if (pollCount < maxPolls) {
                                  setTimeout(pollStatus, 5000); // Poll every 5 seconds
                                } else {
                                  setHeygenPolling(false);
                                  setGeneratingHeygenVideo(false);
                                  toast.error('Video generation timed out. Please try again.', { id: 'heygen-video' });
                                }
                              }
                            } catch (err) {
                              console.error('Polling error:', err);
                              pollCount++;
                              if (pollCount < maxPolls) {
                                setTimeout(pollStatus, 5000);
                              }
                            }
                          };
                          
                          // Start polling after 10 seconds
                          setTimeout(pollStatus, 10000);
                          
                        } else {
                          toast.error(res.data.error || 'Failed to start video generation', { id: 'heygen-video' });
                          setGeneratingHeygenVideo(false);
                        }
                      } catch (err) {
                        toast.error('Error: ' + (err.response?.data?.error || err.message), { id: 'heygen-video' });
                        setGeneratingHeygenVideo(false);
                      }
                    }}
                    disabled={generatingHeygenVideo || !avatarPhoto || !generatedAudio}
                    className="w-full bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white py-6 text-lg"
                  >
                    {generatingHeygenVideo ? (
                      <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> {heygenVideoStatus === 'uploading' ? 'Uploading...' : 'Generating Video...'}</>
                    ) : (
                      <><Video className="w-5 h-5 mr-2" /> Generate Talking Avatar Video</>
                    )}
                  </Button>
                  
                  {/* Video Status & Result */}
                  {heygenVideoStatus && (
                    <div className={`p-4 rounded-xl border-2 ${heygenVideoStatus === 'completed' ? 'bg-green-50 border-green-300' : heygenVideoStatus === 'failed' ? 'bg-red-50 border-red-300' : 'bg-blue-50 border-blue-300'}`}>
                      <div className="flex items-center gap-3">
                        {heygenVideoStatus === 'completed' ? (
                          <Check className="w-6 h-6 text-green-500" />
                        ) : heygenVideoStatus === 'failed' ? (
                          <span className="text-red-500 text-xl">✕</span>
                        ) : (
                          <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
                        )}
                        <div>
                          <p className="font-semibold text-sm">
                            {heygenVideoStatus === 'completed' ? 'Video Ready!' : 
                             heygenVideoStatus === 'failed' ? 'Generation Failed' :
                             heygenVideoStatus === 'processing' ? 'Processing your video...' :
                             'Uploading assets...'}
                          </p>
                          <p className="text-xs text-gray-500">
                            {heygenVideoStatus === 'processing' && 'This usually takes 1-3 minutes'}
                          </p>
                        </div>
                      </div>
                      
                      {heygenVideoUrl && (
                        <div className="mt-4 space-y-3">
                          <video 
                            src={heygenVideoUrl} 
                            controls 
                            className="w-full rounded-lg border"
                            style={{ maxHeight: '300px' }}
                          />
                          <div className="flex gap-2">
                            <a 
                              href={heygenVideoUrl} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="flex-1"
                            >
                              <Button variant="outline" className="w-full">
                                <ExternalLink className="w-4 h-4 mr-2" /> Open in New Tab
                              </Button>
                            </a>
                            <a 
                              href={heygenVideoUrl} 
                              download={`talking_avatar_${Date.now()}.mp4`}
                              className="flex-1"
                            >
                              <Button className="w-full bg-green-500 hover:bg-green-600">
                                <Download className="w-4 h-4 mr-2" /> Download Video
                              </Button>
                            </a>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  
                  <div className="p-3 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200 text-green-800 text-xs">
                    <strong>✨ Powered by HeyGen AI:</strong> Your photo will come to life and speak the audio with realistic lip-sync!
                  </div>
                </div>
              </div>
              
              {/* Step 4: Media Library */}
              <div className="space-y-4 p-4 bg-gray-50 rounded-xl border-2 border-dashed border-gray-300">
                <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                  <span className="w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs">4</span>
                  Media Library
                  <Badge variant="outline" className="ml-2 text-xs">Upload & Download</Badge>
                </div>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {/* Upload Photo */}
                  <div className="space-y-2">
                    <Label className="text-xs text-gray-500">Your Photo</Label>
                    <label className="flex flex-col items-center justify-center w-full h-24 bg-white border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-pink-400 hover:bg-pink-50 transition-colors">
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          
                          toast.loading('Compressing & saving...', { id: 'photo-upload' });
                          
                          try {
                            // Auto-compress image using canvas
                            const compressImage = (file, maxWidth = 800, quality = 0.7) => {
                              return new Promise((resolve) => {
                                const reader = new FileReader();
                                reader.onload = (e) => {
                                  const img = new Image();
                                  img.onload = () => {
                                    const canvas = document.createElement('canvas');
                                    let width = img.width;
                                    let height = img.height;
                                    
                                    // Scale down if too large
                                    if (width > maxWidth) {
                                      height = (height * maxWidth) / width;
                                      width = maxWidth;
                                    }
                                    
                                    canvas.width = width;
                                    canvas.height = height;
                                    const ctx = canvas.getContext('2d');
                                    ctx.drawImage(img, 0, 0, width, height);
                                    
                                    // Convert to compressed JPEG
                                    resolve(canvas.toDataURL('image/jpeg', quality));
                                  };
                                  img.src = e.target.result;
                                };
                                reader.readAsDataURL(file);
                              });
                            };
                            
                            const compressedData = await compressImage(file);
                            
                            const mediaItems = JSON.parse(localStorage.getItem('reel_media_library') || '[]');
                            mediaItems.push({
                              id: Date.now(),
                              type: 'image',
                              name: file.name,
                              data: compressedData,
                              createdAt: new Date().toISOString()
                            });
                            localStorage.setItem('reel_media_library', JSON.stringify(mediaItems.slice(-10)));
                            toast.success('Photo compressed & saved!', { id: 'photo-upload' });
                            refreshMediaLibrary();
                          } catch (err) {
                            toast.error('Upload failed: ' + err.message, { id: 'photo-upload' });
                          }
                        }}
                      />
                      <ImageIcon className="w-6 h-6 text-gray-400" />
                      <span className="text-xs text-gray-500 mt-1">Upload Photo</span>
                      <span className="text-xs text-green-500">Auto-compress</span>
                    </label>
                  </div>
                  
                  {/* Upload Video */}
                  <div className="space-y-2">
                    <Label className="text-xs text-gray-500">Video File</Label>
                    <label className="flex flex-col items-center justify-center w-full h-24 bg-white border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-purple-400 hover:bg-purple-50 transition-colors">
                      <input
                        type="file"
                        accept="video/*"
                        className="hidden"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          
                          toast.loading('Processing video...', { id: 'video-upload' });
                          
                          try {
                            // Create video thumbnail for preview - more robust version
                            const createVideoThumbnail = (file) => {
                              return new Promise((resolve, reject) => {
                                const video = document.createElement('video');
                                video.preload = 'auto'; // Changed from 'metadata' to 'auto' for full loading
                                video.muted = true;
                                video.playsInline = true;
                                video.crossOrigin = 'anonymous';
                                
                                let thumbnailCaptured = false;
                                
                                const captureFrame = () => {
                                  if (thumbnailCaptured) return;
                                  thumbnailCaptured = true;
                                  
                                  // Add delay to ensure frame is rendered
                                  setTimeout(() => {
                                    try {
                                      const canvas = document.createElement('canvas');
                                      const maxWidth = 400;
                                      let width = video.videoWidth || 640;
                                      let height = video.videoHeight || 360;
                                      
                                      if (width > maxWidth) {
                                        height = (height * maxWidth) / width;
                                        width = maxWidth;
                                      }
                                      
                                      canvas.width = width;
                                      canvas.height = height;
                                      const ctx = canvas.getContext('2d');
                                      ctx.drawImage(video, 0, 0, width, height);
                                      
                                      // Check if canvas is not blank (all black pixels)
                                      const imageData = ctx.getImageData(0, 0, Math.min(10, width), Math.min(10, height));
                                      const pixels = imageData.data;
                                      let hasContent = false;
                                      for (let i = 0; i < pixels.length; i += 4) {
                                        if (pixels[i] > 10 || pixels[i+1] > 10 || pixels[i+2] > 10) {
                                          hasContent = true;
                                          break;
                                        }
                                      }
                                      
                                      // If frame is black, try capturing again at a different time
                                      if (!hasContent && video.currentTime < video.duration - 1) {
                                        thumbnailCaptured = false;
                                        video.currentTime = Math.min(video.currentTime + 2, video.duration - 0.5);
                                        return;
                                      }
                                      
                                      URL.revokeObjectURL(video.src);
                                      resolve({
                                        thumbnail: canvas.toDataURL('image/jpeg', 0.7),
                                        duration: Math.round(video.duration),
                                        width: video.videoWidth,
                                        height: video.videoHeight
                                      });
                                    } catch (err) {
                                      URL.revokeObjectURL(video.src);
                                      reject(err);
                                    }
                                  }, 200); // 200ms delay for frame to render
                                };
                                
                                video.onloadeddata = () => {
                                  // Wait for video data to load, then seek
                                  video.currentTime = Math.min(2, video.duration / 4);
                                };
                                
                                video.onseeked = captureFrame;
                                
                                // Fallback: if video plays, capture frame
                                video.oncanplay = () => {
                                  if (!thumbnailCaptured) {
                                    video.currentTime = Math.min(2, video.duration / 4);
                                  }
                                };
                                
                                // Timeout fallback
                                setTimeout(() => {
                                  if (!thumbnailCaptured) {
                                    thumbnailCaptured = true;
                                    URL.revokeObjectURL(video.src);
                                    // Return a placeholder if capture failed
                                    resolve({
                                      thumbnail: null,
                                      duration: Math.round(video.duration || 0),
                                      width: video.videoWidth || 640,
                                      height: video.videoHeight || 360
                                    });
                                  }
                                }, 10000); // 10 second timeout
                                
                                video.onerror = (e) => {
                                  URL.revokeObjectURL(video.src);
                                  reject(new Error('Failed to process video: ' + (e.message || 'Unknown error')));
                                };
                                
                                video.src = URL.createObjectURL(file);
                                video.load(); // Explicitly load the video
                              });
                            };
                            
                            // If video is small enough, store it directly
                            if (file.size <= 3 * 1024 * 1024) {
                              const reader = new FileReader();
                              reader.onload = (event) => {
                                try {
                                  const mediaItems = JSON.parse(localStorage.getItem('reel_media_library') || '[]');
                                  mediaItems.push({
                                    id: Date.now(),
                                    type: 'video',
                                    name: file.name,
                                    data: event.target.result,
                                    createdAt: new Date().toISOString()
                                  });
                                  localStorage.setItem('reel_media_library', JSON.stringify(mediaItems.slice(-10)));
                                  toast.success('Video saved!', { id: 'video-upload' });
                                  refreshMediaLibrary();
                                } catch (storageError) {
                                  toast.error('Storage full! Try smaller video.', { id: 'video-upload' });
                                }
                              };
                              reader.readAsDataURL(file);
                            } else {
                              // For larger videos, save thumbnail + metadata
                              const videoInfo = await createVideoThumbnail(file);
                              const mediaItems = JSON.parse(localStorage.getItem('reel_media_library') || '[]');
                              mediaItems.push({
                                id: Date.now(),
                                type: 'video_preview',
                                name: file.name + ` (${videoInfo.duration}s preview)`,
                                data: videoInfo.thumbnail,
                                metadata: {
                                  duration: videoInfo.duration,
                                  width: videoInfo.width,
                                  height: videoInfo.height,
                                  originalSize: (file.size / 1024 / 1024).toFixed(1) + 'MB'
                                },
                                createdAt: new Date().toISOString()
                              });
                              localStorage.setItem('reel_media_library', JSON.stringify(mediaItems.slice(-10)));
                              toast.success(`Video preview saved! (${videoInfo.duration}s, ${(file.size/1024/1024).toFixed(1)}MB)`, { id: 'video-upload' });
                              refreshMediaLibrary();
                            }
                          } catch (err) {
                            toast.error('Video processing failed: ' + err.message, { id: 'video-upload' });
                          }
                        }}
                      />
                      <Video className="w-6 h-6 text-gray-400" />
                      <span className="text-xs text-gray-500 mt-1">Upload Video</span>
                      <span className="text-xs text-green-500">Auto-compress</span>
                    </label>
                  </div>
                  
                  {/* Upload Audio */}
                  <div className="space-y-2">
                    <Label className="text-xs text-gray-500">Audio File</Label>
                    <label className="flex flex-col items-center justify-center w-full h-24 bg-white border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-green-400 hover:bg-green-50 transition-colors">
                      <input
                        type="file"
                        accept="audio/*"
                        className="hidden"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (file) {
                            const reader = new FileReader();
                            reader.onload = (event) => {
                              const mediaItems = JSON.parse(localStorage.getItem('reel_media_library') || '[]');
                              mediaItems.push({
                                id: Date.now(),
                                type: 'audio',
                                name: file.name,
                                data: event.target.result,
                                createdAt: new Date().toISOString()
                              });
                              localStorage.setItem('reel_media_library', JSON.stringify(mediaItems.slice(-10)));
                              toast.success('Audio saved!');
                              refreshMediaLibrary();
                            };
                            reader.readAsDataURL(file);
                          }
                        }}
                      />
                      <Mic className="w-6 h-6 text-gray-400" />
                      <span className="text-xs text-gray-500 mt-1">Upload Audio</span>
                    </label>
                  </div>
                  
                  {/* Save Link */}
                  <div className="space-y-2">
                    <Label className="text-xs text-gray-500">Save Link/URL</Label>
                    <button
                      className="flex flex-col items-center justify-center w-full h-24 bg-white border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
                      onClick={() => {
                        const url = window.prompt('Enter URL to save:');
                        if (url && url.trim()) {
                          try {
                            new URL(url);
                            const mediaItems = JSON.parse(localStorage.getItem('reel_media_library') || '[]');
                            mediaItems.push({
                              id: Date.now(),
                              type: 'link',
                              name: url.substring(0, 30) + '...',
                              data: url,
                              createdAt: new Date().toISOString()
                            });
                            localStorage.setItem('reel_media_library', JSON.stringify(mediaItems.slice(-10)));
                            toast.success('Link saved!');
                            refreshMediaLibrary();
                          } catch {
                            toast.error('Please enter a valid URL');
                          }
                        }
                      }}
                    >
                      <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                      </svg>
                      <span className="text-xs text-gray-500 mt-1">Save Link</span>
                    </button>
                  </div>
                </div>
                
                {/* Saved Media Items */}
                <MediaLibraryItems refreshKey={mediaRefreshKey} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* UGC Image Tab */}
        <TabsContent value="image">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Step 2: Generate UGC Image</CardTitle>
              <CardDescription>Transform your product photo into influencer-style content</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>UGC Style</Label>
                <Select value={ugcStyle} onValueChange={setUgcStyle}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="natural">🌿 Natural & Authentic</SelectItem>
                    <SelectItem value="luxury">✨ Luxury & Premium</SelectItem>
                    <SelectItem value="minimal">⬜ Clean & Minimal</SelectItem>
                    <SelectItem value="lifestyle">🛁 Lifestyle & Routine</SelectItem>
                    <SelectItem value="closeup">🔍 Macro Close-up</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <Button 
                onClick={generateUGCImage}
                disabled={generatingImage || !uploadedImage}
                className="w-full bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#0a0a0a] hover:from-[#B8960F] hover:to-[#D4AF37]"
              >
                {generatingImage ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating UGC Image...</>
                ) : (
                  <><Sparkles className="w-4 h-4 mr-2" /> Generate UGC Image</>
                )}
              </Button>
              
              {ugcImage && (
                <div className="mt-6 space-y-4">
                  <p className="font-medium text-[#2D2A2E]">Generated UGC Image:</p>
                  <img src={ugcImage} alt="UGC" className="max-h-96 mx-auto rounded-xl shadow-lg" />
                  <Button 
                    onClick={() => downloadImage(ugcImage, `ugc_${productName || 'product'}_${Date.now()}.png`)}
                    className="w-full"
                    variant="outline"
                  >
                    <Download className="w-4 h-4 mr-2" /> Download Image
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Caption Tab */}
        <TabsContent value="caption">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Generate Social Caption</CardTitle>
              <CardDescription>AI-written captions with relevant hashtags</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Platform</Label>
                  <Select value={captionPlatform} onValueChange={setCaptionPlatform}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="instagram">📸 Instagram</SelectItem>
                      <SelectItem value="tiktok">🎵 TikTok</SelectItem>
                      <SelectItem value="facebook">📘 Facebook</SelectItem>
                      <SelectItem value="twitter">🐦 Twitter/X</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Tone</Label>
                  <Select value={captionTone} onValueChange={setCaptionTone}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="casual">😊 Casual & Friendly</SelectItem>
                      <SelectItem value="professional">💼 Professional</SelectItem>
                      <SelectItem value="fun">🎉 Fun & Playful</SelectItem>
                      <SelectItem value="luxurious">✨ Luxurious</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <Button 
                onClick={generateCaption}
                disabled={generatingCaption}
                className="w-full bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#0a0a0a]"
              >
                {generatingCaption ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating...</>
                ) : (
                  <><MessageSquare className="w-4 h-4 mr-2" /> Generate Caption</>
                )}
              </Button>
              
              {caption && (
                <div className="mt-4 space-y-4">
                  <div className="p-4 bg-[#FDF9F9] rounded-lg">
                    <div className="flex justify-between items-start mb-2">
                      <p className="font-medium text-[#2D2A2E]">Caption:</p>
                      <Button size="sm" variant="ghost" onClick={() => copyToClipboard(caption)}>
                        {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                      </Button>
                    </div>
                    <p className="text-[#5A5A5A] whitespace-pre-wrap">{caption}</p>
                  </div>
                  
                  {hashtags.length > 0 && (
                    <div className="p-4 bg-[#FDF9F9] rounded-lg">
                      <div className="flex justify-between items-start mb-2">
                        <p className="font-medium text-[#2D2A2E]">Hashtags:</p>
                        <Button size="sm" variant="ghost" onClick={() => copyToClipboard(hashtags.join(" "))}>
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {hashtags.map((tag, idx) => (
                          <Badge key={idx} variant="secondary" className="text-[#D4AF37]">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  <Button onClick={generateCaption} variant="outline" className="w-full">
                    <RefreshCw className="w-4 h-4 mr-2" /> Regenerate Caption
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Video Tab */}
        <TabsContent value="video">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Generate UGC Video</CardTitle>
              <CardDescription>Create short-form video content with Sora 2 AI</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Video Prompt (optional)</Label>
                <Textarea
                  value={videoPrompt}
                  onChange={(e) => setVideoPrompt(e.target.value)}
                  placeholder={`Leave blank for auto-generated prompt based on product name, or describe your ideal video scene...`}
                  rows={3}
                />
              </div>
              
              <div>
                <Label>Video Duration</Label>
                <Select value={videoDuration} onValueChange={setVideoDuration}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="4">4 seconds (Quick)</SelectItem>
                    <SelectItem value="8">8 seconds (Standard)</SelectItem>
                    <SelectItem value="12">12 seconds (Extended)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
                <p>⏱️ Video generation takes 2-5 minutes. Please wait after clicking generate.</p>
              </div>
              
              <Button 
                onClick={generateVideo}
                disabled={generatingVideo || (!productName && !videoPrompt)}
                className="w-full bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#0a0a0a]"
              >
                {generatingVideo ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating Video (2-5 min)...</>
                ) : (
                  <><Video className="w-4 h-4 mr-2" /> Generate Video</>
                )}
              </Button>
              
              {videoUrl && (
                <div className="mt-6 space-y-4">
                  <p className="font-medium text-[#2D2A2E]">Generated Video:</p>
                  <video 
                    src={videoUrl} 
                    controls 
                    className="w-full max-h-96 rounded-xl shadow-lg"
                  />
                  <a href={videoUrl} download>
                    <Button className="w-full" variant="outline">
                      <Download className="w-4 h-4 mr-2" /> Download Video
                    </Button>
                  </a>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Science Formulation Tab */}
        <TabsContent value="science">
          <ScienceTab />
        </TabsContent>
      </Tabs>
      
      {/* AI Search History Panel */}
      <Card className="border-dashed">
        <CardHeader className="cursor-pointer" onClick={() => setShowHistory(!showHistory)}>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <History className="w-5 h-5 text-[#D4AF37]" />
              AI Search History
              <Badge variant="secondary" className="ml-2">{aiHistory.length}</Badge>
            </CardTitle>
            <div className="flex items-center gap-2">
              {aiHistory.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    clearHistory();
                  }}
                  className="text-red-500 hover:text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="w-4 h-4 mr-1" />
                  Clear
                </Button>
              )}
              {showHistory ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </div>
          </div>
          <CardDescription>
            Your recent AI queries and responses are saved here
          </CardDescription>
        </CardHeader>
        
        {showHistory && (
          <CardContent>
            {aiHistory.length === 0 ? (
              <div className="text-center py-8 text-[#5A5A5A]">
                <History className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No AI searches yet</p>
                <p className="text-sm text-[#9A9A9A]">Your searches will appear here</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {aiHistory.map((item) => (
                  <div 
                    key={item.id}
                    className="p-4 bg-[#FDF9F9] rounded-lg hover:bg-[#FBF5F5] transition-colors cursor-pointer group"
                    onClick={() => loadFromHistory(item)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge 
                            variant="outline" 
                            className={
                              item.type === 'science' ? 'border-purple-300 text-purple-600' :
                              item.type === 'caption' ? 'border-blue-300 text-blue-600' :
                              item.type === 'image' ? 'border-green-300 text-green-600' :
                              'border-orange-300 text-orange-600'
                            }
                          >
                            {item.type === 'science' && <FlaskConical className="w-3 h-3 mr-1" />}
                            {item.type === 'caption' && <MessageSquare className="w-3 h-3 mr-1" />}
                            {item.type === 'image' && <ImageIcon className="w-3 h-3 mr-1" />}
                            {item.type === 'video' && <Video className="w-3 h-3 mr-1" />}
                            {item.type.charAt(0).toUpperCase() + item.type.slice(1)}
                          </Badge>
                          <span className="text-xs text-[#9A9A9A] flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(item.timestamp).toLocaleDateString()} {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        <p className="font-medium text-[#2D2A2E] text-sm truncate">{item.query}</p>
                        <p className="text-xs text-[#5A5A5A] line-clamp-2 mt-1">{item.response?.substring(0, 150)}...</p>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigator.clipboard.writeText(item.response);
                          toast.success('Copied to clipboard');
                        }}
                      >
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        )}
      </Card>
    </div>
  );
};

export default AIContentStudio;
