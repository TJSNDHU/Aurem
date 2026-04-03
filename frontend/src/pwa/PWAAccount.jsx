/**
 * ReRoots AI PWA Account Tab
 * Unified authentication with OLD app + NEW biometric security
 */

import React, { useState, useEffect } from 'react';
import { 
  User, Mail, Phone, MapPin, Package, Heart, Gift, Star, 
  LogOut, ChevronRight, Shield, Bell, Settings, Loader2,
  Eye, EyeOff, Lock
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Safe auth hook
const useSafeAuth = () => {
  try {
    const auth = useAuth();
    return auth || { user: null, login: async () => {}, register: async () => {}, logout: () => {}, loading: false };
  } catch (e) {
    return { user: null, login: async () => {}, register: async () => {}, logout: () => {}, loading: false };
  }
};

export function PWAAccount() {
  const { user, login, register, logout, loading: authLoading } = useSafeAuth();
  const [mode, setMode] = useState('signin'); // 'signin' | 'register' | 'profile'
  const [formLoading, setFormLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loyaltyPoints, setLoyaltyPoints] = useState(0);
  const [orderCount, setOrderCount] = useState(0);
  
  // Form state
  const [form, setForm] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    phone: ''
  });

  // Fetch user stats if logged in
  useEffect(() => {
    if (user) {
      const fetchStats = async () => {
        try {
          const token = localStorage.getItem('reroots_token');
          
          // Get loyalty points
          const loyaltyRes = await fetch(`${API_URL}/api/loyalty/balance`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (loyaltyRes.ok) {
            const data = await loyaltyRes.json();
            setLoyaltyPoints(data.points || 0);
          }

          // Get order count
          const ordersRes = await fetch(`${API_URL}/api/orders/my-orders?limit=1`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (ordersRes.ok) {
            const data = await ordersRes.json();
            setOrderCount(data.total || data.orders?.length || 0);
          }
        } catch (error) {
          console.error('[PWA Account] Stats fetch error:', error);
        }
      };
      fetchStats();
    }
  }, [user]);

  // Handle login
  const handleSignIn = async (e) => {
    e.preventDefault();
    if (!form.email || !form.password) {
      toast.error('Please fill in all fields');
      return;
    }
    
    setFormLoading(true);
    try {
      await login(form.email, form.password);
      toast.success('Welcome back!');
      setForm({ email: '', password: '', first_name: '', last_name: '', phone: '' });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Login failed');
    } finally {
      setFormLoading(false);
    }
  };

  // Handle registration
  const handleRegister = async (e) => {
    e.preventDefault();
    if (!form.email || !form.password || !form.first_name) {
      toast.error('Please fill in all required fields');
      return;
    }
    
    setFormLoading(true);
    try {
      await register({
        email: form.email,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
        phone: form.phone
      });
      toast.success('Account created! Welcome to ReRoots');
      setForm({ email: '', password: '', first_name: '', last_name: '', phone: '' });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Registration failed');
    } finally {
      setFormLoading(false);
    }
  };

  // Handle logout
  const handleLogout = () => {
    logout();
    toast.success('Logged out successfully');
  };

  // Check biometric status
  const hasBiometric = localStorage.getItem('reroots_biometric_credential');

  // If logged in, show profile
  if (user) {
    return (
      <div className="pb-28 px-4">
        {/* Header */}
        <div className="pt-4 pb-6 text-center">
          <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-amber-500/30 to-amber-600/30 flex items-center justify-center">
            <User className="w-10 h-10 text-amber-500" />
          </div>
          <h2 className="text-xl font-bold text-white">
            {user.first_name} {user.last_name}
          </h2>
          <p className="text-white/60 text-sm">{user.email}</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="p-3 rounded-xl bg-white/5 border border-white/10 text-center">
            <Star className="w-5 h-5 text-amber-500 mx-auto mb-1" />
            <p className="text-white font-bold">{loyaltyPoints.toLocaleString()}</p>
            <p className="text-white/40 text-xs">Roots Points</p>
          </div>
          <div className="p-3 rounded-xl bg-white/5 border border-white/10 text-center">
            <Package className="w-5 h-5 text-blue-400 mx-auto mb-1" />
            <p className="text-white font-bold">{orderCount}</p>
            <p className="text-white/40 text-xs">Orders</p>
          </div>
          <div className="p-3 rounded-xl bg-white/5 border border-white/10 text-center">
            <Shield className={`w-5 h-5 ${hasBiometric ? 'text-green-400' : 'text-white/40'} mx-auto mb-1`} />
            <p className="text-white font-bold">{hasBiometric ? 'On' : 'Off'}</p>
            <p className="text-white/40 text-xs">Biometric</p>
          </div>
        </div>

        {/* Menu Items */}
        <div className="space-y-2">
          <MenuButton icon={Package} label="My Orders" sublabel={`${orderCount} orders`} />
          <MenuButton icon={Heart} label="Wishlist" />
          <MenuButton icon={Gift} label="Redeem Points" sublabel={`${loyaltyPoints} available`} />
          <MenuButton icon={MapPin} label="Addresses" />
          <MenuButton icon={Bell} label="Notifications" />
          <MenuButton icon={Shield} label="Security Settings" sublabel={hasBiometric ? 'Biometric enabled' : 'Set up biometric'} />
          <MenuButton icon={Settings} label="App Settings" />
        </div>

        {/* Logout Button */}
        <Button
          onClick={handleLogout}
          variant="outline"
          className="w-full mt-8 h-12 border-red-500/30 text-red-400 hover:bg-red-500/10"
        >
          <LogOut className="w-5 h-5 mr-2" />
          Sign Out
        </Button>

        {/* Account Info Footer */}
        <div className="mt-8 text-center text-white/40 text-xs">
          <p>Member since {new Date(user.created_at || Date.now()).toLocaleDateString()}</p>
          <p className="mt-1">Account ID: {user._id?.slice(-8) || user.id?.slice(-8)}</p>
        </div>
      </div>
    );
  }

  // Auth Forms (Sign In / Register)
  return (
    <div className="pb-28 px-4">
      {/* Header */}
      <div className="pt-4 pb-8 text-center">
        <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-amber-500/20 to-amber-600/20 flex items-center justify-center">
          <Lock className="w-10 h-10 text-amber-500" />
        </div>
        <h2 className="text-2xl font-bold text-white">
          {mode === 'signin' ? 'Welcome Back' : 'Join ReRoots'}
        </h2>
        <p className="text-white/60 text-sm mt-2">
          {mode === 'signin' 
            ? 'Sign in to access your orders and skin vault' 
            : 'Create an account to start your skincare journey'
          }
        </p>
      </div>

      {/* Auth Form */}
      <form onSubmit={mode === 'signin' ? handleSignIn : handleRegister} className="space-y-4">
        {mode === 'register' && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-white/60 text-xs mb-1 block">First Name *</label>
              <Input
                type="text"
                value={form.first_name}
                onChange={e => setForm({ ...form, first_name: e.target.value })}
                placeholder="John"
                className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
              />
            </div>
            <div>
              <label className="text-white/60 text-xs mb-1 block">Last Name</label>
              <Input
                type="text"
                value={form.last_name}
                onChange={e => setForm({ ...form, last_name: e.target.value })}
                placeholder="Doe"
                className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
              />
            </div>
          </div>
        )}

        <div>
          <label className="text-white/60 text-xs mb-1 block">Email *</label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <Input
              type="email"
              value={form.email}
              onChange={e => setForm({ ...form, email: e.target.value })}
              placeholder="your@email.com"
              className="pl-10 bg-white/10 border-white/20 text-white placeholder:text-white/40"
            />
          </div>
        </div>

        {mode === 'register' && (
          <div>
            <label className="text-white/60 text-xs mb-1 block">Phone (optional)</label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
              <Input
                type="tel"
                value={form.phone}
                onChange={e => setForm({ ...form, phone: e.target.value })}
                placeholder="+1 (555) 000-0000"
                className="pl-10 bg-white/10 border-white/20 text-white placeholder:text-white/40"
              />
            </div>
          </div>
        )}

        <div>
          <label className="text-white/60 text-xs mb-1 block">Password *</label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <Input
              type={showPassword ? 'text' : 'password'}
              value={form.password}
              onChange={e => setForm({ ...form, password: e.target.value })}
              placeholder="••••••••"
              className="pl-10 pr-10 bg-white/10 border-white/20 text-white placeholder:text-white/40"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2"
            >
              {showPassword ? (
                <EyeOff className="w-5 h-5 text-white/40" />
              ) : (
                <Eye className="w-5 h-5 text-white/40" />
              )}
            </button>
          </div>
        </div>

        <Button
          type="submit"
          disabled={formLoading}
          className="w-full h-12 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-black font-semibold"
        >
          {formLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : mode === 'signin' ? (
            'Sign In'
          ) : (
            'Create Account'
          )}
        </Button>
      </form>

      {/* Switch Mode */}
      <div className="mt-6 text-center">
        {mode === 'signin' ? (
          <p className="text-white/60 text-sm">
            Don't have an account?{' '}
            <button 
              onClick={() => setMode('register')}
              className="text-amber-500 font-medium"
            >
              Sign up
            </button>
          </p>
        ) : (
          <p className="text-white/60 text-sm">
            Already have an account?{' '}
            <button 
              onClick={() => setMode('signin')}
              className="text-amber-500 font-medium"
            >
              Sign in
            </button>
          </p>
        )}
      </div>

      {/* Security Note */}
      <div className="mt-8 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
        <div className="flex items-start gap-3">
          <Shield className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-white font-medium text-sm">Biometric Security Available</h4>
            <p className="text-white/60 text-xs mt-1">
              After signing in, you can enable FaceID or Fingerprint to protect your encrypted skin vault.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Menu Button Component
function MenuButton({ icon: Icon, label, sublabel, onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-full p-4 rounded-xl bg-white/5 border border-white/10 flex items-center gap-4 hover:bg-white/10 transition-colors"
    >
      <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center">
        <Icon className="w-5 h-5 text-amber-500" />
      </div>
      <div className="flex-1 text-left">
        <p className="text-white font-medium">{label}</p>
        {sublabel && <p className="text-white/40 text-xs">{sublabel}</p>}
      </div>
      <ChevronRight className="w-5 h-5 text-white/40" />
    </button>
  );
}

export default PWAAccount;
