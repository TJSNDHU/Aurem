import React, { useState, useEffect, useCallback } from 'react';
import { 
  LayoutDashboard, ShoppingCart, Package, Users, Megaphone, 
  BarChart3, Settings, Star, Percent, PenTool, Store, Inbox, ExternalLink, UsersRound,
  FileText, Palette, Zap, Database, GripVertical, Plus, Trash2, Edit2, X, Check, Eye, EyeOff,
  Share2, Copy, Link2, ChevronDown, ChevronRight, Layers, BoxIcon, GitCompare, Truck, Coins,
  Gift, MessageSquare, FolderPlus, Beaker, Search, Brain, Shield, ShieldCheck, Map, Send,
  Heart, Phone, Leaf, Smartphone, Calendar, UserPlus, Sparkles, Activity, Wrench, Building,
  Globe, Mail, Key, AlertTriangle, Bot
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { toast } from 'sonner';
import axios from 'axios';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  DragOverlay,
  pointerWithin,
  rectIntersection,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '../ui/popover';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Brand configurations for admin
const ADMIN_BRANDS = {
  reroots: {
    id: 'reroots',
    name: 'ReRoots',
    shortName: 'R',
    color: '#F8A5B8',
    bgColor: '#FDF9F9',
    textColor: '#2D2A2E',
    accentColor: '#E88DA0',
    icon: '/reroots-logo.png'
  },
  lavela: {
    id: 'lavela',
    name: 'La Vela Bianca',
    shortName: 'LA',
    color: '#0D4D4D',
    bgColor: '#0D4D4D',
    textColor: '#FDF8F5',
    accentColor: '#D4A574',
    icon: '/lavela-icon.png'
  }
};

// Icon mapping for sidebar items
const ICON_MAP = {
  LayoutDashboard, ShoppingCart, Package, Users, Megaphone, 
  BarChart3, Settings, Star, Percent, PenTool, Store, Inbox, UsersRound,
  FileText, Palette, Zap, Database, ExternalLink, Layers, BoxIcon, GitCompare, Truck, Coins,
  Gift, MessageSquare, Beaker, Brain, Shield, Map, Send, Heart, Phone, Leaf, Smartphone,
  Calendar, UserPlus, Sparkles, Activity, Wrench, Building, ShieldCheck,
  Globe, Mail, Key, AlertTriangle, Bot
};

// Group label colors
const GROUP_COLORS = {
  'loyalty-reviews': '#4a7c59',  // Green for Loyalty & Reviews
  'whatsapp-group': '#25d366',   // WhatsApp green
  'operations-group': '#f59e0b', // Amber for Operations  
  'intelligence-group': '#8b5cf6', // Purple for Intelligence
  'business-group': '#0ea5e9',   // Blue for Business
  'lavela-group': '#0D4D4D',     // Teal for La Vela Bianca
  default: '#64748b'             // Default gray
};

// Default sidebar configuration - 7 grouped sections
// type: 'group' creates a collapsible menu with children
// Merged items open as tabbed pages
const DEFAULT_MENU_ITEMS = [
  // 1) DASHBOARD
  { 
    id: 'dashboard-group', 
    type: 'group', 
    icon: 'LayoutDashboard', 
    label: 'Dashboard', 
    visible: true,
    badgeCount: 3,
    children: [
      { id: 'overview', icon: 'LayoutDashboard', label: 'Overview', section: 'overview', visible: true },
      { id: 'sales-dashboard', icon: 'BarChart3', label: 'Sales Dashboard', section: 'sales-dashboard', visible: true },
      { id: 'executive-intel', icon: 'Brain', label: 'Executive Intel', section: 'executive-intel', visible: true },
    ]
  },
  
  // 2) COMMERCE
  { 
    id: 'commerce-group', 
    type: 'group', 
    icon: 'ShoppingCart', 
    label: 'Commerce', 
    visible: true,
    badgeCount: 8,
    children: [
      { id: 'orders', icon: 'ShoppingCart', label: 'Orders', section: 'orders', visible: true },
      { id: 'order-flow', icon: 'GitBranch', label: 'Order Flow', section: 'order-flow', visible: true },
      { id: 'flagship-shipments', icon: 'Truck', label: 'FlagShip Shipments', section: 'flagship-shipments', visible: true },
      { id: 'abandoned', icon: 'ShoppingCart', label: 'Abandoned Carts', section: 'abandoned', hasBadge: true, badgeColor: '#e74c3c', visible: true },
      { id: 'products', icon: 'Package', label: 'Products', section: 'products', visible: true },
      { id: 'combos', icon: 'Gift', label: 'Combo Offers', section: 'combos', visible: true },
      { id: 'inventory', icon: 'Boxes', label: 'Inventory', section: 'inventory', visible: true },
      { id: 'discount-codes', icon: 'Percent', label: 'Discount Codes', section: 'discount-codes', visible: true },
    ]
  },
  
  // 3) CUSTOMERS
  { 
    id: 'customers-group', 
    type: 'group', 
    icon: 'Users', 
    label: 'Customers', 
    visible: true,
    badgeCount: 9,
    groupColor: '#4a7c59',
    children: [
      { id: 'crm-module', icon: 'Users', label: 'CRM Module', section: 'crm-module', visible: true },
      { id: 'crm-repurchase', icon: 'RefreshCw', label: 'CRM Repurchase', section: 'crm-repurchase', visible: true },
      { id: 'customers', icon: 'Users', label: 'Customers', section: 'customers', visible: true },
      { id: 'loyalty-points', icon: 'Coins', label: 'Loyalty Points', section: 'loyalty-points', visible: true },
      { id: 'reviews', icon: 'Star', label: 'Reviews', section: 'reviews', visible: true },
      { id: 'programs', icon: 'Zap', label: 'Programs', section: 'programs', visible: true },
      { id: 'waitlist', icon: 'Inbox', label: 'Waitlist', section: 'waitlist', visible: true },
      { id: 'customer-ai-insights', icon: 'Brain', label: 'AI Insights', section: 'customer-ai-insights', visible: true },
      { id: 'language-analytics', icon: 'Globe', label: 'Languages', section: 'language-analytics', visible: true },
    ]
  },
  
  // 4) MARKETING
  { 
    id: 'marketing-group', 
    type: 'group', 
    icon: 'Megaphone', 
    label: 'Marketing', 
    visible: true,
    badgeCount: 10,
    groupColor: '#25d366',
    children: [
      { id: 'whatsapp-ai', icon: 'MessageSquare', label: 'WhatsApp AI', section: 'whatsapp-ai', visible: true },
      { id: 'whatsapp-broadcast', icon: 'Users', label: 'WhatsApp Broadcast', section: 'whatsapp-broadcast', visible: true },
      { id: 'whatsapp-crm', icon: 'Send', label: 'WhatsApp CRM', section: 'whatsapp-crm', hasBadge: true, badgeColor: '#e74c3c', visible: true },
      { id: 'marketing-campaigns', icon: 'Target', label: 'Marketing Campaigns', section: 'marketing-campaigns', visible: true },
      { id: 'promotions', icon: 'Tag', label: 'Promotions', section: 'promotions', visible: true },
      { id: 'marketing-lab', icon: 'FlaskConical', label: 'Marketing Lab', section: 'marketing-lab', visible: true },
      { id: 'email-center', icon: 'Mail', label: 'Email Center', section: 'email-center', visible: true },
      { id: 'content-studio', icon: 'PenTool', label: 'Content Studio', section: 'content-studio', visible: true },
      { id: 'compliance-monitor', icon: 'ShieldCheck', label: 'Compliance', section: 'compliance-monitor', visible: true },
      { id: 'proactive-outreach', icon: 'Send', label: 'Proactive Outreach', section: 'proactive-outreach', visible: true },
    ]
  },
  
  // 5) FINANCE
  { 
    id: 'finance-group', 
    type: 'group', 
    icon: 'DollarSign', 
    label: 'Finance', 
    visible: true,
    badgeCount: 5,
    groupColor: '#0ea5e9',
    children: [
      { id: 'accounting-gst', icon: 'Calculator', label: 'Accounting & GST', section: 'accounting-gst', visible: true },
      { id: 'financials', icon: 'Wallet', label: 'Financials', section: 'financials', visible: true },
      { id: 'payroll', icon: 'Banknote', label: 'Payroll', section: 'payroll', visible: true },
      { id: 'refunds-panel', icon: 'RotateCcw', label: 'Refunds', section: 'refunds-panel', visible: true },
      { id: 'hc-compliance', icon: 'ShieldCheck', label: 'HC Compliance', section: 'hc-compliance', visible: true },
    ]
  },
  
  // 6) BRANDS
  { 
    id: 'brands-group', 
    type: 'group', 
    icon: 'Store', 
    label: 'Brands', 
    visible: true,
    badgeCount: 6,
    groupColor: '#0D4D4D',
    children: [
      { id: 'store', icon: 'Store', label: 'ReRoots Store', section: 'store', visible: true },
      { id: 'pwa-analytics', icon: 'Smartphone', label: 'PWA Analytics', section: 'pwa-analytics', visible: true, badge: 'NEW' },
      { id: 'lavela-dashboard', icon: 'Sparkles', label: 'La Vela Bianca', section: 'lavela-dashboard', visible: true },
      { id: 'oroe-dashboard', icon: 'Crown', label: 'OROÉ', section: 'oroe-dashboard', visible: true },
      { id: 'voice-calls', icon: 'Phone', label: 'Voice Calls', section: 'voice-calls', visible: true },
      { id: 'phone-management', icon: 'Smartphone', label: 'Phone Numbers', section: 'phone-management', visible: true },
    ]
  },
  
  // 7) SYSTEM
  { 
    id: 'system-group', 
    type: 'group', 
    icon: 'Settings', 
    label: 'System', 
    visible: true,
    badgeCount: 14,
    children: [
      { id: 'orchestrator', icon: 'Brain', label: 'Orchestrator', section: 'orchestrator', visible: true, badge: 'NEW' },
      { id: 'db-assistant', icon: 'Database', label: 'DB Assistant', section: 'db-assistant', visible: true },
      { id: 'ai-intelligence', icon: 'Brain', label: 'AI Intelligence', section: 'ai-intelligence', visible: true },
      { id: 'automation-intelligence', icon: 'Zap', label: 'Automation', section: 'automation-intelligence', visible: true },
      { id: 'integration-map', icon: 'Map', label: 'Integration Map', section: 'integration-map', visible: true },
      { id: 'fraud-prevention', icon: 'Shield', label: 'Fraud Prevention', section: 'fraud-prevention', visible: true },
      { id: 'security', icon: 'Lock', label: 'Security', section: 'security', visible: true },
      { id: 'settings', icon: 'Settings', label: 'Settings', section: 'settings', visible: true },
      { id: 'team', icon: 'UsersRound', label: 'Team', section: 'team', visible: true },
      { id: 'auto-heal', icon: 'Heart', label: 'Auto Heal', section: 'auto-heal', visible: true },
      { id: 'auto-repair', icon: 'Bot', label: 'Auto Repair', section: 'auto-repair', visible: true },
      { id: 'site-audit', icon: 'Activity', label: 'Site Audit', section: 'site-audit', visible: true },
      { id: 'api-keys', icon: 'Key', label: 'API Keys', section: 'api-keys', visible: true },
      { id: 'crash-dashboard', icon: 'AlertTriangle', label: 'Crash Dashboard', section: 'crash-dashboard', visible: true },
      { id: 'admin-ai', icon: 'Wrench', label: 'Admin AI', section: 'admin-ai', visible: true },
    ]
  },
  
  // SIGNAL ENGINE (External link)
  { 
    id: 'signal-engine', 
    icon: 'Activity', 
    label: 'Signal Engine', 
    visible: true,
    external: true,
    url: 'https://trade-alerts-75.preview.emergentagent.com?install=true'
  },
];

// Collapsible Group Component for nested menus - now a drop target
const CollapsibleGroup = ({ 
  item, 
  activeSection, 
  onClick, 
  editMode, 
  onEdit,
  onToggleVisibility,
  onDeleteGroup,
  onRemoveFromGroup,
  editingItem,
  setEditingItem,
  tempLabel,
  setTempLabel,
  expandedGroups,
  toggleGroup,
  allGroups,
  onMoveToGroup,
  abandonedCount = 0,
  pendingWhatsAppCount = 0,
  colors,
  getBrandLabel = (label) => label  // Default to identity function
}) => {
  const Icon = item.icon ? ICON_MAP[item.icon] : null;
  const isExpanded = expandedGroups.includes(item.id);
  const isEditing = editingItem === item.id;
  const [showMoveMenu, setShowMoveMenu] = useState(null);
  
  // Make this group a drop target
  const { isOver, setNodeRef } = useDroppable({
    id: item.id,
    disabled: !editMode,
  });
  
  // Check if any child is active
  const hasActiveChild = item.children?.some(child => activeSection === child.section);
  
  if (!item.visible && !editMode) return null;
  
  return (
    <div 
      ref={setNodeRef}
      className={cn(
        "relative group transition-all duration-200",
        !item.visible && "opacity-50",
        isOver && editMode && "ring-2 ring-[#F8A5B8] ring-offset-2 rounded-lg bg-[#F8A5B8]/10"
      )}
    >
      {/* Drop indicator when dragging over */}
      {isOver && editMode && (
        <div className="absolute inset-0 border-2 border-dashed border-[#F8A5B8] rounded-lg pointer-events-none z-10 flex items-center justify-center bg-[#F8A5B8]/5">
          <span className="text-xs text-[#F8A5B8] font-medium bg-white px-2 py-1 rounded">Drop here to add</span>
        </div>
      )}
      
      {/* Group Header */}
      {isEditing ? (
        <div className="flex items-center gap-2 px-3 py-2">
          <Input 
            value={tempLabel}
            onChange={(e) => setTempLabel(e.target.value)}
            className="h-7 text-sm"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') { onEdit(item.id, tempLabel); setEditingItem(null); }
              if (e.key === 'Escape') setEditingItem(null);
            }}
          />
          <button onClick={() => { onEdit(item.id, tempLabel); setEditingItem(null); }} className="text-green-500 hover:text-green-700">
            <Check className="h-4 w-4" />
          </button>
          <button onClick={() => setEditingItem(null)} className="text-red-500 hover:text-red-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <div className="flex items-center">
          <button
            onClick={() => toggleGroup(item.id)}
            className="flex-1 flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-colors text-left"
            style={{
              backgroundColor: (hasActiveChild || isExpanded) ? colors.bgActive : 'transparent',
              color: (hasActiveChild || isExpanded) ? colors.text : colors.textMuted,
              fontWeight: (hasActiveChild || isExpanded) ? 500 : 400
            }}
            data-testid={`sidebar-group-${item.id}`}
          >
            {Icon && <Icon className="h-5 w-5 flex-shrink-0" style={{ color: item.groupColor || (hasActiveChild ? colors.primary : colors.textMuted) }} />}
            <span className="flex-1" style={{ color: item.groupColor || colors.text }}>{item.label}</span>
            <Badge className="text-xs" style={{ backgroundColor: item.groupColor ? `${item.groupColor}20` : colors.bgActive, color: item.groupColor || colors.textMuted }}>{item.children?.length || 0}</Badge>
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" style={{ color: colors.textMuted }} />
            ) : (
              <ChevronRight className="h-4 w-4" style={{ color: colors.textMuted }} />
            )}
          </button>
          
          {/* Edit mode controls for group */}
          {editMode && (
            <div className="flex items-center gap-1 pr-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <button 
                onClick={() => { setEditingItem(item.id); setTempLabel(item.label); }} 
                className="p-1 transition-colors"
                style={{ color: colors.textMuted }}
                title="Rename group"
              >
                <Edit2 className="h-3 w-3" />
              </button>
              <button 
                onClick={() => onToggleVisibility(item.id)} 
                className="p-1 transition-colors"
                style={{ color: colors.textMuted }}
                title={item.visible ? "Hide group" : "Show group"}
              >
                {item.visible ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
              </button>
              <button 
                onClick={() => onDeleteGroup && onDeleteGroup(item.id)} 
                className="p-1 text-red-400 hover:text-red-500"
                title="Delete group (items will be moved out)"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>
      )}
      
      {/* Collapsible Children */}
      <div className={cn(
        "overflow-hidden transition-all duration-200 ease-in-out",
        isExpanded ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"
      )}>
        <div className="pl-4 py-1 space-y-0.5">
          {item.children?.map((child) => {
            if (!child.visible && !editMode) return null;
            const ChildIcon = child.icon ? ICON_MAP[child.icon] : null;
            const isChildActive = activeSection === child.section;
            
            return (
              <div key={child.id} className="relative group/child flex items-center">
                <button
                  onClick={() => onClick(child.section)}
                  className="flex-1 flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-colors text-left"
                  style={{
                    backgroundColor: isChildActive ? colors.bgActive : 'transparent',
                    color: isChildActive ? colors.text : colors.textMuted,
                    fontWeight: isChildActive ? 500 : 400,
                    borderLeft: isChildActive ? `2px solid ${colors.primary}` : 'none',
                    opacity: !child.visible ? 0.5 : 1
                  }}
                  data-testid={`sidebar-item-${child.id}`}
                >
                  {ChildIcon && <ChildIcon className="h-4 w-4 flex-shrink-0" style={{ color: isChildActive ? colors.primary : colors.textMuted }} />}
                  <span className="flex-1">{getBrandLabel(child.label)}</span>
                  {/* Status badge for coming soon items */}
                  {child.statusBadge && (
                    <Badge className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0">{child.statusBadge}</Badge>
                  )}
                  {/* Dynamic badge for abandoned/whatsapp-crm */}
                  {child.hasBadge && child.id === 'abandoned' && abandonedCount > 0 && (
                    <Badge className="text-xs px-1.5 py-0" style={{ backgroundColor: child.badgeColor || '#e74c3c', color: '#fff' }}>{abandonedCount}</Badge>
                  )}
                  {child.hasBadge && child.id === 'whatsapp-crm' && pendingWhatsAppCount > 0 && (
                    <Badge className="text-xs px-1.5 py-0" style={{ backgroundColor: child.badgeColor || '#e74c3c', color: '#fff' }}>{pendingWhatsAppCount}</Badge>
                  )}
                </button>
                
                {/* Edit controls for child items */}
                {editMode && (
                  <button
                    onClick={() => onRemoveFromGroup && onRemoveFromGroup(item.id, child.id)}
                    className="p-1 opacity-0 group-hover/child:opacity-100 transition-opacity"
                    style={{ color: colors.textMuted }}
                    title="Move out of group"
                  >
                    <ExternalLink className="h-3 w-3" />
                  </button>
                )}
              </div>
            );
          })}
          
          {/* Empty group message */}
          {editMode && (!item.children || item.children.length === 0) && (
            <div className="px-3 py-2 text-xs text-gray-400 italic">
              Drag items here to add
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Sortable item component
const SortableItem = ({ 
  item, 
  isActive, 
  onClick, 
  abandonedCount, 
  editMode, 
  onEdit, 
  onToggleVisibility, 
  onDelete,
  editingItem,
  setEditingItem,
  tempLabel,
  setTempLabel,
  onShare,
  allGroups = [],
  onMoveToGroup,
  colors
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id, disabled: !editMode });
  
  const [showGroupMenu, setShowGroupMenu] = useState(false);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const Icon = item.icon ? ICON_MAP[item.icon] : null;
  const isEditing = editingItem === item.id;

  // Get shareable link for this section
  const getShareableLink = () => {
    const baseUrl = window.location.origin;
    if (item.section) {
      return `${baseUrl}/admin?section=${item.section}`;
    }
    if (item.href) {
      return `${baseUrl}${item.href}`;
    }
    return baseUrl;
  };

  // Copy link to clipboard
  const handleCopyLink = () => {
    navigator.clipboard.writeText(getShareableLink());
    toast.success(`Link copied: ${item.label}`);
  };

  // Share via native share API or copy
  const handleShare = async () => {
    const shareData = {
      title: `ReRoots Admin - ${item.label}`,
      text: `Check out ${item.label} in ReRoots Admin`,
      url: getShareableLink()
    };
    
    if (navigator.share) {
      try {
        await navigator.share(shareData);
      } catch (err) {
        // User cancelled or error - fallback to copy
        handleCopyLink();
      }
    } else {
      handleCopyLink();
    }
  };

  // Section header
  if (item.type === 'header') {
    if (!item.visible && !editMode) return null;
    return (
      <div 
        ref={setNodeRef} 
        style={style} 
        className={cn("px-3 pt-4 pb-2 flex items-center justify-between group", !item.visible && "opacity-50")}
      >
        {isEditing ? (
          <div className="flex items-center gap-2 flex-1">
            <Input 
              value={tempLabel}
              onChange={(e) => setTempLabel(e.target.value)}
              className="h-6 text-xs"
              autoFocus
            />
            <button onClick={() => { onEdit(item.id, tempLabel); setEditingItem(null); }} className="text-green-500 hover:text-green-700">
              <Check className="h-4 w-4" />
            </button>
            <button onClick={() => setEditingItem(null)} className="text-red-500 hover:text-red-700">
              <X className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <>
            {editMode && (
              <button {...attributes} {...listeners} className="cursor-grab p-1 -ml-2 transition-colors" style={{ color: colors?.textMuted || '#5A5A5A' }}>
                <GripVertical className="h-3 w-3" />
              </button>
            )}
            <span className="text-xs font-medium uppercase tracking-wider" style={{ color: colors?.primary || '#F8A5B8' }}>{item.label}</span>
            {editMode && (
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={() => { setEditingItem(item.id); setTempLabel(item.label); }} className="p-1 transition-colors" style={{ color: colors?.textMuted || '#5A5A5A' }}>
                  <Edit2 className="h-3 w-3" />
                </button>
                <button onClick={() => onToggleVisibility(item.id)} className="p-1 transition-colors" style={{ color: colors?.textMuted || '#5A5A5A' }}>
                  {item.visible ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    );
  }

  // External link
  if (item.type === 'link') {
    if (!item.visible && !editMode) return null;
    return (
      <div 
        ref={setNodeRef} 
        style={style} 
        className={cn("flex items-center group", !item.visible && "opacity-50")}
      >
        {editMode && (
          <button {...attributes} {...listeners} className="cursor-grab p-1 transition-colors" style={{ color: colors?.textMuted || '#5A5A5A' }}>
            <GripVertical className="h-4 w-4" />
          </button>
        )}
        <a 
          href={item.href} 
          target="_blank" 
          rel="noopener noreferrer"
          className="flex-1 flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-colors"
          style={{ color: colors?.textMuted || '#5A5A5A' }}
        >
          {Icon && <Icon className="h-5 w-5 flex-shrink-0" />}
          <span>{item.label}</span>
        </a>
        {editMode && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity pr-2">
            <button onClick={() => onToggleVisibility(item.id)} className="p-1 text-[#5A5A5A] hover:text-[#F8A5B8]">
              {item.visible ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
            </button>
          </div>
        )}
      </div>
    );
  }

  // External app link (Signal Engine, etc.)
  if (item.external && item.url) {
    if (!item.visible && !editMode) return null;
    
    const handleShareExternal = async () => {
      const shareData = {
        title: item.label,
        text: `Check out ${item.label}`,
        url: item.url
      };
      if (navigator.share) {
        try {
          await navigator.share(shareData);
        } catch (err) {
          navigator.clipboard.writeText(item.url);
          toast.success(`Link copied: ${item.label}`);
        }
      } else {
        navigator.clipboard.writeText(item.url);
        toast.success(`Link copied: ${item.label}`);
      }
    };
    
    return (
      <div 
        ref={setNodeRef} 
        style={style} 
        className={cn("flex items-center group", !item.visible && "opacity-50")}
      >
        {editMode && (
          <button {...attributes} {...listeners} className="cursor-grab p-1 transition-colors" style={{ color: colors?.textMuted || '#5A5A5A' }}>
            <GripVertical className="h-4 w-4" />
          </button>
        )}
        <a 
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-colors hover:bg-[#F8A5B8]/10"
          style={{ color: colors?.primary || '#F8A5B8' }}
          data-testid="signal-engine-link"
        >
          {Icon && <Icon className="h-5 w-5 flex-shrink-0" style={{ color: colors?.primary || '#F8A5B8' }} />}
          <span className="font-medium">{item.label}</span>
          <ExternalLink className="h-3.5 w-3.5 ml-auto" style={{ color: colors?.textMuted || '#5A5A5A' }} />
        </a>
        {/* Share button */}
        <button 
          onClick={handleShareExternal}
          className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-[#F8A5B8]/10 rounded transition-all"
          style={{ color: colors?.textMuted || '#5A5A5A' }}
          title="Share Signal Engine"
          data-testid="signal-engine-share"
        >
          <Share2 className="h-3.5 w-3.5" />
        </button>
        {editMode && (
          <button onClick={() => onToggleVisibility(item.id)} className="p-1 opacity-0 group-hover:opacity-100 text-[#5A5A5A] hover:text-[#F8A5B8]">
            {item.visible ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
          </button>
        )}
      </div>
    );
  }

  // Regular menu item
  if (!item.visible && !editMode) return null;
  
  return (
    <div 
      ref={setNodeRef} 
      style={style}
      className={cn("flex items-center group", !item.visible && "opacity-50")}
    >
      {/* Drag handle - always visible on hover, functional only in edit mode */}
      <button 
        {...(editMode ? { ...attributes, ...listeners } : {})} 
        className={cn(
          "p-1 text-[#5A5A5A] transition-opacity",
          editMode ? "cursor-grab hover:text-[#F8A5B8]" : "cursor-default opacity-0 group-hover:opacity-40"
        )}
        title={editMode ? "Drag to reorder" : "Click gear icon to enable drag"}
      >
        <GripVertical className="h-4 w-4" />
      </button>
      
      {isEditing ? (
        <div className="flex items-center gap-2 flex-1 px-3 py-2">
          <Input 
            value={tempLabel}
            onChange={(e) => setTempLabel(e.target.value)}
            className="h-7 text-sm"
            autoFocus
          />
          <button onClick={() => { onEdit(item.id, tempLabel); setEditingItem(null); }} className="text-green-500 hover:text-green-700">
            <Check className="h-4 w-4" />
          </button>
          <button onClick={() => setEditingItem(null)} className="text-red-500 hover:text-red-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <button
          onClick={() => !editMode && onClick(item.section)}
          className={cn(
            "flex-1 flex items-center gap-3 px-2 py-2 text-sm rounded-lg transition-colors text-left",
            item.indent && "pl-8",
            isActive 
              ? "bg-[#F8A5B8]/20 text-[#2D2A2E] font-medium border-l-2 border-[#F8A5B8]" 
              : "text-[#5A5A5A] hover:bg-[#F8A5B8]/10 hover:text-[#2D2A2E]",
            editMode && "cursor-default"
          )}
          data-testid={`sidebar-item-${item.id}`}
        >
          {Icon && <Icon className={cn("h-5 w-5 flex-shrink-0", isActive ? "text-[#F8A5B8]" : "text-[#5A5A5A]")} />}
          <span className="flex-1">{item.label}</span>
          {item.hasBadge && abandonedCount > 0 && (
            <Badge className="bg-[#F8A5B8] text-white text-xs px-2 py-0.5">{abandonedCount}</Badge>
          )}
        </button>
      )}
      
      {/* Share button - always visible on hover */}
      {!isEditing && item.section && (
        <Popover>
          <PopoverTrigger asChild>
            <button 
              className="p-1 text-[#5A5A5A] opacity-0 group-hover:opacity-100 hover:text-[#F8A5B8] transition-opacity"
              title={`Share ${item.label}`}
              data-testid={`share-btn-${item.id}`}
            >
              <Share2 className="h-3.5 w-3.5" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-64 p-3" side="right" align="start">
            <div className="space-y-3">
              <p className="text-sm font-medium text-[#2D2A2E]">Share "{item.label}"</p>
              <div className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg text-xs text-gray-600 break-all">
                <Link2 className="h-3.5 w-3.5 flex-shrink-0" />
                <span className="truncate">{getShareableLink()}</span>
              </div>
              <div className="flex gap-2">
                <Button 
                  size="sm" 
                  variant="outline"
                  className="flex-1 h-8 text-xs"
                  onClick={handleCopyLink}
                >
                  <Copy className="h-3 w-3 mr-1" />
                  Copy Link
                </Button>
                <Button 
                  size="sm"
                  className="flex-1 h-8 text-xs bg-[#F8A5B8] hover:bg-[#E88DA0] text-white"
                  onClick={handleShare}
                >
                  <Share2 className="h-3 w-3 mr-1" />
                  Share
                </Button>
              </div>
            </div>
          </PopoverContent>
        </Popover>
      )}
      
      {/* Edit mode controls */}
      {editMode && !isEditing && (
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity pr-1">
          <button onClick={() => { setEditingItem(item.id); setTempLabel(item.label); }} className="p-1 text-[#5A5A5A] hover:text-[#F8A5B8]" title="Rename">
            <Edit2 className="h-3 w-3" />
          </button>
          <button onClick={() => onToggleVisibility(item.id)} className="p-1 text-[#5A5A5A] hover:text-[#F8A5B8]" title={item.visible ? "Hide" : "Show"}>
            {item.visible ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
          </button>
          
          {/* Move to Group dropdown */}
          {allGroups.length > 0 && onMoveToGroup && (
            <Popover open={showGroupMenu} onOpenChange={setShowGroupMenu}>
              <PopoverTrigger asChild>
                <button 
                  className="p-1 text-blue-500 hover:text-blue-700 bg-blue-50 rounded"
                  title="Move to group"
                  data-testid={`move-to-group-${item.id}`}
                >
                  <FolderPlus className="h-3.5 w-3.5" />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-44 p-0" side="right" align="start">
                <div className="py-1">
                  <p className="px-3 py-1.5 text-xs text-gray-500 font-medium border-b">Move to group:</p>
                  {allGroups.map(group => (
                    <button
                      key={group.id}
                      onClick={() => {
                        onMoveToGroup(item.id, group.id);
                        setShowGroupMenu(false);
                      }}
                      className="w-full px-3 py-2 text-sm text-left hover:bg-[#F8A5B8]/10 flex items-center gap-2"
                    >
                      {ICON_MAP[group.icon] && React.createElement(ICON_MAP[group.icon], { className: "h-4 w-4 text-[#F8A5B8]" })}
                      {group.label}
                    </button>
                  ))}
                </div>
              </PopoverContent>
            </Popover>
          )}
          
          {!item.section?.match(/^(overview|orders|products|customers|settings)$/) && (
            <button onClick={() => onDelete(item.id)} className="p-1 text-[#5A5A5A] hover:text-red-500" title="Delete">
              <Trash2 className="h-3 w-3" />
            </button>
          )}
        </div>
      )}
    </div>
  );
};

const AdminSidebar = ({ activeSection, setActiveSection, abandonedCount = 0, adminName = '' }) => {
  const [menuItems, setMenuItems] = useState(DEFAULT_MENU_ITEMS);
  const [editMode, setEditMode] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [tempLabel, setTempLabel] = useState('');
  const [hasChanges, setHasChanges] = useState(false);
  const [loading, setLoading] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState(['orders-group', 'shop-group', 'customers-group', 'loyalty-reviews', 'whatsapp-group']); // Default expanded
  const [clearingCache, setClearingCache] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [pendingWhatsAppCount, setPendingWhatsAppCount] = useState(0);
  
  // Brand switcher state
  const [activeBrand, setActiveBrand] = useState(() => {
    return localStorage.getItem('admin_active_brand') || 'reroots';
  });
  const [showBrandMenu, setShowBrandMenu] = useState(false);
  
  const currentBrand = ADMIN_BRANDS[activeBrand] || ADMIN_BRANDS.reroots;
  
  // Get brand-aware label
  const getBrandLabel = (label) => {
    if (!label) return label;
    const pointsName = activeBrand === 'lavela' ? 'Glow Points' : 'Roots';
    return label
      .replace('(Roots)', `(${pointsName})`)
      .replace('Gift Roots', `Gift ${pointsName}`);
  };
  
  // Switch brand handler
  const handleBrandSwitch = (brandId) => {
    setActiveBrand(brandId);
    localStorage.setItem('admin_active_brand', brandId);
    setShowBrandMenu(false);
    toast.success(`Switched to ${ADMIN_BRANDS[brandId].name}`);
  };
  
  // Dynamic colors based on active brand
  const colors = {
    text: activeBrand === 'lavela' ? '#FDF8F5' : '#2D2A2E',
    textMuted: activeBrand === 'lavela' ? '#D4A574' : '#5A5A5A',
    primary: activeBrand === 'lavela' ? '#D4A574' : '#F8A5B8',
    primaryHover: activeBrand === 'lavela' ? '#E6BE8A' : '#E88DA0',
    bg: activeBrand === 'lavela' ? '#0D4D4D' : '#FDF9F9',
    bgHover: activeBrand === 'lavela' ? '#1A6B6B' : '#F8A5B810',
    bgActive: activeBrand === 'lavela' ? '#1A6B6B40' : '#F8A5B820',
    border: activeBrand === 'lavela' ? '#D4A57440' : '#F8A5B820',
  };

  // Fetch pending WhatsApp CRM actions count
  useEffect(() => {
    const fetchPendingWhatsAppCount = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;
        const res = await axios.get(`${API}/admin/crm-actions`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        // Count pending actions
        const pending = res.data?.actions?.filter(a => a.status === 'pending')?.length || 0;
        setPendingWhatsAppCount(pending);
      } catch (err) {
        console.log('Could not fetch WhatsApp CRM count');
      }
    };
    fetchPendingWhatsAppCount();
    // Refresh every 60 seconds
    const interval = setInterval(fetchPendingWhatsAppCount, 60000);
    return () => clearInterval(interval);
  }, []);

  // Filter menu items based on search query
  const getFilteredItems = useCallback(() => {
    if (!searchQuery.trim()) return menuItems;
    
    const query = searchQuery.toLowerCase();
    const filtered = [];
    
    for (const item of menuItems) {
      if (item.type === 'group') {
        // Search in group children
        const matchingChildren = item.children?.filter(child => 
          child.label?.toLowerCase().includes(query) ||
          child.section?.toLowerCase().includes(query)
        ) || [];
        
        if (matchingChildren.length > 0 || item.label?.toLowerCase().includes(query)) {
          filtered.push({
            ...item,
            children: matchingChildren.length > 0 ? matchingChildren : item.children
          });
        }
      } else if (item.type === 'header') {
        // Include headers if they match
        if (item.label?.toLowerCase().includes(query)) {
          filtered.push(item);
        }
      } else {
        // Regular items
        if (item.label?.toLowerCase().includes(query) || item.section?.toLowerCase().includes(query)) {
          filtered.push(item);
        }
      }
    }
    
    return filtered;
  }, [menuItems, searchQuery]);

  // Auto-expand groups when searching
  useEffect(() => {
    if (searchQuery.trim()) {
      // Expand all groups when searching
      const groupIds = menuItems.filter(i => i.type === 'group').map(i => i.id);
      setExpandedGroups(groupIds);
    }
  }, [searchQuery, menuItems]);

  // Use the API constant defined at top of file (line 36)
  // const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api'; is already defined

  // Clear cache function
  const handleClearCache = async () => {
    if (clearingCache) return;
    setClearingCache(true);
    try {
      await axios.post(`${API}/admin/clear-cache`, {}, { 
        headers: { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` }
      });
      toast.success("Cache cleared! Page will reload...");
      setTimeout(() => window.location.reload(), 1000);
    } catch (e) {
      console.error("Clear cache error:", e);
      toast.error("Failed to clear cache");
    }
    setClearingCache(false);
  };

  // Toggle group expansion
  const toggleGroup = useCallback((groupId) => {
    setExpandedGroups(prev => 
      prev.includes(groupId) 
        ? prev.filter(id => id !== groupId)
        : [...prev, groupId]
    );
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  // Load saved sidebar config - ALWAYS use DEFAULT_MENU_ITEMS as source of truth
  // Database config is only used for user customizations (visibility, order)
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        if (!token) {
          // No token - use defaults
          setMenuItems(DEFAULT_MENU_ITEMS);
          return;
        }
        
        const res = await axios.get(`${API}/admin/sidebar-config`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        
        // ALWAYS use DEFAULT_MENU_ITEMS as the base structure
        // Only merge user customizations (visibility toggles) from saved config
        if (res.data?.menu_items?.length > 0) {
          const savedConfig = res.data.menu_items;
          
          // Create a map of saved visibility states
          const visibilityMap = {};
          const childVisibilityMap = {};
          
          savedConfig.forEach(item => {
            visibilityMap[item.id] = item.visible !== false;
            if (item.type === 'group' && item.children) {
              item.children.forEach(child => {
                childVisibilityMap[child.id] = child.visible !== false;
              });
            }
          });
          
          // Apply visibility customizations to DEFAULT_MENU_ITEMS
          const mergedItems = DEFAULT_MENU_ITEMS.map(item => {
            if (item.type === 'group') {
              return {
                ...item,
                visible: visibilityMap[item.id] !== undefined ? visibilityMap[item.id] : item.visible,
                children: (item.children || []).map(child => ({
                  ...child,
                  visible: childVisibilityMap[child.id] !== undefined ? childVisibilityMap[child.id] : child.visible
                }))
              };
            }
            return {
              ...item,
              visible: visibilityMap[item.id] !== undefined ? visibilityMap[item.id] : item.visible
            };
          });
          
          setMenuItems(mergedItems);
          console.log('Sidebar: Using DEFAULT_MENU_ITEMS with user visibility customizations');
        } else {
          // No saved config - use pure defaults
          setMenuItems(DEFAULT_MENU_ITEMS);
          console.log('Sidebar: Using pure DEFAULT_MENU_ITEMS');
        }
      } catch (error) {
        // Use default if error
        setMenuItems(DEFAULT_MENU_ITEMS);
        console.log('Sidebar: Error loading config, using defaults');
      }
    };
    loadConfig();
  }, []);

  // Save sidebar config
  const saveConfig = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      if (!token) {
        toast.error('Please login again to save changes');
        setLoading(false);
        return;
      }
      
      // Clean the menu items to ensure they're serializable
      const cleanMenuItems = menuItems.map(item => {
        // Handle group type with children
        if (item.type === 'group') {
          return {
            id: item.id,
            type: 'group',
            icon: item.icon || null,
            label: item.label,
            visible: item.visible !== false,
            children: (item.children || []).map(child => ({
              id: child.id,
              icon: child.icon || null,
              label: child.label,
              section: child.section || null,
              visible: child.visible !== false,
            }))
          };
        }
        
        // Handle regular items
        return {
          id: item.id,
          icon: item.icon || null,
          label: item.label,
          section: item.section || null,
          visible: item.visible !== false,
          indent: item.indent || false,
          hasBadge: item.hasBadge || false,
          type: item.type || null,
          href: item.href || null,
          parentId: item.parentId || null
        };
      });
      
      console.log('[Sidebar] Saving config with', cleanMenuItems.length, 'items');
      
      const response = await axios.post(`${API}/admin/sidebar-config`, 
        { menu_items: cleanMenuItems },
        { 
          headers: { Authorization: `Bearer ${token}` },
          timeout: 10000 // 10 second timeout
        }
      );
      
      console.log('[Sidebar] Save response:', response.data);
      toast.success('Sidebar layout saved!');
      setHasChanges(false);
    } catch (error) {
      console.error('[Sidebar] Save error:', error);
      console.error('[Sidebar] Error response:', error.response?.data);
      console.error('[Sidebar] Error status:', error.response?.status);
      
      let errorMsg = 'Failed to save sidebar layout';
      if (error.code === 'ECONNABORTED') {
        errorMsg = 'Save request timed out. Please try again.';
      } else if (error.response?.status === 401) {
        errorMsg = 'Session expired. Please login again.';
      } else if (error.response?.status === 403) {
        errorMsg = 'Admin access required.';
      } else if (error.response?.data?.detail) {
        errorMsg = error.response.data.detail;
      }
      
      toast.error(errorMsg);
    }
    setLoading(false);
  }, [menuItems]);

  // Reset to default (local only)
  const resetToDefault = () => {
    setMenuItems(DEFAULT_MENU_ITEMS);
    setHasChanges(true);
    toast.success('Reset to default layout');
  };
  
  // Force reset and clear database config
  const forceResetAndSave = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      setMenuItems(DEFAULT_MENU_ITEMS);
      
      if (token) {
        // Clear the database config by saving fresh defaults
        const cleanItems = DEFAULT_MENU_ITEMS.map(item => {
          if (item.type === 'group') {
            return {
              id: item.id,
              type: item.type,
              icon: item.icon,
              label: item.label,
              visible: item.visible !== false,
              groupColor: item.groupColor,
              children: (item.children || []).map(child => ({
                id: child.id,
                icon: child.icon,
                label: child.label,
                section: child.section,
                visible: child.visible !== false,
                hasBadge: child.hasBadge,
                badgeColor: child.badgeColor,
                statusBadge: child.statusBadge,
                tabs: child.tabs
              }))
            };
          }
          return {
            id: item.id,
            icon: item.icon,
            label: item.label,
            section: item.section,
            visible: item.visible !== false
          };
        });
        
        await axios.post(`${API}/admin/sidebar-config`, { menu_items: cleanItems }, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
      
      setHasChanges(false);
      toast.success('Sidebar reset and saved to database!');
    } catch (error) {
      console.error('Force reset error:', error);
      toast.error('Failed to save reset config');
    }
    setLoading(false);
  };

  const handleDragEnd = (event) => {
    const { active, over } = event;
    
    if (!over || active.id === over.id) return;
    
    // Check if dropping onto a group
    const targetItem = menuItems.find(i => i.id === over.id);
    const draggedItem = menuItems.find(i => i.id === active.id);
    
    if (targetItem?.type === 'group' && draggedItem && draggedItem.type !== 'group' && draggedItem.type !== 'header') {
      // Move item INTO the group
      handleMoveToGroup(active.id, over.id);
      return;
    }
    
    // Check if dropping onto an item that's inside a group (drop into that group)
    for (const item of menuItems) {
      if (item.type === 'group' && item.children) {
        const isOverChild = item.children.some(c => c.id === over.id);
        if (isOverChild && draggedItem && draggedItem.type !== 'group' && draggedItem.type !== 'header') {
          // Move item into the same group as the target child
          handleMoveToGroup(active.id, item.id);
          return;
        }
      }
    }
    
    // Regular reordering within the main list
    setMenuItems((items) => {
      const oldIndex = items.findIndex(i => i.id === active.id);
      const newIndex = items.findIndex(i => i.id === over.id);
      
      if (oldIndex === -1 || newIndex === -1) return items;
      
      const newItems = arrayMove(items, oldIndex, newIndex);
      setHasChanges(true);
      return newItems;
    });
  };

  const handleEdit = (id, newLabel) => {
    setMenuItems(items => items.map(item => 
      item.id === id ? { ...item, label: newLabel } : item
    ));
    setHasChanges(true);
  };

  const handleToggleVisibility = (id) => {
    setMenuItems(items => items.map(item => 
      item.id === id ? { ...item, visible: !item.visible } : item
    ));
    setHasChanges(true);
  };

  const handleDelete = (id) => {
    setMenuItems(items => items.filter(item => item.id !== id));
    setHasChanges(true);
  };

  // State for creating new groups
  const [showNewGroupModal, setShowNewGroupModal] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupIcon, setNewGroupIcon] = useState('Layers');

  // Available icons for groups
  const AVAILABLE_ICONS = [
    'Layers', 'Package', 'ShoppingCart', 'Users', 'Megaphone', 'BarChart3', 
    'Star', 'Percent', 'Store', 'FileText', 'Database', 'Truck', 'Gift', 
    'Coins', 'Settings', 'Inbox', 'Zap', 'PenTool', 'Palette'
  ];

  // Create new group
  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) {
      toast.error('Please enter a group name');
      return;
    }
    
    const newGroup = {
      id: `custom-group-${Date.now()}`,
      type: 'group',
      icon: newGroupIcon,
      label: newGroupName.trim(),
      visible: true,
      children: []
    };
    
    // Insert after the existing groups or at position 3
    const firstHeaderIndex = menuItems.findIndex(item => item.type === 'header');
    const insertIndex = firstHeaderIndex > 0 ? firstHeaderIndex : Math.min(3, menuItems.length);
    
    const newItems = [...menuItems];
    newItems.splice(insertIndex, 0, newGroup);
    
    setMenuItems(newItems);
    setShowNewGroupModal(false);
    setNewGroupName('');
    setNewGroupIcon('Layers');
    
    // Auto-save the new group immediately
    try {
      const token = localStorage.getItem('reroots_token');
      if (token) {
        const cleanMenuItems = newItems.map(item => {
          if (item.type === 'group') {
            return {
              id: item.id,
              type: 'group',
              icon: item.icon || null,
              label: item.label,
              visible: item.visible !== false,
              children: (item.children || []).map(child => ({
                id: child.id,
                icon: child.icon || null,
                label: child.label,
                section: child.section || null,
                visible: child.visible !== false,
              }))
            };
          }
          return {
            id: item.id,
            icon: item.icon || null,
            label: item.label,
            section: item.section || null,
            visible: item.visible !== false,
            indent: item.indent || false,
            hasBadge: item.hasBadge || false,
            type: item.type || null,
            href: item.href || null,
            parentId: item.parentId || null
          };
        });
        
        await axios.post(`${API}/admin/sidebar-config`, 
          { menu_items: cleanMenuItems },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        toast.success(`Created and saved group "${newGroup.label}"`);
        setHasChanges(false);
      }
    } catch (error) {
      console.error('Failed to auto-save group:', error);
      toast.warning(`Group "${newGroup.label}" created but not saved. Click Save to persist.`);
      setHasChanges(true);
    }
  };

  // Move item into a group
  const handleMoveToGroup = async (itemId, groupId) => {
    let newItems = null;
    
    setMenuItems(items => {
      const itemIndex = items.findIndex(i => i.id === itemId);
      if (itemIndex === -1) return items;
      
      const item = items[itemIndex];
      if (item.type === 'group' || item.type === 'header') {
        toast.error("Can't move groups or headers into other groups");
        return items;
      }
      
      const filteredItems = items.filter(i => i.id !== itemId);
      
      // Find the target group and add the item
      newItems = filteredItems.map(i => {
        if (i.id === groupId && i.type === 'group') {
          const childItem = {
            id: item.id,
            icon: item.icon,
            label: item.label,
            section: item.section,
            visible: true
          };
          return {
            ...i,
            children: [...(i.children || []), childItem]
          };
        }
        return i;
      });
      
      return newItems;
    });
    
    // Auto-save after move
    setTimeout(async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        if (token && newItems) {
          const cleanMenuItems = newItems.map(item => {
            if (item.type === 'group') {
              return {
                id: item.id,
                type: 'group',
                icon: item.icon || null,
                label: item.label,
                visible: item.visible !== false,
                children: (item.children || []).map(child => ({
                  id: child.id,
                  icon: child.icon || null,
                  label: child.label,
                  section: child.section || null,
                  visible: child.visible !== false,
                }))
              };
            }
            return {
              id: item.id,
              icon: item.icon || null,
              label: item.label,
              section: item.section || null,
              visible: item.visible !== false,
              indent: item.indent || false,
              hasBadge: item.hasBadge || false,
              type: item.type || null,
              href: item.href || null,
              parentId: item.parentId || null
            };
          });
          
          await axios.post(`${API}/admin/sidebar-config`, 
            { menu_items: cleanMenuItems },
            { headers: { Authorization: `Bearer ${token}` } }
          );
          toast.success('Item moved and saved!');
          setHasChanges(false);
        }
      } catch (error) {
        console.error('Failed to auto-save move:', error);
        toast.warning('Item moved but not saved. Click Save to persist.');
        setHasChanges(true);
      }
    }, 100);
  };

  // Remove item from group (move to top level)
  const handleRemoveFromGroup = async (groupId, childId) => {
    let newItems = null;
    
    setMenuItems(items => {
      let removedChild = null;
      
      // Find and remove the child from its group
      const updatedItems = items.map(item => {
        if (item.id === groupId && item.type === 'group') {
          const child = item.children?.find(c => c.id === childId);
          if (child) {
            removedChild = {
              ...child,
              section: child.section || childId,
              visible: true
            };
          }
          return {
            ...item,
            children: (item.children || []).filter(c => c.id !== childId)
          };
        }
        return item;
      });
      
      // Add the removed child back to top level
      if (removedChild) {
        const groupIndex = updatedItems.findIndex(i => i.id === groupId);
        updatedItems.splice(groupIndex + 1, 0, removedChild);
      }
      
      newItems = updatedItems;
      return updatedItems;
    });
    
    // Auto-save after remove
    setTimeout(async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        if (token && newItems) {
          const cleanMenuItems = newItems.map(item => {
            if (item.type === 'group') {
              return {
                id: item.id,
                type: 'group',
                icon: item.icon || null,
                label: item.label,
                visible: item.visible !== false,
                children: (item.children || []).map(child => ({
                  id: child.id,
                  icon: child.icon || null,
                  label: child.label,
                  section: child.section || null,
                  visible: child.visible !== false,
                }))
              };
            }
            return {
              id: item.id,
              icon: item.icon || null,
              label: item.label,
              section: item.section || null,
              visible: item.visible !== false,
              indent: item.indent || false,
              hasBadge: item.hasBadge || false,
              type: item.type || null,
              href: item.href || null,
              parentId: item.parentId || null
            };
          });
          
          await axios.post(`${API}/admin/sidebar-config`, 
            { menu_items: cleanMenuItems },
            { headers: { Authorization: `Bearer ${token}` } }
          );
          toast.success('Item removed from group and saved!');
          setHasChanges(false);
        }
      } catch (error) {
        console.error('Failed to auto-save:', error);
        setHasChanges(true);
      }
    }, 100);
  };

  // Delete entire group (move children out first)
  const handleDeleteGroup = async (groupId) => {
    let newItems = null;
    
    setMenuItems(items => {
      const group = items.find(i => i.id === groupId);
      if (!group || group.type !== 'group') return items;
      
      const children = (group.children || []).map(child => ({
        ...child,
        section: child.section || child.id,
        visible: true
      }));
      
      const groupIndex = items.findIndex(i => i.id === groupId);
      const filteredItems = items.filter(i => i.id !== groupId);
      
      // Insert children where the group was
      filteredItems.splice(groupIndex, 0, ...children);
      
      newItems = filteredItems;
      return filteredItems;
    });
    
    // Auto-save after delete
    setTimeout(async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        if (token && newItems) {
          const cleanMenuItems = newItems.map(item => {
            if (item.type === 'group') {
              return {
                id: item.id,
                type: 'group',
                icon: item.icon || null,
                label: item.label,
                visible: item.visible !== false,
                children: (item.children || []).map(child => ({
                  id: child.id,
                  icon: child.icon || null,
                  label: child.label,
                  section: child.section || null,
                  visible: child.visible !== false,
                }))
              };
            }
            return {
              id: item.id,
              icon: item.icon || null,
              label: item.label,
              section: item.section || null,
              visible: item.visible !== false,
              indent: item.indent || false,
              hasBadge: item.hasBadge || false,
              type: item.type || null,
              href: item.href || null,
              parentId: item.parentId || null
            };
          });
          
          await axios.post(`${API}/admin/sidebar-config`, 
            { menu_items: cleanMenuItems },
            { headers: { Authorization: `Bearer ${token}` } }
          );
          toast.success('Group deleted and saved!');
          setHasChanges(false);
        }
      } catch (error) {
        console.error('Failed to auto-save:', error);
        setHasChanges(true);
      }
    }, 100);
  };

  return (
    <div 
      className="sidebar-container admin-sidebar w-56 border-r flex flex-col transition-colors duration-300"
      style={{ 
        backgroundColor: activeBrand === 'lavela' ? '#0D4D4D' : '#FDF9F9',
        borderColor: activeBrand === 'lavela' ? '#D4A57440' : '#F8A5B820'
      }}
    >
      {/* Logo/Brand with Switcher - Fixed at top */}
      <div 
        className="p-4 flex items-center gap-2 border-b transition-colors duration-300" 
        style={{ 
          flexShrink: 0,
          borderColor: activeBrand === 'lavela' ? '#D4A57440' : '#F8A5B820',
          backgroundColor: activeBrand === 'lavela' ? '#0D4D4D' : 'white'
        }}
      >
        {/* Brand Switcher Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowBrandMenu(!showBrandMenu)}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-xs transition-all hover:scale-105 hover:shadow-md"
            style={{ 
              background: activeBrand === 'lavela' 
                ? 'linear-gradient(135deg, #0D4D4D, #1A6B6B)' 
                : 'linear-gradient(135deg, #F8A5B8, #E88DA0)'
            }}
            title="Switch brand"
            data-testid="brand-switcher-btn"
          >
            {currentBrand.shortName}
          </button>
          
          {/* Brand Dropdown Menu */}
          {showBrandMenu && (
            <>
              <div 
                className="fixed inset-0 z-40" 
                onClick={() => setShowBrandMenu(false)}
              />
              <div className="absolute top-full left-0 mt-2 w-52 bg-white rounded-xl shadow-2xl border border-gray-100 z-50 overflow-hidden">
                <div className="p-3 border-b border-gray-100 bg-gray-50">
                  <p className="text-xs text-gray-500 font-semibold uppercase tracking-wide">Switch Brand</p>
                </div>
                
                {/* ReRoots Option */}
                <button
                  onClick={() => handleBrandSwitch('reroots')}
                  className={cn(
                    "w-full px-3 py-3 flex items-center gap-3 hover:bg-[#F8A5B8]/10 transition-colors",
                    activeBrand === 'reroots' && "bg-[#F8A5B8]/15"
                  )}
                  data-testid="brand-switch-reroots"
                >
                  <div 
                    className="w-9 h-9 rounded-lg flex items-center justify-center text-white font-bold text-sm shadow-sm" 
                    style={{ background: 'linear-gradient(135deg, #F8A5B8, #E88DA0)' }}
                  >
                    R
                  </div>
                  <div className="text-left flex-1">
                    <p className="text-sm font-semibold text-gray-900">ReRoots</p>
                    <p className="text-xs text-gray-500">Adult Skincare</p>
                  </div>
                  {activeBrand === 'reroots' && (
                    <Check className="w-5 h-5 text-[#F8A5B8]" />
                  )}
                </button>
                
                {/* La Vela Bianca Option */}
                <button
                  onClick={() => handleBrandSwitch('lavela')}
                  className={cn(
                    "w-full px-3 py-3 flex items-center gap-3 hover:bg-[#0D4D4D]/10 transition-colors",
                    activeBrand === 'lavela' && "bg-[#0D4D4D]/15"
                  )}
                  data-testid="brand-switch-lavela"
                >
                  <div 
                    className="w-9 h-9 rounded-lg flex items-center justify-center text-white font-bold text-sm shadow-sm" 
                    style={{ background: 'linear-gradient(135deg, #0D4D4D, #1A6B6B)' }}
                  >
                    LA
                  </div>
                  <div className="text-left flex-1">
                    <p className="text-sm font-semibold text-gray-900">La Vela Bianca</p>
                    <p className="text-xs text-gray-500">Teen Skincare</p>
                  </div>
                  {activeBrand === 'lavela' && (
                    <Check className="w-5 h-5 text-[#0D4D4D]" />
                  )}
                </button>
              </div>
            </>
          )}
        </div>
        
        <div className="min-w-0 flex-1">
          <h1 
            className="font-semibold text-sm truncate transition-colors duration-300" 
            style={{ color: activeBrand === 'lavela' ? '#FDF8F5' : '#2D2A2E' }}
          >
            {currentBrand.name}
          </h1>
          {adminName && (
            <p 
              className="text-xs truncate transition-colors duration-300" 
              style={{ color: activeBrand === 'lavela' ? '#D4A574' : '#5A5A5A' }}
            >
              {adminName}
            </p>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setEditMode(!editMode)}
          className="p-1 h-auto transition-colors"
          style={{ 
            backgroundColor: editMode 
              ? (activeBrand === 'lavela' ? '#D4A57430' : '#F8A5B830') 
              : 'transparent' 
          }}
          title="Customize sidebar"
          data-testid="sidebar-edit-toggle"
        >
          <Settings 
            className="h-4 w-4 transition-colors" 
            style={{ 
              color: editMode 
                ? currentBrand.color 
                : (activeBrand === 'lavela' ? '#D4A574' : '#5A5A5A') 
            }} 
          />
        </Button>
      </div>

      {/* Search Box */}
      <div 
        className="px-3 py-2 border-b transition-colors duration-300"
        style={{ 
          borderColor: activeBrand === 'lavela' ? '#D4A57440' : '#F8A5B820',
          backgroundColor: activeBrand === 'lavela' ? '#1A6B6B40' : 'rgba(255,255,255,0.5)'
        }}
      >
        <div className="relative">
          <Search 
            className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 transition-colors" 
            style={{ color: activeBrand === 'lavela' ? '#D4A574' : '#9ca3af' }}
          />
          <Input
            type="text"
            placeholder="Search menu..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 h-8 text-sm transition-colors"
            style={{ 
              backgroundColor: activeBrand === 'lavela' ? '#0D4D4D' : 'white',
              borderColor: activeBrand === 'lavela' ? '#D4A57440' : '#e5e7eb',
              color: activeBrand === 'lavela' ? '#FDF8F5' : '#1f2937'
            }}
            data-testid="sidebar-search"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 transition-colors"
              style={{ color: activeBrand === 'lavela' ? '#D4A574' : '#9ca3af' }}
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        {searchQuery && (
          <p 
            className="text-xs mt-1 transition-colors"
            style={{ color: activeBrand === 'lavela' ? '#D4A574' : '#6b7280' }}
          >
            Found {getFilteredItems().reduce((acc, item) => 
              acc + (item.type === 'group' ? (item.children?.length || 0) : 1), 0
            )} items
          </p>
        )}
      </div>

      {/* Edit Mode Controls */}
      {editMode && (
        <div className="px-2 py-2 bg-[#F8A5B8]/10 border-b border-[#F8A5B8]/20 space-y-2">
          <p className="text-xs text-[#5A5A5A] text-center">Drag to reorder • Click icons to edit</p>
          
          {/* Create New Group Button */}
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowNewGroupModal(true)}
            className="w-full h-7 text-xs border-dashed border-[#F8A5B8] text-[#F8A5B8] hover:bg-[#F8A5B8]/10"
            data-testid="create-group-btn"
          >
            <Plus className="w-3 h-3 mr-1" />
            Create New Group
          </Button>
          
          <div className="flex gap-2">
            <Button 
              size="sm" 
              variant="outline" 
              onClick={forceResetAndSave}
              disabled={loading}
              className="flex-1 h-7 text-xs"
              data-testid="sidebar-reset-btn"
              title="Reset sidebar to defaults and clear database"
            >
              {loading ? '...' : 'Reset'}
            </Button>
            <Button 
              size="sm" 
              onClick={saveConfig}
              disabled={!hasChanges || loading}
              className="flex-1 h-7 text-xs bg-[#F8A5B8] hover:bg-[#E88DA0] text-white"
              data-testid="sidebar-save-btn"
            >
              {loading ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      )}

      {/* New Group Modal */}
      {showNewGroupModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-xl p-4 w-80 max-w-[90vw]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold text-gray-800">Create New Group</h3>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowNewGroupModal(false)}
                className="h-6 w-6 p-0"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="text-sm text-gray-600 mb-1 block">Group Name</label>
                <Input
                  placeholder="e.g., Marketing Tools"
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  className="h-9"
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handleCreateGroup()}
                />
              </div>
              
              <div>
                <label className="text-sm text-gray-600 mb-1 block">Icon</label>
                <div className="grid grid-cols-6 gap-1 max-h-32 overflow-y-auto">
                  {AVAILABLE_ICONS.map(iconName => {
                    const IconComponent = ICON_MAP[iconName];
                    return (
                      <button
                        key={iconName}
                        onClick={() => setNewGroupIcon(iconName)}
                        className={cn(
                          "p-2 rounded hover:bg-gray-100 transition-colors",
                          newGroupIcon === iconName && "bg-[#F8A5B8]/20 ring-1 ring-[#F8A5B8]"
                        )}
                        title={iconName}
                      >
                        {IconComponent && <IconComponent className="w-4 h-4 text-gray-600" />}
                      </button>
                    );
                  })}
                </div>
              </div>
              
              <div className="flex gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => setShowNewGroupModal(false)}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreateGroup}
                  className="flex-1 bg-[#F8A5B8] hover:bg-[#E88DA0] text-white"
                >
                  Create Group
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Scrollable Menu */}
      <div className="admin-sidebar-scroll py-2 px-2 flex-1" data-testid="admin-sidebar-nav">
        <DndContext 
          sensors={sensors}
          collisionDetection={(args) => {
            // First check if we're over any droppable (group)
            const pointerCollisions = pointerWithin(args);
            if (pointerCollisions.length > 0) {
              // Prefer droppable groups
              const groupCollision = pointerCollisions.find(collision => {
                const item = menuItems.find(i => i.id === collision.id);
                return item?.type === 'group';
              });
              if (groupCollision) {
                return [groupCollision];
              }
            }
            // Fall back to closest center for regular reordering
            return closestCenter(args);
          }}
          onDragEnd={handleDragEnd}
        >
          <SortableContext items={getFilteredItems().map(i => i.id)} strategy={verticalListSortingStrategy}>
            {getFilteredItems().map((item) => {
              // Render collapsible group
              if (item.type === 'group') {
                return (
                  <CollapsibleGroup
                    key={item.id}
                    item={item}
                    activeSection={activeSection}
                    onClick={setActiveSection}
                    editMode={editMode}
                    onEdit={handleEdit}
                    onToggleVisibility={handleToggleVisibility}
                    onDeleteGroup={handleDeleteGroup}
                    onRemoveFromGroup={handleRemoveFromGroup}
                    editingItem={editingItem}
                    setEditingItem={setEditingItem}
                    tempLabel={tempLabel}
                    setTempLabel={setTempLabel}
                    expandedGroups={expandedGroups}
                    toggleGroup={toggleGroup}
                    allGroups={menuItems.filter(i => i.type === 'group')}
                    onMoveToGroup={handleMoveToGroup}
                    searchQuery={searchQuery}
                    abandonedCount={abandonedCount}
                    pendingWhatsAppCount={pendingWhatsAppCount}
                    colors={colors}
                    getBrandLabel={getBrandLabel}
                  />
                );
              }
              
              // Render regular sortable item
              return (
                <SortableItem
                  key={item.id}
                  item={item}
                  isActive={activeSection === item.section}
                  onClick={setActiveSection}
                  abandonedCount={abandonedCount}
                  editMode={editMode}
                  onEdit={handleEdit}
                  onToggleVisibility={handleToggleVisibility}
                  onDelete={handleDelete}
                  editingItem={editingItem}
                  setEditingItem={setEditingItem}
                  tempLabel={tempLabel}
                  setTempLabel={setTempLabel}
                  allGroups={menuItems.filter(i => i.type === 'group')}
                  onMoveToGroup={handleMoveToGroup}
                  searchQuery={searchQuery}
                  colors={colors}
                />
              );
            })}
          </SortableContext>
        </DndContext>
        
        {/* Extra bottom padding */}
        <div style={{ height: '100px', flexShrink: 0 }}></div>
      </div>
    </div>
  );
};

export default AdminSidebar;
