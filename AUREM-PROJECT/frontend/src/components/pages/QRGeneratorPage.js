import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { toast } from "sonner";
import QRCodeLib from "qrcode";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { 
  QrCode, Download, Copy, Link, Sparkles, 
  Palette, RefreshCw, CheckCircle, Star,
  Instagram, Facebook, Twitter, Globe, Mail,
  Upload, History, Edit, Trash2, ExternalLink, Save, Clock
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const QRGeneratorPage = () => {
  const navigate = useNavigate();
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);
  const [url, setUrl] = useState("");
  const [qrGenerated, setQrGenerated] = useState(false);
  const [qrDataUrl, setQrDataUrl] = useState("");
  const [size, setSize] = useState(256);
  const [fgColor, setFgColor] = useState("#000000");
  const [bgColor, setBgColor] = useState("#FFFFFF");
  const [generating, setGenerating] = useState(false);
  
  // New states for upload & history
  const [activeTab, setActiveTab] = useState("generate");
  const [uploadedImage, setUploadedImage] = useState(null);
  const [decodedUrl, setDecodedUrl] = useState("");
  const [newDestination, setNewDestination] = useState("");
  const [qrName, setQrName] = useState("");
  const [decoding, setDecoding] = useState(false);
  const [qrHistory, setQrHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [savingQr, setSavingQr] = useState(false);

  const presetLinks = [
    { name: "Google Review", icon: Star, placeholder: "https://g.page/r/your-review-link" },
    { name: "Instagram", icon: Instagram, placeholder: "https://instagram.com/yourusername" },
    { name: "Facebook", icon: Facebook, placeholder: "https://facebook.com/yourpage" },
    { name: "Twitter/X", icon: Twitter, placeholder: "https://twitter.com/yourusername" },
    { name: "Website", icon: Globe, placeholder: "https://yourwebsite.com" },
    { name: "Email", icon: Mail, placeholder: "mailto:your@email.com" },
  ];

  const colorPresets = [
    { fg: "#000000", bg: "#FFFFFF", name: "Classic" },
    { fg: "#1a1a2e", bg: "#FFFFFF", name: "Dark Blue" },
    { fg: "#7c3aed", bg: "#FFFFFF", name: "Purple" },
    { fg: "#059669", bg: "#FFFFFF", name: "Emerald" },
    { fg: "#dc2626", bg: "#FFFFFF", name: "Red" },
    { fg: "#000000", bg: "#fef3c7", name: "Gold" },
    { fg: "#1e40af", bg: "#dbeafe", name: "Blue" },
    { fg: "#be185d", bg: "#fce7f3", name: "Pink" },
  ];

  // Load QR history on mount
  useEffect(() => {
    if (activeTab === "history") {
      loadQrHistory();
    }
  }, [activeTab]);

  const loadQrHistory = async () => {
    setLoadingHistory(true);
    try {
      const token = localStorage.getItem("reroots_token");
      const res = await axios.get(`${API}/admin/qr/history`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.data.success) {
        const allHistory = [
          ...(res.data.generated_history || []).map(q => ({ ...q, type: 'generated' })),
          ...(res.data.imported_redirects || []).map(q => ({ ...q, type: 'imported' })),
          ...(res.data.dynamic_qr_codes || []).map(q => ({ ...q, type: 'dynamic' }))
        ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        setQrHistory(allHistory);
      }
    } catch (error) {
      console.error("Failed to load QR history:", error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const generateQR = async () => {
    if (!url.trim()) {
      toast.error("Please enter a URL or link");
      return;
    }

    // Basic URL validation
    let finalUrl = url.trim();
    if (!finalUrl.startsWith("http") && !finalUrl.startsWith("mailto:") && !finalUrl.startsWith("tel:")) {
      finalUrl = "https://" + finalUrl;
    }

    setGenerating(true);
    try {
      const dataUrl = await QRCodeLib.toDataURL(finalUrl, {
        width: size,
        margin: 2,
        color: {
          dark: fgColor,
          light: bgColor
        },
        errorCorrectionLevel: 'H'
      });
      
      setQrDataUrl(dataUrl);
      setQrGenerated(true);
      toast.success("QR Code generated!");
    } catch (error) {
      console.error("QR Generation error:", error);
      toast.error("Failed to generate QR code. Please check your URL.");
    } finally {
      setGenerating(false);
    }
  };

  const downloadQR = (format = 'png') => {
    if (!qrDataUrl) return;

    const link = document.createElement('a');
    link.download = `qr-code-${Date.now()}.${format}`;
    link.href = qrDataUrl;
    link.click();
    toast.success(`QR Code downloaded as ${format.toUpperCase()}!`);
  };

  const saveQrToHistory = async () => {
    if (!qrDataUrl || !url) return;
    
    setSavingQr(true);
    try {
      const token = localStorage.getItem("reroots_token");
      await axios.post(`${API}/admin/qr/save-generated`, {
        url: url,
        name: qrName || `QR for ${url.substring(0, 30)}...`,
        qr_image: qrDataUrl,
        qr_type: "custom"
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("QR saved to history!");
      setQrName("");
    } catch (error) {
      toast.error("Failed to save QR. Make sure you're logged in as admin.");
    } finally {
      setSavingQr(false);
    }
  };

  const copyQRToClipboard = async () => {
    if (!qrDataUrl) return;

    try {
      const response = await fetch(qrDataUrl);
      const blob = await response.blob();
      await navigator.clipboard.write([
        new ClipboardItem({ 'image/png': blob })
      ]);
      toast.success("QR Code copied to clipboard!");
    } catch (error) {
      toast.error("Failed to copy. Try downloading instead.");
    }
  };

  const applyColorPreset = (preset) => {
    setFgColor(preset.fg);
    setBgColor(preset.bg);
    if (qrGenerated) {
      // Regenerate with new colors
      setTimeout(generateQR, 100);
    }
  };

  // Handle QR image upload
  const handleImageUpload = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    if (!file.type.startsWith('image/')) {
      toast.error("Please upload an image file");
      return;
    }
    
    const reader = new FileReader();
    reader.onload = (e) => {
      setUploadedImage(e.target.result);
      setDecodedUrl("");
      setNewDestination("");
    };
    reader.readAsDataURL(file);
  };

  // Decode uploaded QR code
  const decodeQrImage = async () => {
    if (!uploadedImage) {
      toast.error("Please upload a QR code image first");
      return;
    }
    
    setDecoding(true);
    try {
      const token = localStorage.getItem("reroots_token");
      const res = await axios.post(`${API}/admin/qr/decode`, {
        image: uploadedImage
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.data.success && res.data.url) {
        setDecodedUrl(res.data.url);
        setNewDestination(res.data.url);
        toast.success("QR code decoded successfully!");
      } else {
        toast.error(res.data.message || "Could not decode QR code");
      }
    } catch (error) {
      toast.error("Failed to decode QR code. Make sure you're logged in as admin.");
    } finally {
      setDecoding(false);
    }
  };

  // Import/save old QR with new redirect
  const importOldQr = async () => {
    if (!decodedUrl) {
      toast.error("Please decode a QR code first");
      return;
    }
    
    try {
      const token = localStorage.getItem("reroots_token");
      await axios.post(`${API}/admin/qr/import`, {
        original_url: decodedUrl,
        new_destination: newDestination,
        name: qrName || `Imported QR - ${decodedUrl.substring(0, 30)}`,
        qr_image: uploadedImage
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success("QR code imported and redirect saved!");
      setUploadedImage(null);
      setDecodedUrl("");
      setNewDestination("");
      setQrName("");
      loadQrHistory();
    } catch (error) {
      toast.error("Failed to import QR code");
    }
  };

  // Delete QR from history
  const deleteFromHistory = async (qrId) => {
    try {
      const token = localStorage.getItem("reroots_token");
      await axios.delete(`${API}/admin/qr/history/${qrId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("QR deleted from history");
      setQrHistory(prev => prev.filter(q => q.id !== qrId));
    } catch (error) {
      toast.error("Failed to delete QR");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#1a1a2e] via-[#16213e] to-[#0f0f1a]">
      <Helmet>
        <title>Free QR Code Generator | ReRoots</title>
        <meta name="description" content="Generate free QR codes for any link - Google Reviews, Social Media, Websites, and more. No signup required." />
      </Helmet>

      {/* Hero Section */}
      <div className="relative py-12 px-4 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/10 to-teal-500/10" />
        <div className="max-w-4xl mx-auto text-center relative">
          <Badge className="mb-4 bg-emerald-500/20 text-emerald-300 border-emerald-500/30">
            <Sparkles className="w-3 h-3 mr-1" /> 100% Free
          </Badge>
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Free QR Code Generator
          </h1>
          <p className="text-xl text-white/70 mb-6 max-w-2xl mx-auto">
            Create custom QR codes for your business - Google Reviews, Social Media, Menus, and more. 
            No signup required!
          </p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 pb-12">
        {/* Main Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-8 bg-white/10">
            <TabsTrigger value="generate" className="text-white data-[state=active]:bg-emerald-500 data-[state=active]:text-white">
              <QrCode className="w-4 h-4 mr-2" />
              Generate
            </TabsTrigger>
            <TabsTrigger value="import" className="text-white data-[state=active]:bg-blue-500 data-[state=active]:text-white">
              <Upload className="w-4 h-4 mr-2" />
              Import Old QR
            </TabsTrigger>
            <TabsTrigger value="history" className="text-white data-[state=active]:bg-purple-500 data-[state=active]:text-white">
              <History className="w-4 h-4 mr-2" />
              History
            </TabsTrigger>
          </TabsList>

          {/* GENERATE TAB */}
          <TabsContent value="generate">
            <div className="grid lg:grid-cols-2 gap-8">
              {/* Input Section */}
              <div className="space-y-6">
                {/* URL Input */}
                <Card className="bg-white/5 border-white/10">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center gap-2">
                      <Link className="w-4 h-4 text-emerald-400" />
                      Enter Your Link
                    </CardTitle>
                    <CardDescription className="text-white/60">
                      Paste any URL to generate a QR code
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Input
                      placeholder="https://g.page/r/CY76Se2EyM-_EAE/review"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      className="bg-white/10 border-white/20 text-white placeholder:text-white/40 h-12 text-lg"
                    />
                    
                    {/* Quick Link Buttons */}
                    <div className="flex flex-wrap gap-2">
                      {presetLinks.map((link, idx) => (
                        <Button
                          key={idx}
                          variant="outline"
                          size="sm"
                          className="border-white/20 text-white/70 hover:bg-white/10 hover:text-white"
                          onClick={() => setUrl(link.placeholder)}
                        >
                          <link.icon className="w-3 h-3 mr-1" />
                          {link.name}
                        </Button>
                      ))}
                    </div>

                    {/* Generate Button */}
                    <Button
                      onClick={generateQR}
                      disabled={generating || !url.trim()}
                      className="w-full h-12 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white font-semibold text-lg"
                    >
                      {generating ? (
                        <>
                          <RefreshCw className="w-5 h-5 mr-2 animate-spin" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <QrCode className="w-5 h-5 mr-2" />
                          Generate QR Code
                        </>
                      )}
                    </Button>
                  </CardContent>
                </Card>

                {/* Customization */}
                <Card className="bg-white/5 border-white/10">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center gap-2">
                      <Palette className="w-5 h-5 text-purple-400" />
                      Customize
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Size Slider */}
                    <div>
                      <label className="text-sm text-white/70 mb-2 block">
                        Size: {size}px
                      </label>
                      <Slider
                        value={[size]}
                        onValueChange={([val]) => setSize(val)}
                        min={128}
                        max={512}
                        step={32}
                        className="w-full"
                      />
                    </div>

                    {/* Color Pickers */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-sm text-white/70 mb-2 block">QR Color</label>
                        <div className="flex gap-2">
                          <input
                            type="color"
                            value={fgColor}
                            onChange={(e) => setFgColor(e.target.value)}
                            className="w-12 h-10 rounded cursor-pointer"
                          />
                          <Input
                            value={fgColor}
                            onChange={(e) => setFgColor(e.target.value)}
                            className="bg-white/10 border-white/20 text-white flex-1"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="text-sm text-white/70 mb-2 block">Background</label>
                        <div className="flex gap-2">
                          <input
                            type="color"
                            value={bgColor}
                            onChange={(e) => setBgColor(e.target.value)}
                            className="w-12 h-10 rounded cursor-pointer"
                          />
                          <Input
                            value={bgColor}
                            onChange={(e) => setBgColor(e.target.value)}
                            className="bg-white/10 border-white/20 text-white flex-1"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Color Presets */}
                    <div>
                      <label className="text-sm text-white/70 mb-2 block">Color Presets</label>
                      <div className="flex flex-wrap gap-2">
                        {colorPresets.map((preset, idx) => (
                          <button
                            key={idx}
                            onClick={() => applyColorPreset(preset)}
                            className="w-10 h-10 rounded-lg border-2 border-white/20 hover:border-white/50 transition-all overflow-hidden"
                            title={preset.name}
                          >
                            <div className="w-full h-1/2" style={{ backgroundColor: preset.bg }} />
                            <div className="w-full h-1/2" style={{ backgroundColor: preset.fg }} />
                          </button>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Preview Section */}
              <div className="space-y-6">
                <Card className="bg-white/5 border-white/10">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center gap-2">
                      <QrCode className="w-5 h-5 text-emerald-400" />
                      Your QR Code
                    </CardTitle>
                    <CardDescription className="text-white/60">
                      {qrGenerated ? "Ready to download or share" : "Enter a URL and click generate"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="aspect-square max-w-sm mx-auto rounded-xl overflow-hidden bg-white flex items-center justify-center">
                      {qrGenerated && qrDataUrl ? (
                        <img 
                          src={qrDataUrl} 
                          alt="Generated QR Code" 
                          className="w-full h-full object-contain p-4"
                        />
                      ) : (
                        <div className="text-center p-8">
                          <QrCode className="w-24 h-24 mx-auto mb-4 text-gray-300" />
                          <p className="text-gray-400">Your QR code will appear here</p>
                        </div>
                      )}
                    </div>

                    {/* Download/Copy/Save Buttons */}
                    {qrGenerated && (
                      <div className="mt-6 space-y-3">
                        {/* Save to History */}
                        <div className="flex gap-2">
                          <Input
                            placeholder="Name this QR (optional)"
                            value={qrName}
                            onChange={(e) => setQrName(e.target.value)}
                            className="bg-white/10 border-white/20 text-white placeholder:text-white/40 flex-1"
                          />
                          <Button
                            onClick={saveQrToHistory}
                            disabled={savingQr}
                            className="bg-purple-500 hover:bg-purple-600"
                          >
                            {savingQr ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                          </Button>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-3">
                          <Button
                            onClick={() => downloadQR('png')}
                            className="bg-emerald-500 hover:bg-emerald-600"
                          >
                            <Download className="w-4 h-4 mr-2" />
                            Download PNG
                          </Button>
                          <Button
                            onClick={copyQRToClipboard}
                            variant="outline"
                            className="border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/20"
                          >
                            <Copy className="w-4 h-4 mr-2" />
                            Copy Image
                          </Button>
                        </div>
                        <p className="text-xs text-center text-white/50">
                          High-quality {size}x{size}px image with error correction
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Tips Card */}
                <Card className="bg-gradient-to-br from-emerald-500/10 to-teal-500/5 border-emerald-500/30">
                  <CardContent className="p-6">
                    <h3 className="font-bold text-white mb-3 flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-emerald-400" />
                      Pro Tips
                    </h3>
                    <ul className="space-y-2 text-sm text-white/70">
                      <li className="flex items-start gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                        <span>Save to history to manage your QR codes later</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                        <span>Use "Import Old QR" tab to update existing printed codes</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                        <span>Test the QR code with your phone before printing</span>
                      </li>
                    </ul>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* IMPORT TAB - Upload old QR codes */}
          <TabsContent value="import">
            <div className="grid lg:grid-cols-2 gap-8">
              <div className="space-y-6">
                <Card className="bg-white/5 border-white/10">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center gap-2">
                      <Upload className="w-5 h-5 text-blue-400" />
                      Upload Old QR Code
                    </CardTitle>
                    <CardDescription className="text-white/60">
                      Upload a QR code image to decode and update its destination
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* File Upload */}
                    <div 
                      className="border-2 border-dashed border-white/20 rounded-xl p-8 text-center cursor-pointer hover:border-blue-400/50 transition-colors"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleImageUpload}
                        accept="image/*"
                        className="hidden"
                      />
                      {uploadedImage ? (
                        <img src={uploadedImage} alt="Uploaded QR" className="max-w-[200px] mx-auto rounded-lg" />
                      ) : (
                        <>
                          <Upload className="w-12 h-12 mx-auto mb-4 text-white/40" />
                          <p className="text-white/60">Click to upload QR code image</p>
                          <p className="text-white/40 text-sm mt-2">PNG, JPG, or GIF</p>
                        </>
                      )}
                    </div>

                    {/* Decode Button */}
                    <Button
                      onClick={decodeQrImage}
                      disabled={!uploadedImage || decoding}
                      className="w-full bg-blue-500 hover:bg-blue-600"
                    >
                      {decoding ? (
                        <>
                          <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                          Decoding...
                        </>
                      ) : (
                        <>
                          <QrCode className="w-4 h-4 mr-2" />
                          Decode QR Code
                        </>
                      )}
                    </Button>

                    {/* Decoded URL & New Destination */}
                    {decodedUrl && (
                      <div className="space-y-4 pt-4 border-t border-white/10">
                        <div>
                          <label className="text-sm text-white/70 mb-2 block">Original URL (in QR)</label>
                          <Input
                            value={decodedUrl}
                            readOnly
                            className="bg-white/5 border-white/20 text-white/70"
                          />
                        </div>
                        <div>
                          <label className="text-sm text-white/70 mb-2 block">New Destination URL</label>
                          <Input
                            value={newDestination}
                            onChange={(e) => setNewDestination(e.target.value)}
                            placeholder="https://new-destination.com"
                            className="bg-white/10 border-white/20 text-white"
                          />
                        </div>
                        <div>
                          <label className="text-sm text-white/70 mb-2 block">Name (optional)</label>
                          <Input
                            value={qrName}
                            onChange={(e) => setQrName(e.target.value)}
                            placeholder="e.g., Thank You Card QR"
                            className="bg-white/10 border-white/20 text-white"
                          />
                        </div>
                        <Button
                          onClick={importOldQr}
                          className="w-full bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600"
                        >
                          <Save className="w-4 h-4 mr-2" />
                          Save & Create Redirect
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Info Panel */}
              <div className="space-y-6">
                <Card className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 border-blue-500/30">
                  <CardContent className="p-6">
                    <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-blue-400" />
                      How It Works
                    </h3>
                    <ol className="space-y-4 text-sm text-white/70">
                      <li className="flex items-start gap-3">
                        <span className="w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold shrink-0">1</span>
                        <span>Upload the QR code image from your printed materials</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold shrink-0">2</span>
                        <span>We'll decode it and show you the URL inside</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold shrink-0">3</span>
                        <span>Enter the new destination URL you want it to go to</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold shrink-0">4</span>
                        <span>We'll save the redirect - no reprinting needed!</span>
                      </li>
                    </ol>
                  </CardContent>
                </Card>

                <Card className="bg-yellow-500/10 border-yellow-500/30">
                  <CardContent className="p-6">
                    <h3 className="font-bold text-yellow-300 mb-2">⚠️ Important Note</h3>
                    <p className="text-sm text-white/70">
                      This feature works best for QR codes that point to YOUR website (reroots.ca). 
                      For QR codes pointing to external sites (Google, Instagram, etc.), the redirect must 
                      be set up on those platforms.
                    </p>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* HISTORY TAB */}
          <TabsContent value="history">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-white flex items-center gap-2">
                    <History className="w-5 h-5 text-purple-400" />
                    QR Code History
                  </CardTitle>
                  <CardDescription className="text-white/60">
                    All your generated and imported QR codes
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadQrHistory}
                  disabled={loadingHistory}
                  className="border-white/20 text-white/70 hover:bg-white/10"
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${loadingHistory ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </CardHeader>
              <CardContent>
                {loadingHistory ? (
                  <div className="text-center py-12">
                    <RefreshCw className="w-8 h-8 mx-auto mb-4 text-white/40 animate-spin" />
                    <p className="text-white/60">Loading history...</p>
                  </div>
                ) : qrHistory.length === 0 ? (
                  <div className="text-center py-12">
                    <History className="w-12 h-12 mx-auto mb-4 text-white/20" />
                    <p className="text-white/60">No QR codes in history yet</p>
                    <p className="text-white/40 text-sm mt-2">Generate or import QR codes to see them here</p>
                  </div>
                ) : (
                  <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {qrHistory.map((qr) => (
                      <div
                        key={qr.id}
                        className="bg-white/5 rounded-lg p-4 border border-white/10 hover:border-white/20 transition-colors"
                      >
                        {/* QR Image */}
                        {qr.qr_image && (
                          <div className="bg-white rounded-lg p-2 mb-3">
                            <img src={qr.qr_image} alt={qr.name} className="w-full max-w-[150px] mx-auto" />
                          </div>
                        )}
                        
                        {/* Details */}
                        <h4 className="text-white font-medium truncate mb-1">{qr.name || 'Unnamed QR'}</h4>
                        <p className="text-white/50 text-xs truncate mb-2">{qr.url || qr.original_url}</p>
                        
                        {/* Type Badge */}
                        <Badge className={`text-xs mb-3 ${
                          qr.type === 'generated' ? 'bg-emerald-500/20 text-emerald-300' :
                          qr.type === 'imported' ? 'bg-blue-500/20 text-blue-300' :
                          'bg-purple-500/20 text-purple-300'
                        }`}>
                          {qr.type === 'generated' ? 'Generated' : qr.type === 'imported' ? 'Imported' : 'Dynamic'}
                        </Badge>
                        
                        {/* Date */}
                        <div className="flex items-center text-white/40 text-xs mb-3">
                          <Clock className="w-3 h-3 mr-1" />
                          {new Date(qr.created_at).toLocaleDateString()}
                        </div>
                        
                        {/* Actions */}
                        <div className="flex gap-2">
                          {qr.qr_image && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="flex-1 border-white/20 text-white/70 hover:bg-white/10"
                              onClick={() => {
                                const link = document.createElement('a');
                                link.download = `${qr.name || 'qr-code'}.png`;
                                link.href = qr.qr_image;
                                link.click();
                              }}
                            >
                              <Download className="w-3 h-3" />
                            </Button>
                          )}
                          {(qr.url || qr.original_url) && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="flex-1 border-white/20 text-white/70 hover:bg-white/10"
                              onClick={() => window.open(qr.url || qr.original_url, '_blank')}
                            >
                              <ExternalLink className="w-3 h-3" />
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-red-500/30 text-red-400 hover:bg-red-500/20"
                            onClick={() => deleteFromHistory(qr.id)}
                          >
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* Back to Home */}
      <div className="text-center pb-12">
        <Button
          variant="ghost"
          onClick={() => navigate("/")}
          className="text-white/60 hover:text-white"
        >
          ← Back to Home
        </Button>
      </div>
    </div>
  );
};

export default QRGeneratorPage;
