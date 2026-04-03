/**
 * AUREM Platform Authentication
 * Login and Onboarding flow
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sparkles, Eye, EyeOff, AlertCircle, Check, ArrowRight, ArrowLeft } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Industry options with icons
const INDUSTRIES = [
  { id: 'ecommerce', label: 'E-Commerce', icon: '🛒' },
  { id: 'saas', label: 'SaaS / Software', icon: '💻' },
  { id: 'agency', label: 'Agency', icon: '🏢' },
  { id: 'healthcare', label: 'Healthcare', icon: '🏥' },
  { id: 'finance', label: 'Finance', icon: '💰' },
  { id: 'retail', label: 'Retail', icon: '🏪' },
  { id: 'education', label: 'Education', icon: '📚' },
  { id: 'other', label: 'Other', icon: '✨' },
];

const TEAM_SIZES = [
  { id: 'solo', label: 'Just me' },
  { id: '2-10', label: '2-10' },
  { id: '11-50', label: '11-50' },
  { id: '51-200', label: '51-200' },
  { id: '200+', label: '200+' },
];

const GOALS = [
  'Automate customer support',
  'Generate more leads',
  'Improve sales process',
  'Reduce operational costs',
  'Scale marketing efforts',
  'Build AI-powered products',
];

// ═══════════════════════════════════════════════════════════════════════════════
// LOGIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

const LoginForm = ({ onSwitchToSignup }) => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/platform/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      const data = await response.json();

      if (response.ok && data.token) {
        localStorage.setItem('platform_token', data.token);
        localStorage.setItem('platform_user', JSON.stringify(data));
        localStorage.setItem('faceid_email', email); // Store for FaceID
        
        // If first login, offer FaceID setup
        if (!faceIDTrained) {
          setSetupFaceID(true);
          return;
        }
        
        navigate('/dashboard');
      } else {
        setError(data.detail || 'Invalid email or password');
      }
    } catch (err) {
      setError('Connection failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleFaceIDSuccess = async (email) => {
    // Auto-login after FaceID recognition
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/platform/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email: email,
          password: 'Admin123' // In production, use a special FaceID token
        })
      });

      const data = await response.json();

      if (response.ok && data.token) {
        localStorage.setItem('platform_token', data.token);
        localStorage.setItem('platform_user', JSON.stringify(data));
        navigate('/dashboard');
      }
    } catch (err) {
      setError('Login failed after FaceID');
      setUseFaceID(false);
    } finally {
      setLoading(false);
    }
  };
  
  const handleFaceIDTrainingComplete = () => {
    navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center mb-4">
            <Sparkles className="w-8 h-8 text-[#050505]" />
          </div>
          <h1 className="text-2xl font-light text-[#F4F4F4] tracking-wider">AUREM</h1>
          <p className="text-xs text-[#666] mt-1">BUSINESS AI PLATFORM</p>
        </div>

        {/* Login Card */}
        <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-8">
          <h2 className="text-xl text-[#F4F4F4] mb-1">Sign In</h2>
          <p className="text-sm text-[#666] mb-6">Access AUREM Command Center</p>

            {error && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@company.com"
                data-testid="login-email"
                className="w-full px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:border-[#D4AF37] focus:outline-none transition-colors"
                required
              />
            </div>

            <div>
              <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  data-testid="login-password"
                  className="w-full px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:border-[#D4AF37] focus:outline-none transition-colors pr-12"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#666] hover:text-[#AAA]"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              data-testid="login-submit"
              className="w-full py-3 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] font-semibold rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-[#050505] border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  Access Command Center
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-[#666]">
              Don't have an account?{' '}
              <button
                onClick={onSwitchToSignup}
                className="text-[#D4AF37] hover:underline"
              >
                Deploy AUREM
              </button>
            </p>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-[#555] mt-6">
          Protected by enterprise-grade security
        </p>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// ONBOARDING COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

const OnboardingForm = ({ onSwitchToLogin }) => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
    company_name: '',
    industry: '',
    team_size: '',
    goals: []
  });

  const totalSteps = 6;

  const updateForm = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const toggleGoal = (goal) => {
    setFormData(prev => ({
      ...prev,
      goals: prev.goals.includes(goal) 
        ? prev.goals.filter(g => g !== goal)
        : [...prev.goals, goal]
    }));
  };

  const handleSubmit = async () => {
    setError('');
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/aurem/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok && data.token) {
        localStorage.setItem('platform_token', data.token);
        localStorage.setItem('platform_user', JSON.stringify(data));
        navigate('/dashboard');
      } else {
        setError(data.detail || 'Registration failed');
      }
    } catch (err) {
      setError('Connection failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 1: return formData.email && formData.password && formData.password.length >= 6;
      case 2: return formData.company_name && formData.industry;
      case 3: return formData.team_size;
      case 4: return formData.goals.length > 0;
      case 5: return formData.full_name;
      default: return true;
    }
  };

  const handleNext = () => {
    if (step < totalSteps) {
      setStep(step + 1);
    } else {
      handleSubmit();
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 mx-auto rounded-xl bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center mb-4">
            <Sparkles className="w-6 h-6 text-[#050505]" />
          </div>
          <h1 className="text-xl font-light text-[#F4F4F4] tracking-wider">AUREM</h1>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-[#666]">Step {step} of {totalSteps}</span>
            <span className="text-xs text-[#D4AF37]">{Math.round((step / totalSteps) * 100)}%</span>
          </div>
          <div className="h-1 bg-[#1A1A1A] rounded-full">
            <div 
              className="h-full bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-full transition-all duration-500"
              style={{ width: `${(step / totalSteps) * 100}%` }}
            />
          </div>
        </div>

        {/* Onboarding Card */}
        <div className="bg-[#0A0A0A] border border-[#1A1A1A] rounded-xl p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Step 1: Credentials */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl text-[#F4F4F4] mb-2">Create your account</h2>
                <p className="text-sm text-[#666]">Start deploying your AI workforce</p>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => updateForm('email', e.target.value)}
                    placeholder="you@company.com"
                    className="w-full px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:border-[#D4AF37] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Password</label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => updateForm('password', e.target.value)}
                    placeholder="Minimum 6 characters"
                    className="w-full px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:border-[#D4AF37] focus:outline-none"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Company Info */}
          {step === 2 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl text-[#F4F4F4] mb-2">Tell us about your business</h2>
                <p className="text-sm text-[#666]">Help us customize your experience</p>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Company Name</label>
                  <input
                    type="text"
                    value={formData.company_name}
                    onChange={(e) => updateForm('company_name', e.target.value)}
                    placeholder="Your company name"
                    className="w-full px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:border-[#D4AF37] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#666] mb-2 uppercase tracking-wider">Industry</label>
                  <div className="grid grid-cols-2 gap-2">
                    {INDUSTRIES.map((industry) => (
                      <button
                        key={industry.id}
                        onClick={() => updateForm('industry', industry.id)}
                        className={`p-3 rounded-lg border text-left transition-all ${
                          formData.industry === industry.id
                            ? 'bg-[#D4AF37]/10 border-[#D4AF37] text-[#D4AF37]'
                            : 'bg-[#050505] border-[#1A1A1A] text-[#AAA] hover:border-[#333]'
                        }`}
                      >
                        <span className="mr-2">{industry.icon}</span>
                        <span className="text-sm">{industry.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Team Size */}
          {step === 3 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl text-[#F4F4F4] mb-2">How big is your team?</h2>
                <p className="text-sm text-[#666]">We'll recommend the right plan</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {TEAM_SIZES.map((size) => (
                  <button
                    key={size.id}
                    onClick={() => updateForm('team_size', size.id)}
                    className={`px-6 py-3 rounded-full border transition-all ${
                      formData.team_size === size.id
                        ? 'bg-[#D4AF37]/10 border-[#D4AF37] text-[#D4AF37]'
                        : 'bg-[#050505] border-[#1A1A1A] text-[#AAA] hover:border-[#333]'
                    }`}
                  >
                    {size.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 4: Goals */}
          {step === 4 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl text-[#F4F4F4] mb-2">What are your goals?</h2>
                <p className="text-sm text-[#666]">Select all that apply</p>
              </div>
              <div className="space-y-2">
                {GOALS.map((goal) => (
                  <button
                    key={goal}
                    onClick={() => toggleGoal(goal)}
                    className={`w-full p-4 rounded-lg border text-left flex items-center justify-between transition-all ${
                      formData.goals.includes(goal)
                        ? 'bg-[#D4AF37]/10 border-[#D4AF37] text-[#D4AF37]'
                        : 'bg-[#050505] border-[#1A1A1A] text-[#AAA] hover:border-[#333]'
                    }`}
                  >
                    <span className="text-sm">{goal}</span>
                    {formData.goals.includes(goal) && <Check className="w-5 h-5" />}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 5: Name */}
          {step === 5 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl text-[#F4F4F4] mb-2">What's your name?</h2>
                <p className="text-sm text-[#666]">We'll personalize your experience</p>
              </div>
              <div>
                <input
                  type="text"
                  value={formData.full_name}
                  onChange={(e) => updateForm('full_name', e.target.value)}
                  placeholder="Your full name"
                  className="w-full px-4 py-3 bg-[#050505] border border-[#1A1A1A] rounded-lg text-[#F4F4F4] placeholder-[#555] focus:border-[#D4AF37] focus:outline-none text-lg"
                  autoFocus
                />
              </div>
            </div>
          )}

          {/* Step 6: Review */}
          {step === 6 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl text-[#F4F4F4] mb-2">Ready to deploy AUREM?</h2>
                <p className="text-sm text-[#666]">Review your information</p>
              </div>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between p-3 bg-[#050505] rounded-lg">
                  <span className="text-[#666]">Email</span>
                  <span className="text-[#F4F4F4]">{formData.email}</span>
                </div>
                <div className="flex justify-between p-3 bg-[#050505] rounded-lg">
                  <span className="text-[#666]">Company</span>
                  <span className="text-[#F4F4F4]">{formData.company_name}</span>
                </div>
                <div className="flex justify-between p-3 bg-[#050505] rounded-lg">
                  <span className="text-[#666]">Industry</span>
                  <span className="text-[#F4F4F4]">{INDUSTRIES.find(i => i.id === formData.industry)?.label}</span>
                </div>
                <div className="flex justify-between p-3 bg-[#050505] rounded-lg">
                  <span className="text-[#666]">Team Size</span>
                  <span className="text-[#F4F4F4]">{formData.team_size}</span>
                </div>
              </div>
            </div>
          )}

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8">
            {step > 1 ? (
              <button
                onClick={() => setStep(step - 1)}
                className="flex items-center gap-2 text-[#666] hover:text-[#AAA] transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
            ) : (
              <button
                onClick={onSwitchToLogin}
                className="text-sm text-[#666] hover:text-[#AAA]"
              >
                Already have an account?
              </button>
            )}
            
            <button
              onClick={handleNext}
              disabled={!canProceed() || loading}
              className="px-6 py-3 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] font-semibold rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-[#050505] border-t-transparent rounded-full animate-spin" />
              ) : step === totalSteps ? (
                <>
                  Deploy AUREM
                  <Sparkles className="w-4 h-4" />
                </>
              ) : (
                <>
                  Continue
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN AUTH COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

const AuremAuth = () => {
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState(searchParams.get('mode') === 'register' ? 'register' : 'login');

  // Check if already logged in
  useEffect(() => {
    const token = localStorage.getItem('platform_token');
    if (token) {
      window.location.href = '/dashboard';
    }
  }, []);

  if (mode === 'register') {
    return <OnboardingForm onSwitchToLogin={() => setMode('login')} />;
  }

  return <LoginForm onSwitchToSignup={() => setMode('register')} />;
};

export default AuremAuth;
