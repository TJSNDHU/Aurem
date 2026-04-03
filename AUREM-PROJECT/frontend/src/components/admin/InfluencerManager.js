import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useAdminBrand } from "./useAdminBrand";
import { 
  Edit, 
  Trash2, 
  Plus, 
  Check, 
  X, 
  ChevronDown, 
  ChevronUp, 
  Mail, 
  Phone, 
  Users, 
  DollarSign, 
  Send, 
  Ticket,
  Link2,
  Gift,
  Copy,
  Trophy,
  Loader2,
  ExternalLink,
  Eye,
  EyeOff,
  Upload,
  FileText,
  Tag,
  Instagram,
  Play,
  Pause,
  MessageCircle,
  Globe,
  Sparkles,
  Settings,
  RefreshCw,
  Shield,
  Search,
  CreditCard
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { ImageUploader } from "@/components/ImageUploader";

// API URL configuration
const getBackendUrl = () => {
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    return window.location.origin;
  }
  return window.location.origin;
};

const BACKEND_URL = getBackendUrl();
const API = `${BACKEND_URL}/api`;

const InfluencerManager = () => {
  const { name: brandName, isLaVela } = useAdminBrand();
  
  const [applications, setApplications] = useState([]);
  const [stats, setStats] = useState({ total: 0, pending: 0, approved: 0, active: 0 });
  const [loading, setLoading] = useState(true);
  const [selectedInfluencer, setSelectedInfluencer] = useState(null);
  const [filterStatus, setFilterStatus] = useState("all");
  const [showDetails, setShowDetails] = useState(false);
  const [programSettings, setProgramSettings] = useState(null);
  const [showSettingsEdit, setShowSettingsEdit] = useState(false);
  const [showLeaderboardEdit, setShowLeaderboardEdit] = useState(false);
  const [editingSettings, setEditingSettings] = useState({
    commission_rate: 15,
    customer_discount_value: 50,
    min_followers: 1000
  });
  const [leaderboardSettings, setLeaderboardSettings] = useState({
    reset_period: "monthly",
    first_prize: 500,
    second_prize: 250,
    third_prize: 100,
    prize_type: "cash" // cash or spotlight
  });
  const [savingSettings, setSavingSettings] = useState(false);
  
  // Landing Page Settings State
  const [showLandingPageSettings, setShowLandingPageSettings] = useState(false);
  const [landingPageSettings, setLandingPageSettings] = useState({
    // Banner settings
    banner_enabled: true,
    banner_text: "50% OFF",
    banner_color: "#FFD700",
    // Hero image
    hero_image_url: "",
    hero_product_image_url: "",
    // Partner tiers visibility
    show_oroe_tier: true,
    show_reroots_tier: true,
    show_lavela_tier: true,
    // Tier customization
    oroe_commission: 25,
    oroe_discount: 15,
    oroe_bonus: 1000,
    reroots_commission: 15,
    reroots_discount: 20,
    reroots_bonus: 500,
    lavela_commission: 12,
    lavela_discount: 25,
    lavela_bonus: 250
  });
  const [savingLandingPage, setSavingLandingPage] = useState(false);
  
  // Influencer Preview State
  const [showInfluencerPreview, setShowInfluencerPreview] = useState(false);
  const [previewPartner, setPreviewPartner] = useState(null);
  
  // Partner Messaging State
  const [showMessageModal, setShowMessageModal] = useState(false);
  const [messageTarget, setMessageTarget] = useState(null);
  const [messageData, setMessageData] = useState({
    type: "message",
    subject: "",
    content: "",
    priority: "normal",
    files: [],
    send_email: true,
    send_sms: false
  });
  const [sendingMessage, setSendingMessage] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [partnerMessages, setPartnerMessages] = useState([]);
  const [showMessagesHistory, setShowMessagesHistory] = useState(false);
  
  // Partner Vouchers State
  const [showVoucherModal, setShowVoucherModal] = useState(false);
  const [voucherTarget, setVoucherTarget] = useState(null);
  const [voucherData, setVoucherData] = useState({
    code: "",
    discount_type: "percentage",
    discount_value: 10,
    partner_commission: 15,
    min_order: 0,
    max_uses: 0,
    valid_from: "",
    valid_until: "",
    description: "",
    is_active: true
  });
  const [creatingVoucher, setCreatingVoucher] = useState(false);
  const [partnerVouchers, setPartnerVouchers] = useState([]);
  const [showVouchersHistory, setShowVouchersHistory] = useState(false);
  
  // Partner Referrals State
  const [showReferralModal, setShowReferralModal] = useState(false);
  const [referralTarget, setReferralTarget] = useState(null);
  const [referralData, setReferralData] = useState({
    name: "Partner Referral Program",
    reward_discount_percent: 15,
    required_referrals: 3,
    referral_action: "signup"
  });
  const [creatingReferral, setCreatingReferral] = useState(false);
  const [partnerReferrals, setPartnerReferrals] = useState([]);
  const [showReferralsHistory, setShowReferralsHistory] = useState(false);
  
  // Partner Live Chat State
  const [showChatPanel, setShowChatPanel] = useState(false);
  const [chatConversations, setChatConversations] = useState([]);
  const [selectedChatPartner, setSelectedChatPartner] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [newChatMessage, setNewChatMessage] = useState("");
  const [loadingChat, setLoadingChat] = useState(false);
  const [sendingChat, setSendingChat] = useState(false);
  const chatMessagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  
  // Online Status State
  const [onlinePartners, setOnlinePartners] = useState({});
  
  const token = localStorage.getItem("reroots_token");

  const fetchInfluencers = async () => {
    const currentToken = localStorage.getItem("reroots_token");
    if (!currentToken) {
      toast.error("Please log in to view partners");
      setLoading(false);
      return;
    }
    try {
      const res = await axios.get(`${API}/admin/influencers`, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      setApplications(res.data.applications || []);
      setStats(res.data.stats || {});
    } catch (error) {
      console.error("Fetch influencers error:", error);
      if (error.response?.status === 401 || error.response?.status === 403) {
        toast.error("Session expired. Please log in again.");
      } else {
        toast.error("Failed to fetch influencers");
      }
    }
    setLoading(false);
  };

  const fetchSettings = async () => {
    try {
      const res = await axios.get(`${API}/partner-program`);
      setProgramSettings(res.data);
      setEditingSettings({
        commission_rate: res.data.influencer_program?.commission_rate || 10,
        customer_discount_value: res.data.influencer_program?.customer_discount_value || 50,
        min_followers: res.data.influencer_program?.min_followers || 1000
      });
      // Leaderboard settings
      if (res.data.leaderboard_settings) {
        setLeaderboardSettings({
          reset_period: res.data.leaderboard_settings.reset_period || "monthly",
          first_prize: res.data.leaderboard_settings.first_prize || 500,
          second_prize: res.data.leaderboard_settings.second_prize || 250,
          third_prize: res.data.leaderboard_settings.third_prize || 100,
          prize_type: res.data.leaderboard_settings.prize_type || "cash"
        });
      }
    } catch (error) {
      console.error("Failed to fetch partner program settings:", error);
    }
  };

  const saveSettings = async () => {
    const currentToken = localStorage.getItem("reroots_token");
    setSavingSettings(true);
    try {
      // Get current store settings
      const storeRes = await axios.get(`${API}/admin/store-settings`, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      const currentSettings = storeRes.data || {};
      
      // Update influencer program settings
      const updatedSettings = {
        ...currentSettings,
        influencer_program: {
          ...currentSettings.influencer_program,
          commission_rate: parseFloat(editingSettings.commission_rate),
          customer_discount_value: parseFloat(editingSettings.customer_discount_value),
          min_followers: parseInt(editingSettings.min_followers)
        },
        leaderboard_settings: {
          reset_period: leaderboardSettings.reset_period,
          first_prize: parseFloat(leaderboardSettings.first_prize),
          second_prize: parseFloat(leaderboardSettings.second_prize),
          third_prize: parseFloat(leaderboardSettings.third_prize),
          prize_type: leaderboardSettings.prize_type
        }
      };
      
      await axios.put(`${API}/admin/store-settings`, updatedSettings, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success("Settings saved!");
      setShowSettingsEdit(false);
      setShowLeaderboardEdit(false);
      fetchSettings();
    } catch (error) {
      toast.error("Failed to save settings");
    }
    setSavingSettings(false);
  };

  // Partner Live Chat Functions
  const fetchChatConversations = async () => {
    const currentToken = localStorage.getItem("reroots_token");
    try {
      const res = await axios.get(`${API}/admin/partner-chats`, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      setChatConversations(res.data.conversations || []);
    } catch (error) {
      console.error("Failed to fetch chat conversations:", error);
    }
  };

  const fetchChatMessages = async (partnerId) => {
    const currentToken = localStorage.getItem("reroots_token");
    setLoadingChat(true);
    try {
      const res = await axios.get(`${API}/admin/partner-chat/${partnerId}`, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      setChatMessages(res.data.messages || []);
      // Update conversation list to reflect read status
      setChatConversations(prev => prev.map(c => 
        c.partner_id === partnerId ? { ...c, unread_count: 0 } : c
      ));
    } catch (error) {
      toast.error("Failed to fetch messages");
    }
    setLoadingChat(false);
  };

  const sendChatMessage = async () => {
    if (!newChatMessage.trim() || !selectedChatPartner || sendingChat) return;
    
    const currentToken = localStorage.getItem("reroots_token");
    setSendingChat(true);
    try {
      await axios.post(`${API}/admin/partner-chat/send`, {
        partner_id: selectedChatPartner.partner_id,
        message: newChatMessage.trim()
      }, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      setNewChatMessage("");
      fetchChatMessages(selectedChatPartner.partner_id);
      toast.success("Message sent!");
    } catch (error) {
      toast.error("Failed to send message");
    }
    setSendingChat(false);
  };

  // Scroll to bottom of chat - only scroll within container, not the page
  useEffect(() => {
    if (chatContainerRef.current && chatMessages.length > 0) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  // Function to open chat directly with a partner
  const openChatWithPartner = async (partner) => {
    const chatPartner = {
      partner_id: partner.id,
      partner_name: partner.full_name,
      partner_code: partner.partner_code
    };
    setSelectedChatPartner(chatPartner);
    setShowChatPanel(true);
    await fetchChatConversations();
    await fetchChatMessages(partner.id);
  };

  // Poll for new messages when chat is open
  useEffect(() => {
    if (showChatPanel && selectedChatPartner) {
      const interval = setInterval(() => {
        fetchChatMessages(selectedChatPartner.partner_id);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [showChatPanel, selectedChatPartner]);

  // Admin presence heartbeat - send every 30 seconds
  useEffect(() => {
    const sendHeartbeat = async () => {
      const currentToken = localStorage.getItem("reroots_token");
      if (currentToken) {
        try {
          await axios.post(`${API}/presence/heartbeat`, { user_type: "admin" }, {
            headers: { Authorization: `Bearer ${currentToken}` }
          });
        } catch (e) {
          // Silently fail heartbeat
        }
      }
    };
    
    sendHeartbeat(); // Send immediately
    const heartbeatInterval = setInterval(sendHeartbeat, 30000);
    return () => clearInterval(heartbeatInterval);
  }, []);

  // Fetch online status of all partners
  const fetchOnlineStatus = useCallback(async () => {
    const currentToken = localStorage.getItem("reroots_token");
    if (currentToken) {
      try {
        const res = await axios.get(`${API}/admin/partners/online-status`, {
          headers: { Authorization: `Bearer ${currentToken}` }
        });
        setOnlinePartners(res.data.online_partners || {});
      } catch (e) {
        // Silently fail
      }
    }
  }, []);

  // Poll for online status every 15 seconds
  useEffect(() => {
    fetchOnlineStatus();
    const statusInterval = setInterval(fetchOnlineStatus, 15000);
    return () => clearInterval(statusInterval);
  }, [fetchOnlineStatus]);

  useEffect(() => {
    fetchInfluencers();
    fetchSettings();
  }, []);

  // Partner Messaging Functions
  const openMessageModal = async (partner) => {
    console.log("Opening message modal for:", partner?.full_name);
    
    // Fetch partner's vouchers and referral programs
    const currentToken = localStorage.getItem("reroots_token");
    const fetchHeaders = { Authorization: `Bearer ${currentToken}` };
    
    let vouchers = [];
    let referralPrograms = [];
    
    try {
      // Fetch vouchers
      const vouchersRes = await axios.get(`${API}/admin/partner-vouchers/${partner.id}`, { headers: fetchHeaders });
      vouchers = vouchersRes.data.vouchers || [];
    } catch (e) {
      console.log("No vouchers found");
    }
    
    try {
      // Fetch referral programs
      const referralsRes = await axios.get(`${API}/admin/partner-referrals/${partner.id}`, { headers: fetchHeaders });
      referralPrograms = referralsRes.data.referrals || [];
    } catch (e) {
      console.log("No referral programs found");
    }
    
    // Set partner with fetched coupons
    setMessageTarget({
      ...partner,
      vouchers: vouchers,
      referral_programs: referralPrograms
    });
    
    setMessageData({
      type: "message",
      subject: "",
      content: "",
      priority: "normal",
      files: [],
      send_email: true,
      send_sms: false
    });
    setShowMessageModal(true);
    console.log("showMessageModal set to true, vouchers:", vouchers.length, "referrals:", referralPrograms.length);
  };

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    
    // Check total file count (limit to 10 files)
    if (messageData.files.length + files.length > 10) {
      toast.error("Maximum 10 files allowed");
      return;
    }
    
    setUploadingFile(true);
    let uploadedCount = 0;
    
    for (const file of files) {
      // Check file size (max 10MB per file)
      if (file.size > 10 * 1024 * 1024) {
        toast.error(`${file.name} is too large (max 10MB)`);
        continue;
      }
      
      try {
        const formData = new FormData();
        formData.append("file", file);
        
        const res = await axios.post(`${API}/upload/file`, formData, {
          headers: { 
            Authorization: `Bearer ${localStorage.getItem("reroots_token")}`,
            "Content-Type": "multipart/form-data"
          }
        });
        
        setMessageData(prev => ({
          ...prev,
          files: [...prev.files, { name: file.name, url: res.data.url, type: file.type }]
        }));
        uploadedCount++;
      } catch (error) {
        console.error("Upload error:", error);
        toast.error(`Failed to upload ${file.name}`);
      }
    }
    
    if (uploadedCount > 0) {
      toast.success(`${uploadedCount} file(s) uploaded!`);
    }
    setUploadingFile(false);
    // Reset input
    e.target.value = '';
  };

  const removeFile = (index) => {
    setMessageData(prev => ({
      ...prev,
      files: prev.files.filter((_, i) => i !== index)
    }));
  };

  const sendMessage = async () => {
    if (!messageData.content.trim()) {
      toast.error("Please enter a message");
      return;
    }
    
    const currentToken = localStorage.getItem("reroots_token");
    setSendingMessage(true);
    try {
      await axios.post(`${API}/admin/partner-messages`, {
        partner_id: messageTarget.id,
        ...messageData
      }, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      toast.success("Message sent successfully!");
      setShowMessageModal(false);
      setMessageTarget(null);
    } catch (error) {
      toast.error("Failed to send message");
    }
    setSendingMessage(false);
  };

  const fetchPartnerMessages = async (partnerId) => {
    const currentToken = localStorage.getItem("reroots_token");
    try {
      const res = await axios.get(`${API}/admin/partner-messages/${partnerId}`, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      setPartnerMessages(res.data.messages || []);
      setShowMessagesHistory(true);
    } catch (error) {
      toast.error("Failed to fetch messages");
    }
  };

  // Partner Voucher Functions
  const openVoucherModal = (partner) => {
    console.log("Opening voucher modal for:", partner?.full_name);
    setVoucherTarget(partner);
    const suggestedCode = `${partner.social_handle?.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8) || 'PARTNER'}${Math.floor(Math.random() * 100)}`;
    setVoucherData({
      code: suggestedCode,
      discount_type: "percentage",
      discount_value: 10,
      partner_commission: programSettings?.influencer_program?.commission_rate || 10,
      min_order: 0,
      max_uses: 0,
      valid_from: new Date().toISOString().split('T')[0],
      valid_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      description: "",
      is_active: true
    });
    setShowVoucherModal(true);
    console.log("showVoucherModal set to true");
  };

  const createVoucher = async () => {
    if (!voucherData.code.trim()) {
      toast.error("Please enter a voucher code");
      return;
    }
    
    const currentToken = localStorage.getItem("reroots_token");
    setCreatingVoucher(true);
    try {
      await axios.post(`${API}/admin/partner-vouchers`, {
        partner_id: voucherTarget.id,
        ...voucherData,
        code: voucherData.code.toUpperCase()
      }, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      toast.success("Voucher created successfully!");
      setShowVoucherModal(false);
      setVoucherTarget(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to create voucher");
    }
    setCreatingVoucher(false);
  };

  const fetchPartnerVouchers = async (partnerId) => {
    const currentToken = localStorage.getItem("reroots_token");
    try {
      const res = await axios.get(`${API}/admin/partner-vouchers/${partnerId}`, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      setPartnerVouchers(res.data.vouchers || []);
      setShowVouchersHistory(true);
    } catch (error) {
      toast.error("Failed to fetch vouchers");
    }
  };

  const toggleVoucherStatus = async (voucher) => {
    const currentToken = localStorage.getItem("reroots_token");
    try {
      await axios.put(`${API}/admin/partner-vouchers/${voucher.id}`, {
        is_active: !voucher.is_active
      }, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      toast.success(`Voucher ${voucher.is_active ? 'deactivated' : 'activated'}`);
      fetchPartnerVouchers(voucher.partner_id);
    } catch (error) {
      toast.error("Failed to update voucher");
    }
  };

  const deleteVoucher = async (voucherId, partnerId) => {
    if (!confirm("Are you sure you want to delete this voucher?")) return;
    const currentToken = localStorage.getItem("reroots_token");
    try {
      await axios.delete(`${API}/admin/partner-vouchers/${voucherId}`, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      toast.success("Voucher deleted");
      fetchPartnerVouchers(partnerId);
    } catch (error) {
      toast.error("Failed to delete voucher");
    }
  };

  // Partner Referral Functions
  const openReferralModal = (partner) => {
    console.log("Opening referral modal for:", partner?.full_name);
    setReferralTarget(partner);
    setReferralData({
      name: `${partner.full_name}'s Referral Program`,
      reward_discount_percent: 15,
      required_referrals: 3,
      referral_action: "signup"
    });
    setShowReferralModal(true);
  };

  const createPartnerReferral = async () => {
    if (!referralData.name.trim()) {
      toast.error("Please enter a program name");
      return;
    }
    
    const currentToken = localStorage.getItem("reroots_token");
    setCreatingReferral(true);
    try {
      await axios.post(`${API}/admin/partner-referrals`, {
        partner_id: referralTarget.id,
        ...referralData
      }, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      toast.success("Referral program created!");
      setShowReferralModal(false);
      setReferralTarget(null);
      // Optionally refresh referrals list
      if (selectedInfluencer?.id === referralTarget.id) {
        fetchPartnerReferrals(referralTarget.id);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to create referral program");
    }
    setCreatingReferral(false);
  };

  const fetchPartnerReferrals = async (partnerId) => {
    const currentToken = localStorage.getItem("reroots_token");
    try {
      const res = await axios.get(`${API}/admin/partner-referrals/${partnerId}`, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      setPartnerReferrals(res.data.referrals || []);
      setShowReferralsHistory(true);
    } catch (error) {
      toast.error("Failed to fetch referrals");
    }
  };

  const toggleReferralStatus = async (referral) => {
    const currentToken = localStorage.getItem("reroots_token");
    try {
      await axios.put(`${API}/admin/partner-referrals/${referral.id}`, {
        is_active: !referral.is_active
      }, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      toast.success(referral.is_active ? "Referral deactivated" : "Referral activated");
      fetchPartnerReferrals(referral.partner_id);
    } catch (error) {
      toast.error("Failed to update referral");
    }
  };

  const deleteReferral = async (referralId, partnerId) => {
    if (!confirm("Are you sure you want to delete this referral program?")) return;
    const currentToken = localStorage.getItem("reroots_token");
    try {
      await axios.delete(`${API}/admin/partner-referrals/${referralId}`, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      toast.success("Referral program deleted");
      fetchPartnerReferrals(partnerId);
    } catch (error) {
      toast.error("Failed to delete referral program");
    }
  };

  const copyReferralLink = (referral) => {
    const link = `${window.location.origin}${referral.referral_link}`;
    navigator.clipboard.writeText(link);
    toast.success("Referral link copied!");
  };

  const renewPartnership = async (partnerId, partnerName) => {
    if (!confirm(`Renew partnership for ${partnerName} for another year?`)) return;
    const currentToken = localStorage.getItem("reroots_token");
    try {
      const res = await axios.put(`${API}/admin/partner/${partnerId}/renew`, {}, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      toast.success(res.data.message);
      fetchInfluencers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to renew partnership");
    }
  };

  const handleApprove = async (id) => {
    const currentToken = localStorage.getItem("reroots_token");
    try {
      const res = await axios.put(`${API}/admin/influencers/${id}/approve`, {}, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      toast.success(`Approved! Code: ${res.data.partner_code}`);
      fetchInfluencers();
      setShowDetails(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to approve");
    }
  };

  const handleReject = async (id, reason) => {
    const currentToken = localStorage.getItem("reroots_token");
    try {
      await axios.put(`${API}/admin/influencers/${id}/reject`, { reason }, {
        headers: { Authorization: `Bearer ${currentToken}` }
      });
      toast.success("Application rejected");
      fetchInfluencers();
      setShowDetails(false);
    } catch (error) {
      toast.error("Failed to reject");
    }
  };

  const copyPartnerLink = (code) => {
    const link = `${window.location.origin}/partner/${code.toLowerCase()}`;
    navigator.clipboard.writeText(link);
    toast.success("Partner link copied!");
  };

  const copyPartnerCode = (code) => {
    navigator.clipboard.writeText(code);
    toast.success("Partner code copied!");
  };

  const filteredApps = filterStatus === "all" 
    ? applications 
    : applications.filter(a => a.status === filterStatus);

  const getStatusBadge = (status) => {
    const styles = {
      pending: "bg-yellow-100 text-yellow-800",
      approved: "bg-green-100 text-green-800",
      active: "bg-blue-100 text-blue-800",
      rejected: "bg-red-100 text-red-800",
      paused: "bg-gray-100 text-gray-800"
    };
    return <Badge className={styles[status] || "bg-gray-100"}>{status}</Badge>;
  };

  const getPlatformIcon = (platform) => {
    const icons = {
      instagram: <Instagram className="h-4 w-4" />,
      tiktok: <Play className="h-4 w-4" />,
      youtube: <Play className="h-4 w-4" />,
      twitter: <MessageCircle className="h-4 w-4" />,
      blog: <Globe className="h-4 w-4" />
    };
    return icons[platform] || <Globe className="h-4 w-4" />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-[#D4AF37]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            <Sparkles className="h-5 w-5 sm:h-6 sm:w-6 text-[#D4AF37]" />
            Partner Program
          </h2>
          <p className="text-sm sm:text-base text-[#5A5A5A]">Manage influencer applications and partnerships</p>
        </div>
        <div className="flex flex-wrap gap-2 w-full lg:w-auto">
          <Button
            size="sm"
            variant={showChatPanel ? "default" : "outline"}
            onClick={() => {
              setShowChatPanel(!showChatPanel);
              if (!showChatPanel) {
                // Fetch chat conversations
                fetchChatConversations();
              }
            }}
            className={`flex-1 sm:flex-none ${showChatPanel ? "bg-[#D4AF37] hover:bg-[#B8960F] text-[#2D2A2E]" : ""}`}
          >
            <MessageCircle className="h-4 w-4 mr-1 sm:mr-2" />
            <span className="hidden xs:inline">Live </span>Chat
            {chatConversations.some(c => c.unread_count > 0) && (
              <span className="ml-1 sm:ml-2 bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                {chatConversations.reduce((sum, c) => sum + (c.unread_count || 0), 0)}
              </span>
            )}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1 sm:flex-none"
            onClick={() => {
              navigator.clipboard.writeText(`${window.location.origin}/become-partner`);
              toast.success("Application link copied!");
            }}
          >
            <Copy className="h-4 w-4 mr-1 sm:mr-2" />
            <span className="hidden sm:inline">Copy </span>Link
          </Button>
          <a href="/become-partner" target="_blank" rel="noopener noreferrer" className="flex-1 sm:flex-none">
            <Button size="sm" className="w-full bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E]">
              <ExternalLink className="h-4 w-4 mr-1 sm:mr-2" />
              <span className="hidden sm:inline">View </span>Apply<span className="hidden sm:inline"> Page</span>
            </Button>
          </a>
          <Button 
            size="sm" 
            variant="outline"
            className="flex-1 sm:flex-none border-[#F8A5B8] text-[#F8A5B8] hover:bg-[#F8A5B8]/10"
            onClick={() => setShowInfluencerPreview(true)}
          >
            <Eye className="h-4 w-4 mr-1 sm:mr-2" />
            <span className="hidden sm:inline">Preview </span>Influencer<span className="hidden sm:inline"> View</span>
          </Button>
          <Button 
            size="sm" 
            variant="outline"
            className="flex-1 sm:flex-none border-purple-500 text-purple-600 hover:bg-purple-50"
            onClick={() => setShowLandingPageSettings(true)}
          >
            <Settings className="h-4 w-4 mr-1 sm:mr-2" />
            <span className="hidden sm:inline">Landing </span>Page<span className="hidden sm:inline"> Settings</span>
          </Button>
        </div>
      </div>

      {/* Landing Page Settings Modal */}
      <Dialog open={showLandingPageSettings} onOpenChange={setShowLandingPageSettings}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5 text-purple-600" />
              Landing Page Settings
            </DialogTitle>
            <DialogDescription>
              Customize the partner application landing page appearance
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-6 py-4">
            {/* Banner Settings */}
            <div className="space-y-4 p-4 bg-yellow-50 rounded-xl border border-yellow-200">
              <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                <Tag className="h-4 w-4 text-yellow-600" />
                Corner Banner (50% OFF)
              </h3>
              <div className="flex items-center justify-between">
                <Label>Show Banner</Label>
                <Switch 
                  checked={landingPageSettings.banner_enabled}
                  onCheckedChange={(v) => setLandingPageSettings({...landingPageSettings, banner_enabled: v})}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Banner Text</Label>
                  <Input 
                    value={landingPageSettings.banner_text}
                    onChange={(e) => setLandingPageSettings({...landingPageSettings, banner_text: e.target.value})}
                    placeholder="50% OFF"
                  />
                </div>
                <div>
                  <Label>Banner Color</Label>
                  <div className="flex gap-2">
                    <Input 
                      type="color"
                      value={landingPageSettings.banner_color}
                      onChange={(e) => setLandingPageSettings({...landingPageSettings, banner_color: e.target.value})}
                      className="w-16 h-10 p-1"
                    />
                    <Input 
                      value={landingPageSettings.banner_color}
                      onChange={(e) => setLandingPageSettings({...landingPageSettings, banner_color: e.target.value})}
                      placeholder="#FFD700"
                    />
                  </div>
                </div>
              </div>
            </div>
            
            {/* Hero Images */}
            <div className="space-y-4 p-4 bg-pink-50 rounded-xl border border-pink-200">
              <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                <Upload className="h-4 w-4 text-pink-600" />
                Hero Images
              </h3>
              
              {/* Hero Background Image */}
              <div className="space-y-2">
                <Label>Hero Background Image</Label>
                <div className="flex gap-2">
                  <Input 
                    value={landingPageSettings.hero_image_url}
                    onChange={(e) => setLandingPageSettings({...landingPageSettings, hero_image_url: e.target.value})}
                    placeholder="https://example.com/hero-image.jpg"
                    className="flex-1"
                  />
                  <label className="cursor-pointer">
                    <input 
                      type="file" 
                      accept="image/*"
                      className="hidden"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        
                        if (file.size > 5 * 1024 * 1024) {
                          toast.error("Image must be less than 5MB");
                          return;
                        }
                        
                        const reader = new FileReader();
                        reader.onload = (event) => {
                          setLandingPageSettings({...landingPageSettings, hero_image_url: event.target.result});
                          toast.success("Hero image uploaded!");
                        };
                        reader.readAsDataURL(file);
                      }}
                    />
                    <Button type="button" variant="outline" className="border-pink-300 text-pink-600 hover:bg-pink-50">
                      <Upload className="h-4 w-4 mr-1" /> Upload
                    </Button>
                  </label>
                </div>
                {landingPageSettings.hero_image_url && (
                  <div className="mt-2 relative inline-block">
                    <img 
                      src={landingPageSettings.hero_image_url} 
                      alt="Hero preview" 
                      className="h-20 rounded-lg border object-cover"
                    />
                    <button 
                      onClick={() => setLandingPageSettings({...landingPageSettings, hero_image_url: ""})}
                      className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full text-xs hover:bg-red-600"
                    >
                      ×
                    </button>
                  </div>
                )}
              </div>
              
              {/* Product Image */}
              <div className="space-y-2">
                <Label>Product Image</Label>
                <div className="flex gap-2">
                  <Input 
                    value={landingPageSettings.hero_product_image_url}
                    onChange={(e) => setLandingPageSettings({...landingPageSettings, hero_product_image_url: e.target.value})}
                    placeholder="https://example.com/product.jpg"
                    className="flex-1"
                  />
                  <label className="cursor-pointer">
                    <input 
                      type="file" 
                      accept="image/*"
                      className="hidden"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        
                        if (file.size > 5 * 1024 * 1024) {
                          toast.error("Image must be less than 5MB");
                          return;
                        }
                        
                        const reader = new FileReader();
                        reader.onload = (event) => {
                          setLandingPageSettings({...landingPageSettings, hero_product_image_url: event.target.result});
                          toast.success("Product image uploaded!");
                        };
                        reader.readAsDataURL(file);
                      }}
                    />
                    <Button type="button" variant="outline" className="border-pink-300 text-pink-600 hover:bg-pink-50">
                      <Upload className="h-4 w-4 mr-1" /> Upload
                    </Button>
                  </label>
                </div>
                {landingPageSettings.hero_product_image_url && (
                  <div className="mt-2 relative inline-block">
                    <img 
                      src={landingPageSettings.hero_product_image_url} 
                      alt="Product preview" 
                      className="h-20 rounded-lg border object-cover"
                    />
                    <button 
                      onClick={() => setLandingPageSettings({...landingPageSettings, hero_product_image_url: ""})}
                      className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full text-xs hover:bg-red-600"
                    >
                      ×
                    </button>
                  </div>
                )}
              </div>
            </div>
            
            {/* Partner Tiers Visibility */}
            <div className="space-y-4 p-4 bg-purple-50 rounded-xl border border-purple-200">
              <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                <Users className="h-4 w-4 text-purple-600" />
                Partner Tiers Visibility
              </h3>
              <p className="text-sm text-gray-500">Choose which partner tiers to show on the landing page</p>
              
              {/* OROÉ Tier */}
              <div className="flex items-center justify-between p-3 bg-white rounded-lg border">
                <div className="flex items-center gap-3">
                  <span className="text-xl">👑</span>
                  <div>
                    <p className="font-medium">OROÉ Luxury Partner</p>
                    <p className="text-xs text-gray-500">35+ Premium Market</p>
                  </div>
                </div>
                <Switch 
                  checked={landingPageSettings.show_oroe_tier}
                  onCheckedChange={(v) => setLandingPageSettings({...landingPageSettings, show_oroe_tier: v})}
                />
              </div>
              
              {/* Brand Tier */}
              <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-[#D4AF37]">
                <div className="flex items-center gap-3">
                  <span className="text-xl">🧬</span>
                  <div>
                    <p className="font-medium text-[#D4AF37]">{brandName} Gold Partner</p>
                    <p className="text-xs text-gray-500">18-35 Young Adults (Main tier)</p>
                  </div>
                </div>
                <Switch 
                  checked={landingPageSettings.show_reroots_tier}
                  onCheckedChange={(v) => setLandingPageSettings({...landingPageSettings, show_reroots_tier: v})}
                />
              </div>
              
              {/* La Vela Bianca Tier */}
              <div className="flex items-center justify-between p-3 bg-white rounded-lg border">
                <div className="flex items-center gap-3">
                  <span className="text-xl">🌸</span>
                  <div>
                    <p className="font-medium">LA VELA BIANCA Ambassador</p>
                    <p className="text-xs text-gray-500">6-18 Teen Market</p>
                  </div>
                </div>
                <Switch 
                  checked={landingPageSettings.show_lavela_tier}
                  onCheckedChange={(v) => setLandingPageSettings({...landingPageSettings, show_lavela_tier: v})}
                />
              </div>
            </div>
            
            {/* Tier Commission Settings */}
            <div className="space-y-4 p-4 bg-green-50 rounded-xl border border-green-200">
              <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-green-600" />
                Commission & Bonus Settings
              </h3>
              
              {landingPageSettings.show_reroots_tier && (
                <div className="p-3 bg-white rounded-lg border space-y-3">
                  <p className="font-medium text-[#D4AF37]">🧬 {brandName} Gold Partner</p>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <Label className="text-xs">Commission %</Label>
                      <Input 
                        type="number"
                        value={landingPageSettings.reroots_commission}
                        onChange={(e) => setLandingPageSettings({...landingPageSettings, reroots_commission: parseInt(e.target.value) || 0})}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Customer Discount %</Label>
                      <Input 
                        type="number"
                        value={landingPageSettings.reroots_discount}
                        onChange={(e) => setLandingPageSettings({...landingPageSettings, reroots_discount: parseInt(e.target.value) || 0})}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Monthly Bonus $</Label>
                      <Input 
                        type="number"
                        value={landingPageSettings.reroots_bonus}
                        onChange={(e) => setLandingPageSettings({...landingPageSettings, reroots_bonus: parseInt(e.target.value) || 0})}
                      />
                    </div>
                  </div>
                </div>
              )}
              
              {landingPageSettings.show_oroe_tier && (
                <div className="p-3 bg-white rounded-lg border space-y-3">
                  <p className="font-medium">👑 OROÉ Luxury Partner</p>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <Label className="text-xs">Commission %</Label>
                      <Input 
                        type="number"
                        value={landingPageSettings.oroe_commission}
                        onChange={(e) => setLandingPageSettings({...landingPageSettings, oroe_commission: parseInt(e.target.value) || 0})}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Customer Discount %</Label>
                      <Input 
                        type="number"
                        value={landingPageSettings.oroe_discount}
                        onChange={(e) => setLandingPageSettings({...landingPageSettings, oroe_discount: parseInt(e.target.value) || 0})}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Monthly Bonus $</Label>
                      <Input 
                        type="number"
                        value={landingPageSettings.oroe_bonus}
                        onChange={(e) => setLandingPageSettings({...landingPageSettings, oroe_bonus: parseInt(e.target.value) || 0})}
                      />
                    </div>
                  </div>
                </div>
              )}
              
              {landingPageSettings.show_lavela_tier && (
                <div className="p-3 bg-white rounded-lg border space-y-3">
                  <p className="font-medium">🌸 LA VELA BIANCA Ambassador</p>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <Label className="text-xs">Commission %</Label>
                      <Input 
                        type="number"
                        value={landingPageSettings.lavela_commission}
                        onChange={(e) => setLandingPageSettings({...landingPageSettings, lavela_commission: parseInt(e.target.value) || 0})}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Customer Discount %</Label>
                      <Input 
                        type="number"
                        value={landingPageSettings.lavela_discount}
                        onChange={(e) => setLandingPageSettings({...landingPageSettings, lavela_discount: parseInt(e.target.value) || 0})}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Monthly Bonus $</Label>
                      <Input 
                        type="number"
                        value={landingPageSettings.lavela_bonus}
                        onChange={(e) => setLandingPageSettings({...landingPageSettings, lavela_bonus: parseInt(e.target.value) || 0})}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowLandingPageSettings(false)}>Cancel</Button>
            <Button 
              onClick={async () => {
                setSavingLandingPage(true);
                try {
                  await axios.post(`${API}/admin/influencer-landing-settings`, landingPageSettings, {
                    headers: { Authorization: `Bearer ${token}` }
                  });
                  toast.success("Landing page settings saved!");
                  setShowLandingPageSettings(false);
                } catch (err) {
                  toast.error("Failed to save settings");
                }
                setSavingLandingPage(false);
              }}
              disabled={savingLandingPage}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {savingLandingPage ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving...</> : "Save Settings"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-[#D4AF37]/10 to-[#F4D03F]/10 border-[#D4AF37]/20">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-[#D4AF37]">{stats.total}</p>
            <p className="text-sm text-[#5A5A5A]">Total Applications</p>
          </CardContent>
        </Card>
        <Card className="bg-yellow-50 border-yellow-200">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-yellow-600">{stats.pending}</p>
            <p className="text-sm text-[#5A5A5A]">Pending Review</p>
          </CardContent>
        </Card>
        <Card className="bg-green-50 border-green-200">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-green-600">{stats.approved}</p>
            <p className="text-sm text-[#5A5A5A]">Approved</p>
          </CardContent>
        </Card>
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-blue-600">{stats.active}</p>
            <p className="text-sm text-[#5A5A5A]">Active Partners</p>
          </CardContent>
        </Card>
      </div>

      {/* Visual Landing Page Preview/Editor */}
      {showLandingPageSettings && (
        <Card className="border-purple-200 overflow-hidden">
          <CardHeader className="bg-gradient-to-r from-purple-50 to-pink-50 py-4">
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-purple-600" />
                Landing Page Visual Editor
              </span>
              <div className="flex items-center gap-2">
                <a href="/influencer" target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm" className="text-purple-600 border-purple-300">
                    <ExternalLink className="h-4 w-4 mr-1" /> View Live Page
                  </Button>
                </a>
                <Button variant="ghost" size="sm" onClick={() => setShowLandingPageSettings(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {/* Mini Preview of Landing Page */}
            <div className="relative bg-[#FAF8F5] min-h-[600px]">
              
              {/* Editable Corner Banner */}
              <div className="absolute top-4 right-4 z-20">
                <div className="group relative">
                  {landingPageSettings.banner_enabled && (
                    <div 
                      className="px-4 py-2 rounded-full font-bold text-sm shadow-lg"
                      style={{ backgroundColor: landingPageSettings.banner_color, color: '#2D2A2E' }}
                    >
                      {landingPageSettings.banner_text}
                    </div>
                  )}
                  <div className="absolute -bottom-20 right-0 opacity-0 group-hover:opacity-100 transition-opacity bg-white p-3 rounded-lg shadow-xl border z-30 w-64">
                    <Label className="text-xs">Banner Text</Label>
                    <Input 
                      value={landingPageSettings.banner_text}
                      onChange={(e) => setLandingPageSettings({...landingPageSettings, banner_text: e.target.value})}
                      className="h-8 text-sm mb-2"
                    />
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Input 
                          type="color"
                          value={landingPageSettings.banner_color}
                          onChange={(e) => setLandingPageSettings({...landingPageSettings, banner_color: e.target.value})}
                          className="w-8 h-8 p-0"
                        />
                        <Label className="text-xs">Color</Label>
                      </div>
                      <label className="flex items-center gap-1 text-xs">
                        <input 
                          type="checkbox"
                          checked={landingPageSettings.banner_enabled}
                          onChange={(e) => setLandingPageSettings({...landingPageSettings, banner_enabled: e.target.checked})}
                        />
                        Show
                      </label>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Hero Section Preview */}
              <div className="relative h-64 bg-gradient-to-br from-[#F8A5B8]/20 via-[#FAF8F5] to-[#D4AF37]/10 flex items-center justify-center border-b">
                <div className="text-center px-8">
                  <div className="inline-block mb-4">
                    <span className="px-3 py-1 bg-[#F8A5B8]/20 text-[#F8A5B8] rounded-full text-xs font-medium">
                      ✨ PARTNER PROGRAM
                    </span>
                  </div>
                  <h1 className="text-2xl md:text-3xl font-serif text-[#2D2A2E] mb-2">
                    Partner With <span className="text-[#D4AF37]">{brandName}</span>
                  </h1>
                  <p className="text-sm text-[#5A5A5A] max-w-md mx-auto">
                    Join our exclusive partner program and earn commissions
                  </p>
                </div>
                
                {/* Product Image Slot */}
                <div className="absolute right-8 bottom-4 group">
                  <div className="w-24 h-32 bg-white rounded-lg shadow-lg border-2 border-dashed border-gray-300 flex items-center justify-center overflow-hidden">
                    {landingPageSettings.hero_product_image_url ? (
                      <img src={landingPageSettings.hero_product_image_url} alt="Product" className="w-full h-full object-cover" />
                    ) : (
                      <div className="text-center p-2">
                        <Upload className="h-6 w-6 mx-auto text-gray-400 mb-1" />
                        <span className="text-xs text-gray-400">Product</span>
                      </div>
                    )}
                  </div>
                  <div className="absolute -bottom-12 right-0 opacity-0 group-hover:opacity-100 transition-opacity bg-white p-2 rounded-lg shadow-xl border z-30 w-48">
                    <Label className="text-xs">Product Image URL</Label>
                    <Input 
                      value={landingPageSettings.hero_product_image_url}
                      onChange={(e) => setLandingPageSettings({...landingPageSettings, hero_product_image_url: e.target.value})}
                      className="h-7 text-xs"
                      placeholder="https://..."
                    />
                  </div>
                </div>
              </div>
              
              {/* Partner Tiers Section */}
              <div className="p-6">
                <h3 className="text-center text-lg font-semibold text-[#2D2A2E] mb-4">Choose Your Tier</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  
                  {/* OROÉ Tier */}
                  <div className={`relative group transition-all ${!landingPageSettings.show_oroe_tier ? 'opacity-40 grayscale' : ''}`}>
                    <div className="absolute -top-2 -right-2 z-10">
                      <label className="flex items-center gap-1 bg-white px-2 py-1 rounded-full shadow text-xs border cursor-pointer">
                        <input 
                          type="checkbox"
                          checked={landingPageSettings.show_oroe_tier}
                          onChange={(e) => setLandingPageSettings({...landingPageSettings, show_oroe_tier: e.target.checked})}
                        />
                        Show
                      </label>
                    </div>
                    <Card className="border-[#1A1A1A] bg-gradient-to-br from-[#1A1A1A] to-[#333] text-white h-full">
                      <CardContent className="p-4 text-center">
                        <span className="text-2xl">👑</span>
                        <h4 className="font-bold mt-2">OROÉ</h4>
                        <p className="text-xs text-gray-300 mb-3">Luxury Partner • 35+</p>
                        <div className="space-y-1 text-xs">
                          <p>{landingPageSettings.oroe_commission}% Commission</p>
                          <p>{landingPageSettings.oroe_discount}% Customer Discount</p>
                          <p>${landingPageSettings.oroe_bonus} Bonus</p>
                        </div>
                        {/* Hover edit panel */}
                        <div className="opacity-0 group-hover:opacity-100 transition-opacity absolute inset-0 bg-black/80 rounded-lg flex items-center justify-center">
                          <div className="p-3 space-y-2 text-left w-full">
                            <div className="flex items-center gap-2">
                              <Input 
                                type="number"
                                value={landingPageSettings.oroe_commission}
                                onChange={(e) => setLandingPageSettings({...landingPageSettings, oroe_commission: parseInt(e.target.value) || 0})}
                                className="h-7 w-16 text-xs text-black"
                              />
                              <span className="text-xs">% Commission</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Input 
                                type="number"
                                value={landingPageSettings.oroe_discount}
                                onChange={(e) => setLandingPageSettings({...landingPageSettings, oroe_discount: parseInt(e.target.value) || 0})}
                                className="h-7 w-16 text-xs text-black"
                              />
                              <span className="text-xs">% Discount</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Input 
                                type="number"
                                value={landingPageSettings.oroe_bonus}
                                onChange={(e) => setLandingPageSettings({...landingPageSettings, oroe_bonus: parseInt(e.target.value) || 0})}
                                className="h-7 w-16 text-xs text-black"
                              />
                              <span className="text-xs">$ Bonus</span>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                  
                  {/* Brand Tier - Featured */}
                  <div className={`relative group transition-all ${!landingPageSettings.show_reroots_tier ? 'opacity-40 grayscale' : ''}`}>
                    <div className="absolute -top-2 -right-2 z-10">
                      <label className="flex items-center gap-1 bg-white px-2 py-1 rounded-full shadow text-xs border cursor-pointer">
                        <input 
                          type="checkbox"
                          checked={landingPageSettings.show_reroots_tier}
                          onChange={(e) => setLandingPageSettings({...landingPageSettings, show_reroots_tier: e.target.checked})}
                        />
                        Show
                      </label>
                    </div>
                    <Card className="border-[#D4AF37] border-2 bg-gradient-to-br from-[#D4AF37]/10 to-[#F4D03F]/5 h-full ring-2 ring-[#D4AF37]/30">
                      <CardContent className="p-4 text-center">
                        <Badge className="absolute -top-2 left-1/2 -translate-x-1/2 bg-[#D4AF37] text-xs">POPULAR</Badge>
                        <span className="text-2xl">🧬</span>
                        <h4 className="font-bold mt-2 text-[#D4AF37]">{brandName} Gold</h4>
                        <p className="text-xs text-gray-500 mb-3">Main Partner • 18-35</p>
                        <div className="space-y-1 text-xs text-[#2D2A2E]">
                          <p>{landingPageSettings.reroots_commission}% Commission</p>
                          <p>{landingPageSettings.reroots_discount}% Customer Discount</p>
                          <p>${landingPageSettings.reroots_bonus} Bonus</p>
                        </div>
                        {/* Hover edit panel */}
                        <div className="opacity-0 group-hover:opacity-100 transition-opacity absolute inset-0 bg-[#D4AF37]/90 rounded-lg flex items-center justify-center">
                          <div className="p-3 space-y-2 text-left w-full">
                            <div className="flex items-center gap-2">
                              <Input 
                                type="number"
                                value={landingPageSettings.reroots_commission}
                                onChange={(e) => setLandingPageSettings({...landingPageSettings, reroots_commission: parseInt(e.target.value) || 0})}
                                className="h-7 w-16 text-xs"
                              />
                              <span className="text-xs text-white">% Commission</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Input 
                                type="number"
                                value={landingPageSettings.reroots_discount}
                                onChange={(e) => setLandingPageSettings({...landingPageSettings, reroots_discount: parseInt(e.target.value) || 0})}
                                className="h-7 w-16 text-xs"
                              />
                              <span className="text-xs text-white">% Discount</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Input 
                                type="number"
                                value={landingPageSettings.reroots_bonus}
                                onChange={(e) => setLandingPageSettings({...landingPageSettings, reroots_bonus: parseInt(e.target.value) || 0})}
                                className="h-7 w-16 text-xs"
                              />
                              <span className="text-xs text-white">$ Bonus</span>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                  
                  {/* La Vela Bianca Tier */}
                  <div className={`relative group transition-all ${!landingPageSettings.show_lavela_tier ? 'opacity-40 grayscale' : ''}`}>
                    <div className="absolute -top-2 -right-2 z-10">
                      <label className="flex items-center gap-1 bg-white px-2 py-1 rounded-full shadow text-xs border cursor-pointer">
                        <input 
                          type="checkbox"
                          checked={landingPageSettings.show_lavela_tier}
                          onChange={(e) => setLandingPageSettings({...landingPageSettings, show_lavela_tier: e.target.checked})}
                        />
                        Show
                      </label>
                    </div>
                    <Card className="border-[#E8C4B8] bg-gradient-to-br from-[#0D4D4D]/5 to-[#E8C4B8]/10 h-full">
                      <CardContent className="p-4 text-center">
                        <span className="text-2xl">🌸</span>
                        <h4 className="font-bold mt-2 text-[#0D4D4D]">La Vela Bianca</h4>
                        <p className="text-xs text-gray-500 mb-3">Teen Ambassador • 6-18</p>
                        <div className="space-y-1 text-xs text-[#2D2A2E]">
                          <p>{landingPageSettings.lavela_commission}% Commission</p>
                          <p>{landingPageSettings.lavela_discount}% Customer Discount</p>
                          <p>${landingPageSettings.lavela_bonus} Bonus</p>
                        </div>
                        {/* Hover edit panel */}
                        <div className="opacity-0 group-hover:opacity-100 transition-opacity absolute inset-0 bg-[#0D4D4D]/90 rounded-lg flex items-center justify-center">
                          <div className="p-3 space-y-2 text-left w-full text-white">
                            <div className="flex items-center gap-2">
                              <Input 
                                type="number"
                                value={landingPageSettings.lavela_commission}
                                onChange={(e) => setLandingPageSettings({...landingPageSettings, lavela_commission: parseInt(e.target.value) || 0})}
                                className="h-7 w-16 text-xs text-black"
                              />
                              <span className="text-xs">% Commission</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Input 
                                type="number"
                                value={landingPageSettings.lavela_discount}
                                onChange={(e) => setLandingPageSettings({...landingPageSettings, lavela_discount: parseInt(e.target.value) || 0})}
                                className="h-7 w-16 text-xs text-black"
                              />
                              <span className="text-xs">% Discount</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Input 
                                type="number"
                                value={landingPageSettings.lavela_bonus}
                                onChange={(e) => setLandingPageSettings({...landingPageSettings, lavela_bonus: parseInt(e.target.value) || 0})}
                                className="h-7 w-16 text-xs text-black"
                              />
                              <span className="text-xs">$ Bonus</span>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
                
                {/* Save Button */}
                <div className="mt-6 flex justify-center gap-3">
                  <Button
                    onClick={async () => {
                      setSavingLandingPage(true);
                      try {
                        await axios.post(`${API}/admin/influencer-landing-settings`, landingPageSettings, {
                          headers: { Authorization: `Bearer ${token}` }
                        });
                        toast.success("Landing page settings saved!");
                      } catch (err) {
                        toast.error("Failed to save settings");
                      }
                      setSavingLandingPage(false);
                    }}
                    disabled={savingLandingPage}
                    className="bg-purple-600 hover:bg-purple-700 px-8"
                  >
                    {savingLandingPage ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving...</> : "💾 Save All Changes"}
                  </Button>
                </div>
                
                <p className="text-center text-xs text-gray-400 mt-3">
                  💡 Hover over any element to edit • Uncheck "Show" to hide a tier
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Live Chat Panel */}
      {showChatPanel && (
        <Card className="border-[#D4AF37]/30 overflow-hidden">
          <CardHeader className="bg-gradient-to-r from-[#D4AF37]/10 to-[#F4D03F]/10 py-3">
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <MessageCircle className="h-5 w-5 text-[#D4AF37]" />
                Partner Live Chat
              </span>
              <Button variant="ghost" size="sm" onClick={() => setShowChatPanel(false)}>
                <X className="h-4 w-4" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="flex h-96">
              {/* Conversations List */}
              <div className="w-1/3 border-r overflow-y-auto">
                {chatConversations.length === 0 ? (
                  <div className="p-4 text-center text-gray-500">
                    <MessageCircle className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                    <p className="text-sm">No conversations yet</p>
                  </div>
                ) : (
                  chatConversations.map(conv => (
                    <div
                      key={conv.partner_id}
                      onClick={() => {
                        setSelectedChatPartner(conv);
                        fetchChatMessages(conv.partner_id);
                      }}
                      className={`p-3 border-b cursor-pointer hover:bg-gray-50 transition-colors ${
                        selectedChatPartner?.partner_id === conv.partner_id ? 'bg-[#D4AF37]/10' : ''
                      }`}
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">{conv.partner_name}</p>
                          <p className="text-xs text-gray-500 truncate">@{conv.partner_code}</p>
                          <p className="text-xs text-gray-400 mt-1 truncate">{conv.last_message}</p>
                        </div>
                        {conv.unread_count > 0 && (
                          <span className="bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full ml-2">
                            {conv.unread_count}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-1">
                        {new Date(conv.last_message_at).toLocaleString()}
                      </p>
                    </div>
                  ))
                )}
              </div>
              
              {/* Chat Messages */}
              <div className="w-2/3 flex flex-col">
                {selectedChatPartner ? (
                  <>
                    {/* Chat Header */}
                    <div className="p-3 border-b bg-gray-50">
                      <p className="font-medium">{selectedChatPartner.partner_name}</p>
                      <p className="text-xs text-gray-500">@{selectedChatPartner.partner_code}</p>
                    </div>
                    
                    {/* Messages */}
                    <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-3 space-y-3 bg-[#FAF8F5]">
                      {loadingChat ? (
                        <div className="flex items-center justify-center h-full">
                          <Loader2 className="h-6 w-6 animate-spin text-[#D4AF37]" />
                        </div>
                      ) : chatMessages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-gray-500">
                          <MessageCircle className="h-8 w-8 mb-2 text-gray-300" />
                          <p className="text-sm">No messages yet</p>
                        </div>
                      ) : (
                        chatMessages.map(msg => (
                          <div
                            key={msg.id}
                            className={`flex ${msg.sender === 'admin' ? 'justify-end' : 'justify-start'}`}
                          >
                            <div
                              className={`max-w-[80%] rounded-lg px-3 py-2 ${
                                msg.sender === 'admin'
                                  ? 'bg-[#D4AF37] text-white'
                                  : 'bg-white border border-gray-200'
                              }`}
                            >
                              <p className="text-sm">{msg.message}</p>
                              <p className={`text-xs mt-1 ${msg.sender === 'admin' ? 'text-white/70' : 'text-gray-400'}`}>
                                {msg.sender === 'admin' && <span className="font-medium">{msg.admin_name || 'Admin'} • </span>}
                                {new Date(msg.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </p>
                            </div>
                          </div>
                        ))
                      )}
                      <div ref={chatMessagesEndRef} />
                    </div>
                    
                    {/* Message Input */}
                    <div className="p-3 border-t bg-white">
                      <form onSubmit={(e) => { e.preventDefault(); sendChatMessage(); }} className="flex gap-2">
                        <Input
                          value={newChatMessage}
                          onChange={(e) => setNewChatMessage(e.target.value)}
                          placeholder="Type your message..."
                          className="flex-1"
                          disabled={sendingChat}
                        />
                        <Button 
                          type="submit"
                          disabled={!newChatMessage.trim() || sendingChat}
                          className="bg-[#D4AF37] hover:bg-[#B8960F] text-[#2D2A2E]"
                        >
                          {sendingChat ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                        </Button>
                      </form>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-gray-500">
                    <MessageCircle className="h-12 w-12 mb-3 text-gray-300" />
                    <p className="font-medium">Select a conversation</p>
                    <p className="text-sm">Choose a partner to start chatting</p>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Program Settings Summary */}
      {programSettings && (
        <Card className="bg-gradient-to-r from-[#2D2A2E] to-[#3D3A3E] text-white">
          <CardContent className="p-6">
            <div className="flex flex-wrap gap-8 items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Commission Rate</p>
                <p className="text-2xl font-bold text-[#D4AF37]">{programSettings.influencer_program?.commission_rate || 10}%</p>
              </div>
              <div>
                <p className="text-gray-400 text-sm">Customer Discount</p>
                <p className="text-2xl font-bold text-[#F8A5B8]">{programSettings.influencer_program?.customer_discount_value || 50}%</p>
              </div>
              <div>
                <p className="text-gray-400 text-sm">Min Followers</p>
                <p className="text-2xl font-bold">{(programSettings.influencer_program?.min_followers || 1000).toLocaleString()}</p>
              </div>
              <div className="text-right">
                <p className="text-gray-400 text-sm mb-2">Share Application Link</p>
                <code className="bg-white/10 px-3 py-1 rounded text-sm">{window.location.origin}/become-partner</code>
              </div>
              <Button 
                variant="outline" 
                className="border-white/30 text-white hover:bg-white/10"
                onClick={() => setShowSettingsEdit(true)}
              >
                <Edit className="h-4 w-4 mr-2" />
                Edit Settings
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Leaderboard Settings Card */}
      <Card className="bg-gradient-to-r from-[#D4AF37]/10 via-white to-[#F4D03F]/10 border-[#D4AF37]/30">
        <CardContent className="p-6">
          <div className="flex flex-wrap gap-6 items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-[#D4AF37] to-[#F4D03F] rounded-xl flex items-center justify-center">
                <Trophy className="h-6 w-6 text-[#2D2A2E]" />
              </div>
              <div>
                <h3 className="font-bold text-[#2D2A2E]">🏆 Founder's Leaderboard</h3>
                <p className="text-sm text-[#5A5A5A]">Competition resets {leaderboardSettings.reset_period}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-4">
              <div className="text-center px-4 py-2 bg-[#D4AF37]/20 rounded-lg">
                <p className="text-xs text-[#5A5A5A]">🥇 1st Prize</p>
                <p className="font-bold text-[#D4AF37]">${leaderboardSettings.first_prize}</p>
              </div>
              <div className="text-center px-4 py-2 bg-gray-100 rounded-lg">
                <p className="text-xs text-[#5A5A5A]">🥈 2nd Prize</p>
                <p className="font-bold text-gray-600">${leaderboardSettings.second_prize}</p>
              </div>
              <div className="text-center px-4 py-2 bg-[#CD7F32]/20 rounded-lg">
                <p className="text-xs text-[#5A5A5A]">🥉 3rd Prize</p>
                <p className="font-bold text-[#CD7F32]">${leaderboardSettings.third_prize}</p>
              </div>
            </div>
            <Button 
              className="bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E] font-semibold"
              onClick={() => setShowLeaderboardEdit(true)}
            >
              <Edit className="h-4 w-4 mr-2" />
              Edit Leaderboard
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Settings Edit Modal */}
      {showSettingsEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setShowSettingsEdit(false)}>
          <Card className="max-w-md w-full" onClick={e => e.stopPropagation()}>
            <CardHeader className="border-b">
              <div className="flex justify-between items-center">
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-5 w-5 text-[#D4AF37]" />
                  Partner Program Settings
                </CardTitle>
                <Button variant="ghost" size="icon" onClick={() => setShowSettingsEdit(false)}>
                  <X className="h-5 w-5" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-6">
              <div>
                <Label className="text-sm font-semibold">Commission Rate (%)</Label>
                <p className="text-xs text-[#5A5A5A] mb-2">How much influencers earn per sale</p>
                <Input
                  type="number"
                  min="1"
                  max="50"
                  value={editingSettings.commission_rate}
                  onChange={(e) => setEditingSettings({...editingSettings, commission_rate: e.target.value})}
                  className="text-lg font-bold"
                />
              </div>
              
              <div>
                <Label className="text-sm font-semibold">Customer Discount (%)</Label>
                <p className="text-xs text-[#5A5A5A] mb-2">Discount customers get with partner code</p>
                <Input
                  type="number"
                  min="1"
                  max="75"
                  value={editingSettings.customer_discount_value}
                  onChange={(e) => setEditingSettings({...editingSettings, customer_discount_value: e.target.value})}
                  className="text-lg font-bold"
                />
              </div>
              
              <div>
                <Label className="text-sm font-semibold">Minimum Followers</Label>
                <p className="text-xs text-[#5A5A5A] mb-2">Minimum followers required to apply</p>
                <Input
                  type="number"
                  min="100"
                  value={editingSettings.min_followers}
                  onChange={(e) => setEditingSettings({...editingSettings, min_followers: e.target.value})}
                  className="text-lg font-bold"
                />
              </div>

              <div className="flex gap-3 pt-4">
                <Button 
                  variant="outline" 
                  className="flex-1"
                  onClick={() => setShowSettingsEdit(false)}
                >
                  Cancel
                </Button>
                <Button 
                  className="flex-1 bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E] font-semibold"
                  onClick={saveSettings}
                  disabled={savingSettings}
                >
                  {savingSettings ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Check className="h-4 w-4 mr-2" />}
                  Save Changes
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Leaderboard Edit Modal */}
      {showLeaderboardEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setShowLeaderboardEdit(false)}>
          <Card className="max-w-md w-full" onClick={e => e.stopPropagation()}>
            <CardHeader className="border-b bg-gradient-to-r from-[#D4AF37]/20 to-[#F4D03F]/20">
              <div className="flex justify-between items-center">
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="h-5 w-5 text-[#D4AF37]" />
                  Leaderboard Settings
                </CardTitle>
                <Button variant="ghost" size="icon" onClick={() => setShowLeaderboardEdit(false)}>
                  <X className="h-5 w-5" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-6">
              <div>
                <Label className="text-sm font-semibold">Reset Period</Label>
                <p className="text-xs text-[#5A5A5A] mb-2">How often the leaderboard resets</p>
                <Select 
                  value={leaderboardSettings.reset_period} 
                  onValueChange={(v) => setLeaderboardSettings({...leaderboardSettings, reset_period: v})}
                >
                  <SelectTrigger className="text-lg font-bold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="weekly">🗓️ Weekly</SelectItem>
                    <SelectItem value="biweekly">📅 Bi-Weekly (Every 2 Weeks)</SelectItem>
                    <SelectItem value="monthly">📆 Monthly</SelectItem>
                    <SelectItem value="quarterly">🗂️ Quarterly (Every 3 Months)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <Separator />
              
              <div className="space-y-4">
                <Label className="text-sm font-semibold flex items-center gap-2">
                  <span className="text-xl">🏆</span> Prize Configuration
                </Label>
                
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-[#D4AF37]/10 p-3 rounded-lg">
                    <Label className="text-xs text-[#D4AF37] font-bold">🥇 1st Place ($)</Label>
                    <Input
                      type="number"
                      min="0"
                      value={leaderboardSettings.first_prize}
                      onChange={(e) => setLeaderboardSettings({...leaderboardSettings, first_prize: e.target.value})}
                      className="mt-1 text-center font-bold"
                    />
                  </div>
                  <div className="bg-gray-100 p-3 rounded-lg">
                    <Label className="text-xs text-gray-600 font-bold">🥈 2nd Place ($)</Label>
                    <Input
                      type="number"
                      min="0"
                      value={leaderboardSettings.second_prize}
                      onChange={(e) => setLeaderboardSettings({...leaderboardSettings, second_prize: e.target.value})}
                      className="mt-1 text-center font-bold"
                    />
                  </div>
                  <div className="bg-[#CD7F32]/10 p-3 rounded-lg">
                    <Label className="text-xs text-[#CD7F32] font-bold">🥉 3rd Place ($)</Label>
                    <Input
                      type="number"
                      min="0"
                      value={leaderboardSettings.third_prize}
                      onChange={(e) => setLeaderboardSettings({...leaderboardSettings, third_prize: e.target.value})}
                      className="mt-1 text-center font-bold"
                    />
                  </div>
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <Button 
                  variant="outline" 
                  className="flex-1"
                  onClick={() => setShowLeaderboardEdit(false)}
                >
                  Cancel
                </Button>
                <Button 
                  className="flex-1 bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E] font-semibold"
                  onClick={saveSettings}
                  disabled={savingSettings}
                >
                  {savingSettings ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Check className="h-4 w-4 mr-2" />}
                  Save Changes
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-2 flex-wrap">
        {["all", "pending", "approved", "active", "rejected"].map(status => (
          <Button
            key={status}
            variant={filterStatus === status ? "default" : "outline"}
            size="sm"
            onClick={() => setFilterStatus(status)}
            className={filterStatus === status ? "bg-[#2D2A2E]" : ""}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
            {status !== "all" && (
              <span className="ml-1 text-xs">
                ({status === "pending" ? stats.pending : status === "approved" ? stats.approved : status === "active" ? stats.active : applications.filter(a => a.status === status).length})
              </span>
            )}
          </Button>
        ))}
      </div>

      {/* Applications List */}
      <Card>
        <CardHeader>
          <CardTitle>Applications ({filteredApps.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {filteredApps.length === 0 ? (
            <div className="text-center py-12">
              <Users className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <p className="text-[#5A5A5A]">No applications found</p>
              <p className="text-sm text-gray-400">Share the application link with potential partners</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredApps.map(app => (
                <div 
                  key={app.id} 
                  className="border rounded-lg p-4 hover:border-[#D4AF37] transition-colors cursor-pointer"
                  onClick={() => { setSelectedInfluencer(app); setShowDetails(true); }}
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-gradient-to-br from-[#F8A5B8] to-[#D4AF37] rounded-full flex items-center justify-center text-white font-bold">
                        {app.full_name?.charAt(0) || "?"}
                      </div>
                      <div>
                        <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                          {app.full_name}
                          {getStatusBadge(app.status)}
                        </h3>
                        <div className="flex items-center gap-3 text-sm text-[#5A5A5A]">
                          <span className="flex items-center gap-1">
                            {getPlatformIcon(app.primary_platform)}
                            {app.social_handle}
                          </span>
                          <span>•</span>
                          <span>{(app.follower_count || 0).toLocaleString()} followers</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                      {/* Chat & Action Buttons - For approved/active partners */}
                      {(app.status === "approved" || app.status === "active") && (
                        <>
                          {/* Primary Chat Button with Online Indicator */}
                          <Button 
                            size="sm" 
                            className={`font-medium relative ${
                              onlinePartners[app.partner_code] 
                                ? "bg-green-500 hover:bg-green-600 text-white" 
                                : "bg-[#D4AF37] hover:bg-[#B8960F] text-[#2D2A2E]"
                            }`}
                            onClick={(e) => { e.stopPropagation(); openChatWithPartner(app); }}
                          >
                            {/* Online/Offline indicator dot */}
                            <span className={`absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full border-2 border-white ${
                              onlinePartners[app.partner_code] ? "bg-green-400 animate-pulse" : "bg-red-500"
                            }`} />
                            <MessageCircle className="h-3 w-3 mr-1" />
                            {onlinePartners[app.partner_code] ? "Live" : "Chat"}
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            className="bg-[#D4AF37]/10 border-[#D4AF37]/30 text-[#D4AF37] hover:bg-[#D4AF37]/20 text-xs sm:text-sm"
                            onClick={(e) => { e.stopPropagation(); openVoucherModal(app); }}
                          >
                            <Ticket className="h-3 w-3 sm:mr-1" />
                            <span className="hidden sm:inline">Voucher</span>
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            className="bg-purple-50 border-purple-200 text-purple-700 hover:bg-purple-100 text-xs sm:text-sm"
                            onClick={(e) => { e.stopPropagation(); setSelectedInfluencer(app); fetchPartnerVouchers(app.id); }}
                          >
                            <Gift className="h-3 w-3 sm:mr-1" />
                            <span className="hidden sm:inline">View</span>
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            className="bg-green-50 border-green-200 text-green-700 hover:bg-green-100 text-xs sm:text-sm"
                            onClick={(e) => { e.stopPropagation(); openReferralModal(app); }}
                          >
                            <Users className="h-3 w-3 sm:mr-1" />
                            <span className="hidden sm:inline">Referral</span>
                          </Button>
                        </>
                      )}
                      {app.partner_code && (
                        <div className="flex gap-1">
                          <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); copyPartnerCode(app.partner_code); }}>
                            <Copy className="h-3 w-3 mr-1" />
                            {app.partner_code}
                          </Button>
                        </div>
                      )}
                      {app.status === "pending" && (
                        <>
                          <Button size="sm" className="bg-green-500 hover:bg-green-600" onClick={(e) => { e.stopPropagation(); handleApprove(app.id); }}>
                            <Check className="h-4 w-4 mr-1" /> Approve
                          </Button>
                          <Button size="sm" variant="destructive" onClick={(e) => { e.stopPropagation(); handleReject(app.id, "Does not meet requirements"); }}>
                            <X className="h-4 w-4 mr-1" /> Reject
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  {app.status === "approved" || app.status === "active" ? (
                    <div className="mt-4 pt-4 border-t">
                      {/* Partnership Expiry Info */}
                      {app.partnership_expires_at && (
                        <div className={`mb-4 p-3 rounded-lg flex justify-between items-center ${
                          new Date(app.partnership_expires_at) < new Date() 
                            ? 'bg-red-100 border border-red-300' 
                            : app.renewal_requested 
                              ? 'bg-yellow-100 border border-yellow-300'
                              : 'bg-green-100 border border-green-300'
                        }`}>
                          <div>
                            {new Date(app.partnership_expires_at) < new Date() ? (
                              <>
                                <span className="text-red-700 font-semibold">⚠️ Partnership Expired</span>
                                <p className="text-sm text-red-600">Expired: {new Date(app.partnership_expires_at).toLocaleDateString()}</p>
                                {app.renewal_requested && (
                                  <p className="text-xs text-yellow-600 mt-1">🔄 Renewal requested on {new Date(app.renewal_requested_at).toLocaleDateString()}</p>
                                )}
                              </>
                            ) : app.renewal_requested ? (
                              <>
                                <span className="text-yellow-700 font-semibold">🔄 Renewal Requested</span>
                                <p className="text-sm text-yellow-600">Expires: {new Date(app.partnership_expires_at).toLocaleDateString()}</p>
                              </>
                            ) : (
                              <>
                                <span className="text-green-700 font-semibold">✅ Active</span>
                                <p className="text-sm text-green-600">Expires: {new Date(app.partnership_expires_at).toLocaleDateString()}</p>
                              </>
                            )}
                          </div>
                          <Button 
                            size="sm"
                            className={new Date(app.partnership_expires_at) < new Date() || app.renewal_requested 
                              ? 'bg-[#D4AF37] hover:bg-[#B8960F] text-[#2D2A2E]' 
                              : 'bg-gray-200 hover:bg-gray-300 text-gray-700'}
                            onClick={(e) => { e.stopPropagation(); renewPartnership(app.id, app.full_name); }}
                          >
                            <RefreshCw className="h-3 w-3 mr-1" />
                            Renew (+1 Year)
                          </Button>
                        </div>
                      )}
                      {/* Stats Grid */}
                      <div className="grid grid-cols-4 gap-4 text-center">
                        <div>
                          <p className="text-lg font-bold text-[#2D2A2E]">{app.total_clicks || 0}</p>
                          <p className="text-xs text-[#5A5A5A]">Clicks</p>
                        </div>
                        <div>
                          <p className="text-lg font-bold text-[#2D2A2E]">{app.total_orders || 0}</p>
                          <p className="text-xs text-[#5A5A5A]">Orders</p>
                        </div>
                        <div>
                          <p className="text-lg font-bold text-green-600">${(app.total_revenue || 0).toFixed(2)}</p>
                          <p className="text-xs text-[#5A5A5A]">Revenue</p>
                        </div>
                        <div>
                          <p className="text-lg font-bold text-[#D4AF37]">${(app.total_commission || 0).toFixed(2)}</p>
                          <p className="text-xs text-[#5A5A5A]">Commission</p>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Influencer Details Modal */}
      {showDetails && selectedInfluencer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setShowDetails(false)}>
          <Card className="max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <CardHeader className="border-b">
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    {selectedInfluencer.full_name}
                    {getStatusBadge(selectedInfluencer.status)}
                  </CardTitle>
                  <p className="text-sm text-[#5A5A5A]">Applied: {new Date(selectedInfluencer.applied_at).toLocaleDateString()}</p>
                </div>
                <Button variant="ghost" size="icon" onClick={() => setShowDetails(false)}>
                  <X className="h-5 w-5" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-6">
              {/* Contact Info */}
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-xs text-[#5A5A5A]">Email</Label>
                  <p className="font-medium">{selectedInfluencer.email}</p>
                </div>
                <div>
                  <Label className="text-xs text-[#5A5A5A]">Phone</Label>
                  <p className="font-medium">{selectedInfluencer.phone || "Not provided"}</p>
                </div>
                <div>
                  <Label className="text-xs text-[#5A5A5A]">Country</Label>
                  <p className="font-medium">{selectedInfluencer.country}</p>
                </div>
                <div>
                  <Label className="text-xs text-[#5A5A5A]">Content Niche</Label>
                  <p className="font-medium capitalize">{selectedInfluencer.content_niche}</p>
                </div>
              </div>

              {/* Social Media */}
              <div className="bg-[#FAF8F5] rounded-lg p-4">
                <h4 className="font-semibold mb-3 flex items-center gap-2">
                  {getPlatformIcon(selectedInfluencer.primary_platform)}
                  {selectedInfluencer.primary_platform?.charAt(0).toUpperCase() + selectedInfluencer.primary_platform?.slice(1)}
                </h4>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-2xl font-bold text-[#2D2A2E]">{(selectedInfluencer.follower_count || 0).toLocaleString()}</p>
                    <p className="text-xs text-[#5A5A5A]">Followers</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-[#2D2A2E]">{selectedInfluencer.engagement_rate || 0}%</p>
                    <p className="text-xs text-[#5A5A5A]">Engagement</p>
                  </div>
                  <div>
                    <a href={selectedInfluencer.profile_url} target="_blank" rel="noopener noreferrer" className="inline-block">
                      <Button variant="outline" size="sm">
                        <ExternalLink className="h-3 w-3 mr-1" /> View Profile
                      </Button>
                    </a>
                  </div>
                </div>
              </div>

              {/* Application Text */}
              <div>
                <Label className="text-xs text-[#5A5A5A]">Why they want to partner</Label>
                <p className="mt-1 text-[#2D2A2E] bg-gray-50 p-3 rounded">{selectedInfluencer.why_partner}</p>
              </div>
              {selectedInfluencer.content_ideas && (
                <div>
                  <Label className="text-xs text-[#5A5A5A]">Content Ideas</Label>
                  <p className="mt-1 text-[#2D2A2E] bg-gray-50 p-3 rounded">{selectedInfluencer.content_ideas}</p>
                </div>
              )}

              {/* Partner Code (if approved) */}
              {selectedInfluencer.partner_code && (
                <div className="bg-gradient-to-r from-[#D4AF37]/10 to-[#F4D03F]/10 rounded-lg p-4">
                  <h4 className="font-semibold mb-3 text-[#D4AF37]">Partner Details</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-[#5A5A5A]">Code:</span>
                      <div className="flex gap-2">
                        <code className="bg-white px-3 py-1 rounded font-bold">{selectedInfluencer.partner_code}</code>
                        <Button size="sm" variant="outline" onClick={() => copyPartnerCode(selectedInfluencer.partner_code)}>
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[#5A5A5A]">Link:</span>
                      <div className="flex gap-2">
                        <code className="bg-white px-3 py-1 rounded text-sm">/partner/{selectedInfluencer.partner_code?.toLowerCase()}</code>
                        <Button size="sm" variant="outline" onClick={() => copyPartnerLink(selectedInfluencer.partner_code)}>
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#5A5A5A]">Commission:</span>
                      <span className="font-bold text-green-600">{selectedInfluencer.custom_commission || 10}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#5A5A5A]">Customer Discount:</span>
                      <span className="font-bold text-[#F8A5B8]">{selectedInfluencer.custom_discount || 50}%</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-4 border-t flex-wrap">
                {selectedInfluencer.status === "pending" && (
                  <>
                    <Button className="flex-1 bg-green-500 hover:bg-green-600" onClick={() => handleApprove(selectedInfluencer.id)}>
                      <Check className="h-4 w-4 mr-2" /> Approve Partner
                    </Button>
                    <Button variant="destructive" className="flex-1" onClick={() => handleReject(selectedInfluencer.id, "Does not meet our requirements at this time")}>
                      <X className="h-4 w-4 mr-2" /> Reject
                    </Button>
                  </>
                )}
                {(selectedInfluencer.status === "approved" || selectedInfluencer.status === "active") && (
                  <>
                    <Button variant="outline" className="flex-1" onClick={() => copyPartnerLink(selectedInfluencer.partner_code)}>
                      <Copy className="h-4 w-4 mr-2" /> Copy Partner Link
                    </Button>
                    <Button 
                      className="flex-1 bg-blue-500 hover:bg-blue-600 text-white" 
                      onClick={() => { setShowDetails(false); openMessageModal(selectedInfluencer); }}
                    >
                      <MessageCircle className="h-4 w-4 mr-2" /> Send Message
                    </Button>
                    <Button 
                      variant="outline" 
                      className="flex-1"
                      onClick={() => { setShowDetails(false); fetchPartnerMessages(selectedInfluencer.id); }}
                    >
                      <FileText className="h-4 w-4 mr-2" /> View History
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Partner Message Modal - Using Dialog for proper portal rendering */}
      <Dialog open={showMessageModal} onOpenChange={setShowMessageModal}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MessageCircle className="h-5 w-5 text-blue-600" />
              Send Message to {messageTarget?.full_name}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {/* Message Type */}
            <div>
              <Label className="text-sm font-medium">Message Type</Label>
              <Select value={messageData.type} onValueChange={(v) => setMessageData({...messageData, type: v})}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="message">💬 General Message</SelectItem>
                  <SelectItem value="task">📋 Task / Action Required</SelectItem>
                  <SelectItem value="announcement">📢 Announcement</SelectItem>
                  <SelectItem value="reward">🎁 Reward / Bonus</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Priority */}
            <div>
              <Label className="text-sm font-medium">Priority</Label>
              <Select value={messageData.priority} onValueChange={(v) => setMessageData({...messageData, priority: v})}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">🟢 Low</SelectItem>
                  <SelectItem value="normal">🔵 Normal</SelectItem>
                  <SelectItem value="high">🟠 High</SelectItem>
                  <SelectItem value="urgent">🔴 Urgent</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Quick Coupon Insert - All Partner Coupons */}
            <div className="bg-gradient-to-r from-purple-50 to-pink-50 p-4 rounded-lg border border-purple-200">
              <Label className="text-sm font-medium flex items-center gap-2 mb-3">
                <Gift className="h-4 w-4 text-purple-600" />
                Attach Coupon / Code
              </Label>
              
              <div className="space-y-3 max-h-60 overflow-y-auto">
                {/* Partner's Main Referral Code */}
                {messageTarget?.partner_code && (
                  <div 
                    className="flex items-center justify-between p-3 bg-white rounded-lg border cursor-pointer hover:border-purple-400 hover:shadow-sm transition-all"
                    onClick={() => {
                      const refMessage = `🎉 Here's your personal referral code!\n\nCode: ${messageTarget.partner_code}\nDiscount: ${messageTarget.custom_discount || 50}% OFF\n\nShare this code with your audience. When they use it at checkout, they get ${messageTarget.custom_discount || 50}% off and you earn ${messageTarget.custom_commission || 10}% commission!\n\n💜 Thank you for being our partner!`;
                      setMessageData({
                        ...messageData, 
                        type: 'reward',
                        subject: `Your Referral Code: ${messageTarget.partner_code}`,
                        content: refMessage
                      });
                      toast.success("✅ Main referral code attached!");
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
                        <Tag className="h-4 w-4 text-purple-600" />
                      </div>
                      <div>
                        <p className="font-medium text-sm">{messageTarget.partner_code}</p>
                        <p className="text-xs text-gray-500">Main Referral • {messageTarget.custom_discount || 50}% OFF</p>
                      </div>
                    </div>
                    <Badge className="bg-purple-100 text-purple-700 text-xs">Attach</Badge>
                  </div>
                )}

                {/* Partner's Vouchers */}
                {messageTarget?.vouchers?.map((voucher, idx) => (
                  <div 
                    key={`voucher-${idx}`}
                    className="flex items-center justify-between p-3 bg-white rounded-lg border cursor-pointer hover:border-pink-400 hover:shadow-sm transition-all"
                    onClick={() => {
                      const voucherMessage = `🎁 Special Offer Just For You!\n\nVoucher Code: ${voucher.code}\nDiscount: ${voucher.discount_type === 'percentage' ? `${voucher.discount_value}% OFF` : `$${voucher.discount_value} OFF`}${voucher.min_order > 0 ? `\nMinimum Order: $${voucher.min_order}` : ''}\n\nShare this exclusive voucher with your audience!\n\n${voucher.valid_until ? `⏰ Valid until: ${new Date(voucher.valid_until).toLocaleDateString()}` : '⏰ Limited time!'}\n\n💜 Thank you for being our partner!`;
                      setMessageData({
                        ...messageData,
                        type: 'reward',
                        subject: `Your Voucher Code: ${voucher.code}`,
                        content: voucherMessage
                      });
                      toast.success("✅ Voucher attached!");
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-pink-100 flex items-center justify-center">
                        <Ticket className="h-4 w-4 text-pink-600" />
                      </div>
                      <div>
                        <p className="font-medium text-sm">{voucher.code}</p>
                        <p className="text-xs text-gray-500">Voucher • {voucher.discount_type === 'percentage' ? `${voucher.discount_value}%` : `$${voucher.discount_value}`} OFF</p>
                      </div>
                    </div>
                    <Badge className="bg-pink-100 text-pink-700 text-xs">Attach</Badge>
                  </div>
                ))}

                {/* Partner's Referral Programs */}
                {messageTarget?.referral_programs?.map((ref, idx) => (
                  <div 
                    key={`ref-${idx}`}
                    className="flex items-center justify-between p-3 bg-white rounded-lg border cursor-pointer hover:border-indigo-400 hover:shadow-sm transition-all"
                    onClick={() => {
                      const refProgramMessage = `🔗 Your Referral Program!\n\nCode: ${ref.referral_code}\nProgram: ${ref.name}\n\nHow it works:\n• Share this code with your audience\n• When ${ref.required_referrals} people ${ref.referral_action === 'signup' ? 'sign up' : 'make a purchase'}\n• You earn ${ref.reward_discount_percent}% reward!\n\n🚀 Start sharing and earning!\n\n💜 Thank you for being our partner!`;
                      setMessageData({
                        ...messageData,
                        type: 'reward',
                        subject: `Your Referral Program: ${ref.referral_code}`,
                        content: refProgramMessage
                      });
                      toast.success("✅ Referral program attached!");
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center">
                        <Link2 className="h-4 w-4 text-indigo-600" />
                      </div>
                      <div>
                        <p className="font-medium text-sm">{ref.referral_code}</p>
                        <p className="text-xs text-gray-500">{ref.name} • {ref.reward_discount_percent}% reward</p>
                      </div>
                    </div>
                    <Badge className="bg-indigo-100 text-indigo-700 text-xs">Attach</Badge>
                  </div>
                ))}

                {/* No coupons message */}
                {!messageTarget?.partner_code && !messageTarget?.vouchers?.length && !messageTarget?.referral_programs?.length && (
                  <p className="text-sm text-gray-500 text-center py-2">No coupons available for this partner</p>
                )}

                {/* Manual entry for new code */}
                <div className="pt-2 border-t">
                  <p className="text-xs text-gray-500 mb-2">Or enter a new code manually:</p>
                  <div className="flex gap-2">
                    <Input 
                      placeholder="Enter any code..."
                      id="manual-coupon-input"
                      className="flex-1 h-9 text-sm"
                    />
                    <Button 
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        const code = document.getElementById('manual-coupon-input').value.trim().toUpperCase();
                        if (!code) {
                          toast.error("Please enter a code");
                          return;
                        }
                        const manualMessage = `🎁 Special Code For You!\n\nCode: ${code}\n\nUse this code at checkout to claim your discount.\n\n💜 Thank you for being our partner!`;
                        setMessageData({
                          ...messageData,
                          type: 'reward',
                          subject: `Your Code: ${code}`,
                          content: manualMessage
                        });
                        document.getElementById('manual-coupon-input').value = '';
                        toast.success("✅ Code attached!");
                      }}
                    >
                      Attach
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            {/* Subject */}
            <div>
              <Label className="text-sm font-medium">Subject</Label>
              <Input 
                placeholder="Message subject..."
                value={messageData.subject}
                onChange={(e) => setMessageData({...messageData, subject: e.target.value})}
              />
            </div>

            {/* Content */}
            <div>
              <Label className="text-sm font-medium">Message *</Label>
              <Textarea 
                placeholder="Write your message here..."
                value={messageData.content}
                onChange={(e) => setMessageData({...messageData, content: e.target.value})}
                rows={4}
                className="resize-none"
              />
            </div>

            {/* File Attachments */}
            <div>
              <Label className="text-sm font-medium">Attachments ({messageData.files.length}/10)</Label>
              <div className="mt-2 space-y-2">
                {messageData.files.map((file, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-gray-50 p-2 rounded-lg">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-gray-500" />
                      <span className="text-sm truncate max-w-[200px]">{file.name}</span>
                    </div>
                    <Button size="sm" variant="ghost" onClick={() => removeFile(idx)}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                <label className="flex items-center justify-center gap-2 p-4 border-2 border-dashed rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                  <input type="file" className="hidden" multiple onChange={handleFileUpload} disabled={uploadingFile || messageData.files.length >= 10} />
                  {uploadingFile ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Uploading...</>
                  ) : (
                    <><Upload className="h-4 w-4 text-gray-500" /> <span className="text-sm text-gray-500">Click to upload files (max 10)</span></>
                  )}
                </label>
              </div>
            </div>

            {/* Notification Options */}
            <div className="bg-gray-50 p-4 rounded-lg space-y-3">
              <Label className="text-sm font-medium">Notification Preferences</Label>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={messageData.send_email}
                    onChange={(e) => setMessageData({...messageData, send_email: e.target.checked})}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm">📧 Send Email</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={messageData.send_sms}
                    onChange={(e) => setMessageData({...messageData, send_sms: e.target.checked})}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm">📱 Send SMS</span>
                </label>
              </div>
              {messageTarget?.email && <p className="text-xs text-gray-500">Partner will receive notification at: {messageTarget.email}</p>}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowMessageModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-gradient-to-r from-blue-500 to-indigo-500 text-white"
              onClick={sendMessage}
              disabled={sendingMessage || !messageData.content.trim()}
            >
              {sendingMessage ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Sending...</>
              ) : (
                <><Send className="h-4 w-4 mr-2" /> Send Message</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Messages History Modal - Using Dialog */}
      <Dialog open={showMessagesHistory} onOpenChange={setShowMessagesHistory}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MessageCircle className="h-5 w-5 text-blue-600" />
              Messages with {selectedInfluencer?.full_name}
            </DialogTitle>
          </DialogHeader>
          <div className="py-4">
            {partnerMessages.length === 0 ? (
              <div className="text-center py-8">
                <MessageCircle className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No messages yet</p>
              </div>
            ) : (
              <div className="space-y-4">
                {partnerMessages.map(msg => (
                  <div key={msg.id} className={`p-4 rounded-lg border ${msg.priority === 'urgent' ? 'border-red-200 bg-red-50' : msg.priority === 'high' ? 'border-orange-200 bg-orange-50' : 'border-gray-200 bg-gray-50'}`}>
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{msg.type === 'task' ? '📋' : msg.type === 'announcement' ? '📢' : msg.type === 'reward' ? '🎁' : '💬'}</span>
                        <span className="font-semibold">{msg.subject || 'No Subject'}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {msg.read && <span className="text-xs text-green-600">✓ Read</span>}
                        <span className="text-xs text-gray-500">{new Date(msg.sent_at).toLocaleString()}</span>
                      </div>
                    </div>
                    <p className="text-gray-700 whitespace-pre-wrap">{msg.content}</p>
                    {msg.files?.length > 0 && (
                      <div className="mt-3 pt-3 border-t flex flex-wrap gap-2">
                        {msg.files.map((file, idx) => (
                          <a key={idx} href={file.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-sm text-blue-600 hover:underline bg-blue-50 px-2 py-1 rounded">
                            <FileText className="h-3 w-3" /> {file.name}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Create Voucher Modal - Using Dialog */}
      <Dialog open={showVoucherModal} onOpenChange={setShowVoucherModal}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader className="bg-gradient-to-r from-[#D4AF37]/20 to-[#F4D03F]/20 -mx-6 -mt-6 px-6 py-4 mb-4 rounded-t-lg">
            <DialogTitle className="flex items-center gap-2">
              <Ticket className="h-5 w-5 text-[#D4AF37]" />
              Create Voucher for {voucherTarget?.full_name}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {/* Voucher Code */}
            <div>
              <Label className="text-sm font-medium">Voucher Code *</Label>
              <Input 
                placeholder="e.g., SARAH20"
                value={voucherData.code}
                onChange={(e) => setVoucherData({...voucherData, code: e.target.value.toUpperCase()})}
                className="font-mono uppercase"
              />
              <p className="text-xs text-gray-500 mt-1">Partner will share this code with their audience</p>
            </div>

            {/* Discount Settings */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-medium">Discount Type</Label>
                <Select value={voucherData.discount_type} onValueChange={(v) => setVoucherData({...voucherData, discount_type: v})}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="percentage">Percentage (%)</SelectItem>
                    <SelectItem value="fixed">Fixed Amount ($)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-sm font-medium">Discount Value</Label>
                <Input 
                  type="number"
                  min="0"
                  value={voucherData.discount_value}
                  onChange={(e) => setVoucherData({...voucherData, discount_value: parseFloat(e.target.value) || 0})}
                />
              </div>
            </div>

            {/* Partner Commission */}
            <div className="bg-[#D4AF37]/10 p-4 rounded-lg">
              <Label className="text-sm font-medium flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-[#D4AF37]" />
                Partner Commission (%)
              </Label>
              <Input 
                type="number"
                min="0"
                max="100"
                value={voucherData.partner_commission}
                onChange={(e) => setVoucherData({...voucherData, partner_commission: parseFloat(e.target.value) || 0})}
                className="mt-2"
              />
              <p className="text-xs text-gray-600 mt-1">Partner earns {voucherData.partner_commission}% commission on each sale using this voucher</p>
            </div>

            {/* Usage Limits */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-medium">Min Order ($)</Label>
                <Input 
                  type="number"
                  min="0"
                  value={voucherData.min_order}
                  onChange={(e) => setVoucherData({...voucherData, min_order: parseFloat(e.target.value) || 0})}
                />
              </div>
              <div>
                <Label className="text-sm font-medium">Max Uses (0 = Unlimited)</Label>
                <Input 
                  type="number"
                  min="0"
                  value={voucherData.max_uses}
                  onChange={(e) => setVoucherData({...voucherData, max_uses: parseInt(e.target.value) || 0})}
                />
              </div>
            </div>

            {/* Validity Period */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-medium">Valid From</Label>
                <Input 
                  type="date"
                  value={voucherData.valid_from}
                  onChange={(e) => setVoucherData({...voucherData, valid_from: e.target.value})}
                />
              </div>
              <div>
                <Label className="text-sm font-medium">Valid Until</Label>
                <Input 
                  type="date"
                  value={voucherData.valid_until}
                  onChange={(e) => setVoucherData({...voucherData, valid_until: e.target.value})}
                />
              </div>
            </div>

            {/* Description */}
            <div>
              <Label className="text-sm font-medium">Description (Optional)</Label>
              <Textarea 
                placeholder="Internal notes about this voucher..."
                value={voucherData.description}
                onChange={(e) => setVoucherData({...voucherData, description: e.target.value})}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter className="pt-4">
            <Button variant="outline" onClick={() => setShowVoucherModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E] font-semibold"
              onClick={createVoucher}
              disabled={creatingVoucher || !voucherData.code.trim()}
            >
              {creatingVoucher ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Creating...</>
              ) : (
                <><Ticket className="h-4 w-4 mr-2" /> Create Voucher</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Partner Vouchers History Modal - Using Dialog */}
      <Dialog open={showVouchersHistory} onOpenChange={setShowVouchersHistory}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex justify-between items-center">
              <DialogTitle className="flex items-center gap-2">
                <Gift className="h-5 w-5 text-purple-600" />
                Vouchers for {selectedInfluencer?.full_name}
              </DialogTitle>
              <Button 
                size="sm"
                className="bg-[#D4AF37] hover:bg-[#B8960F] text-[#2D2A2E]"
                onClick={() => { setShowVouchersHistory(false); openVoucherModal(selectedInfluencer); }}
              >
                <Plus className="h-4 w-4 mr-1" /> New Voucher
              </Button>
            </div>
          </DialogHeader>
          <div className="py-4">
            {partnerVouchers.length === 0 ? (
              <div className="text-center py-8">
                <Ticket className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No vouchers created yet</p>
                <Button 
                  className="mt-4 bg-[#D4AF37] hover:bg-[#B8960F] text-[#2D2A2E]"
                  onClick={() => { setShowVouchersHistory(false); openVoucherModal(selectedInfluencer); }}
                >
                  <Plus className="h-4 w-4 mr-2" /> Create First Voucher
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                {partnerVouchers.map(voucher => (
                  <div key={voucher.id} className={`p-4 rounded-lg border ${voucher.is_active ? 'border-green-200 bg-green-50/50' : 'border-gray-200 bg-gray-50'}`}>
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <code className="text-lg font-bold bg-white px-3 py-1 rounded border">{voucher.code}</code>
                          <Badge className={voucher.is_active ? 'bg-green-500' : 'bg-gray-400'}>
                            {voucher.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-500 mt-1">
                          {voucher.discount_type === 'percentage' ? `${voucher.discount_value}% off` : `$${voucher.discount_value} off`}
                          {voucher.min_order > 0 && ` • Min order: $${voucher.min_order}`}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          variant="outline"
                          className="text-blue-600 border-blue-200 hover:bg-blue-50"
                          onClick={() => {
                            // Close vouchers modal and open message modal with voucher pre-filled
                            const voucherMessage = `🎁 Special Offer Just For You!\n\nVoucher Code: ${voucher.code}\nDiscount: ${voucher.discount_type === 'percentage' ? `${voucher.discount_value}% OFF` : `$${voucher.discount_value} OFF`}${voucher.min_order > 0 ? `\nMinimum Order: $${voucher.min_order}` : ''}\n\nShare this exclusive voucher code with your audience. When they use it at checkout, they get the discount and you earn ${voucher.partner_commission}% commission!\n\n⏰ ${voucher.valid_until ? `Valid until: ${new Date(voucher.valid_until).toLocaleDateString()}` : 'Limited time offer!'}\n\n💜 Thank you for being our partner!`;
                            
                            setMessageData({
                              type: 'reward',
                              subject: `Your Voucher Code: ${voucher.code}`,
                              content: voucherMessage,
                              priority: 'normal',
                              send_email: true,
                              send_sms: false,
                              files: []
                            });
                            setMessageTarget(selectedInfluencer);
                            setShowVouchersHistory(false);
                            setShowMessageModal(true);
                            toast.success("Voucher attached to message!");
                          }}
                        >
                          <Send className="h-3 w-3 mr-1" /> Send
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => { navigator.clipboard.writeText(voucher.code); toast.success("Code copied!"); }}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          className={voucher.is_active ? 'text-orange-600' : 'text-green-600'}
                          onClick={() => toggleVoucherStatus(voucher)}
                        >
                          {voucher.is_active ? 'Deactivate' : 'Activate'}
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          className="text-red-600"
                          onClick={() => deleteVoucher(voucher.id, voucher.partner_id)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                    <div className="grid grid-cols-4 gap-4 text-center bg-white rounded-lg p-3">
                      <div>
                        <p className="text-lg font-bold text-[#D4AF37]">{voucher.partner_commission}%</p>
                        <p className="text-xs text-gray-500">Commission</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-blue-600">{voucher.current_uses || 0}</p>
                        <p className="text-xs text-gray-500">Uses{voucher.max_uses > 0 ? ` / ${voucher.max_uses}` : ''}</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-green-600">${(voucher.total_revenue || 0).toFixed(2)}</p>
                        <p className="text-xs text-gray-500">Revenue</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-purple-600">${(voucher.total_commission_earned || 0).toFixed(2)}</p>
                        <p className="text-xs text-gray-500">Earned</p>
                      </div>
                    </div>
                    {voucher.valid_from && voucher.valid_until && (
                      <p className="text-xs text-gray-500 mt-2">
                        Valid: {new Date(voucher.valid_from).toLocaleDateString()} - {new Date(voucher.valid_until).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Create Partner Referral Modal - Using Dialog */}
      <Dialog open={showReferralModal} onOpenChange={setShowReferralModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Users className="h-5 w-5 text-green-600" />
              Create Referral Program for {referralTarget?.full_name}
            </DialogTitle>
            <DialogDescription>
              Reward this partner's audience for referring new customers
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {/* Program Name */}
            <div>
              <Label className="text-sm font-medium">Program Name</Label>
              <Input 
                placeholder="e.g., Refer a Friend"
                value={referralData.name}
                onChange={(e) => setReferralData({...referralData, name: e.target.value})}
                className="mt-1"
              />
            </div>

            {/* Reward & Required Referrals */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-medium">Reward Discount %</Label>
                <Input 
                  type="number"
                  min="1"
                  max="100"
                  value={referralData.reward_discount_percent}
                  onChange={(e) => setReferralData({...referralData, reward_discount_percent: parseInt(e.target.value) || 0})}
                  onFocus={(e) => e.target.select()}
                  placeholder="15"
                  className="mt-1"
                />
              </div>
              <div>
                <Label className="text-sm font-medium">Required Referrals</Label>
                <Input 
                  type="number"
                  min="1"
                  value={referralData.required_referrals}
                  onChange={(e) => setReferralData({...referralData, required_referrals: parseInt(e.target.value) || 1})}
                  onFocus={(e) => e.target.select()}
                  placeholder="3"
                  className="mt-1"
                />
              </div>
            </div>

            {/* Referral Action */}
            <div>
              <Label className="text-sm font-medium">Referral Action</Label>
              <Select value={referralData.referral_action} onValueChange={(v) => setReferralData({...referralData, referral_action: v})}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="signup">New Signup</SelectItem>
                  <SelectItem value="purchase">New Purchase</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500 mt-1">
                Customers earn {referralData.reward_discount_percent}% reward after {referralData.required_referrals} successful {referralData.referral_action === 'signup' ? 'signups' : 'purchases'}
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowReferralModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-green-500 hover:bg-green-600 text-white"
              onClick={createPartnerReferral}
              disabled={creatingReferral || !referralData.name.trim()}
            >
              {creatingReferral ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Creating...</>
              ) : (
                <>Create Program</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Partner Referrals History Modal - Using Dialog */}
      <Dialog open={showReferralsHistory} onOpenChange={setShowReferralsHistory}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex justify-between items-center">
              <DialogTitle className="flex items-center gap-2">
                <Link2 className="h-5 w-5 text-indigo-600" />
                Referral Programs for {selectedInfluencer?.full_name}
              </DialogTitle>
              <Button 
                size="sm"
                className="bg-green-500 hover:bg-green-600 text-white"
                onClick={() => { setShowReferralsHistory(false); openReferralModal(selectedInfluencer); }}
              >
                <Plus className="h-4 w-4 mr-1" /> New Referral
              </Button>
            </div>
          </DialogHeader>
          <div className="py-4">
            {partnerReferrals.length === 0 ? (
              <div className="text-center py-8">
                <Users className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No referral programs created yet</p>
                <Button 
                  className="mt-4 bg-green-500 hover:bg-green-600 text-white"
                  onClick={() => { setShowReferralsHistory(false); openReferralModal(selectedInfluencer); }}
                >
                  <Plus className="h-4 w-4 mr-2" /> Create First Referral Program
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                {partnerReferrals.map(referral => (
                  <div key={referral.id} className={`p-4 rounded-lg border ${referral.is_active ? 'border-green-200 bg-green-50/50' : 'border-gray-200 bg-gray-50'}`}>
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-lg font-bold">{referral.name}</span>
                          <Badge className={referral.is_active ? 'bg-green-500' : 'bg-gray-400'}>
                            {referral.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <code className="text-sm bg-white px-2 py-0.5 rounded border">{referral.referral_code}</code>
                          <Button size="sm" variant="ghost" onClick={() => copyReferralLink(referral)}>
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
                        <p className="text-sm text-gray-500 mt-1">
                          {referral.reward_discount_percent}% reward after {referral.required_referrals} {referral.referral_action === 'signup' ? 'signups' : 'purchases'}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          variant="outline"
                          className="text-blue-600 border-blue-200 hover:bg-blue-50"
                          onClick={() => {
                            // Close referrals modal and open message modal with referral pre-filled
                            const refMessage = `🔗 Your Referral Program Code!\n\nReferral Code: ${referral.referral_code}\nProgram: ${referral.name}\n\nHow it works:\n• Share this code with your audience\n• When ${referral.required_referrals} people ${referral.referral_action === 'signup' ? 'sign up' : 'make a purchase'} using your code\n• You earn ${referral.reward_discount_percent}% reward!\n\nShare Link: ${window.location.origin}/ref/${referral.referral_code.toLowerCase()}\n\n🚀 Start sharing and earning today!\n\n💜 Thank you for being our partner!`;
                            
                            setMessageData({
                              type: 'reward',
                              subject: `Your Referral Code: ${referral.referral_code}`,
                              content: refMessage,
                              priority: 'normal',
                              send_email: true,
                              send_sms: false,
                              files: []
                            });
                            setMessageTarget(selectedInfluencer);
                            setShowReferralsHistory(false);
                            setShowMessageModal(true);
                            toast.success("Referral code attached to message!");
                          }}
                        >
                          <Send className="h-3 w-3 mr-1" /> Send
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          className={referral.is_active ? 'text-orange-600' : 'text-green-600'}
                          onClick={() => toggleReferralStatus(referral)}
                        >
                          {referral.is_active ? 'Deactivate' : 'Activate'}
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          className="text-red-600"
                          onClick={() => deleteReferral(referral.id, referral.partner_id)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-center bg-white rounded-lg p-3">
                      <div>
                        <p className="text-lg font-bold text-blue-600">{referral.total_referrals || 0}</p>
                        <p className="text-xs text-gray-500">Total Referrals</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-green-600">{referral.successful_referrals || 0}</p>
                        <p className="text-xs text-gray-500">Successful</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-purple-600">{referral.rewards_earned || 0}</p>
                        <p className="text-xs text-gray-500">Rewards Earned</p>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      Created: {new Date(referral.created_at).toLocaleDateString()}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Influencer Preview Modal */}
      <Dialog open={showInfluencerPreview} onOpenChange={setShowInfluencerPreview}>
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-auto p-0">
          <DialogHeader className="p-6 pb-0">
            <DialogTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5 text-[#D4AF37]" />
              Influencer Dashboard Preview
            </DialogTitle>
            <DialogDescription>
              This is what your influencers see when they access their dashboard
            </DialogDescription>
          </DialogHeader>
          
          {/* Partner Selection */}
          <div className="px-6 py-4 border-b bg-gray-50">
            <Label className="text-sm font-medium mb-2 block">Preview as Partner:</Label>
            <Select 
              value={previewPartner?.partner_code || ""} 
              onValueChange={(code) => {
                const partner = applications.find(a => a.partner_code === code);
                setPreviewPartner(partner);
              }}
            >
              <SelectTrigger className="w-full max-w-md">
                <SelectValue placeholder="Select a partner to preview their view..." />
              </SelectTrigger>
              <SelectContent>
                {applications.filter(a => a.status === "approved").map(app => (
                  <SelectItem key={app.partner_code} value={app.partner_code}>
                    {app.name} ({app.partner_code})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Preview Content */}
          <div className="p-6">
            {previewPartner ? (
              <div className="space-y-6">
                {/* Welcome Header */}
                <div className="bg-gradient-to-r from-[#2D2A2E] to-[#3D3A3E] rounded-xl p-6 text-white">
                  <h2 className="text-2xl font-display font-bold mb-2">Welcome back, {previewPartner.name}!</h2>
                  <p className="text-white/70">Partner Code: <span className="font-mono bg-white/10 px-2 py-1 rounded">{previewPartner.partner_code}</span></p>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Card className="bg-gradient-to-br from-[#D4AF37]/10 to-[#F4D03F]/10 border-[#D4AF37]/20">
                    <CardContent className="p-4 text-center">
                      <p className="text-2xl font-bold text-[#D4AF37]">{previewPartner.total_referrals || 0}</p>
                      <p className="text-xs text-[#5A5A5A]">Total Referrals</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-green-50 border-green-200">
                    <CardContent className="p-4 text-center">
                      <p className="text-2xl font-bold text-green-600">${previewPartner.earnings || 0}</p>
                      <p className="text-xs text-[#5A5A5A]">Earnings</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-blue-50 border-blue-200">
                    <CardContent className="p-4 text-center">
                      <p className="text-2xl font-bold text-blue-600">{previewPartner.conversions || 0}</p>
                      <p className="text-xs text-[#5A5A5A]">Conversions</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-purple-50 border-purple-200">
                    <CardContent className="p-4 text-center">
                      <p className="text-2xl font-bold text-purple-600">{previewPartner.custom_commission || 10}%</p>
                      <p className="text-xs text-[#5A5A5A]">Your Commission</p>
                    </CardContent>
                  </Card>
                </div>

                {/* Shareable Links */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Link2 className="h-5 w-5 text-[#D4AF37]" />
                      Your Shareable Links
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
                      <Input 
                        readOnly 
                        value={`${window.location.origin}/ref/${previewPartner.partner_code}`}
                        className="flex-1 bg-white"
                      />
                      <Button size="sm" variant="outline">
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
                      <Input 
                        readOnly 
                        value={`${window.location.origin}/waitlist?ref=${previewPartner.partner_code}`}
                        className="flex-1 bg-white"
                      />
                      <Button size="sm" variant="outline">
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                {/* Discount Breakdown */}
                <Card className="border-[#D4AF37]/30">
                  <CardHeader className="bg-gradient-to-r from-[#D4AF37]/10 to-[#F4D03F]/10">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Sparkles className="h-5 w-5 text-[#D4AF37]" />
                      Founding Member Discount Stack
                    </CardTitle>
                    <CardDescription>What your audience gets with your link</CardDescription>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="divide-y">
                      <div className="flex justify-between items-center px-6 py-3">
                        <span className="text-sm text-gray-600">Retail Value</span>
                        <span className="font-medium">$100.00</span>
                      </div>
                      <div className="flex justify-between items-center px-6 py-3">
                        <span className="text-sm text-gray-600">Founder's Launch Subsidy</span>
                        <span className="font-medium text-[#D4AF37]">-50%</span>
                      </div>
                      <div className="flex justify-between items-center px-6 py-3 bg-[#F8A5B8]/10">
                        <span className="text-sm text-gray-600">Your Influencer Referral (Customer Discount)</span>
                        <span className="font-medium text-[#F8A5B8]">-50%</span>
                      </div>
                      <div className="flex justify-between items-center px-6 py-3">
                        <span className="text-sm text-gray-600">First-Time Protocol Access</span>
                        <span className="font-medium text-[#D4AF37]">-25%</span>
                      </div>
                      <div className="flex justify-between items-center px-6 py-4 bg-gradient-to-r from-[#D4AF37]/10 to-[#F4D03F]/10">
                        <span className="font-semibold">Final Price for Your Audience</span>
                        <span className="text-xl font-bold text-[#D4AF37]">$70</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Commission Info */}
                <Card className="border-purple-200 bg-purple-50/50">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-purple-900">Your Commission Rate</p>
                        <p className="text-sm text-purple-600">You earn {previewPartner.custom_commission || 10}% of each sale made with your code</p>
                      </div>
                      <div className="text-right">
                        <p className="text-2xl font-bold text-purple-600">{previewPartner.custom_commission || 10}%</p>
                        <p className="text-xs text-purple-500">per sale</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Quick Actions */}
                <div className="flex gap-3">
                  <Button 
                    className="flex-1 bg-[#D4AF37] hover:bg-[#B8960F] text-[#2D2A2E]"
                    onClick={() => window.open(`/partner/${previewPartner.partner_code}`, '_blank')}
                  >
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Open Landing Page
                  </Button>
                  <Button variant="outline" className="flex-1">
                    <MessageCircle className="h-4 w-4 mr-2" />
                    Contact Support
                  </Button>
                </div>

                {/* Partner's Chat View Preview */}
                <Card className="border-[#D4AF37]/30 mt-6">
                  <CardHeader className="bg-[#FAF8F5]">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <MessageCircle className="h-5 w-5 text-[#D4AF37]" />
                      What {previewPartner.full_name || previewPartner.name}'s Chat Looks Like
                      <Badge className="ml-2 bg-green-100 text-green-700 text-xs">Partner View</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4">
                    <div className="bg-[#FAF8F5] rounded-lg p-3 space-y-3 min-h-[200px] max-h-[300px] overflow-y-auto">
                      {/* Sample Admin Message */}
                      <div className="flex justify-start">
                        <div className="max-w-[80%] rounded-lg px-3 py-2 bg-white border border-gray-200">
                          <p className="text-sm">Welcome to the {brandName} Partner Program! Your unique code is ready to share.</p>
                          <p className="text-xs mt-1 text-gray-400">
                            <span className="font-medium">Admin • </span>
                            {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                      </div>
                      {/* Sample Partner Reply */}
                      <div className="flex justify-end">
                        <div className="max-w-[80%] rounded-lg px-3 py-2 bg-[#D4AF37] text-white">
                          <p className="text-sm">Thanks! How does the commission work?</p>
                          <p className="text-xs mt-1 text-white/70">
                            {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                      </div>
                      {/* Admin Response */}
                      <div className="flex justify-start">
                        <div className="max-w-[80%] rounded-lg px-3 py-2 bg-white border border-gray-200">
                          <p className="text-sm">You earn {previewPartner.custom_commission || 10}% commission on every sale made with your code. Your audience gets {previewPartner.custom_discount || 50}% off!</p>
                          <p className="text-xs mt-1 text-gray-400">
                            <span className="font-medium">Admin • </span>
                            {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500 mt-2 text-center">
                      💡 This is how messages appear in the partner's "Chat with Admin" widget on their Account page
                    </p>
                  </CardContent>
                </Card>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <Eye className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p>Select a partner above to preview their dashboard view</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// Team Manager Component - Role-Based Access Control
const TeamManager = () => {
  const [roles, setRoles] = useState([]);
  const [teamMembers, setTeamMembers] = useState([]);
  const [permissionsList, setPermissionsList] = useState({ features: [], actions: [] });
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState("members"); // members, roles
  const [showRoleForm, setShowRoleForm] = useState(false);
  const [showMemberForm, setShowMemberForm] = useState(false);
  const [editingRole, setEditingRole] = useState(null);
  const [editingMember, setEditingMember] = useState(null);
  const [myPermissions, setMyPermissions] = useState(null);
  const [teamSearch, setTeamSearch] = useState("");
  
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  // Filter team members by search
  const filteredTeamMembers = React.useMemo(() => {
    if (!teamSearch.trim()) return teamMembers;
    const q = teamSearch.toLowerCase();
    return teamMembers.filter(m => 
      m.email?.toLowerCase().includes(q) ||
      m.first_name?.toLowerCase().includes(q) ||
      m.last_name?.toLowerCase().includes(q) ||
      m.role_name?.toLowerCase().includes(q)
    );
  }, [teamSearch, teamMembers]);

  const fetchData = useCallback(async () => {
    try {
      const [rolesRes, membersRes, permsRes, myPermsRes] = await Promise.all([
        axios.get(`${API}/admin/roles`, { headers }),
        axios.get(`${API}/admin/team`, { headers }),
        axios.get(`${API}/admin/permissions-list`, { headers }),
        axios.get(`${API}/admin/my-permissions`, { headers })
      ]);
      setRoles(rolesRes.data);
      setTeamMembers(membersRes.data);
      setPermissionsList(permsRes.data);
      setMyPermissions(myPermsRes.data);
    } catch (error) {
      console.error("Error fetching team data:", error);
      if (error.response?.status === 403) {
        toast.error("Permission denied. Only administrators can manage team.");
      }
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Role Form Component
  const RoleForm = ({ role, onClose }) => {
    const [formData, setFormData] = useState(role || {
      name: "",
      description: "",
      permissions: permissionsList.features.reduce((acc, f) => ({
        ...acc,
        [f.id]: { view: false, create: false, edit: false, delete: false }
      }), {})
    });
    const [saving, setSaving] = useState(false);

    const handlePermissionChange = (featureId, action, value) => {
      setFormData(prev => ({
        ...prev,
        permissions: {
          ...prev.permissions,
          [featureId]: {
            ...prev.permissions[featureId],
            [action]: value
          }
        }
      }));
    };

    const toggleAllForFeature = (featureId, enable) => {
      setFormData(prev => ({
        ...prev,
        permissions: {
          ...prev.permissions,
          [featureId]: { view: enable, create: enable, edit: enable, delete: enable }
        }
      }));
    };

    const handleSubmit = async (e) => {
      e.preventDefault();
      if (!formData.name.trim()) {
        toast.error("Role name is required");
        return;
      }
      setSaving(true);
      try {
        if (role?.id) {
          await axios.put(`${API}/admin/roles/${role.id}`, formData, { headers });
          toast.success("Role updated successfully");
        } else {
          await axios.post(`${API}/admin/roles`, formData, { headers });
          toast.success("Role created successfully");
        }
        fetchData();
        onClose();
      } catch (error) {
        toast.error(error.response?.data?.detail || "Failed to save role");
      }
      setSaving(false);
    };

    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-4xl max-h-[90vh] overflow-y-auto">
          <CardHeader>
            <CardTitle>{role ? "Edit Role" : "Create New Role"}</CardTitle>
            <CardDescription>Define permissions for this role</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Role Name *</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., Manager, Finance, Support"
                    required
                  />
                </div>
                <div>
                  <Label>Description</Label>
                  <Input
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Brief description of this role"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-4">
                  <Label className="text-base font-semibold">Permissions Matrix</Label>
                  
                  {/* Permission Presets */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">Quick Presets:</span>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        // Full Access - enable all permissions
                        const newPerms = {};
                        permissionsList.features.forEach(f => {
                          newPerms[f.id] = { view: true, create: true, edit: true, delete: true };
                        });
                        setFormData(prev => ({ ...prev, permissions: newPerms }));
                      }}
                      className="text-xs h-7 px-2 bg-green-50 text-green-700 border-green-200 hover:bg-green-100"
                    >
                      <Check className="h-3 w-3 mr-1" />
                      Full Access
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        // Read Only - only view permissions
                        const newPerms = {};
                        permissionsList.features.forEach(f => {
                          newPerms[f.id] = { view: true, create: false, edit: false, delete: false };
                        });
                        setFormData(prev => ({ ...prev, permissions: newPerms }));
                      }}
                      className="text-xs h-7 px-2 bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100"
                    >
                      <Eye className="h-3 w-3 mr-1" />
                      Read Only
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        // Manager - view, create, edit but no delete
                        const newPerms = {};
                        permissionsList.features.forEach(f => {
                          newPerms[f.id] = { view: true, create: true, edit: true, delete: false };
                        });
                        setFormData(prev => ({ ...prev, permissions: newPerms }));
                      }}
                      className="text-xs h-7 px-2 bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100"
                    >
                      <Users className="h-3 w-3 mr-1" />
                      Manager
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        // Clear All - disable all permissions
                        const newPerms = {};
                        permissionsList.features.forEach(f => {
                          newPerms[f.id] = { view: false, create: false, edit: false, delete: false };
                        });
                        setFormData(prev => ({ ...prev, permissions: newPerms }));
                      }}
                      className="text-xs h-7 px-2 bg-red-50 text-red-700 border-red-200 hover:bg-red-100"
                    >
                      <X className="h-3 w-3 mr-1" />
                      Clear All
                    </Button>
                  </div>
                </div>

                {/* Permission Stats */}
                <div className="flex gap-4 mb-4 p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-full bg-green-100 flex items-center justify-center">
                      <Check className="h-4 w-4 text-green-600" />
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Enabled</p>
                      <p className="text-sm font-semibold text-green-600">
                        {Object.values(formData.permissions).reduce((acc, perms) => 
                          acc + Object.values(perms || {}).filter(Boolean).length, 0
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-full bg-gray-100 flex items-center justify-center">
                      <X className="h-4 w-4 text-gray-500" />
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Disabled</p>
                      <p className="text-sm font-semibold text-gray-600">
                        {(permissionsList.features.length * 4) - Object.values(formData.permissions).reduce((acc, perms) => 
                          acc + Object.values(perms || {}).filter(Boolean).length, 0
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center">
                      <Tag className="h-4 w-4 text-blue-600" />
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Features</p>
                      <p className="text-sm font-semibold text-blue-600">{permissionsList.features.length}</p>
                    </div>
                  </div>
                </div>

                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                      <tr>
                        <th className="text-left p-3 font-medium text-sm">Feature</th>
                        {/* Column headers with toggle all */}
                        {[
                          { key: "view", label: "View", icon: Eye, color: "blue" },
                          { key: "create", label: "Create", icon: Plus, color: "green" },
                          { key: "edit", label: "Edit", icon: Edit, color: "amber" },
                          { key: "delete", label: "Delete", icon: Trash2, color: "red" }
                        ].map(({ key, label, icon: Icon, color }) => (
                          <th key={key} className="text-center p-2 w-20">
                            <button
                              type="button"
                              onClick={() => {
                                // Toggle all in this column
                                const allEnabled = permissionsList.features.every(f => 
                                  formData.permissions[f.id]?.[key]
                                );
                                const newPerms = { ...formData.permissions };
                                permissionsList.features.forEach(f => {
                                  newPerms[f.id] = { ...newPerms[f.id], [key]: !allEnabled };
                                });
                                setFormData(prev => ({ ...prev, permissions: newPerms }));
                              }}
                              className={`flex flex-col items-center gap-1 w-full p-1 rounded hover:bg-${color}-50 transition-colors`}
                            >
                              <Icon className={`h-3.5 w-3.5 text-${color}-600`} />
                              <span className="text-xs font-medium">{label}</span>
                              <span className="text-[10px] text-gray-400">
                                {permissionsList.features.filter(f => formData.permissions[f.id]?.[key]).length}/{permissionsList.features.length}
                              </span>
                            </button>
                          </th>
                        ))}
                        <th className="text-center p-3 font-medium text-sm w-20">Row</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {permissionsList.features.map((feature, index) => {
                        const featurePerms = formData.permissions[feature.id] || {};
                        const enabledCount = Object.values(featurePerms).filter(Boolean).length;
                        const isFullAccess = enabledCount === 4;
                        const isPartial = enabledCount > 0 && enabledCount < 4;
                        
                        return (
                          <tr 
                            key={feature.id} 
                            className={`hover:bg-blue-50/50 transition-colors ${
                              isFullAccess ? 'bg-green-50/30' : isPartial ? 'bg-amber-50/30' : ''
                            }`}
                          >
                            <td className="p-3">
                              <div className="flex items-start gap-3">
                                <div className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                                  isFullAccess ? 'bg-green-100' : isPartial ? 'bg-amber-100' : 'bg-gray-100'
                                }`}>
                                  <span className="text-xs font-bold text-gray-600">
                                    {feature.name.charAt(0)}
                                  </span>
                                </div>
                                <div>
                                  <p className="font-medium text-sm">{feature.name}</p>
                                  <p className="text-xs text-gray-500">{feature.description}</p>
                                </div>
                              </div>
                            </td>
                            {["view", "create", "edit", "delete"].map(action => (
                              <td key={action} className="text-center p-3">
                                <Checkbox
                                  checked={formData.permissions[feature.id]?.[action] || false}
                                  onCheckedChange={(checked) => handlePermissionChange(feature.id, action, checked)}
                                  className={`h-5 w-5 ${
                                    action === 'view' ? 'data-[state=checked]:bg-blue-600' :
                                    action === 'create' ? 'data-[state=checked]:bg-green-600' :
                                    action === 'edit' ? 'data-[state=checked]:bg-amber-600' :
                                    'data-[state=checked]:bg-red-600'
                                  }`}
                                />
                              </td>
                            ))}
                            <td className="text-center p-3">
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  const allEnabled = ["view", "create", "edit", "delete"].every(
                                    a => formData.permissions[feature.id]?.[a]
                                  );
                                  toggleAllForFeature(feature.id, !allEnabled);
                                }}
                                className={`text-xs h-7 px-2 ${
                                  isFullAccess 
                                    ? 'bg-green-100 text-green-700 hover:bg-green-200' 
                                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                              >
                                {isFullAccess ? "Clear" : "All"}
                              </Button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t">
                <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
                <Button type="submit" disabled={saving} className="bg-blue-600 hover:bg-blue-700">
                  {saving ? "Saving..." : (role ? "Update Role" : "Create Role")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  };

  // Member Form Component
  const MemberForm = ({ member, onClose }) => {
    const [formData, setFormData] = useState(member || {
      email: "",
      first_name: "",
      last_name: "",
      role_id: roles[0]?.id || "",
      password: ""
    });
    const [inviteMode, setInviteMode] = useState(false);
    const [saving, setSaving] = useState(false);
    const [showQuickRoleForm, setShowQuickRoleForm] = useState(false);
    const [quickRoleName, setQuickRoleName] = useState("");
    const [quickRoleDesc, setQuickRoleDesc] = useState("");
    const [creatingRole, setCreatingRole] = useState(false);

    const handleQuickCreateRole = async () => {
      if (!quickRoleName.trim()) {
        toast.error("Role name is required");
        return;
      }
      setCreatingRole(true);
      try {
        // Create role with basic permissions
        const newRole = {
          name: quickRoleName.trim(),
          description: quickRoleDesc.trim() || `${quickRoleName} role`,
          permissions: permissionsList.features.reduce((acc, f) => ({
            ...acc,
            [f.id]: { view: true, create: false, edit: false, delete: false }
          }), {})
        };
        const res = await axios.post(`${API}/admin/roles`, newRole, { headers });
        toast.success(`Role "${quickRoleName}" created!`);
        
        // Refresh roles and select the new one
        const rolesRes = await axios.get(`${API}/admin/roles`, { headers });
        setRoles(rolesRes.data);
        
        // Find the new role and select it
        const createdRole = rolesRes.data.find(r => r.name === quickRoleName.trim());
        if (createdRole) {
          setFormData({ ...formData, role_id: createdRole.id });
        }
        
        setShowQuickRoleForm(false);
        setQuickRoleName("");
        setQuickRoleDesc("");
      } catch (error) {
        toast.error(error.response?.data?.detail || "Failed to create role");
      }
      setCreatingRole(false);
    };

    const handleSubmit = async (e) => {
      e.preventDefault();
      if (!formData.email.trim() || !formData.first_name.trim() || !formData.role_id) {
        toast.error("Please fill in all required fields");
        return;
      }
      
      if (!member && !inviteMode && !formData.password) {
        toast.error("Password is required for direct creation");
        return;
      }

      setSaving(true);
      try {
        if (member?.id) {
          // Update existing member
          const updateData = {
            first_name: formData.first_name,
            last_name: formData.last_name,
            role_id: formData.role_id
          };
          await axios.put(`${API}/admin/team/${member.id}`, updateData, { headers });
          toast.success("Team member updated");
        } else if (inviteMode) {
          // Send invitation
          const res = await axios.post(`${API}/admin/team/invite`, {
            email: formData.email,
            first_name: formData.first_name,
            last_name: formData.last_name,
            role_id: formData.role_id,
            send_email: true
          }, { headers });
          toast.success(`Invitation sent! Token: ${res.data.invite_token}`);
        } else {
          // Create with password
          await axios.post(`${API}/admin/team`, {
            email: formData.email,
            first_name: formData.first_name,
            last_name: formData.last_name,
            role_id: formData.role_id,
            password: formData.password
          }, { headers });
          toast.success("Team member created successfully");
        }
        fetchData();
        onClose();
      } catch (error) {
        toast.error(error.response?.data?.detail || "Failed to save team member");
      }
      setSaving(false);
    };

    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>{member ? "Edit Team Member" : "Add Team Member"}</CardTitle>
            <CardDescription>
              {member ? "Update member details and role" : "Create a new team account or send an invitation"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {!member && (
                <div className="flex gap-2 mb-4">
                  <Button
                    type="button"
                    variant={!inviteMode ? "default" : "outline"}
                    onClick={() => setInviteMode(false)}
                    className="flex-1"
                  >
                    Create with Password
                  </Button>
                  <Button
                    type="button"
                    variant={inviteMode ? "default" : "outline"}
                    onClick={() => setInviteMode(true)}
                    className="flex-1"
                  >
                    Send Invitation
                  </Button>
                </div>
              )}

              <div>
                <Label>Email *</Label>
                <Input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="team@example.com"
                  disabled={!!member}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>First Name *</Label>
                  <Input
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <Label>Last Name</Label>
                  <Input
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  />
                </div>
              </div>

              <div>
                <Label>Role *</Label>
                <div className="flex gap-2">
                  <select
                    value={formData.role_id}
                    onChange={(e) => {
                      if (e.target.value === "create_new") {
                        setShowQuickRoleForm(true);
                      } else {
                        setFormData({ ...formData, role_id: e.target.value });
                      }
                    }}
                    className="w-full p-2 border rounded-md flex-1"
                    required
                  >
                    <option value="">Select a role</option>
                    {roles.map(role => (
                      <option key={role.id} value={role.id}>{role.name}</option>
                    ))}
                    <option value="create_new" className="text-blue-600 font-medium">➕ Create New Role...</option>
                  </select>
                </div>
                {roles.length === 0 && (
                  <p className="text-sm text-amber-600 mt-1">
                    No roles found. <button type="button" onClick={() => setShowQuickRoleForm(true)} className="text-blue-600 underline">Create a role first</button>
                  </p>
                )}
              </div>

              {/* Quick Role Creation Form */}
              {showQuickRoleForm && (
                <div className="bg-blue-50 p-4 rounded-lg border border-blue-200 space-y-3">
                  <div className="flex justify-between items-center">
                    <Label className="text-blue-800 font-medium">Create New Role</Label>
                    <Button type="button" variant="ghost" size="sm" onClick={() => setShowQuickRoleForm(false)}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                  <Input
                    value={quickRoleName}
                    onChange={(e) => setQuickRoleName(e.target.value)}
                    placeholder="Role name (e.g., Editor, Viewer)"
                  />
                  <Input
                    value={quickRoleDesc}
                    onChange={(e) => setQuickRoleDesc(e.target.value)}
                    placeholder="Description (optional)"
                  />
                  <Button 
                    type="button" 
                    onClick={handleQuickCreateRole}
                    disabled={!quickRoleName.trim() || creatingRole}
                    className="w-full bg-blue-600 hover:bg-blue-700"
                  >
                    {creatingRole ? "Creating..." : "Create Role"}
                  </Button>
                </div>
              )}

              {!member && !inviteMode && (
                <div>
                  <Label>Password *</Label>
                  <Input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="Min 8 characters"
                    required={!inviteMode}
                  />
                </div>
              )}

              {inviteMode && !member && (
                <div className="bg-blue-50 p-3 rounded-lg text-sm text-blue-700">
                  <p>An invitation link will be generated. Share it with the team member to complete their account setup.</p>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
                <Button type="submit" disabled={saving} className="bg-blue-600 hover:bg-blue-700">
                  {saving ? "Saving..." : (member ? "Update" : (inviteMode ? "Send Invite" : "Create"))}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  };

  const handleDeleteRole = async (roleId) => {
    if (!window.confirm("Are you sure you want to delete this role?")) return;
    try {
      await axios.delete(`${API}/admin/roles/${roleId}`, { headers });
      toast.success("Role deleted");
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to delete role");
    }
  };

  const handleToggleMember = async (memberId) => {
    try {
      const res = await axios.put(`${API}/admin/team/${memberId}/toggle`, {}, { headers });
      toast.success(res.data.message);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update member");
    }
  };

  const handleDeleteMember = async (memberId) => {
    if (!window.confirm("Are you sure you want to remove this team member?")) return;
    try {
      await axios.delete(`${API}/admin/team/${memberId}`, { headers });
      toast.success("Team member removed");
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to remove team member");
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-10 bg-gray-200 rounded animate-pulse w-1/3" />
        <div className="h-64 bg-gray-200 rounded animate-pulse" />
      </div>
    );
  }

  // Check if user has permission
  if (myPermissions && !myPermissions.is_super_admin) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Shield className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-600">Access Restricted</h3>
          <p className="text-gray-500 mt-2">Only the super admin can manage team members and roles.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E]">Team Management</h2>
          <p className="text-[#5A5A5A]">Manage roles and team member access</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={activeSection === "members" ? "default" : "outline"}
            onClick={() => setActiveSection("members")}
          >
            <Users className="h-4 w-4 mr-2" /> Members ({teamMembers.length})
          </Button>
          <Button
            variant={activeSection === "roles" ? "default" : "outline"}
            onClick={() => setActiveSection("roles")}
          >
            <Shield className="h-4 w-4 mr-2" /> Roles ({roles.length})
          </Button>
        </div>
      </div>

      {/* Team Members Section */}
      {activeSection === "members" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-4">
            <div>
              <CardTitle>Team Members ({filteredTeamMembers.length})</CardTitle>
              <CardDescription>People with access to the admin panel</CardDescription>
            </div>
            <div className="flex gap-2 flex-wrap">
              {/* Team Search */}
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Search members..."
                  value={teamSearch}
                  onChange={(e) => setTeamSearch(e.target.value)}
                  className="pl-10 pr-8"
                />
                {teamSearch && (
                  <button onClick={() => setTeamSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
              <Button onClick={() => { setEditingMember(null); setShowMemberForm(true); }} className="bg-blue-600 hover:bg-blue-700">
                <Plus className="h-4 w-4 mr-2" /> Add Member
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {filteredTeamMembers.length === 0 && teamSearch ? (
              <div className="text-center py-12">
                <p className="text-gray-500">No members found for "{teamSearch}"</p>
                <Button variant="outline" className="mt-4" onClick={() => setTeamSearch("")}>Clear Search</Button>
              </div>
            ) : teamMembers.length === 0 ? (
              <div className="text-center py-12">
                <Users className="h-16 w-16 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No team members yet</p>
                <p className="text-sm text-gray-400">Add team members to delegate admin tasks</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left p-3 font-medium text-sm">Member</th>
                      <th className="text-left p-3 font-medium text-sm">Role</th>
                      <th className="text-left p-3 font-medium text-sm">Status</th>
                      <th className="text-left p-3 font-medium text-sm">Last Login</th>
                      <th className="text-right p-3 font-medium text-sm">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {filteredTeamMembers.map(member => (
                      <tr key={member.id} className="hover:bg-gray-50">
                        <td className="p-3">
                          <div>
                            <p className="font-medium">{member.first_name} {member.last_name}</p>
                            <p className="text-sm text-gray-500">{member.email}</p>
                          </div>
                        </td>
                        <td className="p-3">
                          <Badge variant="outline">{member.role_name}</Badge>
                        </td>
                        <td className="p-3">
                          <Badge className={
                            member.status === "active" ? "bg-green-100 text-green-700" :
                            member.status === "pending" ? "bg-yellow-100 text-yellow-700" :
                            "bg-red-100 text-red-700"
                          }>
                            {member.status}
                          </Badge>
                        </td>
                        <td className="p-3 text-sm text-gray-500">
                          {member.last_login 
                            ? new Date(member.last_login).toLocaleDateString() 
                            : "Never"}
                        </td>
                        <td className="p-3 text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => { setEditingMember(member); setShowMemberForm(true); }}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleToggleMember(member.id)}
                              className={member.status === "active" ? "text-yellow-600" : "text-green-600"}
                            >
                              {member.status === "active" ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteMember(member.id)}
                              className="text-red-600"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Roles Section */}
      {activeSection === "roles" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Roles</CardTitle>
              <CardDescription>Define permission sets for team members</CardDescription>
            </div>
            <Button onClick={() => { setEditingRole(null); setShowRoleForm(true); }} className="bg-blue-600 hover:bg-blue-700">
              <Plus className="h-4 w-4 mr-2" /> Create Role
            </Button>
          </CardHeader>
          <CardContent>
            {roles.length === 0 ? (
              <div className="text-center py-12">
                <Shield className="h-16 w-16 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No roles defined yet</p>
                <p className="text-sm text-gray-400">Create roles to define different permission levels</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {roles.map(role => {
                  const permCount = Object.values(role.permissions || {}).reduce((acc, perms) => 
                    acc + Object.values(perms).filter(Boolean).length, 0
                  );
                  const membersWithRole = teamMembers.filter(m => m.role_id === role.id).length;
                  
                  return (
                    <Card key={role.id} className="border-2 hover:border-blue-200 transition-colors">
                      <CardHeader className="pb-2">
                        <div className="flex justify-between items-start">
                          <div>
                            <CardTitle className="text-lg">{role.name}</CardTitle>
                            {role.description && (
                              <CardDescription className="text-xs">{role.description}</CardDescription>
                            )}
                          </div>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => { setEditingRole(role); setShowRoleForm(true); }}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteRole(role.id)}
                              className="text-red-600"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-500">{permCount} permissions</span>
                          <span className="text-blue-600">{membersWithRole} member(s)</span>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Modals */}
      {showRoleForm && (
        <RoleForm 
          role={editingRole} 
          onClose={() => { setShowRoleForm(false); setEditingRole(null); }} 
        />
      )}
      {showMemberForm && (
        <MemberForm 
          member={editingMember} 
          onClose={() => { setShowMemberForm(false); setEditingMember(null); }} 
        />
      )}
    </div>
  );
};


// Customer Chats Manager Component - Inbox for Customer Support
const CustomerChatsManager = () => {
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [replyMessage, setReplyMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [filter, setFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const loadConversations = useCallback(async () => {
    try {
      const token = localStorage.getItem("admin_token");
      const params = filter !== "all" ? `?status=${filter}` : "";
      const res = await axios.get(`${API}/admin/customer-chats${params}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setConversations(res.data);
    } catch (error) {
      console.error("Failed to load conversations:", error);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  const loadMessages = useCallback(async (conversationId) => {
    try {
      const token = localStorage.getItem("admin_token");
      const res = await axios.get(`${API}/admin/customer-chats/${conversationId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages(res.data.messages || []);
      setSelectedConversation(res.data.conversation);
    } catch (error) {
      console.error("Failed to load messages:", error);
    }
  }, []);

  useEffect(() => {
    loadConversations();
    // Poll for new messages
    const interval = setInterval(loadConversations, 30000);
    return () => clearInterval(interval);
  }, [loadConversations]);

  const handleSendReply = async () => {
    if (!replyMessage.trim() || !selectedConversation) return;
    
    setSending(true);
    try {
      const token = localStorage.getItem("admin_token");
      await axios.post(`${API}/admin/customer-chats/${selectedConversation.id}/reply`, 
        { message: replyMessage },
        { headers: { Authorization: `Bearer ${token}` }}
      );
      setReplyMessage("");
      await loadMessages(selectedConversation.id);
      await loadConversations();
    } catch (error) {
      console.error("Failed to send reply:", error);
    } finally {
      setSending(false);
    }
  };

  const handleUpdateStatus = async (conversationId, status) => {
    try {
      const token = localStorage.getItem("admin_token");
      await axios.put(`${API}/admin/customer-chats/${conversationId}/status`,
        { status },
        { headers: { Authorization: `Bearer ${token}` }}
      );
      await loadConversations();
      if (selectedConversation?.id === conversationId) {
        setSelectedConversation(prev => ({ ...prev, status }));
      }
    } catch (error) {
      console.error("Failed to update status:", error);
    }
  };

  const filteredConversations = useMemo(() => {
    if (!searchQuery) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter(c => 
      c.customer_name?.toLowerCase().includes(q) ||
      c.customer_email?.toLowerCase().includes(q) ||
      c.last_message?.toLowerCase().includes(q)
    );
  }, [conversations, searchQuery]);

  const getStatusBadge = (status) => {
    const badges = {
      active: "bg-green-100 text-green-800",
      pending: "bg-yellow-100 text-yellow-800",
      resolved: "bg-gray-100 text-gray-800",
      escalated: "bg-red-100 text-red-800"
    };
    return badges[status] || badges.pending;
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;
    if (diff < 60000) return "Just now";
    if (diff < 3600000) return `${Math.floor(diff/60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff/3600000)}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E]">💬 Customer Inbox</h2>
          <p className="text-[#5A5A5A]">View and respond to customer messages</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className="bg-indigo-100 text-indigo-800">{conversations.length} Total</Badge>
          <Badge className="bg-yellow-100 text-yellow-800">
            {conversations.filter(c => c.needs_attention).length} Need Attention
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Conversations List */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-3">
            <div className="space-y-3">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search conversations..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              {/* Filter */}
              <Select value={filter} onValueChange={setFilter}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Conversations</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="escalated">Escalated</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-8 text-center text-[#5A5A5A]">Loading...</div>
            ) : filteredConversations.length === 0 ? (
              <div className="p-8 text-center">
                <MessageCircle className="h-12 w-12 mx-auto text-gray-300 mb-3" />
                <p className="text-[#5A5A5A]">No conversations yet</p>
                <p className="text-sm text-gray-400">Customer messages will appear here</p>
              </div>
            ) : (
              <div className="divide-y max-h-[500px] overflow-y-auto">
                {filteredConversations.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => loadMessages(conv.id)}
                    className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
                      selectedConversation?.id === conv.id ? "bg-indigo-50 border-l-4 border-indigo-500" : ""
                    } ${conv.needs_attention ? "bg-yellow-50" : ""}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-[#2D2A2E] truncate">
                            {conv.customer_name || "Customer"}
                          </span>
                          {conv.needs_attention && (
                            <span className="w-2 h-2 bg-red-500 rounded-full"></span>
                          )}
                        </div>
                        <p className="text-sm text-[#5A5A5A] truncate">{conv.last_message || "No messages"}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusBadge(conv.status)}`}>
                            {conv.status || "pending"}
                          </span>
                          <span className="text-xs text-gray-400">{formatTime(conv.updated_at)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Chat View */}
        <Card className="lg:col-span-2">
          {selectedConversation ? (
            <>
              <CardHeader className="border-b">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">
                      {selectedConversation.customer_name || "Customer"}
                    </CardTitle>
                    <p className="text-sm text-[#5A5A5A]">{selectedConversation.customer_email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Select 
                      value={selectedConversation.status || "pending"}
                      onValueChange={(value) => handleUpdateStatus(selectedConversation.id, value)}
                    >
                      <SelectTrigger className="w-[140px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="active">✅ Active</SelectItem>
                        <SelectItem value="pending">⏳ Pending</SelectItem>
                        <SelectItem value="escalated">🚨 Escalated</SelectItem>
                        <SelectItem value="resolved">✔️ Resolved</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-4">
                {/* Messages */}
                <div className="h-[350px] overflow-y-auto space-y-4 mb-4 p-2">
                  {messages.length === 0 ? (
                    <div className="text-center text-[#5A5A5A] py-8">No messages in this conversation</div>
                  ) : (
                    messages.map((msg, idx) => (
                      <div 
                        key={msg.id || idx}
                        className={`flex ${msg.sender === "admin" ? "justify-end" : "justify-start"}`}
                      >
                        <div className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                          msg.sender === "admin" 
                            ? "bg-indigo-600 text-white rounded-br-md" 
                            : msg.sender === "ai"
                            ? "bg-purple-100 text-[#2D2A2E] rounded-bl-md"
                            : "bg-gray-100 text-[#2D2A2E] rounded-bl-md"
                        }`}>
                          <p className="text-sm">{msg.content}</p>
                          <div className={`text-xs mt-1 ${
                            msg.sender === "admin" ? "text-indigo-200" : "text-gray-400"
                          }`}>
                            {msg.sender === "ai" ? "🤖 AI" : msg.sender === "admin" ? "You" : "Customer"} • {formatTime(msg.created_at)}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Reply Input */}
                <div className="flex gap-2">
                  <Input
                    value={replyMessage}
                    onChange={(e) => setReplyMessage(e.target.value)}
                    placeholder="Type your reply..."
                    onKeyPress={(e) => e.key === "Enter" && !e.shiftKey && handleSendReply()}
                    className="flex-1"
                    disabled={sending}
                  />
                  <Button 
                    onClick={handleSendReply}
                    disabled={!replyMessage.trim() || sending}
                    className="bg-indigo-600 hover:bg-indigo-700"
                  >
                    {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  </Button>
                </div>
              </CardContent>
            </>
          ) : (
            <div className="h-[500px] flex items-center justify-center text-center">
              <div>
                <MessageCircle className="h-16 w-16 mx-auto text-gray-300 mb-4" />
                <h3 className="text-lg font-medium text-[#2D2A2E] mb-2">Select a Conversation</h3>
                <p className="text-[#5A5A5A]">Choose a conversation from the list to view and reply</p>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

// Ad Campaign Manager Component
const AdCampaignManager = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState(null);
  const [stats, setStats] = useState(null);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterPlatform, setFilterPlatform] = useState("all");
  const [activeView, setActiveView] = useState("campaigns"); // campaigns, budget
  const [campaignSearch, setCampaignSearch] = useState("");
  
  // Ad Budget state
  const [adBudget, setAdBudget] = useState({ balance: 0, total_deposited: 0, total_spent: 0 });
  const [budgetTransactions, setBudgetTransactions] = useState([]);
  const [addFundsAmount, setAddFundsAmount] = useState(50);
  const [processingPayment, setProcessingPayment] = useState(false);

  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  const platformIcons = {
    facebook: "📘", instagram: "📸", google: "🔍", tiktok: "🎵",
    youtube: "▶️", twitter: "🐦", linkedin: "💼", pinterest: "📌",
    snapchat: "👻", other: "🌐"
  };

  const statusColors = {
    draft: "bg-gray-100 text-gray-700",
    active: "bg-green-100 text-green-700",
    paused: "bg-yellow-100 text-yellow-700",
    completed: "bg-blue-100 text-blue-700",
    cancelled: "bg-red-100 text-red-700"
  };

  // Filter campaigns by search and filters
  const filteredCampaigns = React.useMemo(() => {
    let result = campaigns;
    
    // Apply search
    if (campaignSearch.trim()) {
      const q = campaignSearch.toLowerCase();
      result = result.filter(c => 
        c.name?.toLowerCase().includes(q) ||
        c.platform?.toLowerCase().includes(q) ||
        c.objective?.toLowerCase().includes(q)
      );
    }
    
    // Apply status filter
    if (filterStatus !== "all") {
      result = result.filter(c => c.status === filterStatus);
    }
    
    // Apply platform filter
    if (filterPlatform !== "all") {
      result = result.filter(c => c.platform === filterPlatform);
    }
    
    return result;
  }, [campaigns, campaignSearch, filterStatus, filterPlatform]);

  const fetchData = useCallback(async () => {
    try {
      const [campaignsRes, platformsRes, statsRes, budgetRes, transactionsRes] = await Promise.all([
        axios.get(`${API}/admin/ad-campaigns`, { headers }),
        axios.get(`${API}/admin/ad-platforms`, { headers }),
        axios.get(`${API}/admin/ad-campaigns/stats/summary`, { headers }),
        axios.get(`${API}/admin/ad-budget`, { headers }).catch(() => ({ data: { balance: 0 } })),
        axios.get(`${API}/admin/ad-budget/transactions`, { headers }).catch(() => ({ data: [] }))
      ]);
      setCampaigns(campaignsRes.data);
      setPlatforms(platformsRes.data);
      setStats(statsRes.data);
      setAdBudget(budgetRes.data || { balance: 0 });
      setBudgetTransactions(transactionsRes.data || []);
    } catch (error) {
      console.error("Error fetching campaigns:", error);
      toast.error("Failed to load campaigns");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle Add Funds via Stripe
  const handleAddFunds = async () => {
    if (addFundsAmount < 10) {
      toast.error("Minimum amount is $10");
      return;
    }
    setProcessingPayment(true);
    try {
      const res = await axios.post(`${API}/admin/ad-budget/add-funds?amount=${addFundsAmount}`, {}, { headers });
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url;
      } else if (res.data.demo_mode) {
        // Demo mode - simulate successful payment
        toast.success(`Demo Mode: $${addFundsAmount} added to your ad budget!`);
        fetchData(); // Refresh to show updated balance
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || "Failed to initiate payment";
      if (errorMsg.includes("Stripe not configured")) {
        toast.error("Payment system not configured. Please set up Stripe account first.");
      } else {
        toast.error(errorMsg);
      }
    }
    setProcessingPayment(false);
  };

  // Campaign Form Component
  const CampaignForm = ({ campaign, onClose }) => {
    const [formData, setFormData] = useState(campaign || {
      name: "",
      platform: "facebook",
      objective: "awareness",
      budget: 0,
      budget_type: "daily",
      currency: "CAD",
      start_date: "",
      end_date: "",
      target_audience: "",
      ad_creative_url: "",
      landing_page_url: "",
      notes: "",
      // Metrics for editing
      impressions: 0,
      clicks: 0,
      conversions: 0,
      spend: 0,
      revenue: 0
    });
    const [saving, setSaving] = useState(false);

    const handleSubmit = async (e) => {
      e.preventDefault();
      if (!formData.name.trim()) {
        toast.error("Campaign name is required");
        return;
      }
      setSaving(true);
      try {
        if (campaign?.id) {
          await axios.put(`${API}/admin/ad-campaigns/${campaign.id}`, formData, { headers });
          toast.success("Campaign updated successfully");
        } else {
          await axios.post(`${API}/admin/ad-campaigns`, formData, { headers });
          toast.success("Campaign created successfully");
        }
        fetchData();
        onClose();
      } catch (error) {
        toast.error(error.response?.data?.detail || "Failed to save campaign");
      }
      setSaving(false);
    };

    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-3xl max-h-[90vh] overflow-y-auto">
          <CardHeader>
            <CardTitle>{campaign ? "Edit Campaign" : "Create New Campaign"}</CardTitle>
            <CardDescription>
              {campaign ? "Update campaign details and metrics" : "Set up a new advertising campaign"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Basic Info */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <Label>Campaign Name *</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., Summer Sale 2025"
                    required
                  />
                </div>
                <div>
                  <Label>Platform *</Label>
                  <select
                    value={formData.platform}
                    onChange={(e) => setFormData({ ...formData, platform: e.target.value })}
                    className="w-full p-2 border rounded-md"
                  >
                    {platforms.map(p => (
                      <option key={p.id} value={p.id}>{platformIcons[p.id]} {p.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <Label>Objective</Label>
                  <select
                    value={formData.objective}
                    onChange={(e) => setFormData({ ...formData, objective: e.target.value })}
                    className="w-full p-2 border rounded-md"
                  >
                    <option value="awareness">Brand Awareness</option>
                    <option value="traffic">Website Traffic</option>
                    <option value="engagement">Engagement</option>
                    <option value="leads">Lead Generation</option>
                    <option value="sales">Sales/Conversions</option>
                  </select>
                </div>
              </div>

              {/* Budget */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label>Budget</Label>
                  <Input
                    type="text"
                    inputMode="decimal"
                    value={formData.budget}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === '' || /^\d*\.?\d*$/.test(val)) {
                        setFormData({ ...formData, budget: val === '' ? 0 : parseFloat(val) || 0 });
                      }
                    }}
                  />
                </div>
                <div>
                  <Label>Budget Type</Label>
                  <select
                    value={formData.budget_type}
                    onChange={(e) => setFormData({ ...formData, budget_type: e.target.value })}
                    className="w-full p-2 border rounded-md"
                  >
                    <option value="daily">Daily</option>
                    <option value="lifetime">Lifetime</option>
                  </select>
                </div>
                <div>
                  <Label>Currency</Label>
                  <select
                    value={formData.currency}
                    onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                    className="w-full p-2 border rounded-md"
                  >
                    <option value="CAD">CAD</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                    <option value="INR">INR</option>
                  </select>
                </div>
              </div>

              {/* Dates */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Start Date</Label>
                  <Input
                    type="date"
                    value={formData.start_date}
                    onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                  />
                </div>
                <div>
                  <Label>End Date</Label>
                  <Input
                    type="date"
                    value={formData.end_date}
                    onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                  />
                </div>
              </div>

              {/* Additional Info */}
              <div className="space-y-4">
                <div>
                  <Label>Target Audience</Label>
                  <Input
                    value={formData.target_audience}
                    onChange={(e) => setFormData({ ...formData, target_audience: e.target.value })}
                    placeholder="e.g., Women 25-45, interested in skincare"
                  />
                </div>
                <div>
                  <Label>Ad Creative (Image/Video)</Label>
                  <ImageUploader
                    value={formData.ad_creative_url}
                    onChange={(url) => setFormData({ ...formData, ad_creative_url: url })}
                    placeholder="Upload image/video or enter URL"
                  />
                  {formData.ad_creative_url && (
                    <div className="mt-2 p-2 border rounded bg-gray-50">
                      {formData.ad_creative_url.match(/\.(mp4|webm|mov|avi)$/i) ? (
                        <video src={formData.ad_creative_url} className="h-24 rounded" controls />
                      ) : (
                        <img src={formData.ad_creative_url} alt="Ad Preview" className="h-24 object-contain rounded" onError={(e) => e.target.style.display='none'} />
                      )}
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="text-red-500 hover:text-red-700 mt-1"
                        onClick={() => setFormData({ ...formData, ad_creative_url: "" })}
                      >
                        <X className="h-4 w-4 mr-1" /> Remove
                      </Button>
                    </div>
                  )}
                </div>
                <div>
                  <Label>Landing Page URL</Label>
                  <Input
                    value={formData.landing_page_url}
                    onChange={(e) => setFormData({ ...formData, landing_page_url: e.target.value })}
                    placeholder="Where users go when they click"
                  />
                </div>
                <div>
                  <Label>Notes</Label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    className="w-full p-2 border rounded-md h-20"
                    placeholder="Any additional notes..."
                  />
                </div>
              </div>

              {/* Metrics (only for editing) */}
              {campaign && (
                <div className="border-t pt-4">
                  <Label className="text-base font-semibold mb-4 block">Performance Metrics</Label>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <div>
                      <Label className="text-xs">Impressions</Label>
                      <Input
                        type="text"
                        inputMode="numeric"
                        value={formData.impressions}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (val === '' || /^\d*$/.test(val)) {
                            setFormData({ ...formData, impressions: val === '' ? 0 : parseInt(val) || 0 });
                          }
                        }}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Clicks</Label>
                      <Input
                        type="text"
                        inputMode="numeric"
                        value={formData.clicks}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (val === '' || /^\d*$/.test(val)) {
                            setFormData({ ...formData, clicks: val === '' ? 0 : parseInt(val) || 0 });
                          }
                        }}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Conversions</Label>
                      <Input
                        type="text"
                        inputMode="numeric"
                        value={formData.conversions}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (val === '' || /^\d*$/.test(val)) {
                            setFormData({ ...formData, conversions: val === '' ? 0 : parseInt(val) || 0 });
                          }
                        }}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Spend ($)</Label>
                      <Input
                        type="text"
                        inputMode="decimal"
                        value={formData.spend}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (val === '' || /^\d*\.?\d*$/.test(val)) {
                            setFormData({ ...formData, spend: val === '' ? 0 : parseFloat(val) || 0 });
                          }
                        }}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Revenue ($)</Label>
                      <Input
                        type="text"
                        inputMode="decimal"
                        value={formData.revenue}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (val === '' || /^\d*\.?\d*$/.test(val)) {
                            setFormData({ ...formData, revenue: val === '' ? 0 : parseFloat(val) || 0 });
                          }
                        }}
                      />
                    </div>
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4 border-t">
                <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
                <Button type="submit" disabled={saving} className="bg-orange-500 hover:bg-orange-600">
                  {saving ? "Saving..." : (campaign ? "Update Campaign" : "Create Campaign")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  };

  const handleStatusChange = async (campaignId, newStatus) => {
    try {
      await axios.put(`${API}/admin/ad-campaigns/${campaignId}/status?status=${newStatus}`, {}, { headers });
      toast.success(`Campaign ${newStatus}`);
      fetchData();
    } catch (error) {
      toast.error("Failed to update status");
    }
  };

  const handleDelete = async (campaignId) => {
    if (!window.confirm("Are you sure you want to delete this campaign?")) return;
    try {
      await axios.delete(`${API}/admin/ad-campaigns/${campaignId}`, { headers });
      toast.success("Campaign deleted");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete campaign");
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-10 bg-gray-200 rounded animate-pulse w-1/3" />
        <div className="h-64 bg-gray-200 rounded animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with View Tabs */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E]">Ad Campaign Manager</h2>
          <p className="text-[#5A5A5A]">Track campaigns and create AI-powered ad content</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button 
            variant={activeView === "campaigns" ? "default" : "outline"}
            onClick={() => setActiveView("campaigns")}
            className={activeView === "campaigns" ? "bg-orange-500 hover:bg-orange-600" : ""}
          >
            📊 Campaigns
          </Button>
          <Button 
            variant={activeView === "budget" ? "default" : "outline"}
            onClick={() => setActiveView("budget")}
            className={activeView === "budget" ? "bg-green-600 hover:bg-green-700" : ""}
          >
            💳 Ad Budget
          </Button>
        </div>
      </div>

      {/* Ad Budget View */}
      {activeView === "budget" && (
        <div className="space-y-6">
          {/* Budget Balance Card */}
          <Card className="bg-gradient-to-r from-green-500 to-emerald-600 text-white">
            <CardContent className="p-6">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-green-100 text-sm">Available Ad Budget</p>
                  <p className="text-4xl font-bold mt-2">${(adBudget.balance || 0).toFixed(2)} CAD</p>
                  <div className="flex gap-4 mt-4 text-sm">
                    <div>
                      <p className="text-green-200">Total Deposited</p>
                      <p className="font-semibold">${(adBudget.total_deposited || 0).toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-green-200">Total Spent</p>
                      <p className="font-semibold">${(adBudget.total_spent || 0).toFixed(2)}</p>
                    </div>
                  </div>
                </div>
                <div className="text-6xl opacity-20">💰</div>
              </div>
            </CardContent>
          </Card>

          {/* Add Funds Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                💳 Add Funds to Ad Budget
              </CardTitle>
              <p className="text-sm text-gray-500">Use credit or debit card to add funds via Stripe</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-4 gap-2">
                {[25, 50, 100, 250].map(amount => (
                  <Button
                    key={amount}
                    variant={addFundsAmount === amount ? "default" : "outline"}
                    onClick={() => setAddFundsAmount(amount)}
                    className={addFundsAmount === amount ? "bg-green-600" : ""}
                  >
                    ${amount}
                  </Button>
                ))}
              </div>
              <div className="flex gap-2 items-center">
                <Label className="whitespace-nowrap">Custom Amount:</Label>
                <div className="relative flex-1">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                  <Input
                    type="number"
                    min="10"
                    max="10000"
                    value={addFundsAmount}
                    onChange={(e) => setAddFundsAmount(parseFloat(e.target.value) || 0)}
                    className="pl-8"
                    placeholder="Enter amount"
                  />
                </div>
                <span className="text-gray-500">CAD</span>
              </div>
              <Button 
                onClick={handleAddFunds}
                disabled={processingPayment || addFundsAmount < 10}
                className="w-full bg-green-600 hover:bg-green-700 text-white"
                size="lg"
              >
                {processingPayment ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Processing...</>
                ) : (
                  <><CreditCard className="h-4 w-4 mr-2" /> Add ${addFundsAmount.toFixed(2)} CAD</>
                )}
              </Button>
              <p className="text-xs text-center text-gray-400">
                Secure payment powered by Stripe. Minimum $10, Maximum $10,000.
              </p>
              <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>💡 Demo Mode Active:</strong> Payments are simulated. To accept real payments:
                </p>
                <ol className="text-xs text-blue-700 mt-2 space-y-1 list-decimal list-inside">
                  <li>Create a free <a href="https://dashboard.stripe.com/register" target="_blank" rel="noopener noreferrer" className="underline font-medium">Stripe account</a></li>
                  <li>Get your API key from Stripe Dashboard → Developers → API Keys</li>
                  <li>Contact support to configure your Stripe key</li>
                </ol>
              </div>
            </CardContent>
          </Card>

          {/* Transaction History */}
          <Card>
            <CardHeader>
              <CardTitle>📋 Transaction History</CardTitle>
            </CardHeader>
            <CardContent>
              {budgetTransactions.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <p>No transactions yet. Add funds to get started!</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {budgetTransactions.map((tx) => (
                    <div key={tx.id} className="flex justify-between items-center p-3 border rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                          tx.type === 'deposit' ? 'bg-green-100 text-green-600' : 'bg-orange-100 text-orange-600'
                        }`}>
                          {tx.type === 'deposit' ? '💵' : '📢'}
                        </div>
                        <div>
                          <p className="font-medium">
                            {tx.type === 'deposit' ? 'Funds Added' : 'Budget Allocated'}
                          </p>
                          <p className="text-xs text-gray-500">
                            {new Date(tx.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`font-bold ${tx.amount > 0 ? 'text-green-600' : 'text-orange-600'}`}>
                          {tx.amount > 0 ? '+' : ''}{tx.amount.toFixed(2)} {tx.currency}
                        </p>
                        <Badge className={
                          tx.status === 'completed' ? 'bg-green-100 text-green-700' : 
                          tx.status === 'pending' ? 'bg-yellow-100 text-yellow-700' : 
                          'bg-gray-100 text-gray-700'
                        }>
                          {tx.status}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Campaigns View */}
      {activeView === "campaigns" && (
        <>
          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Card>
                <CardContent className="pt-4">
                  <p className="text-sm text-gray-500">Total Campaigns</p>
                  <p className="text-2xl font-bold">{campaigns.length}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <p className="text-sm text-gray-500">Active</p>
                  <p className="text-2xl font-bold text-green-600">{stats.by_status?.active || 0}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <p className="text-sm text-gray-500">Total Spend</p>
                  <p className="text-2xl font-bold">${(stats.totals?.total_spend || 0).toFixed(2)}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <p className="text-sm text-gray-500">Total Clicks</p>
                  <p className="text-2xl font-bold">{stats.totals?.total_clicks || 0}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <p className="text-sm text-gray-500">Total Revenue</p>
                  <p className="text-2xl font-bold text-green-600">${(stats.totals?.total_revenue || 0).toFixed(2)}</p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Add Campaign Button and Search */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            {/* Campaign Search */}
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                type="text"
                placeholder="Search campaigns..."
                value={campaignSearch}
                onChange={(e) => setCampaignSearch(e.target.value)}
                className="pl-10 pr-8"
              />
              {campaignSearch && (
                <button onClick={() => setCampaignSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <Button onClick={() => { setEditingCampaign(null); setShowForm(true); }} className="bg-orange-500 hover:bg-orange-600">
              <Plus className="h-4 w-4 mr-2" /> New Campaign
            </Button>
          </div>

          {/* Filters */}
          <div className="flex gap-4 flex-wrap">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="p-2 border rounded-md"
        >
          <option value="all">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select
          value={filterPlatform}
          onChange={(e) => setFilterPlatform(e.target.value)}
          className="p-2 border rounded-md"
        >
          <option value="all">All Platforms</option>
          {platforms.map(p => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      {/* Campaigns List */}
      <Card>
        <CardContent className="p-0">
          {filteredCampaigns.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-5xl mb-4">📢</div>
              <p className="text-gray-500">No campaigns found</p>
              <p className="text-sm text-gray-400">Create your first ad campaign to get started</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left p-4 font-medium text-sm">Campaign</th>
                    <th className="text-left p-4 font-medium text-sm">Platform</th>
                    <th className="text-left p-4 font-medium text-sm">Status</th>
                    <th className="text-left p-4 font-medium text-sm">Budget</th>
                    <th className="text-left p-4 font-medium text-sm">Performance</th>
                    <th className="text-right p-4 font-medium text-sm">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filteredCampaigns.map(campaign => (
                    <tr key={campaign.id} className="hover:bg-gray-50">
                      <td className="p-4">
                        <div>
                          <p className="font-medium">{campaign.name}</p>
                          <p className="text-xs text-gray-500">
                            {campaign.start_date && `${campaign.start_date} - ${campaign.end_date || "Ongoing"}`}
                          </p>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className="flex items-center gap-2">
                          <span className="text-xl">{platformIcons[campaign.platform]}</span>
                          <span className="capitalize">{campaign.platform}</span>
                        </span>
                      </td>
                      <td className="p-4">
                        <Badge className={statusColors[campaign.status]}>
                          {campaign.status}
                        </Badge>
                      </td>
                      <td className="p-4">
                        <p className="font-medium">${campaign.budget.toFixed(2)}</p>
                        <p className="text-xs text-gray-500">{campaign.budget_type} • {campaign.currency}</p>
                      </td>
                      <td className="p-4">
                        <div className="text-sm space-y-1">
                          <p>👁️ {campaign.impressions.toLocaleString()} impr</p>
                          <p>👆 {campaign.clicks.toLocaleString()} clicks ({campaign.ctr || 0}% CTR)</p>
                          <p>💰 ${campaign.spend.toFixed(2)} spent</p>
                        </div>
                      </td>
                      <td className="p-4 text-right">
                        <div className="flex justify-end gap-1">
                          {campaign.status === "draft" && (
                            <Button variant="ghost" size="sm" onClick={() => handleStatusChange(campaign.id, "active")} className="text-green-600">
                              <Play className="h-4 w-4" />
                            </Button>
                          )}
                          {campaign.status === "active" && (
                            <Button variant="ghost" size="sm" onClick={() => handleStatusChange(campaign.id, "paused")} className="text-yellow-600">
                              <Pause className="h-4 w-4" />
                            </Button>
                          )}
                          {campaign.status === "paused" && (
                            <Button variant="ghost" size="sm" onClick={() => handleStatusChange(campaign.id, "active")} className="text-green-600">
                              <Play className="h-4 w-4" />
                            </Button>
                          )}
                          <Button variant="ghost" size="sm" onClick={() => { setEditingCampaign(campaign); setShowForm(true); }}>
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDelete(campaign.id)} className="text-red-600">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
        </>
      )}

      {/* Campaign Form Modal */}
      {showForm && (
        <CampaignForm 
          campaign={editingCampaign} 
          onClose={() => { setShowForm(false); setEditingCampaign(null); }} 
        />
      )}
    </div>
  );
};

export { InfluencerManager, TeamManager, CustomerChatsManager, AdCampaignManager };
export default InfluencerManager;
