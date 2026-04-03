import React, { useState, useEffect, useCallback, useRef, Suspense, lazy, memo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import GridLayout from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import {
  DollarSign, Users, ShoppingCart, TrendingUp, TestTube, Sparkles,
  FileText, Eye, Edit2, Check, X, GripVertical, Maximize2, Minimize2,
  Save, RotateCcw, Plus, Trash2, Settings, Lock, Unlock, BarChart3,
  Activity, Crown, Star, Mail, Clock, ArrowUp, ArrowDown, LayoutGrid,
  Loader2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter
} from '../ui/dialog';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator
} from '../ui/dropdown-menu';
import { useAdminBrand } from './useAdminBrand';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// ============ LAZY LOADING COMPONENTS ============
// Widget Loading Skeleton - shown while widget content loads
const WidgetSkeleton = () => (
  <div className="h-full flex flex-col justify-center animate-pulse">
    <div className="h-8 w-24 bg-gray-200 rounded mb-2"></div>
    <div className="h-4 w-32 bg-gray-100 rounded mb-4"></div>
    <div className="space-y-2">
      <div className="h-3 w-full bg-gray-100 rounded"></div>
      <div className="h-3 w-3/4 bg-gray-100 rounded"></div>
    </div>
  </div>
);

// Lazy Widget Wrapper - uses IntersectionObserver for viewport detection
const LazyWidget = memo(({ widgetId, data, onNavigate, getWidgetContent }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          setHasLoaded(true);
          observer.disconnect();
        }
      },
      { rootMargin: '100px', threshold: 0.1 }
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="h-full">
      {hasLoaded ? (
        <Suspense fallback={<WidgetSkeleton />}>
          {getWidgetContent(widgetId, data, onNavigate)}
        </Suspense>
      ) : (
        <WidgetSkeleton />
      )}
    </div>
  );
});

LazyWidget.displayName = 'LazyWidget';

// ============ DEFAULT WIDGET CONFIGURATIONS ============
const DEFAULT_WIDGETS = {
  revenue: {
    id: 'revenue',
    title: 'Revenue / Earnings',
    icon: DollarSign,
    color: 'green',
    minW: 2,
    minH: 2,
    defaultW: 3,
    defaultH: 2,
  },
  quiz_conversions: {
    id: 'quiz_conversions',
    title: 'Quiz Conversions',
    icon: Sparkles,
    color: 'pink',
    minW: 2,
    minH: 2,
    defaultW: 3,
    defaultH: 2,
  },
  bio_age_stats: {
    id: 'bio_age_stats',
    title: 'Bio-Age Scan Stats',
    icon: TestTube,
    color: 'purple',
    minW: 2,
    minH: 2,
    defaultW: 3,
    defaultH: 2,
  },
  recent_blog: {
    id: 'recent_blog',
    title: 'Recent Blog Activity',
    icon: FileText,
    color: 'blue',
    minW: 2,
    minH: 2,
    defaultW: 3,
    defaultH: 2,
  },
  orders: {
    id: 'orders',
    title: 'Recent Orders',
    icon: ShoppingCart,
    color: 'orange',
    minW: 2,
    minH: 2,
    defaultW: 4,
    defaultH: 3,
  },
  partners: {
    id: 'partners',
    title: 'Partner Performance',
    icon: Star,
    color: 'yellow',
    minW: 2,
    minH: 2,
    defaultW: 3,
    defaultH: 2,
  },
  founding_members: {
    id: 'founding_members',
    title: 'Founding Members',
    icon: Crown,
    color: 'amber',
    minW: 2,
    minH: 2,
    defaultW: 3,
    defaultH: 2,
  },
  subscribers: {
    id: 'subscribers',
    title: 'Email Subscribers',
    icon: Mail,
    color: 'indigo',
    minW: 2,
    minH: 2,
    defaultW: 3,
    defaultH: 2,
  },
  quick_actions: {
    id: 'quick_actions',
    title: 'Quick Actions',
    icon: Activity,
    color: 'slate',
    minW: 2,
    minH: 1,
    defaultW: 6,
    defaultH: 1,
  },
};

// Default layout for 12-column grid
const DEFAULT_LAYOUT = [
  { i: 'revenue', x: 0, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
  { i: 'quiz_conversions', x: 3, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
  { i: 'bio_age_stats', x: 6, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
  { i: 'recent_blog', x: 9, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
  { i: 'orders', x: 0, y: 2, w: 6, h: 3, minW: 2, minH: 2 },
  { i: 'partners', x: 6, y: 2, w: 3, h: 2, minW: 2, minH: 2 },
  { i: 'founding_members', x: 9, y: 2, w: 3, h: 2, minW: 2, minH: 2 },
];

// ============ DASHBOARD TEMPLATES ============
const DASHBOARD_TEMPLATES = {
  sales_focus: {
    name: 'Sales Focus',
    description: 'Optimized for tracking revenue, orders, and conversions',
    icon: DollarSign,
    layout: [
      { i: 'revenue', x: 0, y: 0, w: 4, h: 3, minW: 2, minH: 2 },
      { i: 'orders', x: 4, y: 0, w: 8, h: 3, minW: 2, minH: 2 },
      { i: 'founding_members', x: 0, y: 3, w: 4, h: 2, minW: 2, minH: 2 },
      { i: 'partners', x: 4, y: 3, w: 4, h: 2, minW: 2, minH: 2 },
      { i: 'quiz_conversions', x: 8, y: 3, w: 4, h: 2, minW: 2, minH: 2 },
      { i: 'quick_actions', x: 0, y: 5, w: 12, h: 1, minW: 2, minH: 1 },
    ],
    activeWidgets: ['revenue', 'orders', 'founding_members', 'partners', 'quiz_conversions', 'quick_actions'],
  },
  content_focus: {
    name: 'Content Focus',
    description: 'Optimized for tracking content engagement and leads',
    icon: FileText,
    layout: [
      { i: 'recent_blog', x: 0, y: 0, w: 6, h: 3, minW: 2, minH: 2 },
      { i: 'quiz_conversions', x: 6, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
      { i: 'bio_age_stats', x: 9, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
      { i: 'subscribers', x: 6, y: 2, w: 6, h: 2, minW: 2, minH: 2 },
      { i: 'partners', x: 0, y: 3, w: 4, h: 2, minW: 2, minH: 2 },
      { i: 'founding_members', x: 4, y: 3, w: 4, h: 2, minW: 2, minH: 2 },
      { i: 'quick_actions', x: 8, y: 3, w: 4, h: 1, minW: 2, minH: 1 },
    ],
    activeWidgets: ['recent_blog', 'quiz_conversions', 'bio_age_stats', 'subscribers', 'partners', 'founding_members', 'quick_actions'],
  },
};

// ============ WIDGET CONTENT COMPONENTS ============
const RevenueWidget = ({ data }) => (
  <div className="h-full flex flex-col justify-center">
    <div className="text-3xl font-bold text-green-600">${data?.total || '0.00'}</div>
    <p className="text-sm text-gray-500 mt-1">Total Revenue</p>
    <div className="flex items-center gap-2 mt-2">
      {data?.trend > 0 ? (
        <Badge className="bg-green-100 text-green-700 flex items-center gap-1">
          <ArrowUp className="h-3 w-3" /> {data?.trend}%
        </Badge>
      ) : (
        <Badge className="bg-gray-100 text-gray-600">No change</Badge>
      )}
      <span className="text-xs text-gray-400">vs last month</span>
    </div>
    <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
      <div className="bg-green-50 rounded p-2">
        <p className="text-green-700 font-medium">{data?.orders_count || 0}</p>
        <p className="text-green-600 text-xs">Orders</p>
      </div>
      <div className="bg-green-50 rounded p-2">
        <p className="text-green-700 font-medium">${data?.avg_order || '0'}</p>
        <p className="text-green-600 text-xs">Avg Order</p>
      </div>
    </div>
  </div>
);

const QuizConversionsWidget = ({ data }) => (
  <div className="h-full flex flex-col justify-center">
    <div className="text-3xl font-bold text-pink-600">{data?.total || 0}</div>
    <p className="text-sm text-gray-500 mt-1">Quiz Completions</p>
    <div className="mt-3 space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-xs text-gray-500">Conversion Rate</span>
        <span className="text-sm font-medium text-pink-600">{data?.conversion_rate || '0'}%</span>
      </div>
      <div className="w-full bg-pink-100 rounded-full h-2">
        <div 
          className="bg-pink-500 h-2 rounded-full" 
          style={{ width: `${Math.min(data?.conversion_rate || 0, 100)}%` }}
        />
      </div>
    </div>
    <div className="mt-2 text-xs text-gray-500">
      {data?.this_week || 0} this week
    </div>
  </div>
);

const BioAgeStatsWidget = ({ data }) => (
  <div className="h-full flex flex-col justify-center">
    <div className="text-3xl font-bold text-purple-600">{data?.total || 0}</div>
    <p className="text-sm text-gray-500 mt-1">Bio-Age Scans</p>
    <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
      <div className="bg-purple-50 rounded p-2">
        <p className="text-purple-700 font-medium">{data?.emails_captured || 0}</p>
        <p className="text-purple-600 text-xs">Emails Captured</p>
      </div>
      <div className="bg-purple-50 rounded p-2">
        <p className="text-purple-700 font-medium">{data?.this_month || 0}</p>
        <p className="text-purple-600 text-xs">This Month</p>
      </div>
    </div>
  </div>
);

const RecentBlogWidget = ({ data, onNavigate }) => (
  <div className="h-full flex flex-col">
    <div className="text-sm font-medium text-gray-700 mb-2">Recent Posts</div>
    <div className="space-y-2 overflow-y-auto flex-1">
      {(data?.posts || []).slice(0, 3).map((post, idx) => (
        <div key={idx} className="flex items-center gap-2 p-2 bg-blue-50 rounded text-xs">
          <FileText className="h-3 w-3 text-blue-500 flex-shrink-0" />
          <span className="truncate flex-1">{post.title}</span>
          <Badge className="bg-blue-100 text-blue-600 text-xs">{post.views || 0} views</Badge>
        </div>
      ))}
      {(!data?.posts || data.posts.length === 0) && (
        <div className="text-center py-6 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg">
          <FileText className="w-8 h-8 text-blue-300 mx-auto mb-2" />
          <p className="text-sm text-gray-600 font-medium">No Blog Posts Yet</p>
          <p className="text-xs text-gray-400 mt-1 mb-3">Start creating content to boost SEO</p>
          <button 
            onClick={() => onNavigate?.('blog')}
            className="px-3 py-1.5 bg-blue-500 text-white text-xs rounded-full hover:bg-blue-600 transition-colors"
          >
            Create First Post
          </button>
        </div>
      )}
    </div>
    {data?.posts?.length > 0 && (
      <div className="mt-2 pt-2 border-t text-xs text-gray-500">
        {data?.total || 0} total posts
      </div>
    )}
  </div>
);

const OrdersWidget = ({ data }) => (
  <div className="h-full flex flex-col">
    <div className="text-sm font-medium text-gray-700 mb-2">Recent Orders</div>
    <div className="space-y-2 overflow-y-auto flex-1">
      {(data?.orders || []).slice(0, 5).map((order, idx) => (
        <div key={idx} className="flex items-center justify-between p-2 bg-orange-50 rounded text-xs">
          <div className="flex items-center gap-2">
            <ShoppingCart className="h-3 w-3 text-orange-500" />
            <span className="font-medium">#{order.id?.slice(-6) || idx}</span>
          </div>
          <span className="text-orange-700 font-medium">${order.total || '0'}</span>
          <Badge className={`text-xs ${
            order.status === 'completed' ? 'bg-green-100 text-green-700' :
            order.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
            'bg-gray-100 text-gray-600'
          }`}>
            {order.status || 'pending'}
          </Badge>
        </div>
      ))}
      {(!data?.orders || data.orders.length === 0) && (
        <p className="text-xs text-gray-400 text-center py-4">No orders yet</p>
      )}
    </div>
  </div>
);

const PartnersWidget = ({ data, onNavigate }) => (
  <div className="h-full flex flex-col justify-center">
    {data?.total > 0 ? (
      <>
        <div className="text-3xl font-bold text-yellow-600">{data?.total || 0}</div>
        <p className="text-sm text-gray-500 mt-1">Active Partners</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
          <div className="bg-yellow-50 rounded p-2">
            <p className="text-yellow-700 font-medium">{data?.total_sales || 0}</p>
            <p className="text-yellow-600 text-xs">Partner Sales</p>
          </div>
          <div className="bg-yellow-50 rounded p-2">
            <p className="text-yellow-700 font-medium">{data?.pending || 0}</p>
            <p className="text-yellow-600 text-xs">Pending</p>
          </div>
        </div>
      </>
    ) : (
      <div className="text-center py-4 bg-gradient-to-br from-yellow-50 to-amber-50 rounded-lg">
        <Crown className="w-8 h-8 text-yellow-300 mx-auto mb-2" />
        <p className="text-sm text-gray-600 font-medium">No Partners Yet</p>
        <p className="text-xs text-gray-400 mt-1 mb-3">Invite influencers to join your program</p>
        <button 
          onClick={() => onNavigate?.('influencer')}
          className="px-3 py-1.5 bg-yellow-500 text-white text-xs rounded-full hover:bg-yellow-600 transition-colors"
        >
          Manage Partners
        </button>
      </div>
    )}
  </div>
);

const FoundingMembersWidget = ({ data }) => (
  <div className="h-full flex flex-col justify-center">
    <div className="flex items-center gap-2">
      <Crown className="h-6 w-6 text-amber-500" />
      <div className="text-3xl font-bold text-amber-600">{data?.total || 0}</div>
    </div>
    <p className="text-sm text-gray-500 mt-1">Founding Members</p>
    <div className="mt-3 text-sm">
      <div className="flex justify-between">
        <span className="text-gray-500">This Week</span>
        <span className="text-amber-600 font-medium">{data?.this_week || 0}</span>
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-gray-500">Total Referrals</span>
        <span className="text-amber-600 font-medium">{data?.referrals || 0}</span>
      </div>
    </div>
  </div>
);

const SubscribersWidget = ({ data }) => (
  <div className="h-full flex flex-col justify-center">
    <div className="text-3xl font-bold text-indigo-600">{data?.total || 0}</div>
    <p className="text-sm text-gray-500 mt-1">Email Subscribers</p>
    <div className="mt-3 flex items-center gap-2">
      <Mail className="h-4 w-4 text-indigo-400" />
      <span className="text-sm text-indigo-600">{data?.this_month || 0} this month</span>
    </div>
  </div>
);

const QuickActionsWidget = ({ onNavigate }) => (
  <div className="h-full flex items-center gap-3 overflow-x-auto">
    <Button size="sm" variant="outline" onClick={() => onNavigate?.('products')}>
      <Plus className="h-4 w-4 mr-1" /> Add Product
    </Button>
    <Button size="sm" variant="outline" onClick={() => onNavigate?.('blog')}>
      <FileText className="h-4 w-4 mr-1" /> New Blog Post
    </Button>
    <Button size="sm" variant="outline" onClick={() => onNavigate?.('data-hub')}>
      <Users className="h-4 w-4 mr-1" /> View Leads
    </Button>
    <Button size="sm" variant="outline" onClick={() => onNavigate?.('programs')}>
      <Settings className="h-4 w-4 mr-1" /> Programs
    </Button>
  </div>
);

// Widget content renderer
const getWidgetContent = (widgetId, data, onNavigate) => {
  switch (widgetId) {
    case 'revenue':
      return <RevenueWidget data={data?.revenue} />;
    case 'quiz_conversions':
      return <QuizConversionsWidget data={data?.quiz} />;
    case 'bio_age_stats':
      return <BioAgeStatsWidget data={data?.bio_age} />;
    case 'recent_blog':
      return <RecentBlogWidget data={data?.blog} />;
    case 'orders':
      return <OrdersWidget data={data?.orders} />;
    case 'partners':
      return <PartnersWidget data={data?.partners} />;
    case 'founding_members':
      return <FoundingMembersWidget data={data?.founding} />;
    case 'subscribers':
      return <SubscribersWidget data={data?.subscribers} />;
    case 'quick_actions':
      return <QuickActionsWidget onNavigate={onNavigate} />;
    default:
      return <div className="text-gray-400 text-sm">Unknown widget</div>;
  }
};

// ============ MAIN CUSTOMIZABLE DASHBOARD ============
const CustomizableDashboard = ({ onNavigate }) => {
  const { activeBrand } = useAdminBrand();
  const [layout, setLayout] = useState(DEFAULT_LAYOUT);
  const [activeWidgets, setActiveWidgets] = useState([
    'revenue', 'quiz_conversions', 'bio_age_stats', 'recent_blog', 
    'orders', 'partners', 'founding_members'
  ]);
  const [widgetTitles, setWidgetTitles] = useState({});
  const [isLocked, setIsLocked] = useState(false);
  const [editingTitle, setEditingTitle] = useState(null);
  const [tempTitle, setTempTitle] = useState('');
  const [showAddWidget, setShowAddWidget] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dashboardData, setDashboardData] = useState({});
  const [hasChanges, setHasChanges] = useState(false);
  const [containerWidth, setContainerWidth] = useState(1200);

  const token = localStorage.getItem('reroots_token');
  const headers = { Authorization: `Bearer ${token}` };

  // Measure container width
  useEffect(() => {
    const updateWidth = () => {
      const container = document.querySelector('.dashboard-container');
      if (container) {
        setContainerWidth(container.offsetWidth);
      }
    };
    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  // Load saved layout from database
  const loadLayout = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/api/admin/dashboard-layout`, { headers });
      if (res.data?.layout) {
        setLayout(res.data.layout.layout || DEFAULT_LAYOUT);
        setActiveWidgets(res.data.layout.activeWidgets || activeWidgets);
        setWidgetTitles(res.data.layout.widgetTitles || {});
        setIsLocked(res.data.layout.isLocked || false);
      }
    } catch (error) {
      console.log('Using default layout');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load dashboard data
  const loadDashboardData = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/api/admin/dashboard-stats?brand=${activeBrand}`, { headers });
      setDashboardData(res.data || {});
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    }
  }, [activeBrand]);

  useEffect(() => {
    loadLayout();
    loadDashboardData();
    // Refresh data every 30 seconds
    const interval = setInterval(loadDashboardData, 30000);
    return () => clearInterval(interval);
  }, [loadLayout, loadDashboardData, activeBrand]);

  // Save layout to database
  const saveLayout = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/api/admin/dashboard-layout`, {
        layout,
        activeWidgets,
        widgetTitles,
        isLocked
      }, { headers });
      toast.success('Dashboard layout saved!');
      setHasChanges(false);
    } catch (error) {
      toast.error('Failed to save layout');
    } finally {
      setSaving(false);
    }
  };

  // Reset to default layout
  const resetLayout = async () => {
    setLayout(DEFAULT_LAYOUT);
    setActiveWidgets(['revenue', 'quiz_conversions', 'bio_age_stats', 'recent_blog', 'orders', 'partners', 'founding_members']);
    setWidgetTitles({});
    setHasChanges(true);
    toast.info('Layout reset to default');
  };

  // Handle layout change
  const onLayoutChange = (newLayout) => {
    if (!isLocked) {
      setLayout(newLayout);
      setHasChanges(true);
    }
  };

  // Start editing title
  const startEditTitle = (widgetId) => {
    setEditingTitle(widgetId);
    setTempTitle(widgetTitles[widgetId] || DEFAULT_WIDGETS[widgetId]?.title || 'Widget');
  };

  // Save edited title
  const saveTitle = () => {
    if (editingTitle && tempTitle.trim()) {
      setWidgetTitles({ ...widgetTitles, [editingTitle]: tempTitle.trim() });
      setHasChanges(true);
    }
    setEditingTitle(null);
    setTempTitle('');
  };

  // Cancel editing
  const cancelEdit = () => {
    setEditingTitle(null);
    setTempTitle('');
  };

  // Add widget
  const addWidget = (widgetId) => {
    if (!activeWidgets.includes(widgetId)) {
      setActiveWidgets([...activeWidgets, widgetId]);
      // Add to layout
      const config = DEFAULT_WIDGETS[widgetId];
      const maxY = Math.max(0, ...layout.map(l => l.y + l.h));
      setLayout([...layout, {
        i: widgetId,
        x: 0,
        y: maxY,
        w: config.defaultW,
        h: config.defaultH,
        minW: config.minW,
        minH: config.minH,
      }]);
      setHasChanges(true);
    }
    setShowAddWidget(false);
  };

  // Remove widget
  const removeWidget = (widgetId) => {
    setActiveWidgets(activeWidgets.filter(w => w !== widgetId));
    setLayout(layout.filter(l => l.i !== widgetId));
    setHasChanges(true);
    toast.info('Widget removed');
  };

  // Get widget title
  const getWidgetTitle = (widgetId) => {
    return widgetTitles[widgetId] || DEFAULT_WIDGETS[widgetId]?.title || 'Widget';
  };

  // Apply template
  const applyTemplate = (templateKey) => {
    const template = DASHBOARD_TEMPLATES[templateKey];
    if (template) {
      setLayout(template.layout);
      setActiveWidgets(template.activeWidgets);
      setWidgetTitles({});
      setHasChanges(true);
      toast.success(`Applied "${template.name}" template`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pink-500"></div>
      </div>
    );
  }

  const availableWidgets = Object.keys(DEFAULT_WIDGETS).filter(w => !activeWidgets.includes(w));

  return (
    <div className="space-y-4">
      {/* Dashboard Controls */}
      <div className="flex items-center justify-between bg-white rounded-lg p-4 shadow-sm border">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold text-[#2D2A2E]">Dashboard</h2>
          <Badge className={isLocked ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}>
            {isLocked ? <Lock className="h-3 w-3 mr-1" /> : <Unlock className="h-3 w-3 mr-1" />}
            {isLocked ? 'Locked' : 'Editable'}
          </Badge>
          {hasChanges && (
            <Badge className="bg-yellow-100 text-yellow-700 animate-pulse">
              Unsaved changes
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              const newLockedState = !isLocked;
              setIsLocked(newLockedState);
              // Auto-save when locking to persist the state
              setSaving(true);
              try {
                await axios.put(`${API}/api/admin/dashboard-layout`, {
                  layout,
                  activeWidgets,
                  widgetTitles,
                  isLocked: newLockedState
                }, { headers });
                toast.success(newLockedState ? 'Dashboard locked!' : 'Dashboard unlocked!');
                setHasChanges(false);
              } catch (error) {
                toast.error('Failed to save lock state');
                setIsLocked(!newLockedState); // Revert on error
              } finally {
                setSaving(false);
              }
            }}
            disabled={saving}
          >
            {isLocked ? <Unlock className="h-4 w-4 mr-1" /> : <Lock className="h-4 w-4 mr-1" />}
            {isLocked ? 'Unlock' : 'Lock'}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" disabled={isLocked}>
                <LayoutGrid className="h-4 w-4 mr-1" />
                Templates
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              <div className="px-2 py-1.5 text-xs font-medium text-gray-500">
                Quick Layout Templates
              </div>
              <DropdownMenuSeparator />
              {Object.entries(DASHBOARD_TEMPLATES).map(([key, template]) => {
                const Icon = template.icon;
                return (
                  <DropdownMenuItem 
                    key={key} 
                    onClick={() => applyTemplate(key)}
                    className="flex items-start gap-3 py-2"
                  >
                    <div className="p-1.5 rounded bg-gray-100">
                      <Icon className="h-4 w-4 text-gray-600" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-sm">{template.name}</p>
                      <p className="text-xs text-gray-500">{template.description}</p>
                    </div>
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAddWidget(true)}
            disabled={isLocked || availableWidgets.length === 0}
          >
            <Plus className="h-4 w-4 mr-1" />
            Add Widget
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={resetLayout}
            disabled={isLocked}
          >
            <RotateCcw className="h-4 w-4 mr-1" />
            Reset
          </Button>
          <Button
            size="sm"
            onClick={saveLayout}
            disabled={!hasChanges || saving}
            className="bg-pink-500 hover:bg-pink-600 text-white"
          >
            {saving ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-1" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save Layout
          </Button>
        </div>
      </div>

      {/* Help Text */}
      {!isLocked && (
        <div className="bg-blue-50 text-blue-700 text-sm p-3 rounded-lg flex items-center gap-2">
          <GripVertical className="h-4 w-4" />
          Drag widgets to rearrange • Drag corners to resize • Click settings icon to rename/remove
        </div>
      )}

      {/* Grid Layout */}
      <div className="dashboard-container">
        <GridLayout
          className="layout"
          layout={layout}
          cols={12}
          rowHeight={80}
          width={containerWidth}
          onLayoutChange={onLayoutChange}
          isDraggable={!isLocked}
          isResizable={!isLocked}
          draggableHandle=".drag-handle"
          margin={[16, 16]}
        >
          {activeWidgets.map(widgetId => {
            const config = DEFAULT_WIDGETS[widgetId];
            const Icon = config?.icon || Settings;
            const colorClass = config?.color || 'gray';
            
            return (
              <div key={widgetId} className="widget-container admin-card">
                <Card className="h-full overflow-hidden shadow-sm hover:shadow-md transition-shadow admin-hover-optimized">
                  <CardHeader className="p-3 pb-2 border-b bg-gray-50/50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 flex-1">
                        {!isLocked && (
                          <div className="drag-handle cursor-move p-1 hover:bg-gray-200 rounded">
                            <GripVertical className="h-4 w-4 text-gray-400" />
                          </div>
                        )}
                        <div className={`p-1.5 rounded bg-${colorClass}-100`}>
                          <Icon className={`h-4 w-4 text-${colorClass}-600`} />
                        </div>
                        
                        {editingTitle === widgetId ? (
                          <div className="flex items-center gap-1 flex-1">
                            <Input
                              value={tempTitle}
                              onChange={(e) => setTempTitle(e.target.value)}
                              className="h-7 text-sm"
                              autoFocus
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') saveTitle();
                                if (e.key === 'Escape') cancelEdit();
                              }}
                            />
                            <button onClick={saveTitle} className="p-1 hover:bg-green-100 rounded">
                              <Check className="h-4 w-4 text-green-600" />
                            </button>
                            <button onClick={cancelEdit} className="p-1 hover:bg-red-100 rounded">
                              <X className="h-4 w-4 text-red-600" />
                            </button>
                          </div>
                        ) : (
                          <CardTitle className="text-sm font-medium text-[#2D2A2E] flex-1">
                            {getWidgetTitle(widgetId)}
                          </CardTitle>
                        )}
                      </div>
                      
                      {!isLocked && editingTitle !== widgetId && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="p-1 hover:bg-gray-200 rounded">
                              <Settings className="h-4 w-4 text-gray-400" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => startEditTitle(widgetId)}>
                              <Edit2 className="h-4 w-4 mr-2" />
                              Rename
                            </DropdownMenuItem>
                            <DropdownMenuItem 
                              onClick={() => removeWidget(widgetId)}
                              className="text-red-600"
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Remove
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="p-3 h-[calc(100%-52px)] overflow-auto">
                    <LazyWidget
                      widgetId={widgetId}
                      data={dashboardData}
                      onNavigate={onNavigate}
                      getWidgetContent={getWidgetContent}
                    />
                  </CardContent>
                </Card>
              </div>
            );
          })}
        </GridLayout>
      </div>

      {/* Add Widget Dialog */}
      <Dialog open={showAddWidget} onOpenChange={setShowAddWidget}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Widget</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3 py-4">
            {availableWidgets.map(widgetId => {
              const config = DEFAULT_WIDGETS[widgetId];
              const Icon = config?.icon || Settings;
              return (
                <button
                  key={widgetId}
                  onClick={() => addWidget(widgetId)}
                  className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 transition-colors text-left"
                >
                  <div className={`p-2 rounded bg-${config?.color || 'gray'}-100`}>
                    <Icon className={`h-5 w-5 text-${config?.color || 'gray'}-600`} />
                  </div>
                  <span className="font-medium text-sm">{config?.title}</span>
                </button>
              );
            })}
            {availableWidgets.length === 0 && (
              <p className="col-span-2 text-center text-gray-500 py-4">
                All widgets are already on your dashboard
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CustomizableDashboard;
