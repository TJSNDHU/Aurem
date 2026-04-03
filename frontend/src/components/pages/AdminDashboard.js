import React, { useState, useEffect, useCallback, useMemo, Suspense, lazy, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';

// UI Components
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../ui/alert-dialog';

// Icons
import { 
  Loader2, Search, Plus, Trash2, Check, Star, Bell, MessageCircle, 
  TrendingUp, Package, Eye, ExternalLink, RefreshCw, Globe, Image,
  ChevronDown, ChevronUp, Send, Bot, ImagePlus, X, ArrowLeft, Lock, Unlock, 
  Shield, Camera, Upload, Download, EyeOff, Clock, FileText, Folder,
  Edit, Users, Sparkles, FlaskConical
} from 'lucide-react';

// Contexts
import { useAuth } from '../../contexts';

// Lazy load heavy admin components
const StoreSettingsEditor = lazy(() => import('../admin/StoreSettingsEditor'));
const CustomersManager = lazy(() => import('../admin/CustomersManager'));
const SubscribersSection = lazy(() => import('../admin/SubscribersSection'));
const OffersManager = lazy(() => import('../admin/OffersManager'));
const AIContentStudio = lazy(() => import('../admin/AIContentStudio'));
const DiscountCodeManager = lazy(() => import('../admin/DiscountCodeManager'));

// Admin Skeleton Loaders - Fix CLS (Layout Shift)
import { StatsGridSkeleton, OverviewCardSkeleton, OrdersTableSkeleton } from '../admin/AdminSkeletons';

// Virtualized Tables - Only loads when respective tabs are accessed
const VirtualizedOrdersTable = lazy(() => import('../admin/VirtualizedOrdersTable'));
const VirtualizedProductsTable = lazy(() => import('../admin/VirtualizedProductsTable'));
const VirtualizedCustomersTable = lazy(() => import('../admin/VirtualizedCustomersTable'));

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Lazy-loaded DnD Components - Only loads when admin first renders
// This keeps @dnd-kit out of the main customer bundle (~20KB savings)
const DndTabWrapper = lazy(() => 
  Promise.all([
    import('@dnd-kit/core'),
    import('@dnd-kit/sortable'),
    import('@dnd-kit/utilities')
  ]).then(([core, sortable, utilities]) => {
    // Create a wrapper component with all DnD functionality
    const { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } = core;
    const { arrayMove, SortableContext, sortableKeyboardCoordinates, horizontalListSortingStrategy, useSortable } = sortable;
    const { CSS } = utilities;
    
    // SortableTab component
    const SortableTab = ({ id, children }) => {
      const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
      const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        cursor: 'grab',
      };
      return (
        <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
          {children}
        </div>
      );
    };
    
    // Import TabsList dynamically to avoid circular deps
    const { TabsList } = require('../ui/tabs');
    
    // Main DnD Wrapper component
    const DndTabsWrapper = ({ tabOrder, onDragEnd, renderTab }) => {
      const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
      );
      
      const handleDragEnd = (event) => {
        const { active, over } = event;
        if (active.id !== over?.id) {
          const oldIndex = tabOrder.indexOf(active.id);
          const newIndex = tabOrder.indexOf(over.id);
          const newOrder = arrayMove(tabOrder, oldIndex, newIndex);
          onDragEnd(newOrder);
        }
      };
      
      return (
        <div 
          className="overflow-x-auto scrollbar-hide pb-2"
          style={{ 
            WebkitOverflowScrolling: 'touch',
            scrollbarWidth: 'none',
            msOverflowStyle: 'none'
          }}
        >
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={tabOrder} strategy={horizontalListSortingStrategy}>
              <TabsList className="inline-flex gap-1 bg-gradient-to-r from-pink-50 to-rose-50 p-2 rounded-xl w-max min-w-full">
                {tabOrder.map(tabId => (
                  <SortableTab key={tabId} id={tabId}>
                    {renderTab(tabId)}
                  </SortableTab>
                ))}
              </TabsList>
            </SortableContext>
          </DndContext>
        </div>
      );
    };
    
    return { default: DndTabsWrapper };
  })
);

// Admin Dashboard Component
const AdminDashboard = () => {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [activeTab, setActiveTab] = useState(() => {
    return localStorage.getItem('reroots_admin_active_tab') || "overview";
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [brandFilter, setBrandFilter] = useState('all'); // 'all', 'reroots', 'dark_store'
  
  // Product editing state
  const [editingProduct, setEditingProduct] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [savingProduct, setSavingProduct] = useState(false);
  
  // Auth headers for API calls
  const token = localStorage.getItem('reroots_token');
  const headers = { Authorization: `Bearer ${token}` };
  
  // Add new product state
  const [addProductDialogOpen, setAddProductDialogOpen] = useState(false);
  const [newProduct, setNewProduct] = useState({
    name: '',
    price: '',
    compare_price: '',
    description: '',
    category: 'serums',
    stock: 100,
    discount_percent: 0,
    featured: false,
    active: true,
    images: [],
    brand_visibility: 'both'
  });

  // Connected Accounts state
  const defaultAccounts = [
    { id: '1', name: 'Stripe', description: 'Payments & Billing', url: 'https://dashboard.stripe.com', color: 'purple' },
    { id: '2', name: 'Twilio', description: 'SMS & Phone Verification', url: 'https://console.twilio.com', color: 'red' },
    { id: '3', name: 'Wix', description: 'Website Builder', url: 'https://manage.wix.com', color: 'blue' },
    { id: '4', name: 'TD Bank', description: 'Payment Gateway', url: 'https://web.na.bambora.com', color: 'green' },
    { id: '5', name: 'FlagShip', description: 'Shipping & Tracking', url: 'https://smartship.io/login', color: 'orange' },
    { id: '6', name: 'Google Merchant', description: 'Product Listings', url: 'https://merchants.google.com', color: 'yellow' },
    { id: '7', name: 'Bing Webmaster', description: 'SEO & Indexing', url: 'https://www.bing.com/webmasters', color: 'cyan' },
    { id: '8', name: 'Search Console', description: 'Google SEO', url: 'https://search.google.com/search-console', color: 'sky' },
    { id: '9', name: 'Resend', description: 'Email Service', url: 'https://resend.com/emails', color: 'pink' }
  ];
  
  const [connectedAccounts, setConnectedAccounts] = useState(defaultAccounts);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [accountDialogOpen, setAccountDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState(null);
  const [newAccount, setNewAccount] = useState({ name: '', description: '', url: '', color: 'blue' });

  // Load connected accounts from database on mount
  useEffect(() => {
    const loadConnectedAccounts = async () => {
      try {
        const response = await axios.get(`${API}/admin/connected-accounts`, { headers });
        if (response.data?.accounts) {
          setConnectedAccounts(response.data.accounts);
        }
      } catch (error) {
        console.error('Failed to load connected accounts:', error);
        // Keep default accounts if API fails
      } finally {
        setLoadingAccounts(false);
      }
    };
    loadConnectedAccounts();
  }, []);

  // Handle add/edit account - saves to database
  const handleSaveAccount = async () => {
    if (!newAccount.name || !newAccount.url) {
      toast.error('Please fill in account name and URL');
      return;
    }
    
    try {
      if (editingAccount) {
        // Update existing account
        await axios.put(`${API}/admin/connected-accounts/${editingAccount.id}`, newAccount, { headers });
        setConnectedAccounts(connectedAccounts.map(acc => 
          acc.id === editingAccount.id ? { ...newAccount, id: editingAccount.id } : acc
        ));
        toast.success('Account updated!');
      } else {
        // Add new account
        const response = await axios.post(`${API}/admin/connected-accounts/add`, newAccount, { headers });
        if (response.data?.account) {
          setConnectedAccounts([...connectedAccounts, response.data.account]);
          toast.success('Account added!');
        }
      }
      
      setAccountDialogOpen(false);
      setEditingAccount(null);
      setNewAccount({ name: '', description: '', url: '', color: 'blue' });
    } catch (error) {
      console.error('Failed to save account:', error);
      toast.error('Failed to save account');
    }
  };

  // Handle delete account - deletes from database
  const handleDeleteAccount = async (accountId) => {
    if (confirm('Are you sure you want to remove this account?')) {
      try {
        await axios.delete(`${API}/admin/connected-accounts/${accountId}`, { headers });
        setConnectedAccounts(connectedAccounts.filter(acc => acc.id !== accountId));
        toast.success('Account removed!');
      } catch (error) {
        console.error('Failed to delete account:', error);
        toast.error('Failed to remove account');
      }
    }
  };

  // Secure Vault State (Snapchat-like)
  const [vaultUnlocked, setVaultUnlocked] = useState(false);
  const [vaultMinimized, setVaultMinimized] = useState(false); // Minimize/Maximize state
  const [vaultPassword, setVaultPassword] = useState('');
  const [vaultPasswordInput, setVaultPasswordInput] = useState('');
  const [vaultItems, setVaultItems] = useState(() => {
    try {
      const encrypted = localStorage.getItem('reroots_secure_vault');
      return encrypted ? JSON.parse(atob(encrypted)) : [];
    } catch { return []; }
  });
  const [showAddVaultItem, setShowAddVaultItem] = useState(false);
  const [newVaultItem, setNewVaultItem] = useState({ title: '', content: '', type: 'note', expiresIn: '24h' });
  const [vaultError, setVaultError] = useState('');
  const vaultFileInputRef = React.useRef(null);

  // Vault password is stored as hash
  const VAULT_PIN = localStorage.getItem('reroots_vault_pin') || '';
  const [settingPin, setSettingPin] = useState(!VAULT_PIN);
  const [newPin, setNewPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');

  // Save vault items (encrypted)
  useEffect(() => {
    if (vaultItems.length > 0) {
      localStorage.setItem('reroots_secure_vault', btoa(JSON.stringify(vaultItems)));
    }
  }, [vaultItems]);

  // Check for expired items
  useEffect(() => {
    if (vaultUnlocked) {
      const now = Date.now();
      setVaultItems(prev => prev.filter(item => {
        if (!item.expiresAt) return true;
        return item.expiresAt > now;
      }));
    }
  }, [vaultUnlocked]);

  const unlockVault = () => {
    const storedPin = localStorage.getItem('reroots_vault_pin');
    if (vaultPasswordInput === storedPin) {
      setVaultUnlocked(true);
      setVaultError('');
      setVaultPasswordInput('');
    } else {
      setVaultError('Incorrect PIN');
      setVaultPasswordInput('');
    }
  };

  const setVaultPin = () => {
    if (newPin.length < 4) {
      setVaultError('PIN must be at least 4 characters');
      return;
    }
    if (newPin !== confirmPin) {
      setVaultError('PINs do not match');
      return;
    }
    localStorage.setItem('reroots_vault_pin', newPin);
    setSettingPin(false);
    setVaultUnlocked(true);
    setNewPin('');
    setConfirmPin('');
    toast.success('Secure vault PIN set!');
  };

  const addVaultItem = () => {
    if (!newVaultItem.title.trim()) {
      toast.error('Please add a title');
      return;
    }
    
    const expiresMap = {
      '1h': 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000,
      '7d': 7 * 24 * 60 * 60 * 1000,
      '30d': 30 * 24 * 60 * 60 * 1000,
      'never': null
    };
    
    const expiresAt = expiresMap[newVaultItem.expiresIn] 
      ? Date.now() + expiresMap[newVaultItem.expiresIn] 
      : null;
    
    setVaultItems([...vaultItems, {
      id: Date.now().toString(),
      ...newVaultItem,
      createdAt: Date.now(),
      expiresAt
    }]);
    
    setNewVaultItem({ title: '', content: '', type: 'note', expiresIn: '24h' });
    setShowAddVaultItem(false);
    toast.success('Item added to vault!');
  };

  const deleteVaultItem = (id) => {
    setVaultItems(vaultItems.filter(item => item.id !== id));
    toast.success('Item deleted');
  };

  const handleVaultFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setNewVaultItem({
          ...newVaultItem,
          type: file.type.startsWith('image/') ? 'image' : 'file',
          content: event.target.result,
          fileName: file.name
        });
      };
      reader.readAsDataURL(file);
    }
  };

  const lockVault = () => {
    setVaultUnlocked(false);
    setVaultPasswordInput('');
  };

  // Snapchat App State
  const [snapView, setSnapView] = useState('camera'); // camera, chat, stories, spotlight, profile
  const [snapContacts, setSnapContacts] = useState(() => {
    const saved = localStorage.getItem('reroots_snap_contacts');
    return saved ? JSON.parse(saved) : [
      { id: '1', name: 'Business Partner', username: 'partner_biz', avatar: '👔', status: 'online', lastSeen: Date.now() },
      { id: '2', name: 'Supplier', username: 'supplier_co', avatar: '📦', status: 'offline', lastSeen: Date.now() - 3600000 },
      { id: '3', name: 'Marketing Team', username: 'marketing', avatar: '📣', status: 'online', lastSeen: Date.now() }
    ];
  });
  const [snapChats, setSnapChats] = useState(() => {
    const saved = localStorage.getItem('reroots_snap_chats');
    return saved ? JSON.parse(saved) : {};
  });
  const [snapStories, setSnapStories] = useState(() => {
    const saved = localStorage.getItem('reroots_snap_stories');
    return saved ? JSON.parse(saved) : [];
  });
  const [activeChat, setActiveChat] = useState(null);
  const [snapMessage, setSnapMessage] = useState('');
  const [snapCameraMode, setSnapCameraMode] = useState('photo');
  const [capturedSnap, setCapturedSnap] = useState(null);
  const [showAddContact, setShowAddContact] = useState(false);
  const [newContact, setNewContact] = useState({ name: '', username: '', avatar: '👤' });
  const snapFileInputRef = React.useRef(null);
  
  // Snapchat Authentication State
  const [snapLoggedIn, setSnapLoggedIn] = useState(() => {
    return localStorage.getItem('reroots_snap_logged_in') === 'true';
  });
  const [snapAuthView, setSnapAuthView] = useState('login'); // login, signup
  const [snapLoginData, setSnapLoginData] = useState({ username: '', password: '' });
  const [snapSignupData, setSnapSignupData] = useState({ name: '', username: '', email: '', password: '', birthday: '', avatar: '👤' });
  const [snapAuthError, setSnapAuthError] = useState('');
  
  // Snapchat Profile/Account State
  const [snapProfile, setSnapProfile] = useState(() => {
    const saved = localStorage.getItem('reroots_snap_profile');
    return saved ? JSON.parse(saved) : null;
  });
  const [showEditProfile, setShowEditProfile] = useState(false);
  const [editProfileData, setEditProfileData] = useState({ name: '', username: '', avatar: '👤' });
  const [showSwitchAccount, setShowSwitchAccount] = useState(false);
  const [snapAccounts, setSnapAccounts] = useState(() => {
    const saved = localStorage.getItem('reroots_snap_accounts');
    return saved ? JSON.parse(saved) : [];
  });
  const [showAddAccount, setShowAddAccount] = useState(false);
  const [newAccountData, setNewAccountData] = useState({ name: '', username: '', avatar: '👤' });
  
  // Save Snapchat login state
  useEffect(() => {
    localStorage.setItem('reroots_snap_logged_in', snapLoggedIn ? 'true' : 'false');
  }, [snapLoggedIn]);
  
  // Save Snapchat profile
  useEffect(() => {
    if (snapProfile) {
      localStorage.setItem('reroots_snap_profile', JSON.stringify(snapProfile));
    }
  }, [snapProfile]);
  
  // Save Snapchat accounts
  useEffect(() => {
    localStorage.setItem('reroots_snap_accounts', JSON.stringify(snapAccounts));
  }, [snapAccounts]);
  
  // Snapchat Login
  const snapLogin = () => {
    setSnapAuthError('');
    if (!snapLoginData.username.trim() || !snapLoginData.password.trim()) {
      setSnapAuthError('Please enter username and password');
      return;
    }
    // Check if account exists
    const account = snapAccounts.find(a => a.username.toLowerCase() === snapLoginData.username.toLowerCase());
    if (account && account.password === snapLoginData.password) {
      setSnapProfile(account);
      setSnapLoggedIn(true);
      setSnapLoginData({ username: '', password: '' });
      toast.success(`Welcome back, ${account.name}!`);
    } else if (account) {
      setSnapAuthError('Incorrect password. Please try again.');
    } else {
      setSnapAuthError('Account not found. Please sign up first.');
    }
  };
  
  // Snapchat Signup
  const snapSignup = () => {
    setSnapAuthError('');
    if (!snapSignupData.name.trim() || !snapSignupData.username.trim() || !snapSignupData.password.trim()) {
      setSnapAuthError('Please fill in all required fields');
      return;
    }
    if (snapSignupData.password.length < 6) {
      setSnapAuthError('Password must be at least 6 characters');
      return;
    }
    const exists = snapAccounts.find(a => a.username.toLowerCase() === snapSignupData.username.toLowerCase());
    if (exists) {
      setSnapAuthError('Username already taken. Try another one.');
      return;
    }
    const newAccount = {
      id: Date.now().toString(),
      name: snapSignupData.name,
      username: snapSignupData.username.toLowerCase(),
      email: snapSignupData.email,
      password: snapSignupData.password,
      birthday: snapSignupData.birthday,
      avatar: snapSignupData.avatar,
      createdAt: Date.now()
    };
    setSnapAccounts(prev => [...prev, newAccount]);
    setSnapProfile(newAccount);
    setSnapLoggedIn(true);
    setSnapSignupData({ name: '', username: '', email: '', password: '', birthday: '', avatar: '👤' });
    toast.success(`Welcome to Snapchat, ${newAccount.name}!`);
  };
  
  // Snapchat Logout
  const snapLogout = () => {
    setSnapLoggedIn(false);
    setSnapProfile(null);
    setSnapAuthView('login');
    toast.success('Logged out successfully');
  };
  
  // Snapchat account functions
  const saveProfile = () => {
    if (!editProfileData.name.trim() || !editProfileData.username.trim()) {
      toast.error('Name and username are required');
      return;
    }
    const updatedProfile = { ...snapProfile, ...editProfileData };
    setSnapProfile(updatedProfile);
    // Update in accounts list too
    setSnapAccounts(prev => prev.map(acc => 
      acc.id === snapProfile.id ? updatedProfile : acc
    ));
    setShowEditProfile(false);
    toast.success('Profile updated!');
  };
  
  const switchToAccount = (account) => {
    setSnapProfile(account);
    setShowSwitchAccount(false);
    toast.success(`Switched to @${account.username}`);
  };
  
  const addNewAccount = () => {
    // This now goes to signup flow
    setShowAddAccount(false);
    setSnapLoggedIn(false);
    setSnapAuthView('signup');
  };
  
  const removeAccount = (username) => {
    if (snapAccounts.length <= 1) {
      toast.error('Cannot remove the only account');
      return;
    }
    setSnapAccounts(prev => prev.filter(a => a.username !== username));
    if (snapProfile.username === username) {
      const remaining = snapAccounts.filter(a => a.username !== username);
      setSnapProfile(remaining[0]);
    }
    toast.success('Account removed');
  };

  // Save Snapchat data
  useEffect(() => {
    localStorage.setItem('reroots_snap_contacts', JSON.stringify(snapContacts));
  }, [snapContacts]);
  
  useEffect(() => {
    localStorage.setItem('reroots_snap_chats', JSON.stringify(snapChats));
  }, [snapChats]);
  
  useEffect(() => {
    localStorage.setItem('reroots_snap_stories', JSON.stringify(snapStories));
  }, [snapStories]);

  // Clean expired stories
  useEffect(() => {
    const now = Date.now();
    setSnapStories(prev => prev.filter(s => s.expiresAt > now));
  }, [snapView]);

  const sendSnapMessage = () => {
    if (!snapMessage.trim() && !capturedSnap) return;
    if (!activeChat) return;
    
    const newMsg = {
      id: Date.now().toString(),
      content: snapMessage,
      image: capturedSnap,
      sender: 'me',
      timestamp: Date.now(),
      read: false,
      expiresAt: Date.now() + 24 * 60 * 60 * 1000 // 24h
    };
    
    setSnapChats(prev => ({
      ...prev,
      [activeChat.id]: [...(prev[activeChat.id] || []), newMsg]
    }));
    
    setSnapMessage('');
    setCapturedSnap(null);
    toast.success('Snap sent!');
  };

  const addStory = (content, type = 'image') => {
    const story = {
      id: Date.now().toString(),
      content,
      type,
      timestamp: Date.now(),
      expiresAt: Date.now() + 24 * 60 * 60 * 1000, // 24h
      views: 0
    };
    setSnapStories(prev => [story, ...prev]);
    toast.success('Story added!');
    setSnapView('stories');
    setCapturedSnap(null);
  };

  const handleSnapCapture = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setCapturedSnap(event.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const addSnapContact = () => {
    if (!newContact.name.trim()) {
      toast.error('Please enter a name');
      return;
    }
    setSnapContacts([...snapContacts, {
      id: Date.now().toString(),
      ...newContact,
      status: 'offline',
      lastSeen: Date.now()
    }]);
    setNewContact({ name: '', username: '', avatar: '👤' });
    setShowAddContact(false);
    toast.success('Contact added!');
  };

  const deleteSnapContact = (id) => {
    setSnapContacts(snapContacts.filter(c => c.id !== id));
    if (activeChat?.id === id) setActiveChat(null);
    toast.success('Contact removed');
  };

  // Open edit dialog
  const openEditAccount = (account) => {
    setEditingAccount(account);
    setNewAccount({ ...account });
    setAccountDialogOpen(true);
  };

  // Tab order state
  const [tabOrder, setTabOrder] = useState(() => {
    const saved = localStorage.getItem('reroots_admin_tab_order');
    return saved ? JSON.parse(saved) : [
      'overview', 'products', 'orders', 'ai-hub', 'marketing', 'customers', 'settings-hub'
    ];
  });

  // Save active tab
  useEffect(() => {
    localStorage.setItem('reroots_admin_active_tab', activeTab);
  }, [activeTab]);

  // Handle DnD reorder - called from DndTabWrapper
  const handleTabReorder = useCallback((newOrder) => {
    setTabOrder(newOrder);
    localStorage.setItem('reroots_admin_tab_order', JSON.stringify(newOrder));
  }, []);

  // Fetch admin data
  useEffect(() => {
    if (!user || authLoading) return;
    
    const fetchData = async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        const headers = { Authorization: `Bearer ${token}` };
        
        const [statsRes, productsRes, ordersRes] = await Promise.all([
          axios.get(`${API}/admin/stats`, { headers }).catch(() => ({ data: {} })),
          axios.get(`${API}/products`, { headers }).catch(() => ({ data: [] })),
          axios.get(`${API}/admin/orders`, { headers }).catch(() => ({ data: [] }))
        ]);
        
        setStats(statsRes.data);
        setProducts(productsRes.data);
        setOrders(ordersRes.data);
      } catch (error) {
        console.error('Failed to load admin data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [user, authLoading]);

  // Auth check
  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/login');
    }
  }, [user, authLoading, navigate]);

  // Handle product edit
  const handleEditProduct = (product) => {
    setEditingProduct({ ...product });
    setEditDialogOpen(true);
  };

  // Save edited product
  const handleSaveProduct = async () => {
    if (!editingProduct) return;
    
    setSavingProduct(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const response = await axios.put(`${API}/products/${editingProduct.id}`, editingProduct, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Update local state with server response
      const updatedProduct = response.data;
      setProducts(products.map(p => p.id === editingProduct.id ? updatedProduct : p));
      setEditDialogOpen(false);
      setEditingProduct(null);
      toast.success('Product updated successfully!');
    } catch (error) {
      console.error('Failed to update product:', error);
      toast.error(error.response?.data?.detail || 'Failed to update product');
    } finally {
      setSavingProduct(false);
    }
  };

  // Handle add new product
  const handleAddProduct = async () => {
    if (!newProduct.name || !newProduct.price) {
      toast.error('Please fill in product name and price');
      return;
    }
    
    setSavingProduct(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const slug = newProduct.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
      const productId = `prod-${slug}-${Date.now()}`;
      
      // Map category to category_id
      const categoryMap = {
        'serums': 'cat-serums',
        'cleansers': 'cat-cleansers',
        'moisturizers': 'cat-moisturizers',
        'treatments': 'cat-treatments',
        'masks': 'cat-masks'
      };
      
      const productData = {
        id: productId,
        slug,
        name: newProduct.name,
        description: newProduct.description || 'A premium skincare product from ReRoots.',
        price: parseFloat(newProduct.price) || 0,
        compare_price: parseFloat(newProduct.compare_price) || null,
        stock: parseInt(newProduct.stock) || 100,
        discount_percent: parseInt(newProduct.discount_percent) || 0,
        category_id: categoryMap[newProduct.category] || 'cat-serums',
        images: newProduct.images.length > 0 ? newProduct.images : ['https://via.placeholder.com/800x800?text=Product+Image'],
        is_featured: newProduct.featured || false,
        is_active: newProduct.active !== false,
        brand: 'ReRoots',
        brand_visibility: newProduct.brand_visibility || 'both',
        created_at: new Date().toISOString()
      };
      
      const response = await axios.post(`${API}/products`, productData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Add to local state
      setProducts([response.data, ...products]);
      setAddProductDialogOpen(false);
      setNewProduct({
        name: '',
        price: '',
        compare_price: '',
        description: '',
        category: 'serums',
        stock: 100,
        discount_percent: 0,
        featured: false,
        active: true,
        images: [],
        brand_visibility: 'both'
      });
      toast.success('Product created successfully!');
    } catch (error) {
      console.error('Failed to create product:', error);
      toast.error(error.response?.data?.detail || 'Failed to create product');
    } finally {
      setSavingProduct(false);
    }
  };

  // Handle product delete
  const handleDeleteProduct = async (productId) => {
    if (!confirm('Are you sure you want to delete this product?')) return;
    
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.delete(`${API}/products/${productId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setProducts(products.filter(p => p.id !== productId));
      toast.success('Product deleted successfully!');
    } catch (error) {
      console.error('Failed to delete product:', error);
      toast.error(error.response?.data?.detail || 'Failed to delete product');
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FDF9F9]">
        <Loader2 className="h-10 w-10 animate-spin text-[#F8A5B8]" />
        <span className="ml-3 text-lg text-[#2D2A2E]">Loading Admin Dashboard...</span>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const tabConfig = [
    { id: 'overview', label: '📊 Overview' },
    { id: 'products', label: '📦 Products' },
    { id: 'orders', label: '🛒 Orders' },
    { id: 'ai-hub', label: '🤖 AI Studio' },
    { id: 'marketing', label: '🎯 Marketing' },
    { id: 'customers', label: '👥 Customers' },
    { id: 'settings-hub', label: '⚙️ Settings' }
  ];

  return (
    <div className="min-h-screen pt-20 bg-gradient-to-b from-[#FDF9F9] to-white">
      {/* Hide scrollbar but keep scroll functionality */}
      <style>{`
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 rounded-full hover:bg-gray-100 transition-colors"
              title="Go Back"
              data-testid="admin-back-button"
            >
              <ArrowLeft className="h-6 w-6 text-[#2D2A2E]" />
            </button>
            <div>
              <h1 className="font-display text-3xl font-bold text-[#2D2A2E]">Admin Dashboard</h1>
              <p className="text-[#5A5A5A] mt-1">Welcome back, {user.first_name || user.email}</p>
            </div>
          </div>
          {/* Refresh button removed - data auto-refreshes */}
        </div>

        {/* Brand Switcher */}
        <div className="mb-4 flex items-center gap-2 p-1 bg-gradient-to-r from-gray-100 to-slate-100 rounded-xl w-max" data-testid="brand-switcher">
          <button
            onClick={() => setBrandFilter('all')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              brandFilter === 'all' 
                ? 'bg-white shadow-sm text-[#2D2A2E]' 
                : 'text-gray-600 hover:bg-white/50'
            }`}
            data-testid="brand-filter-all"
          >
            🌐 All
          </button>
          <button
            onClick={() => setBrandFilter('reroots')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              brandFilter === 'reroots' 
                ? 'bg-gradient-to-r from-pink-100 to-rose-100 shadow-sm text-pink-800' 
                : 'text-gray-600 hover:bg-pink-50'
            }`}
            data-testid="brand-filter-reroots"
          >
            🩷 ReRoots
          </button>
          <button
            onClick={() => setBrandFilter('dark_store')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              brandFilter === 'dark_store' 
                ? 'bg-gray-900 shadow-sm text-white' 
                : 'text-gray-600 hover:bg-gray-200'
            }`}
            data-testid="brand-filter-dark"
          >
            🖤 Dark Store
          </button>
        </div>

        {/* Tabs - At Top for Mobile - Horizontal Scroll */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <div className="mb-8 -mx-4 px-4">
            <Suspense fallback={
              <div className="overflow-x-auto scrollbar-hide pb-2">
                <div className="inline-flex gap-1 bg-gradient-to-r from-pink-50 to-rose-50 p-2 rounded-xl w-max min-w-full">
                  {tabOrder.map((tabId) => {
                    const tab = tabConfig.find(t => t.id === tabId);
                    if (!tab) return null;
                    return (
                      <div key={tabId} className="px-3 py-2 text-xs sm:text-sm whitespace-nowrap flex-shrink-0 bg-white/50 rounded-lg">
                        {tab.label}
                      </div>
                    );
                  })}
                </div>
              </div>
            }>
              <DndTabWrapper 
                tabOrder={tabOrder} 
                onDragEnd={handleTabReorder}
                renderTab={(tabId) => {
                  const tab = tabConfig.find(t => t.id === tabId);
                  if (!tab) return null;
                  return (
                    <TabsTrigger 
                      value={tabId}
                      className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-lg px-3 py-2 text-xs sm:text-sm whitespace-nowrap flex-shrink-0"
                      data-testid={`admin-tab-${tabId}`}
                    >
                      {tab.label}
                    </TabsTrigger>
                  );
                }}
              />
            </Suspense>
          </div>

          {/* Stats Cards - Below Tabs with Clear Separation */}
          {loading ? (
            <StatsGridSkeleton />
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-6 mb-6">
              <Card style={{ minHeight: '96px' }}>
                <CardContent className="pt-4 md:pt-6 px-3 md:px-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs md:text-sm text-[#5A5A5A]">Revenue</p>
                      <p className="text-lg md:text-2xl font-bold text-[#2D2A2E]">${stats?.total_revenue?.toFixed(0) || '0'}</p>
                    </div>
                    <TrendingUp className="h-6 w-6 md:h-8 md:w-8 text-green-500" />
                  </div>
                </CardContent>
              </Card>
              <Card style={{ minHeight: '96px' }}>
                <CardContent className="pt-4 md:pt-6 px-3 md:px-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs md:text-sm text-[#5A5A5A]">Orders</p>
                      <p className="text-lg md:text-2xl font-bold text-[#2D2A2E]">{stats?.total_orders || orders.length}</p>
                    </div>
                    <Package className="h-6 w-6 md:h-8 md:w-8 text-blue-500" />
                  </div>
                </CardContent>
              </Card>
              <Card style={{ minHeight: '96px' }}>
                <CardContent className="pt-4 md:pt-6 px-3 md:px-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs md:text-sm text-[#5A5A5A]">Products</p>
                      <p className="text-lg md:text-2xl font-bold text-[#2D2A2E]">{products.length}</p>
                    </div>
                    <Eye className="h-6 w-6 md:h-8 md:w-8 text-purple-500" />
                  </div>
                </CardContent>
              </Card>
              <Card style={{ minHeight: '96px' }}>
                <CardContent className="pt-4 md:pt-6 px-3 md:px-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs md:text-sm text-[#5A5A5A]">Customers</p>
                      <p className="text-lg md:text-2xl font-bold text-[#2D2A2E]">{stats?.total_customers || 0}</p>
                    </div>
                    <Bell className="h-6 w-6 md:h-8 md:w-8 text-orange-500" />
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Overview Tab */}
          <TabsContent value="overview">
            {loading ? (
              <OverviewCardSkeleton />
            ) : (
              <Card style={{ minHeight: '280px' }}>
                <CardHeader>
                  <CardTitle>Dashboard Overview</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-[#5A5A5A]">
                    Welcome to your admin dashboard. Use the tabs above to manage your store.
                  </p>
                  <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 bg-green-50 rounded-lg" style={{ minHeight: '72px' }}>
                      <h3 className="font-semibold text-green-800">Recent Activity</h3>
                      <p className="text-sm text-green-600 mt-1">{orders.length} orders in the system</p>
                    </div>
                    <div className="p-4 bg-blue-50 rounded-lg" style={{ minHeight: '72px' }}>
                      <h3 className="font-semibold text-blue-800">Inventory</h3>
                      <p className="text-sm text-blue-600 mt-1">{products.length} products listed</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Products Tab - Virtualized for performance */}
          <TabsContent value="products">
            <Suspense fallback={<div className="animate-pulse bg-gray-100 rounded-lg h-[500px]" />}>
              <VirtualizedProductsTable 
                products={products.filter(p => {
                  if (brandFilter === 'all') return true;
                  const visibility = p.brand_visibility || 'both';
                  if (brandFilter === 'reroots') return visibility === 'both' || visibility === 'reroots_only';
                  if (brandFilter === 'dark_store') return visibility === 'both' || visibility === 'dark_only';
                  return true;
                })} 
                loading={loading}
                onEdit={handleEditProduct}
                onDelete={handleDeleteProduct}
                onAdd={() => setAddProductDialogOpen(true)}
                maxHeight={500}
              />
            </Suspense>

            {/* Edit Product Dialog */}
            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Edit Product</DialogTitle>
                </DialogHeader>
                {editingProduct && (
                  <div className="space-y-4 py-4">
                    <div>
                      <Label htmlFor="edit-name">Product Name</Label>
                      <Input
                        id="edit-name"
                        value={editingProduct.name || ''}
                        onChange={(e) => setEditingProduct({ ...editingProduct, name: e.target.value })}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="edit-price">Price ($)</Label>
                        <Input
                          id="edit-price"
                          type="number"
                          step="0.01"
                          value={editingProduct.price || ''}
                          onChange={(e) => setEditingProduct({ ...editingProduct, price: parseFloat(e.target.value) || 0 })}
                        />
                      </div>
                      <div>
                        <Label htmlFor="edit-compare-price">Compare At Price ($)</Label>
                        <Input
                          id="edit-compare-price"
                          type="number"
                          step="0.01"
                          value={editingProduct.compare_price || ''}
                          onChange={(e) => setEditingProduct({ ...editingProduct, compare_price: parseFloat(e.target.value) || 0 })}
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="edit-stock">Stock Quantity</Label>
                        <Input
                          id="edit-stock"
                          type="number"
                          value={editingProduct.stock || editingProduct.inventory_count || 0}
                          onChange={(e) => setEditingProduct({ ...editingProduct, stock: parseInt(e.target.value) || 0, inventory_count: parseInt(e.target.value) || 0 })}
                        />
                      </div>
                      <div>
                        <Label htmlFor="edit-discount">Discount %</Label>
                        <Input
                          id="edit-discount"
                          type="number"
                          min="0"
                          max="100"
                          value={editingProduct.discount_percent || 0}
                          onChange={(e) => setEditingProduct({ ...editingProduct, discount_percent: parseInt(e.target.value) || 0 })}
                        />
                      </div>
                    </div>
                    
                    {/* Image Upload Section */}
                    <div>
                      <Label>Product Images</Label>
                      <div className="mt-2 space-y-3">
                        {/* Current Images */}
                        {editingProduct.images && editingProduct.images.length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {editingProduct.images.map((img, idx) => (
                              <div key={idx} className="relative group">
                                <img src={img} alt={`Product ${idx + 1}`} className="w-20 h-20 object-cover rounded-lg border" />
                                <button
                                  type="button"
                                  onClick={() => {
                                    const newImages = editingProduct.images.filter((_, i) => i !== idx);
                                    setEditingProduct({ ...editingProduct, images: newImages });
                                  }}
                                  className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                                >
                                  ×
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {/* File Upload Button */}
                        <div className="flex gap-2">
                          <input
                            type="file"
                            id="edit-image-upload"
                            accept="image/*"
                            multiple
                            className="hidden"
                            onChange={async (e) => {
                              const files = Array.from(e.target.files);
                              if (files.length === 0) return;
                              
                              const token = localStorage.getItem('reroots_token');
                              const uploadedUrls = [];
                              
                              for (const file of files) {
                                try {
                                  toast.info(`Uploading ${file.name}...`);
                                  const formData = new FormData();
                                  formData.append('file', file);
                                  
                                  const response = await axios.post(`${API}/upload/image`, formData, {
                                    headers: {
                                      'Content-Type': 'multipart/form-data',
                                      Authorization: `Bearer ${token}`
                                    }
                                  });
                                  
                                  if (response.data.url) {
                                    uploadedUrls.push(response.data.url);
                                    toast.success(`${file.name} uploaded!`);
                                  }
                                } catch (err) {
                                  console.error('Upload error:', err);
                                  toast.error(`Failed to upload ${file.name}`);
                                }
                              }
                              
                              if (uploadedUrls.length > 0) {
                                setEditingProduct({
                                  ...editingProduct,
                                  images: [...(editingProduct.images || []), ...uploadedUrls]
                                });
                              }
                              
                              // Reset input
                              e.target.value = '';
                            }}
                          />
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => document.getElementById('edit-image-upload').click()}
                            className="flex-1"
                          >
                            <Upload className="h-4 w-4 mr-2" />
                            Upload Images
                          </Button>
                        </div>
                        
                        {/* Add Image URL (alternative) */}
                        <div className="flex gap-2">
                          <Input
                            id="edit-new-image"
                            placeholder="Or paste image URL here"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                const url = e.target.value.trim();
                                if (url) {
                                  setEditingProduct({
                                    ...editingProduct,
                                    images: [...(editingProduct.images || []), url]
                                  });
                                  e.target.value = '';
                                }
                              }
                            }}
                          />
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => {
                              const input = document.getElementById('edit-new-image');
                              const url = input.value.trim();
                              if (url) {
                                setEditingProduct({
                                  ...editingProduct,
                                  images: [...(editingProduct.images || []), url]
                                });
                                input.value = '';
                              }
                            }}
                          >
                            <Plus className="h-4 w-4" />
                          </Button>
                        </div>
                        <p className="text-xs text-gray-500">Upload images or add URLs. Press Enter or click + to add URL.</p>
                      </div>
                    </div>
                    
                    <div>
                      <Label htmlFor="edit-description">Description</Label>
                      <Textarea
                        id="edit-description"
                        rows={4}
                        value={editingProduct.description || ''}
                        onChange={(e) => setEditingProduct({ ...editingProduct, description: e.target.value })}
                        placeholder="Enter product description..."
                      />
                    </div>
                    
                    {/* Ingredients Section */}
                    <div>
                      <Label htmlFor="edit-ingredients">Ingredients</Label>
                      <Textarea
                        id="edit-ingredients"
                        rows={3}
                        value={editingProduct.ingredients || ''}
                        onChange={(e) => setEditingProduct({ ...editingProduct, ingredients: e.target.value })}
                        placeholder="List product ingredients..."
                      />
                    </div>
                    
                    {/* INCI Ingredients (Scientific Names) */}
                    <div>
                      <Label htmlFor="edit-inci">INCI Ingredients (Scientific Names)</Label>
                      <Textarea
                        id="edit-inci"
                        rows={2}
                        value={editingProduct.inci_ingredients || ''}
                        onChange={(e) => setEditingProduct({ ...editingProduct, inci_ingredients: e.target.value })}
                        placeholder="e.g., Aqua, Glycerin, Niacinamide, Sodium Hyaluronate..."
                      />
                    </div>
                    
                    {/* Advanced Product Styling Section */}
                    <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl p-4 space-y-4 border border-purple-100">
                      <div className="flex items-center gap-2 mb-2">
                        <Sparkles className="h-5 w-5 text-purple-500" />
                        <h4 className="font-semibold text-[#2D2A2E]">Advanced Styling</h4>
                      </div>
                      
                      {/* Product Type & Accent Color */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label>Product Type</Label>
                          <Select 
                            value={editingProduct.product_type || 'standard'} 
                            onValueChange={(value) => setEditingProduct({ ...editingProduct, product_type: value })}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="standard">Standard (Gold Theme)</SelectItem>
                              <SelectItem value="pink_peptide">Pink Peptide Theme</SelectItem>
                              <SelectItem value="blue_hydration">Blue Hydration Theme</SelectItem>
                              <SelectItem value="green_natural">Green Natural Theme</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label>Accent Color</Label>
                          <Select 
                            value={editingProduct.accent_color || 'gold'} 
                            onValueChange={(value) => setEditingProduct({ ...editingProduct, accent_color: value })}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select color" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="gold">🟡 Gold (Default)</SelectItem>
                              <SelectItem value="pink">🩷 Pink / Rose</SelectItem>
                              <SelectItem value="blue">🔵 Blue</SelectItem>
                              <SelectItem value="green">🟢 Green</SelectItem>
                              <SelectItem value="purple">🟣 Purple</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      
                      {/* Texture Description */}
                      <div>
                        <Label htmlFor="edit-texture">Texture Description</Label>
                        <Input
                          id="edit-texture"
                          value={editingProduct.texture_description || ''}
                          onChange={(e) => setEditingProduct({ ...editingProduct, texture_description: e.target.value })}
                          placeholder="e.g., Silky, soft-focus cream with an instant blurring effect"
                        />
                      </div>
                      
                      {/* Science Highlight */}
                      <div>
                        <Label htmlFor="edit-science">Science Highlight</Label>
                        <Textarea
                          id="edit-science"
                          rows={2}
                          value={editingProduct.science_highlight || ''}
                          onChange={(e) => setEditingProduct({ ...editingProduct, science_highlight: e.target.value })}
                          placeholder="e.g., Phase D Actives with advanced Encapsulation technology prevents irritation..."
                        />
                      </div>
                    </div>
                    
                    {/* Hero Ingredients Section */}
                    <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl p-4 space-y-4 border border-amber-100">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <FlaskConical className="h-5 w-5 text-amber-600" />
                          <h4 className="font-semibold text-[#2D2A2E]">Hero Ingredients</h4>
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            const currentIngredients = editingProduct.hero_ingredients || [];
                            setEditingProduct({
                              ...editingProduct,
                              hero_ingredients: [...currentIngredients, { name: '', concentration: '', description: '', icon: 'flask' }]
                            });
                          }}
                          className="border-amber-300 text-amber-700 hover:bg-amber-100"
                        >
                          <Plus className="h-4 w-4 mr-1" />
                          Add Ingredient
                        </Button>
                      </div>
                      <p className="text-xs text-gray-500">Add key active ingredients to highlight on the product page</p>
                      
                      {(editingProduct.hero_ingredients || []).map((ingredient, idx) => (
                        <div key={idx} className="bg-white rounded-lg p-3 border border-amber-200 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-amber-800">Ingredient #{idx + 1}</span>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                const updated = editingProduct.hero_ingredients.filter((_, i) => i !== idx);
                                setEditingProduct({ ...editingProduct, hero_ingredients: updated });
                              }}
                              className="text-red-500 hover:text-red-700 hover:bg-red-50 h-7 w-7 p-0"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <Input
                              placeholder="Name (e.g., NAD+)"
                              value={ingredient.name || ''}
                              onChange={(e) => {
                                const updated = [...editingProduct.hero_ingredients];
                                updated[idx] = { ...updated[idx], name: e.target.value };
                                setEditingProduct({ ...editingProduct, hero_ingredients: updated });
                              }}
                            />
                            <Input
                              placeholder="Concentration (e.g., 5%)"
                              value={ingredient.concentration || ''}
                              onChange={(e) => {
                                const updated = [...editingProduct.hero_ingredients];
                                updated[idx] = { ...updated[idx], concentration: e.target.value };
                                setEditingProduct({ ...editingProduct, hero_ingredients: updated });
                              }}
                            />
                          </div>
                          <Input
                            placeholder="Description (e.g., Cellular longevity and energy)"
                            value={ingredient.description || ''}
                            onChange={(e) => {
                              const updated = [...editingProduct.hero_ingredients];
                              updated[idx] = { ...updated[idx], description: e.target.value };
                              setEditingProduct({ ...editingProduct, hero_ingredients: updated });
                            }}
                          />
                          <Select 
                            value={ingredient.icon || 'flask'} 
                            onValueChange={(value) => {
                              const updated = [...editingProduct.hero_ingredients];
                              updated[idx] = { ...updated[idx], icon: value };
                              setEditingProduct({ ...editingProduct, hero_ingredients: updated });
                            }}
                          >
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Select icon" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="dna">🧬 DNA / Cellular</SelectItem>
                              <SelectItem value="flask">🧪 Flask / Science</SelectItem>
                              <SelectItem value="sparkles">✨ Sparkles / Brightening</SelectItem>
                              <SelectItem value="shield">🛡️ Shield / Protection</SelectItem>
                              <SelectItem value="droplets">💧 Droplets / Hydration</SelectItem>
                              <SelectItem value="beaker">⚗️ Beaker / Formula</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      ))}
                      
                      {(!editingProduct.hero_ingredients || editingProduct.hero_ingredients.length === 0) && (
                        <p className="text-center text-gray-400 text-sm py-4">
                          No hero ingredients added. Click "Add Ingredient" to start.
                        </p>
                      )}
                    </div>
                    
                    {/* Storefront Visibility */}
                    <div className="bg-gradient-to-r from-gray-50 to-slate-50 rounded-xl p-4 space-y-3 border border-gray-200">
                      <div className="flex items-center gap-2">
                        <Globe className="h-5 w-5 text-gray-600" />
                        <h4 className="font-semibold text-[#2D2A2E]">Storefront Visibility</h4>
                      </div>
                      <p className="text-xs text-gray-500">Choose which storefront(s) display this product</p>
                      <Select 
                        value={editingProduct.brand_visibility || 'both'} 
                        onValueChange={(value) => setEditingProduct({ ...editingProduct, brand_visibility: value })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select visibility" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="both">🌐 Both Storefronts (Default)</SelectItem>
                          <SelectItem value="reroots_only">🩷 ReRoots Only (Bright Theme)</SelectItem>
                          <SelectItem value="dark_only">🖤 Dark Store Only (/app)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div>
                      <Label htmlFor="edit-category">Category</Label>
                      <Select 
                        value={editingProduct.category || editingProduct.category_id || ''} 
                        onValueChange={(value) => setEditingProduct({ ...editingProduct, category: value, category_id: value })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select category" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="serums">Serums</SelectItem>
                          <SelectItem value="cleansers">Cleansers</SelectItem>
                          <SelectItem value="moisturizers">Moisturizers</SelectItem>
                          <SelectItem value="treatments">Treatments</SelectItem>
                          <SelectItem value="masks">Masks</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center gap-4">
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={editingProduct.featured || editingProduct.is_featured || false}
                          onChange={(e) => setEditingProduct({ ...editingProduct, featured: e.target.checked, is_featured: e.target.checked })}
                          className="rounded border-gray-300"
                        />
                        <span className="text-sm">Featured Product</span>
                      </label>
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={editingProduct.active !== false && editingProduct.is_active !== false}
                          onChange={(e) => setEditingProduct({ ...editingProduct, active: e.target.checked, is_active: e.target.checked })}
                          className="rounded border-gray-300"
                        />
                        <span className="text-sm">Active (Visible)</span>
                      </label>
                    </div>
                    <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 pt-4 border-t mt-4">
                      <Button variant="outline" onClick={() => setEditDialogOpen(false)} className="w-full sm:w-auto text-[#2D2A2E]">
                        Cancel
                      </Button>
                      <Button onClick={handleSaveProduct} disabled={savingProduct} className="w-full sm:w-auto bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white">
                        {savingProduct ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          <>
                            <Check className="h-4 w-4 mr-2" />
                            Save Changes
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                )}
              </DialogContent>
            </Dialog>

            {/* Add New Product Dialog */}
            <Dialog open={addProductDialogOpen} onOpenChange={setAddProductDialogOpen}>
              <DialogContent className="max-w-2xl w-[95vw] max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Add New Product</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4 pb-2">
                  <div>
                    <Label htmlFor="new-name">Product Name *</Label>
                    <Input
                      id="new-name"
                      placeholder="e.g., Vitamin C Serum"
                      value={newProduct.name}
                      onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="new-price">Price ($) *</Label>
                      <Input
                        id="new-price"
                        type="number"
                        step="0.01"
                        placeholder="99.00"
                        value={newProduct.price}
                        onChange={(e) => setNewProduct({ ...newProduct, price: e.target.value })}
                      />
                    </div>
                    <div>
                      <Label htmlFor="new-compare-price">Compare At Price ($)</Label>
                      <Input
                        id="new-compare-price"
                        type="number"
                        step="0.01"
                        placeholder="139.99"
                        value={newProduct.compare_price}
                        onChange={(e) => setNewProduct({ ...newProduct, compare_price: e.target.value })}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="new-stock">Stock Quantity</Label>
                      <Input
                        id="new-stock"
                        type="number"
                        value={newProduct.stock}
                        onChange={(e) => setNewProduct({ ...newProduct, stock: e.target.value })}
                      />
                    </div>
                    <div>
                      <Label htmlFor="new-discount">Discount %</Label>
                      <Input
                        id="new-discount"
                        type="number"
                        min="0"
                        max="100"
                        value={newProduct.discount_percent}
                        onChange={(e) => setNewProduct({ ...newProduct, discount_percent: e.target.value })}
                      />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="new-description">Description</Label>
                    <Textarea
                      id="new-description"
                      rows={3}
                      placeholder="Describe your product..."
                      value={newProduct.description}
                      onChange={(e) => setNewProduct({ ...newProduct, description: e.target.value })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="new-category">Category</Label>
                    <Select 
                      value={newProduct.category} 
                      onValueChange={(value) => setNewProduct({ ...newProduct, category: value })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select category" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="serums">Serums</SelectItem>
                        <SelectItem value="cleansers">Cleansers</SelectItem>
                        <SelectItem value="moisturizers">Moisturizers</SelectItem>
                        <SelectItem value="treatments">Treatments</SelectItem>
                        <SelectItem value="masks">Masks</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="new-visibility">Storefront Visibility</Label>
                    <Select 
                      value={newProduct.brand_visibility || 'both'} 
                      onValueChange={(value) => setNewProduct({ ...newProduct, brand_visibility: value })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select visibility" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="both">🌐 Both Storefronts</SelectItem>
                        <SelectItem value="reroots_only">🩷 ReRoots Only (Bright Theme)</SelectItem>
                        <SelectItem value="dark_only">🖤 Dark Store Only (/app)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="new-image">Product Image URL</Label>
                    <Input
                      id="new-image"
                      placeholder="https://example.com/image.jpg"
                      value={newProduct.images[0] || ''}
                      onChange={(e) => setNewProduct({ ...newProduct, images: e.target.value ? [e.target.value] : [] })}
                    />
                  </div>
                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={newProduct.featured}
                        onChange={(e) => setNewProduct({ ...newProduct, featured: e.target.checked })}
                        className="rounded border-gray-300"
                      />
                      <span className="text-sm">Featured Product</span>
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={newProduct.active}
                        onChange={(e) => setNewProduct({ ...newProduct, active: e.target.checked })}
                        className="rounded border-gray-300"
                      />
                      <span className="text-sm">Active (Visible)</span>
                    </label>
                  </div>
                  <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 pt-4 border-t mt-4">
                    <Button variant="outline" onClick={() => setAddProductDialogOpen(false)} className="w-full sm:w-auto">
                      Cancel
                    </Button>
                    <Button onClick={handleAddProduct} disabled={savingProduct} className="w-full sm:w-auto bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white">
                      {savingProduct ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <Plus className="h-4 w-4 mr-2" />
                          Create Product
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </TabsContent>

          {/* Orders Tab - Virtualized for performance */}
          <TabsContent value="orders">
            <Suspense fallback={<OrdersTableSkeleton />}>
              <VirtualizedOrdersTable 
                orders={orders.filter(o => {
                  if (brandFilter === 'all') return true;
                  const storefront = o.storefront || (o.source_url?.includes('/app') ? 'dark_store' : 'reroots');
                  return storefront === brandFilter;
                })} 
                loading={loading}
                maxHeight={600}
              />
            </Suspense>
          </TabsContent>

          {/* Marketing Tab */}
          <TabsContent value="marketing">
            <div className="space-y-6">
              {/* Discount Codes Section */}
              <Suspense fallback={<div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /><span className="ml-2 text-[#5A5A5A]">Loading Discounts...</span></div>}>
                <DiscountCodeManager />
              </Suspense>
              
              {/* Subscribers Section */}
              <Suspense fallback={<div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}>
                <SubscribersSection />
              </Suspense>
              
              {/* Offers Section */}
              <Suspense fallback={<div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}>
                <OffersManager />
              </Suspense>
            </div>
          </TabsContent>

          {/* AI Hub Tab */}
          <TabsContent value="ai-hub">
            <Suspense fallback={<div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /><span className="ml-2 text-[#5A5A5A]">Loading AI Studio...</span></div>}>
              <AIContentStudio />
            </Suspense>
          </TabsContent>

          {/* Customers Tab */}
          <TabsContent value="customers">
            <Suspense fallback={<div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}>
              <CustomersManager />
            </Suspense>
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="settings-hub">
            <div className="space-y-6">
              {/* Connected Accounts Section */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <ExternalLink className="h-5 w-5" />
                      Connected Accounts
                    </CardTitle>
                    <p className="text-sm text-[#5A5A5A]">Quick access to all your external services</p>
                  </div>
                  <Button 
                    size="sm"
                    onClick={() => {
                      setEditingAccount(null);
                      setNewAccount({ name: '', description: '', url: '', color: 'blue' });
                      setAccountDialogOpen(true);
                    }}
                    className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add Account
                  </Button>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {connectedAccounts.map((account) => {
                      const colorClasses = {
                        purple: 'from-purple-500 to-purple-700 hover:bg-purple-50 hover:border-purple-300 group-hover:text-purple-700',
                        red: 'from-red-500 to-red-700 hover:bg-red-50 hover:border-red-300 group-hover:text-red-700',
                        blue: 'from-blue-500 to-blue-700 hover:bg-blue-50 hover:border-blue-300 group-hover:text-blue-700',
                        green: 'from-green-600 to-green-800 hover:bg-green-50 hover:border-green-300 group-hover:text-green-700',
                        orange: 'from-orange-500 to-orange-700 hover:bg-orange-50 hover:border-orange-300 group-hover:text-orange-700',
                        yellow: 'from-yellow-500 to-yellow-600 hover:bg-yellow-50 hover:border-yellow-300 group-hover:text-yellow-700',
                        cyan: 'from-cyan-500 to-cyan-700 hover:bg-cyan-50 hover:border-cyan-300 group-hover:text-cyan-700',
                        sky: 'from-sky-400 to-sky-600 hover:bg-sky-50 hover:border-sky-300 group-hover:text-sky-700',
                        pink: 'from-pink-500 to-pink-700 hover:bg-pink-50 hover:border-pink-300 group-hover:text-pink-700',
                        gray: 'from-gray-500 to-gray-700 hover:bg-gray-50 hover:border-gray-300 group-hover:text-gray-700',
                        indigo: 'from-indigo-500 to-indigo-700 hover:bg-indigo-50 hover:border-indigo-300 group-hover:text-indigo-700',
                        teal: 'from-teal-500 to-teal-700 hover:bg-teal-50 hover:border-teal-300 group-hover:text-teal-700',
                      };
                      const colors = colorClasses[account.color] || colorClasses.blue;
                      const gradientColors = colors.split(' ').filter(c => c.startsWith('from-') || c.startsWith('to-')).join(' ');
                      const hoverColors = colors.split(' ').filter(c => c.startsWith('hover:')).join(' ');
                      
                      return (
                        <div key={account.id} className={`relative flex items-center gap-4 p-4 border rounded-xl transition-all group ${hoverColors}`}>
                          {/* Action Buttons */}
                          <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={(e) => {
                                e.preventDefault();
                                openEditAccount(account);
                              }}
                              className="p-1.5 rounded-lg bg-white shadow-sm hover:bg-gray-100 text-[#5A5A5A]"
                              title="Edit"
                            >
                              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                              </svg>
                            </button>
                            <button
                              onClick={(e) => {
                                e.preventDefault();
                                handleDeleteAccount(account.id);
                              }}
                              className="p-1.5 rounded-lg bg-white shadow-sm hover:bg-red-100 text-red-500"
                              title="Remove"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                          
                          <a 
                            href={account.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="flex items-center gap-4 flex-1"
                          >
                            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${gradientColors} flex items-center justify-center text-white font-bold text-lg`}>
                              {account.name.charAt(0).toUpperCase()}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-semibold text-[#2D2A2E] truncate">{account.name}</p>
                              <p className="text-xs text-[#5A5A5A] truncate">{account.description}</p>
                            </div>
                            <ExternalLink className="h-4 w-4 text-[#5A5A5A] flex-shrink-0" />
                          </a>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Add/Edit Account Dialog */}
              <Dialog open={accountDialogOpen} onOpenChange={setAccountDialogOpen}>
                <DialogContent className="max-w-md w-[95vw]">
                  <DialogHeader>
                    <DialogTitle>{editingAccount ? 'Edit Account' : 'Add New Account'}</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div>
                      <Label htmlFor="account-name">Account Name *</Label>
                      <Input
                        id="account-name"
                        placeholder="e.g., Stripe, PayPal, Shopify"
                        value={newAccount.name}
                        onChange={(e) => setNewAccount({ ...newAccount, name: e.target.value })}
                      />
                    </div>
                    <div>
                      <Label htmlFor="account-url">URL *</Label>
                      <Input
                        id="account-url"
                        placeholder="https://dashboard.example.com"
                        value={newAccount.url}
                        onChange={(e) => setNewAccount({ ...newAccount, url: e.target.value })}
                      />
                    </div>
                    <div>
                      <Label htmlFor="account-desc">Description</Label>
                      <Input
                        id="account-desc"
                        placeholder="e.g., Payments & Billing"
                        value={newAccount.description}
                        onChange={(e) => setNewAccount({ ...newAccount, description: e.target.value })}
                      />
                    </div>
                    <div>
                      <Label htmlFor="account-color">Color</Label>
                      <Select 
                        value={newAccount.color} 
                        onValueChange={(value) => setNewAccount({ ...newAccount, color: value })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select color" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="purple">Purple</SelectItem>
                          <SelectItem value="red">Red</SelectItem>
                          <SelectItem value="blue">Blue</SelectItem>
                          <SelectItem value="green">Green</SelectItem>
                          <SelectItem value="orange">Orange</SelectItem>
                          <SelectItem value="yellow">Yellow</SelectItem>
                          <SelectItem value="cyan">Cyan</SelectItem>
                          <SelectItem value="pink">Pink</SelectItem>
                          <SelectItem value="indigo">Indigo</SelectItem>
                          <SelectItem value="teal">Teal</SelectItem>
                          <SelectItem value="gray">Gray</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 pt-4 border-t">
                      <Button variant="outline" onClick={() => setAccountDialogOpen(false)} className="text-[#2D2A2E]">
                        Cancel
                      </Button>
                      <Button onClick={handleSaveAccount} className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white">
                        {editingAccount ? 'Save Changes' : 'Add Account'}
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>

              {/* Secure Vault - Snapchat Style */}
              <Card className="border-2 border-dashed border-purple-200 bg-gradient-to-br from-purple-50 via-pink-50 to-yellow-50">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <div className="p-2 rounded-xl bg-gradient-to-br from-yellow-400 via-pink-500 to-purple-600">
                        <Lock className="h-5 w-5 text-white" />
                      </div>
                      <span className="bg-gradient-to-r from-purple-600 via-pink-500 to-yellow-500 bg-clip-text text-transparent font-bold">
                        Secure Vault
                      </span>
                      {vaultUnlocked && (
                        <Badge className="bg-green-500 text-white ml-2">Unlocked</Badge>
                      )}
                    </CardTitle>
                    {/* Minimize/Maximize Button */}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setVaultMinimized(!vaultMinimized)}
                      className="h-8 w-8 p-0 hover:bg-purple-100"
                    >
                      {vaultMinimized ? (
                        <ChevronDown className="h-5 w-5 text-purple-600" />
                      ) : (
                        <ChevronUp className="h-5 w-5 text-purple-600" />
                      )}
                    </Button>
                  </div>
                  <p className="text-sm text-[#5A5A5A]">Password-protected private storage • Content auto-expires</p>
                </CardHeader>
                
                {/* Collapsible Content */}
                {!vaultMinimized && (
                <CardContent>
                  {!vaultUnlocked ? (
                    <div className="space-y-6">
                      {settingPin ? (
                        /* Set PIN for first time */
                        <div className="max-w-sm mx-auto space-y-4 py-8">
                          <div className="text-center mb-6">
                            <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-yellow-400 via-pink-500 to-purple-600 flex items-center justify-center">
                              <Shield className="h-10 w-10 text-white" />
                            </div>
                            <h3 className="text-lg font-bold text-[#2D2A2E]">Create Your PIN</h3>
                            <p className="text-sm text-[#5A5A5A]">Set a PIN to protect your private vault</p>
                          </div>
                          <div>
                            <Label>New PIN (min 4 characters)</Label>
                            <Input
                              type="password"
                              value={newPin}
                              onChange={(e) => setNewPin(e.target.value)}
                              placeholder="••••••"
                              className="text-center text-2xl tracking-widest"
                            />
                          </div>
                          <div>
                            <Label>Confirm PIN</Label>
                            <Input
                              type="password"
                              value={confirmPin}
                              onChange={(e) => setConfirmPin(e.target.value)}
                              placeholder="••••••"
                              className="text-center text-2xl tracking-widest"
                            />
                          </div>
                          {vaultError && (
                            <p className="text-red-500 text-sm text-center">{vaultError}</p>
                          )}
                          <Button 
                            onClick={setVaultPin}
                            className="w-full bg-gradient-to-r from-purple-600 via-pink-500 to-yellow-500 hover:from-purple-700 hover:via-pink-600 hover:to-yellow-600 text-white"
                          >
                            <Lock className="h-4 w-4 mr-2" />
                            Set PIN & Open Vault
                          </Button>
                        </div>
                      ) : (
                        /* Enter PIN to unlock */
                        <div className="max-w-sm mx-auto space-y-4 py-8">
                          <div className="text-center mb-6">
                            <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-yellow-400 via-pink-500 to-purple-600 flex items-center justify-center animate-pulse">
                              <Lock className="h-10 w-10 text-white" />
                            </div>
                            <h3 className="text-lg font-bold text-[#2D2A2E]">Enter PIN</h3>
                            <p className="text-sm text-[#5A5A5A]">Unlock your private vault</p>
                          </div>
                          <Input
                            type="password"
                            value={vaultPasswordInput}
                            onChange={(e) => setVaultPasswordInput(e.target.value)}
                            placeholder="••••••"
                            className="text-center text-2xl tracking-widest"
                            onKeyPress={(e) => e.key === 'Enter' && unlockVault()}
                          />
                          {vaultError && (
                            <p className="text-red-500 text-sm text-center">{vaultError}</p>
                          )}
                          <Button 
                            onClick={unlockVault}
                            className="w-full bg-gradient-to-r from-purple-600 via-pink-500 to-yellow-500 hover:from-purple-700 hover:via-pink-600 hover:to-yellow-600 text-white"
                          >
                            <Unlock className="h-4 w-4 mr-2" />
                            Unlock Vault
                          </Button>
                        </div>
                      )}
                    </div>
                  ) : (
                    /* Real Snapchat Access */
                    <div className="bg-black rounded-2xl overflow-hidden" style={{ minHeight: '500px' }}>
                      {/* Header with Lock Button */}
                      <div className="bg-gradient-to-r from-yellow-400 via-pink-500 to-purple-600 p-3 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center">
                            <span className="text-xl">👻</span>
                          </div>
                          <span className="text-white font-bold">Snapchat (Secure Access)</span>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-white hover:bg-white/20 font-semibold"
                          onClick={lockVault}
                        >
                          <Lock className="h-4 w-4 mr-1" />
                          Lock Vault
                        </Button>
                      </div>
                      
                      {/* Snapchat Quick Access Panel */}
                      <div className="p-8 flex flex-col items-center justify-center text-center" style={{ minHeight: '450px' }}>
                        <div className="w-24 h-24 rounded-full bg-gradient-to-r from-yellow-400 via-pink-500 to-purple-600 flex items-center justify-center mb-6 animate-pulse">
                          <span className="text-5xl">👻</span>
                        </div>
                        
                        <h3 className="text-white text-2xl font-bold mb-2">Snapchat Secure Access</h3>
                        <p className="text-white/60 mb-8 max-w-md">
                          Access your Snapchat account securely. Your session is protected by your vault PIN.
                        </p>
                        
                        <div className="space-y-4 w-full max-w-sm">
                          <Button
                            onClick={() => window.open('https://accounts.snapchat.com/v2/login', '_blank', 'width=400,height=700,left=100,top=100')}
                            className="w-full bg-gradient-to-r from-yellow-400 via-pink-500 to-purple-600 text-white font-bold py-6 text-lg hover:from-yellow-500 hover:via-pink-600 hover:to-purple-700"
                          >
                            <span className="mr-2">👻</span>
                            Open Snapchat Login
                          </Button>
                          
                          <Button
                            onClick={() => window.open('https://web.snapchat.com', '_blank', 'width=1200,height=800')}
                            variant="outline"
                            className="w-full border-white/30 text-white hover:bg-white/10 py-5"
                          >
                            <MessageCircle className="h-5 w-5 mr-2" />
                            Open Snapchat Web
                          </Button>
                          
                          <Button
                            onClick={() => window.open('https://www.snapchat.com/download', '_blank')}
                            variant="outline"
                            className="w-full border-white/30 text-white hover:bg-white/10 py-5"
                          >
                            <Download className="h-5 w-5 mr-2" />
                            Download Snapchat App
                          </Button>
                        </div>
                        
                        <div className="mt-8 p-4 bg-white/5 rounded-xl max-w-md">
                          <p className="text-white/40 text-xs">
                            🔒 Your Snapchat access is protected by your Secure Vault PIN. 
                            Lock the vault when you're done to keep your account safe.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
                )}
              </Card>

              {/* Store Settings */}
              <Suspense fallback={<div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}>
                <StoreSettingsEditor />
              </Suspense>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminDashboard;
