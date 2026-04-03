import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useSearchParams, useLocation } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth, useStoreSettings, useTranslation } from "@/contexts";
import PromoPopup from "@/components/PromoPopup";
import { API } from "@/lib/api";
import { GoogleAuthButton } from "@/components/GoogleAuthButton";

// UI Translations fallback
const UI_TRANSLATIONS = {
  en: { 
    login: "Login", 
    signup: "Sign Up", 
    email: "Email", 
    password: "Password",
    first_name: "First Name",
    last_name: "Last Name",
    phone: "Phone Number",
    optional: "Optional",
    forgot_password: "Forgot password?",
    sign_in: "Sign In",
    create_account: "Create Account",
    signing_in: "Signing in...",
    creating_account: "Creating account...",
    dont_have_account: "Don't have an account?",
    join_community_link: "Create one",
    already_have_account: "Already have an account?",
    sign_in_link: "Sign in"
  }
};

const LoginPage = () => {
  const [searchParams] = useSearchParams();
  const hasSignupParam = searchParams.get('signup') === 'true';
  
  const [isLogin, setIsLogin] = useState(!hasSignupParam);
  const [loading, setLoading] = useState(false);
  const [loginBackground, setLoginBackground] = useState(null);
  const [loginMethod, setLoginMethod] = useState("email");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(localStorage.getItem("reroots_remember_me") === "true");
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
    phone: ""
  });
  const { login, register } = useAuth();
  const { settings } = useStoreSettings();
  const { currentLang } = useTranslation() || {};
  const navigate = useNavigate();
  
  const thankYouMessages = settings?.thank_you_messages || {};
  const lang = currentLang || localStorage.getItem("reroots_lang") || "en-CA";
  const t = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS.en;

  useEffect(() => {
    axios.get(`${API}/public/login-backgrounds`)
      .then(res => setLoginBackground(res.data.login_background_image))
      .catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      let loggedInUser;
      if (isLogin) {
        const loginData = loginMethod === "phone" 
          ? { phone: formData.phone, password: formData.password }
          : { email: formData.email, password: formData.password };
        loggedInUser = await login(loginData.email || null, loginData.password, loginData.phone || null, rememberMe);
        localStorage.setItem('reroots_returning_customer', 'true');
        toast.success(t.welcome_back || "Welcome back!");
      } else {
        loggedInUser = await register(formData);
        localStorage.setItem('reroots_returning_customer', 'true');
        toast.success(thankYouMessages.registration || "Account created! Welcome to ReRoots!");
      }
      
      if (loggedInUser?.is_team_member || loggedInUser?.is_admin) {
        navigate("/reroots-admin");
        return;
      }
      
      // Check redirect from sessionStorage first, then from URL query param
      const redirectFromStorage = sessionStorage.getItem('redirectAfterLogin');
      const redirectFromUrl = searchParams.get('redirect');
      const redirectTo = redirectFromStorage || redirectFromUrl || "/";
      sessionStorage.removeItem('redirectAfterLogin');
      navigate(redirectTo);
    } catch (error) {
      const errorDetail = error.response?.data?.detail || "Authentication failed";
      if (isLogin && errorDetail === "Invalid credentials") {
        toast.error("Invalid email or password. Don't have an account? Click 'Create Account' below.");
      } else {
        toast.error(errorDetail);
      }
    }
    setLoading(false);
  };

  // Optimized background image via Cloudinary - use smaller mobile version
  // Desktop: w_1920, Mobile: w_768 (matched to viewport)
  const getOptimizedBg = (url) => {
    const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
    const width = isMobile ? 768 : 1920;
    const quality = isMobile ? 60 : 70;
    if (url?.includes('cloudinary.com')) return url;
    return `https://res.cloudinary.com/ddpphzqdg/image/fetch/w_${width},q_${quality},f_auto/${encodeURIComponent(url)}`;
  };
  
  const defaultBg = "https://res.cloudinary.com/ddpphzqdg/image/fetch/w_768,q_60,f_auto/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_mission-control-84%2Fartifacts%2Ff80chpuq_1767220017661.jpg";
  const bgUrl = loginBackground ? getOptimizedBg(loginBackground) : defaultBg;

  return (
    <div 
      className="min-h-screen flex items-center justify-center py-12 px-4"
      style={{
        background: `linear-gradient(135deg, rgba(45,42,46,0.85) 0%, rgba(45,42,46,0.7) 100%), url('${bgUrl}') center/cover fixed`,
      }}
    >
      <div className="w-full max-w-md relative">
        <PromoPopup settings={settings} />
        
        <Card className="shadow-2xl border-0 bg-white/95 backdrop-blur-sm rounded-xl overflow-hidden" style={{ borderTop: '4px solid #C9A86C' }}>
          <CardHeader className="text-center pt-8 pb-4">
            <img 
              src="https://res.cloudinary.com/ddpphzqdg/image/fetch/w_200,h_64,c_fit,q_auto,f_auto/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_a381cf1d-579d-4c54-9ee9-c2aab86c5628%2Fartifacts%2F2n6enhsj_1769103145313.png" 
              alt="ReRoots Beauty Enhancer" 
              width="200"
              height="64"
              className="h-16 w-auto object-contain mx-auto mb-4"
              style={{ mixBlendMode: 'multiply' }}
              loading="eager"
              fetchPriority="high"
            />
            <CardTitle className="font-display text-xl text-[#2D2A2E]">
              {isLogin ? (
                <>
                  {t.welcome_back}<br />
                  <span className="text-[#2D2A2E]">{t.esteemed_client}</span>
                </>
              ) : (
                <>
                  {t.create_account}<br />
                  <span className="text-[#2D2A2E]">{t.join_community_link}</span>
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {!isLogin && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="first_name">{t.first_name || "First Name"}</Label>
                    <Input
                      id="first_name"
                      required={!isLogin}
                      value={formData.first_name}
                      onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                      data-testid="register-first-name"
                    />
                  </div>
                  <div>
                    <Label htmlFor="last_name">{t.last_name || "Last Name"}</Label>
                    <Input
                      id="last_name"
                      required={!isLogin}
                      value={formData.last_name}
                      onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                      data-testid="register-last-name"
                    />
                  </div>
                </div>
              )}
              {!isLogin && (
                <div>
                  <Label htmlFor="phone">{t.phone || "Phone Number"} <span className="text-red-500">*</span></Label>
                  <Input
                    id="phone"
                    type="tel"
                    required={!isLogin}
                    placeholder="+1 (xxx) xxx-xxxx"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    data-testid="register-phone"
                  />
                  <p className="text-xs text-gray-500 mt-1">Required for order updates & delivery notifications</p>
                </div>
              )}
              
              {isLogin && (
                <div className="flex rounded-lg bg-gray-100 p-1 mb-2">
                  <button
                    type="button"
                    onClick={() => setLoginMethod("email")}
                    className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                      loginMethod === "email" 
                        ? "bg-white shadow text-[#2D2A2E]" 
                        : "text-[#5A5A5A] hover:text-[#2D2A2E]"
                    }`}
                  >
                    📧 {t.email || "Email"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setLoginMethod("phone")}
                    className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                      loginMethod === "phone" 
                        ? "bg-white shadow text-[#2D2A2E]" 
                        : "text-[#5A5A5A] hover:text-[#2D2A2E]"
                    }`}
                  >
                    📱 {t.phone || "Phone"}
                  </button>
                </div>
              )}
              
              {(!isLogin || loginMethod === "email") && (
                <div>
                  <Label htmlFor="email">{t.email}</Label>
                  <Input
                    id="email"
                    type="email"
                    required={!isLogin || loginMethod === "email"}
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="email@example.com"
                    data-testid="login-email"
                  />
                </div>
              )}
              
              {isLogin && loginMethod === "phone" && (
                <div>
                  <Label htmlFor="login-phone">{t.phone || "Phone Number"}</Label>
                  <Input
                    id="login-phone"
                    type="tel"
                    required
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    placeholder="+1 (xxx) xxx-xxxx"
                    data-testid="login-phone"
                  />
                </div>
              )}
              
              <div>
                <Label htmlFor="password">{t.password}</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    data-testid="login-password"
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 transition-colors p-1 min-w-[44px] min-h-[44px] flex items-center justify-center"
                    data-testid="toggle-password-visibility"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>
              {isLogin && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="remember-me"
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-300 text-[#C9A86C] focus:ring-[#C9A86C]"
                    />
                    <Label htmlFor="remember-me" className="text-sm text-[#5A5A5A] cursor-pointer">
                      Keep me logged in
                    </Label>
                  </div>
                  <Link
                    to="/forgot-password"
                    className="text-sm text-[#C9A86C] hover:text-[#B8956A] hover:underline"
                  >
                    {t.forgot_password}
                  </Link>
                </div>
              )}
              <Button 
                type="submit" 
                className="w-full text-white font-bold tracking-wider rounded-full py-6 uppercase" 
                style={{ background: 'linear-gradient(135deg, #C9A86C 0%, #B8956A 100%)' }}
                disabled={loading} 
                data-testid="auth-submit"
              >
                {loading ? (isLogin ? t.signing_in : t.creating_account) : (isLogin ? t.sign_in : t.create_account)}
              </Button>
            </form>
            
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-200"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-4 bg-white text-gray-500">or continue with</span>
              </div>
            </div>
            
            {/* Google OAuth Button - Uses Custom Credentials */}
            <GoogleAuthButton
              isAdmin={false}
              onSuccess={(user) => {
                // Redirect to appropriate page after login
                const redirectTo = sessionStorage.getItem('redirectAfterLogin') || '/';
                sessionStorage.removeItem('redirectAfterLogin');
                window.location.href = redirectTo;
              }}
              onError={(error) => console.error('Google login error:', error)}
              buttonText="Continue with Google"
              data-testid="google-login-btn"
            />
            
            <div className="mt-6 text-center">
              <button
                type="button"
                onClick={() => setIsLogin(!isLogin)}
                className="text-sm text-[#888888] hover:text-[#C9A86C] italic"
                data-testid="toggle-auth-mode"
              >
                {isLogin ? `${t.dont_have_account} ${t.join_community_link}` : `${t.already_have_account} ${t.sign_in_link}`}
              </button>
            </div>
          </CardContent>
        </Card>
        
        <div className="absolute bottom-8 right-8 text-white/50 text-2xl">✦</div>
      </div>
    </div>
  );
};

// Google Auth Callback Handler
export const AuthCallback = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const hasProcessed = useRef(false);
  
  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;
    
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    
    // Check URL fragment (hash) for session_id - Emergent returns #session_id=xxx
    const hashParams = new URLSearchParams(window.location.hash.slice(1));
    const sessionId = hashParams.get('session_id');
    
    // Also check query params as fallback
    const searchParams = new URLSearchParams(location.search);
    const querySessionId = searchParams.get('session_id');
    const token = searchParams.get('token');
    const error = searchParams.get('error');
    
    const finalSessionId = sessionId || querySessionId;
    
    console.log('[AuthCallback] Processing:', { 
      hashSessionId: sessionId ? sessionId.substring(0, 10) + '...' : 'none',
      querySessionId: querySessionId ? 'present' : 'none',
      token: token ? 'present' : 'none',
      hash: window.location.hash ? window.location.hash.substring(0, 30) + '...' : 'none',
      href: window.location.href
    });
    
    // Prevent double-processing of the same session_id (critical for StrictMode and HMR)
    if (finalSessionId) {
      const processedKey = `auth_processed_${finalSessionId.substring(0, 20)}`;
      if (sessionStorage.getItem(processedKey)) {
        console.log('[AuthCallback] Session already processed, skipping...');
        // Clear hash and redirect
        window.history.replaceState(null, '', window.location.pathname);
        const redirectTo = sessionStorage.getItem('redirectAfterLogin') || '/';
        sessionStorage.removeItem('redirectAfterLogin');
        window.location.href = redirectTo;
        return;
      }
      // Mark as processing
      sessionStorage.setItem(processedKey, 'processing');
    }
    
    if (error) {
      toast.error(`Authentication failed: ${error}`);
      navigate('/login');
      return;
    }
    
    // Handle Emergent Google OAuth (session_id in hash or query)
    if (finalSessionId) {
      const processedKey = `auth_processed_${finalSessionId.substring(0, 20)}`;
      console.log('[AuthCallback] Exchanging session_id with backend...');
      console.log('[AuthCallback] API URL:', API);
      console.log('[AuthCallback] Session ID (first 10 chars):', finalSessionId.substring(0, 10) + '...');
      
      axios.post(`${API}/auth/google/session`, { session_id: finalSessionId })
        .then(res => {
          console.log('[AuthCallback] Backend response:', res.status, res.data);
          const { token: authToken, user } = res.data;
          
          // Mark as successfully processed
          sessionStorage.setItem(processedKey, 'success');
          
          localStorage.setItem("reroots_token", authToken);
          localStorage.setItem("reroots_user", JSON.stringify(user));
          localStorage.setItem('reroots_returning_customer', 'true');
          
          toast.success(`Welcome${user?.first_name ? ', ' + user.first_name : ''}!`);
          
          // Clear hash from URL
          window.history.replaceState(null, '', window.location.pathname);
          
          if (user?.is_team_member || user?.is_admin) {
            window.location.href = '/admin';
          } else {
            const redirectTo = sessionStorage.getItem('redirectAfterLogin') || '/';
            sessionStorage.removeItem('redirectAfterLogin');
            window.location.href = redirectTo;
          }
        })
        .catch(err => {
          console.error("[AuthCallback] Google auth failed:", err);
          console.error("[AuthCallback] Error response:", err.response?.data);
          console.error("[AuthCallback] Error status:", err.response?.status);
          // Clear processing flag so user can retry
          sessionStorage.removeItem(processedKey);
          toast.error(err.response?.data?.detail || "Authentication failed");
          navigate('/login');
        });
      return;
    }
    
    // Handle direct token flow (legacy)
    if (token) {
      localStorage.setItem("reroots_token", token);
      
      axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      .then(res => {
        localStorage.setItem("reroots_user", JSON.stringify(res.data));
        localStorage.setItem('reroots_returning_customer', 'true');
        toast.success("Welcome to ReRoots!");
        
        if (res.data?.is_team_member || res.data?.is_admin) {
          window.location.href = '/admin';
        } else {
          const redirectTo = sessionStorage.getItem('redirectAfterLogin') || '/';
          sessionStorage.removeItem('redirectAfterLogin');
          window.location.href = redirectTo;
        }
      })
      .catch(err => {
        console.error("Failed to fetch user:", err);
        toast.error("Failed to complete authentication");
        localStorage.removeItem("reroots_token");
        navigate('/login');
      });
      return;
    }
    
    toast.error("No authentication data received");
    navigate('/login');
  }, [location, navigate]);
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#FDF9F9]">
      <div className="text-center">
        <div className="w-16 h-16 border-4 border-[#F8A5B8] border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-[#5A5A5A]">Completing authentication...</p>
      </div>
    </div>
  );
};

export default LoginPage;
