import React, { useState, useEffect, useCallback, useMemo, lazy, Suspense } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { AuthContext } from "@/contexts";
import { useContext } from "react";
import {
  Plus,
  Minus,
  Trash2,
  Star,
  Check,
  CheckCircle,
  Search,
  Edit,
  Image,
  Globe,
  Save,
  Eye,
  EyeOff,
  MessageCircle,
  Users,
  Download,
  DollarSign,
  ExternalLink,
  Send,
  Bot,
  Loader2,
  RotateCcw,
  Upload,
  RefreshCw,
  Gift,
  Copy,
  Bell,
  FileText,
  Trophy,
  ArrowLeft,
  Ticket,
  Tag,
  Link2,
  Award,
  Microscope,
  Share2,
  Target,
  Crown,
  TrendingUp,
  QrCode,
  X,
  Package,
  ShoppingBag,
  Clock,
  MapPin,
  Truck
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { arrayMove, sortableKeyboardCoordinates, useSortable, horizontalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

// Lazy load heavy components
const DndContext = lazy(() => import('@dnd-kit/core').then(mod => ({ default: mod.DndContext })));
const SortableContext = lazy(() => import('@dnd-kit/sortable').then(mod => ({ default: mod.SortableContext })));

// Lazy load admin sub-components
const StoreSettingsEditor = lazy(() => import('@/components/admin/StoreSettingsEditor'));
const InfluencerManager = lazy(() => import('@/components/admin/InfluencerManager'));
const DiscountCodeManager = lazy(() => import('@/components/admin/DiscountCodeManager'));
const AIContentStudio = lazy(() => import('@/components/admin/AIContentStudio'));
const PromotionsCenter = lazy(() => import('@/components/admin/PromotionsCenter'));
const OroeCommandCenter = lazy(() => import('@/components/admin/OroeCommandCenter'));

// Named exports from InfluencerManager
import { TeamManager, CustomerChatsManager, AdCampaignManager } from '@/components/admin/InfluencerManager';

// Get backend URL
// Get backend URL from environment
const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // For localhost development
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    
    // For custom domains (reroots.ca, etc.) - ALWAYS use same origin
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    
    // For preview/staging environments
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

const BACKEND_URL = getBackendUrl();
const API = `${BACKEND_URL}/api`;

// Default admin tab order
const DEFAULT_ADMIN_TABS = [
  { id: 'overview', label: 'view_all', defaultLabel: '📊 Overview', style: 'data-[state=active]:bg-[#2D2A2E] data-[state=active]:text-white' },
  { id: 'catalog', label: 'catalog', defaultLabel: '🛍️ Catalog', style: 'data-[state=active]:bg-[#2D2A2E] data-[state=active]:text-white' },
  { id: 'orders', label: 'orders', defaultLabel: '📋 Orders', style: 'data-[state=active]:bg-[#2D2A2E] data-[state=active]:text-white' },
  { id: 'sales', label: 'sales', defaultLabel: '💰 Finance', style: 'data-[state=active]:bg-emerald-600 data-[state=active]:text-white', icon: '💰' },
  { id: 'marketing', label: 'marketing', defaultLabel: '🎯 Marketing', style: 'data-[state=active]:bg-gradient-to-r data-[state=active]:from-pink-500 data-[state=active]:to-orange-500 data-[state=active]:text-white', icon: '🎯' },
  { id: 'people', label: 'people', defaultLabel: '👥 People', style: 'data-[state=active]:bg-indigo-600 data-[state=active]:text-white', icon: '👥' },
  { id: 'oroe', label: 'oroe', defaultLabel: '✨ OROÉ', style: 'data-[state=active]:bg-gradient-to-r data-[state=active]:from-[#D4AF37] data-[state=active]:to-[#B8860B] data-[state=active]:text-[#0A0A0A]', icon: '✨' },
  { id: 'ai-hub', label: 'ai_hub', defaultLabel: '🤖 AI', style: 'data-[state=active]:bg-gradient-to-r data-[state=active]:from-purple-600 data-[state=active]:to-green-500 data-[state=active]:text-white', icon: '🤖' },
  { id: 'settings-hub', label: 'settings_hub', defaultLabel: '⚙️ Settings', style: 'data-[state=active]:bg-[#F8A5B8] data-[state=active]:text-[#2D2A2E]', icon: '⚙️' },
];

// UI Translations (minimal set needed for admin)
const UI_TRANSLATIONS = {
  en: { view_all: "Overview", catalog: "Catalog", orders: "Orders", sales: "Finance", marketing: "Marketing", people: "People", oroe: "OROÉ", ai_hub: "AI", settings_hub: "Settings" },
  "en-CA": { view_all: "Overview", catalog: "Catalog", orders: "Orders", sales: "Finance", marketing: "Marketing", people: "People", oroe: "OROÉ", ai_hub: "AI", settings_hub: "Settings" },
  fr: { view_all: "Aperçu", catalog: "Catalogue", orders: "Commandes", sales: "Finances", marketing: "Marketing", people: "Personnes", oroe: "OROÉ", ai_hub: "IA", settings_hub: "Paramètres" },
  ar: { view_all: "نظرة عامة", catalog: "الكتالوج", orders: "الطلبات", sales: "المالية", marketing: "التسويق", people: "الأشخاص", oroe: "OROÉ", ai_hub: "ذكاء اصطناعي", settings_hub: "الإعدادات" },
};

// Auth hook
const useAuth = () => useContext(AuthContext);

// Sortable Tab Component
const SortableTab = ({ id, children, value, className, activeTab, onValueChange }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 50 : undefined,
    opacity: isDragging ? 0.8 : 1,
    cursor: 'grab'
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <button
        onClick={() => onValueChange(value)}
        className={`${className} ${activeTab === value ? 'bg-opacity-100' : ''}`}
        data-state={activeTab === value ? 'active' : 'inactive'}
      >
        {children}
      </button>
    </div>
  );
};

// Image Uploader Component
const ImageUploader = ({ value, onChange, placeholder = "Enter image URL or upload", showWarning = false, acceptVideo = false }) => {
  const [uploading, setUploading] = useState(false);
  const fileInputRef = React.useRef(null);
  
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const token = localStorage.getItem("reroots_token");
      const res = await axios.post(`${API}/upload`, formData, {
        headers: { 
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${token}`
        }
      });
      onChange(res.data.url);
      toast.success("File uploaded!");
    } catch (err) {
      toast.error("Upload failed");
    }
    setUploading(false);
  };
  
  return (
    <div className="flex gap-2">
      <Input
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="flex-1"
      />
      <input
        ref={fileInputRef}
        type="file"
        accept={acceptVideo ? "image/*,video/*" : "image/*"}
        onChange={handleFileUpload}
        className="hidden"
      />
      <Button
        type="button"
        variant="outline"
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
      >
        {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
      </Button>
    </div>
  );
};

// Auditor Analytics Card Component
const AuditorAnalyticsCard = ({ API: apiUrl, headers }) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await axios.get(`${apiUrl}/admin/auditor/share-stats`, { headers });
        setStats(res.data);
      } catch (err) {
        console.error("Error fetching auditor stats:", err);
      }
      setLoading(false);
    };
    fetchStats();
  }, [apiUrl, headers]);

  if (loading) {
    return (
      <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200">
        <CardContent className="p-6 flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <Microscope className="h-5 w-5 text-blue-600" />
          Auditor Analytics
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white/60 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-blue-600">{stats?.total_shares || 0}</p>
            <p className="text-xs text-gray-600">Total Shares</p>
          </div>
          <div className="bg-white/60 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-indigo-600">{stats?.audits_run || 0}</p>
            <p className="text-xs text-gray-600">Audits Run</p>
          </div>
          <div className="bg-white/60 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-purple-600">{stats?.leads_captured || 0}</p>
            <p className="text-xs text-gray-600">Leads</p>
          </div>
          <div className="bg-white/60 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-green-600">{stats?.conversion_rate || 0}%</p>
            <p className="text-xs text-gray-600">Conversion</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Export the main AdminDashboard component
export { API, DEFAULT_ADMIN_TABS, UI_TRANSLATIONS, ImageUploader, AuditorAnalyticsCard, SortableTab };
