import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Helmet } from 'react-helmet-async';
import { useAuth } from '../../contexts';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { 
  Gift, Loader2, Sparkles, ShoppingBag, Clock, 
  User, Mail, Lock, Eye, EyeOff, Check, AlertTriangle
} from 'lucide-react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const GiftClaimPage = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const { user, login } = useAuth();
  
  // Gift state
  const [giftInfo, setGiftInfo] = useState(null);
  const [loadingGift, setLoadingGift] = useState(true);
  const [giftError, setGiftError] = useState(null);
  
  // Auth state
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'signup'
  const [showPassword, setShowPassword] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    phone: ''
  });
  
  // Claim state
  const [claiming, setClaiming] = useState(false);
  const [claimed, setClaimed] = useState(false);

  // Validate gift token on mount
  useEffect(() => {
    const validateGift = async () => {
      try {
        const res = await axios.get(`${API}/gifts/claim/${token}`);
        setGiftInfo(res.data);
        
        // Pre-fill email if recipient email is known
        if (res.data.recipient_email) {
          setFormData(prev => ({ ...prev, email: res.data.recipient_email }));
        }
      } catch (error) {
        const status = error.response?.status;
        if (status === 404) {
          setGiftError('This gift link is invalid or has already been used.');
        } else if (status === 410) {
          setGiftError('This gift has expired. Please ask the sender for a new gift.');
        } else if (status === 409) {
          setGiftError('This gift has already been claimed.');
        } else {
          setGiftError('Unable to load gift. Please try again.');
        }
      }
      setLoadingGift(false);
    };
    
    validateGift();
  }, [token]);

  // Auto-claim if user is already logged in
  useEffect(() => {
    if (user && giftInfo && !claimed && !claiming) {
      handleClaimGift();
    }
  }, [user, giftInfo]);

  const handleClaimGift = async () => {
    if (!user) {
      toast.error('Please log in or create an account first');
      return;
    }
    
    setClaiming(true);
    try {
      const authToken = localStorage.getItem('reroots_token');
      const res = await axios.post(
        `${API}/gifts/claim/${token}`,
        {},
        { headers: { Authorization: `Bearer ${authToken}` } }
      );
      
      setClaimed(true);
      toast.success(res.data.message || `🎉 ${res.data.points_claimed} points added!`);
      
      // Redirect to shop after 2 seconds
      setTimeout(() => {
        navigate('/shop');
      }, 2000);
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (error.response?.status === 423) {
        toast.error('This gift is being claimed by another user. Please try again in a moment.');
      } else {
        toast.error(detail || 'Failed to claim gift. Please try again.');
      }
    }
    setClaiming(false);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    
    try {
      const res = await axios.post(`${API}/auth/login`, {
        email: formData.email,
        password: formData.password
      });
      
      localStorage.setItem('reroots_token', res.data.token);
      login(res.data.user, res.data.token);
      toast.success('Logged in successfully!');
      
      // Gift will be claimed automatically via useEffect
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Invalid email or password');
    }
    setAuthLoading(false);
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    
    try {
      // Register
      await axios.post(`${API}/auth/register`, {
        email: formData.email,
        password: formData.password,
        first_name: formData.first_name,
        last_name: formData.last_name,
        phone: formData.phone
      });
      
      // Auto-login after registration
      const loginRes = await axios.post(`${API}/auth/login`, {
        email: formData.email,
        password: formData.password
      });
      
      localStorage.setItem('reroots_token', loginRes.data.token);
      login(loginRes.data.user, loginRes.data.token);
      toast.success('Account created successfully!');
      
      // Gift will be claimed automatically via useEffect
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create account');
    }
    setAuthLoading(false);
  };

  // Loading state
  if (loadingGift) {
    return (
      <div className="min-h-screen pt-24 bg-gradient-to-br from-[#FDF9F9] to-[#FFF5F7] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-[#F8A5B8] mx-auto mb-4" />
          <p className="text-[#5A5A5A]">Loading your gift...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (giftError) {
    return (
      <div className="min-h-screen pt-24 bg-gradient-to-br from-[#FDF9F9] to-[#FFF5F7] flex items-center justify-center px-4">
        <Card className="max-w-md w-full">
          <CardContent className="pt-8 pb-8 text-center">
            <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="h-8 w-8 text-amber-600" />
            </div>
            <h1 className="text-xl font-bold text-[#2D2A2E] mb-2">Gift Unavailable</h1>
            <p className="text-[#5A5A5A] mb-6">{giftError}</p>
            <Button onClick={() => navigate('/shop')} className="bg-[#F8A5B8] hover:bg-[#E8959A] text-[#2D2A2E]">
              <ShoppingBag className="h-4 w-4 mr-2" />
              Continue Shopping
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Claimed success state
  if (claimed) {
    return (
      <div className="min-h-screen pt-24 bg-gradient-to-br from-[#FDF9F9] to-[#FFF5F7] flex items-center justify-center px-4">
        <Helmet>
          <title>Gift Claimed! | ReRoots</title>
        </Helmet>
        <Card className="max-w-md w-full overflow-hidden">
          <div className="bg-gradient-to-r from-emerald-500 to-green-500 py-6 text-center">
            <div className="w-16 h-16 rounded-full bg-white flex items-center justify-center mx-auto mb-3">
              <Check className="h-10 w-10 text-emerald-500" />
            </div>
            <h1 className="text-2xl font-bold text-white">Points Claimed!</h1>
          </div>
          <CardContent className="pt-6 pb-8 text-center">
            <div className="text-4xl font-bold text-[#D4AF37] mb-2">
              {giftInfo?.points_amount} <span className="text-xl">points</span>
            </div>
            <p className="text-[#5A5A5A] mb-6">
              Worth <strong>${giftInfo?.points_value?.toFixed(2)}</strong> has been added to your account!
            </p>
            <p className="text-sm text-[#888] mb-6">Redirecting to shop...</p>
            <Button onClick={() => navigate('/shop')} className="bg-[#F8A5B8] hover:bg-[#E8959A] text-[#2D2A2E] w-full">
              <ShoppingBag className="h-4 w-4 mr-2" />
              Start Shopping Now
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 pb-12 bg-gradient-to-br from-[#FDF9F9] to-[#FFF5F7]">
      <Helmet>
        <title>Claim Your Gift | ReRoots</title>
        <meta name="robots" content="noindex, nofollow" />
      </Helmet>
      
      <div className="max-w-lg mx-auto px-4">
        {/* Gift Info Card */}
        <Card className="overflow-hidden mb-6">
          <div className="bg-gradient-to-r from-[#F8A5B8] to-[#FFB6C1] py-8 text-center relative overflow-hidden">
            <div className="absolute inset-0 opacity-10">
              <div className="absolute top-2 left-4 text-6xl">🎁</div>
              <div className="absolute bottom-2 right-4 text-4xl">✨</div>
            </div>
            <div className="relative z-10">
              <Gift className="h-12 w-12 text-white mx-auto mb-3" />
              <h1 className="text-2xl font-bold text-white mb-1">You Received a Gift!</h1>
              <p className="text-white/90">{giftInfo?.sender_name} sent you something special</p>
            </div>
          </div>
          
          <CardContent className="pt-6 pb-6">
            {/* Points Display */}
            <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-xl p-6 text-center border-2 border-[#D4AF37]/30 mb-6">
              <div className="text-5xl font-bold text-[#D4AF37] mb-1">
                {giftInfo?.points_amount}
              </div>
              <div className="text-lg text-[#2D2A2E] font-medium">points</div>
              <div className="text-[#5A5A5A] mt-2">
                Worth <strong className="text-[#F8A5B8]">${giftInfo?.points_value?.toFixed(2)}</strong> off your order!
              </div>
            </div>
            
            {/* Personal Note */}
            {giftInfo?.personal_note && (
              <div className="bg-[#FFF5F7] rounded-lg p-4 mb-6 border-l-4 border-[#F8A5B8]">
                <p className="text-[#5A5A5A] italic">"{giftInfo.personal_note}"</p>
                <p className="text-sm text-[#888] mt-2">— {giftInfo.sender_name}</p>
              </div>
            )}
            
            {/* Expiry Notice */}
            <div className="flex items-center justify-center gap-2 text-amber-600 bg-amber-50 rounded-lg py-2 px-4">
              <Clock className="h-4 w-4" />
              <span className="text-sm">
                Expires: {new Date(giftInfo?.expires_at).toLocaleDateString()}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Auth Card - Only show if not logged in */}
        {!user && (
          <Card>
            <CardContent className="pt-6 pb-6">
              <div className="flex items-center justify-center gap-2 mb-6">
                <Sparkles className="h-5 w-5 text-[#D4AF37]" />
                <h2 className="text-lg font-semibold text-[#2D2A2E]">
                  {authMode === 'login' ? 'Log in to claim your points' : 'Create an account to claim'}
                </h2>
              </div>

              {/* Auth Mode Toggle */}
              <div className="flex rounded-lg bg-gray-100 p-1 mb-6">
                <button
                  onClick={() => setAuthMode('login')}
                  className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                    authMode === 'login'
                      ? 'bg-white text-[#2D2A2E] shadow-sm'
                      : 'text-[#5A5A5A] hover:text-[#2D2A2E]'
                  }`}
                >
                  Log In
                </button>
                <button
                  onClick={() => setAuthMode('signup')}
                  className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                    authMode === 'signup'
                      ? 'bg-white text-[#2D2A2E] shadow-sm'
                      : 'text-[#5A5A5A] hover:text-[#2D2A2E]'
                  }`}
                >
                  Sign Up
                </button>
              </div>

              {/* Login Form */}
              {authMode === 'login' ? (
                <form onSubmit={handleLogin} className="space-y-4">
                  <div>
                    <Label htmlFor="email">Email</Label>
                    <div className="relative mt-1">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <Input
                        id="email"
                        type="email"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        placeholder="your@email.com"
                        className="pl-10"
                        required
                      />
                    </div>
                  </div>
                  
                  <div>
                    <Label htmlFor="password">Password</Label>
                    <div className="relative mt-1">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <Input
                        id="password"
                        type={showPassword ? 'text' : 'password'}
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        placeholder="••••••••"
                        className="pl-10 pr-10"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                  
                  <Button
                    type="submit"
                    disabled={authLoading}
                    className="w-full bg-gradient-to-r from-[#F8A5B8] to-[#FFB6C1] hover:from-[#E8959A] hover:to-[#F8A5B8] text-[#2D2A2E] font-semibold py-6"
                  >
                    {authLoading ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <>
                        <Gift className="h-5 w-5 mr-2" />
                        Log In & Claim Points
                      </>
                    )}
                  </Button>
                </form>
              ) : (
                /* Signup Form */
                <form onSubmit={handleSignup} className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label htmlFor="first_name">First Name</Label>
                      <Input
                        id="first_name"
                        value={formData.first_name}
                        onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                        placeholder="Jane"
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="last_name">Last Name</Label>
                      <Input
                        id="last_name"
                        value={formData.last_name}
                        onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                        placeholder="Doe"
                        required
                      />
                    </div>
                  </div>
                  
                  <div>
                    <Label htmlFor="signup_email">Email</Label>
                    <div className="relative mt-1">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <Input
                        id="signup_email"
                        type="email"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        placeholder="your@email.com"
                        className="pl-10"
                        required
                      />
                    </div>
                  </div>
                  
                  <div>
                    <Label htmlFor="phone">Phone (optional)</Label>
                    <Input
                      id="phone"
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      placeholder="+1 (555) 123-4567"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="signup_password">Password</Label>
                    <div className="relative mt-1">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <Input
                        id="signup_password"
                        type={showPassword ? 'text' : 'password'}
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        placeholder="Create a password"
                        className="pl-10 pr-10"
                        minLength={6}
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                  
                  <Button
                    type="submit"
                    disabled={authLoading}
                    className="w-full bg-gradient-to-r from-[#F8A5B8] to-[#FFB6C1] hover:from-[#E8959A] hover:to-[#F8A5B8] text-[#2D2A2E] font-semibold py-6"
                  >
                    {authLoading ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <>
                        <Sparkles className="h-5 w-5 mr-2" />
                        Create Account & Claim Points
                      </>
                    )}
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        )}

        {/* If logged in, show claim button */}
        {user && !claimed && (
          <Card>
            <CardContent className="pt-6 pb-6 text-center">
              <p className="text-[#5A5A5A] mb-4">
                Logged in as <strong>{user.email}</strong>
              </p>
              <Button
                onClick={handleClaimGift}
                disabled={claiming}
                className="w-full bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-600 hover:to-green-600 text-white font-semibold py-6"
              >
                {claiming ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <>
                    <Gift className="h-5 w-5 mr-2" />
                    Claim {giftInfo?.points_amount} Points Now!
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default GiftClaimPage;
