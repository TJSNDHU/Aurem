import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Smartphone, X, Plus, Download, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

// AURA-GEN Luxury Theme Colors
const COLORS = {
  void: "#05050A",
  card: "#0A0A10",
  surface: "#12121A",
  gold: "#C9A86E",
  goldDeep: "#A68B4B",
  champagne: "#F5E6D3",
  text: "#F5F3EF",
  textSub: "#B8B5AF",
  textDim: "#6A675F",
  border: "rgba(201,168,110,0.15)",
  borderGold: "rgba(201,168,110,0.35)",
};

// Global handler to capture the install prompt early (before component mounts)
if (typeof window !== 'undefined' && !window.pwaInstallPromptHandlerAdded) {
  window.pwaInstallPromptHandlerAdded = true;
  window.addEventListener('beforeinstallprompt', (e) => {
    console.log('PWA: Global beforeinstallprompt captured');
    e.preventDefault();
    window.deferredPWAPrompt = e;
  });
}

const PWAInstallBanner = () => {
  const location = useLocation();
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showBanner, setShowBanner] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [showIOSInstructions, setShowIOSInstructions] = useState(false);
  
  // Hide on bio-scan and related quiz pages, OROÉ pages, LA VELA pages, admin pages, and PWA
  const hiddenPaths = ['/Bio-Age-Repair-Scan', '/quiz', '/skin-scan', '/oroe', '/ritual', '/la-vela-bianca', '/lavela', '/admin', '/new-admin', '/reroots-admin', '/pwa'];
  const shouldHideOnPath = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));

  useEffect(() => {
    // =======================================================
    // SERVICE WORKER REGISTRATION - Robust, No-Retry Version
    // Prevents "Double Loading" performance killer
    // =======================================================
    if ('serviceWorker' in navigator) {
      // Check if we've already failed registration (stop retry loop)
      const swFailCount = parseInt(sessionStorage.getItem('sw-fail-count') || '0');
      const SW_MAX_RETRIES = 1; // Only try once per session to prevent TBT hit
      
      if (swFailCount >= SW_MAX_RETRIES) {
        console.log('ReRoots PWA: Service Worker disabled for this session (previous failures)');
        // Unregister any broken service workers
        navigator.serviceWorker.getRegistrations().then((registrations) => {
          registrations.forEach((registration) => {
            registration.unregister();
            console.log('ReRoots PWA: Unregistered broken Service Worker');
          });
        });
        return;
      }

      window.addEventListener('load', () => {
        // Add timeout to prevent blocking
        const swTimeout = setTimeout(() => {
          console.warn('ReRoots PWA: Service Worker registration timed out');
          sessionStorage.setItem('sw-fail-count', String(swFailCount + 1));
        }, 5000);

        navigator.serviceWorker.register('/service-worker.js')
          .then((registration) => {
            clearTimeout(swTimeout);
            sessionStorage.removeItem('sw-fail-count'); // Reset on success
            console.log('ReRoots PWA: Service Worker registered', registration.scope);
            
            // Check for updates (non-blocking)
            registration.update().catch(() => {});
            
            // Force the new service worker to activate
            if (registration.waiting) {
              registration.waiting.postMessage({ type: 'SKIP_WAITING' });
            }
            
            // Clear old caches (keep current version v7)
            if ('caches' in window) {
              caches.keys().then((names) => {
                names.forEach((name) => {
                  if (!name.includes('v7')) {
                    caches.delete(name);
                  }
                });
              }).catch(() => {});
            }
            
            // Listen for new service worker
            registration.addEventListener('updatefound', () => {
              const newWorker = registration.installing;
              if (newWorker) {
                newWorker.addEventListener('statechange', () => {
                  if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                    console.log('ReRoots PWA: New version available');
                    // Don't auto-reload - let user decide
                  }
                });
              }
            });
          })
          .catch((error) => {
            clearTimeout(swTimeout);
            console.warn('ReRoots PWA: Service Worker registration failed', error.message);
            sessionStorage.setItem('sw-fail-count', String(swFailCount + 1));
            
            // Unregister any broken service workers to stop retry loop
            navigator.serviceWorker.getRegistrations().then((registrations) => {
              registrations.forEach((registration) => {
                registration.unregister();
              });
            });
          });
      }, { once: true }); // Only run once
    }

    // Check if iOS
    const isIOSDevice = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    setIsIOS(isIOSDevice);

    // Check if already installed
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
    const hasDeclined = localStorage.getItem('pwa-declined');
    const hasInstalled = localStorage.getItem('pwa-installed');
    
    if (isStandalone || hasInstalled) {
      return;
    }

    // Show banner after delay if not declined recently
    const declinedTime = hasDeclined ? parseInt(hasDeclined) : 0;
    const daysSinceDeclined = (Date.now() - declinedTime) / (1000 * 60 * 60 * 24);
    
    // Track page visits
    const pageVisits = parseInt(sessionStorage.getItem('pwa-page-visits') || '0') + 1;
    sessionStorage.setItem('pwa-page-visits', pageVisits.toString());
    
    // Show after 1 page visit AND if not declined in last 7 days (more user-friendly)
    if ((daysSinceDeclined > 7 || !hasDeclined) && pageVisits >= 1) {
      const delay = isIOSDevice ? 5000 : 6000; // Show faster for better conversion
      setTimeout(() => setShowBanner(true), delay);
    }

    // Listen for beforeinstallprompt (Android/Desktop only - not supported on iOS)
    const handler = (e) => {
      console.log('PWA: beforeinstallprompt event fired');
      e.preventDefault();
      setDeferredPrompt(e);
      // Show banner immediately when install prompt is available
      setTimeout(() => setShowBanner(true), 2000);
    };

    window.addEventListener('beforeinstallprompt', handler);
    
    // Also check if the app is already installable (event may have fired before component mount)
    // This handles the case where the component re-mounts
    if (window.deferredPWAPrompt) {
      console.log('PWA: Using cached install prompt');
      setDeferredPrompt(window.deferredPWAPrompt);
    }

    return () => {
      window.removeEventListener('beforeinstallprompt', handler);
    };
  }, []);

  const handleInstall = async () => {
    if (isIOS) {
      setShowIOSInstructions(true);
      return;
    }

    // Try to use local state first, then global cached prompt
    const promptToUse = deferredPrompt || window.deferredPWAPrompt;
    
    if (promptToUse) {
      try {
        console.log('PWA: Triggering install prompt');
        promptToUse.prompt();
        const { outcome } = await promptToUse.userChoice;
        console.log('PWA: Install outcome:', outcome);
        if (outcome === 'accepted') {
          localStorage.setItem('pwa-installed', 'true');
          setShowBanner(false);
        }
        setDeferredPrompt(null);
        window.deferredPWAPrompt = null; // Clear global cache
      } catch (err) {
        console.error('PWA install prompt error:', err);
        // Show manual install instructions if prompt fails
        showManualInstallInstructions();
      }
    } else {
      // No deferred prompt available - show manual install instructions
      console.log('PWA: No install prompt available, showing manual instructions');
      showManualInstallInstructions();
    }
  };

  const showManualInstallInstructions = () => {
    // Try to detect if the user is on Chrome/Edge/other browser
    const isChrome = /Chrome/.test(navigator.userAgent) && !/Edge/.test(navigator.userAgent);
    const isEdge = /Edg/.test(navigator.userAgent);
    const isFirefox = /Firefox/.test(navigator.userAgent);
    const isSamsung = /SamsungBrowser/.test(navigator.userAgent);
    
    let instructions = '';
    if (isChrome || isSamsung) {
      instructions = 'Tap the menu (⋮) at the top right corner and select "Install app" or "Add to Home Screen"';
    } else if (isEdge) {
      instructions = 'Tap the menu (...) at the bottom and select "Add to phone"';
    } else if (isFirefox) {
      instructions = 'Tap the menu at the bottom and select "Install"';
    } else {
      instructions = 'Look for "Install app" or "Add to Home Screen" in your browser menu';
    }
    
    alert(`To install the app:\n\n${instructions}`);
  };

  const handleDismiss = () => {
    localStorage.setItem('pwa-declined', Date.now().toString());
    setShowBanner(false);
    setShowIOSInstructions(false);
  };

  if (!showBanner || shouldHideOnPath) return null;

  // Luxury AURA-GEN Style Banner
  return (
    <>
      {/* iOS-specific Banner with instructions */}
      {isIOS ? (
        <div className="fixed bottom-4 left-4 right-4 z-[9999] sm:left-auto sm:right-4 sm:w-96 animate-in slide-in-from-bottom-4 duration-500">
          <div style={{
            background: `linear-gradient(160deg, ${COLORS.card}, ${COLORS.void})`,
            border: `1px solid ${COLORS.borderGold}`,
            borderRadius: '16px',
            overflow: 'hidden',
            boxShadow: `0 20px 60px rgba(0,0,0,0.5), 0 0 40px ${COLORS.gold}15`
          }}>
            {/* Header */}
            <div style={{
              background: `linear-gradient(135deg, ${COLORS.goldDeep}, ${COLORS.gold})`,
              padding: '14px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}>
              <div style={{
                background: 'rgba(255,255,255,0.15)',
                backdropFilter: 'blur(8px)',
                borderRadius: '10px',
                padding: '10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Sparkles style={{ width: 22, height: 22, color: 'white' }} />
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ fontFamily: 'Cormorant Garamond, serif', fontSize: '16px', fontWeight: 500, color: COLORS.void, margin: 0 }}>
                  AURA-GEN Experience
                </p>
                <p style={{ fontFamily: 'Inter, sans-serif', fontSize: '11px', color: 'rgba(5,5,10,0.7)', margin: 0, letterSpacing: '0.05em' }}>
                  Add to Home Screen
                </p>
              </div>
              <button 
                onClick={handleDismiss}
                style={{ background: 'rgba(0,0,0,0.1)', border: 'none', borderRadius: '8px', padding: '6px', cursor: 'pointer' }}
                data-testid="pwa-dismiss-btn"
              >
                <X style={{ width: 18, height: 18, color: COLORS.void }} />
              </button>
            </div>
            
            {/* Content */}
            <div style={{ padding: '18px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '18px' }}>
                {[
                  { num: 1, text: 'Tap Share', sub: 'in Safari toolbar', icon: '↑' },
                  { num: 2, text: 'Add to Home Screen', sub: 'scroll to find it', icon: '+' },
                  { num: 3, text: 'Tap Add', sub: 'to confirm', icon: '✓' }
                ].map((step) => (
                  <div key={step.num} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: '50%',
                      background: `linear-gradient(135deg, ${COLORS.goldDeep}, ${COLORS.gold})`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontFamily: 'Cormorant Garamond, serif', fontSize: '13px', fontWeight: 600, color: COLORS.void
                    }}>{step.num}</div>
                    <div style={{ flex: 1 }}>
                      <p style={{ fontFamily: 'Cormorant Garamond, serif', fontSize: '14px', color: COLORS.text, margin: 0 }}>{step.text}</p>
                      <p style={{ fontFamily: 'Inter, sans-serif', fontSize: '10px', color: COLORS.textDim, margin: 0 }}>{step.sub}</p>
                    </div>
                    <div style={{
                      background: COLORS.surface, border: `1px solid ${COLORS.border}`,
                      borderRadius: '6px', padding: '4px 10px',
                      fontFamily: 'Inter, sans-serif', fontSize: '12px', color: COLORS.gold
                    }}>{step.icon}</div>
                  </div>
                ))}
              </div>
              
              <button 
                onClick={handleDismiss}
                style={{
                  width: '100%', padding: '12px',
                  background: `linear-gradient(135deg, ${COLORS.goldDeep}, ${COLORS.gold})`,
                  border: 'none', borderRadius: '8px',
                  fontFamily: 'Inter, sans-serif', fontSize: '11px', fontWeight: 600,
                  letterSpacing: '0.12em', textTransform: 'uppercase',
                  color: COLORS.void, cursor: 'pointer'
                }}
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Android/Desktop Install Banner - Luxury AURA-GEN Style */
        <div className="fixed bottom-4 left-4 right-4 z-[9999] sm:left-auto sm:right-4 sm:w-96 animate-in slide-in-from-bottom-4 duration-500">
          <div style={{
            background: `linear-gradient(160deg, ${COLORS.card}, ${COLORS.void})`,
            border: `1px solid ${COLORS.borderGold}`,
            borderRadius: '16px',
            overflow: 'hidden',
            boxShadow: `0 20px 60px rgba(0,0,0,0.5), 0 0 40px ${COLORS.gold}15`
          }}>
            {/* Header */}
            <div style={{
              background: `linear-gradient(135deg, ${COLORS.goldDeep}, ${COLORS.gold})`,
              padding: '14px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}>
              <div style={{
                background: 'rgba(255,255,255,0.15)',
                backdropFilter: 'blur(8px)',
                borderRadius: '10px',
                padding: '10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Sparkles style={{ width: 22, height: 22, color: 'white' }} />
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ fontFamily: 'Cormorant Garamond, serif', fontSize: '16px', fontWeight: 500, color: COLORS.void, margin: 0 }}>
                  Install AURA-GEN
                </p>
                <p style={{ fontFamily: 'Inter, sans-serif', fontSize: '11px', color: 'rgba(5,5,10,0.7)', margin: 0, letterSpacing: '0.05em' }}>
                  Premium Skincare Experience
                </p>
              </div>
              <button 
                onClick={handleDismiss}
                style={{ background: 'rgba(0,0,0,0.1)', border: 'none', borderRadius: '8px', padding: '6px', cursor: 'pointer' }}
                data-testid="pwa-dismiss-btn"
              >
                <X style={{ width: 18, height: 18, color: COLORS.void }} />
              </button>
            </div>
            
            {/* Content */}
            <div style={{ padding: '18px' }}>
              {/* Benefits */}
              <div style={{ 
                display: 'flex', gap: '8px', marginBottom: '16px',
                padding: '12px', background: COLORS.surface, borderRadius: '10px',
                border: `1px solid ${COLORS.border}`
              }}>
                {['Offline Access', 'Fast Loading', 'Easy Checkout'].map((benefit, i) => (
                  <div key={benefit} style={{
                    flex: 1, textAlign: 'center', padding: '8px 4px',
                    borderRight: i < 2 ? `1px solid ${COLORS.border}` : 'none'
                  }}>
                    <p style={{ fontFamily: 'Cormorant Garamond, serif', fontSize: '11px', color: COLORS.gold, margin: 0 }}>✦</p>
                    <p style={{ fontFamily: 'Inter, sans-serif', fontSize: '9px', color: COLORS.textSub, margin: '4px 0 0', letterSpacing: '0.03em' }}>{benefit}</p>
                  </div>
                ))}
              </div>
              
              {/* Buttons */}
              <div style={{ display: 'flex', gap: '10px' }}>
                <button 
                  onClick={handleInstall}
                  style={{
                    flex: 2, padding: '12px 16px',
                    background: `linear-gradient(135deg, ${COLORS.goldDeep}, ${COLORS.gold})`,
                    border: 'none', borderRadius: '8px',
                    fontFamily: 'Inter, sans-serif', fontSize: '11px', fontWeight: 600,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    color: COLORS.void, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                    opacity: 1,
                    transition: 'transform 0.2s, box-shadow 0.2s'
                  }}
                  onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-1px)'}
                  onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
                  data-testid="pwa-install-btn"
                >
                  <Download style={{ width: 14, height: 14 }} />
                  {(deferredPrompt || window.deferredPWAPrompt) ? 'Install' : 'How to Install'}
                </button>
                <button 
                  onClick={handleDismiss}
                  style={{
                    flex: 1, padding: '12px',
                    background: 'transparent',
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: '8px',
                    fontFamily: 'Inter, sans-serif', fontSize: '10px',
                    letterSpacing: '0.08em', color: COLORS.textDim,
                    cursor: 'pointer'
                  }}
                >
                  Later
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* iOS Instructions Modal - Luxury Style */}
      {showIOSInstructions && (
        <div 
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(5,5,10,0.85)',
            backdropFilter: 'blur(12px)',
            zIndex: 10000,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '20px'
          }}
          onClick={handleDismiss}
        >
          <div 
            style={{
              background: `linear-gradient(160deg, ${COLORS.card}, ${COLORS.void})`,
              border: `1px solid ${COLORS.borderGold}`,
              borderRadius: '20px',
              maxWidth: '360px', width: '100%',
              padding: '28px',
              boxShadow: `0 30px 80px rgba(0,0,0,0.6), 0 0 60px ${COLORS.gold}10`
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Logo */}
            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
              <div style={{
                width: 72, height: 72, margin: '0 auto 16px',
                borderRadius: '18px',
                background: `linear-gradient(135deg, ${COLORS.goldDeep}, ${COLORS.gold})`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: `0 8px 32px ${COLORS.gold}33`
              }}>
                <Sparkles style={{ width: 32, height: 32, color: COLORS.void }} />
              </div>
              <p style={{ fontFamily: 'Inter, sans-serif', fontSize: '9px', letterSpacing: '0.2em', color: COLORS.gold, margin: '0 0 6px' }}>AURA-GEN</p>
              <p style={{ fontFamily: 'Cormorant Garamond, serif', fontSize: '22px', fontWeight: 400, color: COLORS.text, margin: 0 }}>
                Install on iOS
              </p>
              <p style={{ fontFamily: 'Inter, sans-serif', fontSize: '11px', color: COLORS.textDim, margin: '6px 0 0' }}>
                Add to your home screen
              </p>
            </div>
            
            {/* Steps */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '24px' }}>
              {[
                { num: 1, title: 'Tap Share button', desc: 'At the bottom of Safari', icon: '↑' },
                { num: 2, title: 'Find "Add to Home Screen"', desc: 'Scroll down in the menu', icon: '+' },
                { num: 3, title: 'Tap Add', desc: 'Confirm to install', icon: '✓' }
              ].map((step) => (
                <div key={step.num} style={{
                  display: 'flex', alignItems: 'flex-start', gap: '14px',
                  padding: '14px', background: COLORS.surface,
                  border: `1px solid ${COLORS.border}`, borderRadius: '12px'
                }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                    background: `linear-gradient(135deg, ${COLORS.goldDeep}, ${COLORS.gold})`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontFamily: 'Cormorant Garamond, serif', fontSize: '14px', fontWeight: 600, color: COLORS.void
                  }}>{step.num}</div>
                  <div style={{ flex: 1 }}>
                    <p style={{ fontFamily: 'Cormorant Garamond, serif', fontSize: '14px', color: COLORS.text, margin: 0 }}>{step.title}</p>
                    <p style={{ fontFamily: 'Inter, sans-serif', fontSize: '10px', color: COLORS.textDim, margin: '4px 0 0' }}>{step.desc}</p>
                  </div>
                  <div style={{
                    background: COLORS.card, border: `1px solid ${COLORS.borderGold}`,
                    borderRadius: '6px', padding: '6px 10px',
                    fontFamily: 'Inter, sans-serif', fontSize: '14px', color: COLORS.gold
                  }}>{step.icon}</div>
                </div>
              ))}
            </div>
            
            <button 
              onClick={handleDismiss}
              style={{
                width: '100%', padding: '14px',
                background: `linear-gradient(135deg, ${COLORS.goldDeep}, ${COLORS.gold})`,
                border: 'none', borderRadius: '10px',
                fontFamily: 'Inter, sans-serif', fontSize: '11px', fontWeight: 600,
                letterSpacing: '0.14em', textTransform: 'uppercase',
                color: COLORS.void, cursor: 'pointer'
              }}
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </>
  );
};

export default PWAInstallBanner;
