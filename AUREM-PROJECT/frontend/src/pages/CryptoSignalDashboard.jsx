/**
 * Crypto Signal Engine - Dashboard
 * Single page React app for crypto signals and portfolio tracking
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';

// Colors
const C = {
  bg: '#0a0a0f',
  surface: '#12121a',
  surface2: '#1a1a24',
  border: 'rgba(99,102,241,0.2)',
  text: '#f1f5f9',
  textDim: 'rgba(241,245,249,0.5)',
  primary: '#6366f1',
  green: '#22c55e',
  red: '#ef4444',
  gold: '#f59e0b',
  blue: '#3b82f6'
};

// API Base URL
const API_BASE = process.env.REACT_APP_BACKEND_URL || window.location.origin;

// Styles
const Styles = () => (
  <style>{`
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: ${C.bg}; color: ${C.text}; font-family: 'Inter', -apple-system, sans-serif; }
    input, button { font-family: inherit; }
    input:focus { outline: none; border-color: ${C.primary} !important; }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: ${C.surface}; }
    ::-webkit-scrollbar-thumb { background: ${C.primary}33; border-radius: 3px; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
  `}</style>
);

export default function CryptoSignalDashboard() {
  // Auth state
  const [token, setToken] = useState(localStorage.getItem('crypto_token') || '');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  
  // Data state
  const [watchlist, setWatchlist] = useState([]);
  const [signals, setSignals] = useState([]);
  const [prices, setPrices] = useState({});
  const [cadRate, setCadRate] = useState(1.36);
  const [currency, setCurrency] = useState('CAD'); // CAD or USD
  
  // UI state
  const [showAddCoin, setShowAddCoin] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedCoin, setSelectedCoin] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // WebSocket
  const wsRef = useRef(null);
  
  // API helper
  const api = useCallback(async (method, path, body = null) => {
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    };
    
    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);
    
    const res = await fetch(`${API_BASE}${path}`, options);
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }
    return res.json();
  }, [token]);
  
  // Login
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    try {
      const res = await fetch(`${API_BASE}/api/crypto/auth/login?password=${encodeURIComponent(password)}`, {
        method: 'POST'
      });
      
      if (!res.ok) {
        setLoginError('Invalid password');
        return;
      }
      
      const data = await res.json();
      setToken(data.token);
      localStorage.setItem('crypto_token', data.token);
      setIsLoggedIn(true);
    } catch (e) {
      setLoginError('Login failed');
    }
  };
  
  // Logout
  const handleLogout = () => {
    setToken('');
    localStorage.removeItem('crypto_token');
    setIsLoggedIn(false);
  };
  
  // Verify token on mount
  useEffect(() => {
    if (token) {
      api('GET', '/api/crypto/watchlist')
        .then(data => {
          setIsLoggedIn(true);
          setWatchlist(data.coins || []);
          setCadRate(data.cad_rate || 1.36);
        })
        .catch(() => {
          setToken('');
          localStorage.removeItem('crypto_token');
        });
    }
  }, [token, api]);
  
  // WebSocket connection
  useEffect(() => {
    if (!isLoggedIn) return;
    
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = API_BASE.replace(/^https?:\/\//, '');
    const ws = new WebSocket(`${wsProtocol}//${wsHost}/api/crypto/ws`);
    wsRef.current = ws;
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'price') {
        setPrices(prev => ({
          ...prev,
          [data.symbol]: { usd: data.price_usd, cad: data.price_cad }
        }));
      } else if (data.type === 'signal') {
        setSignals(prev => [data.signal, ...prev].slice(0, 100));
      } else if (data.type === 'init') {
        setPrices(data.prices || {});
      }
    };
    
    ws.onclose = () => {
      // Reconnect after 3 seconds
      setTimeout(() => {
        if (isLoggedIn) {
          // Will trigger useEffect again
        }
      }, 3000);
    };
    
    return () => ws.close();
  }, [isLoggedIn]);
  
  // Fetch signals
  useEffect(() => {
    if (!isLoggedIn) return;
    
    api('GET', '/api/crypto/signals?limit=50')
      .then(data => setSignals(data.signals || []))
      .catch(console.error);
  }, [isLoggedIn, api]);
  
  // Search coins
  const searchCoins = async (q) => {
    if (!q || q.length < 2) {
      setSearchResults([]);
      return;
    }
    
    try {
      const data = await api('GET', `/api/crypto/search?q=${encodeURIComponent(q)}`);
      setSearchResults(data.results || []);
    } catch (e) {
      console.error('Search error:', e);
    }
  };
  
  // Add coin
  const addCoin = async (coin) => {
    try {
      setLoading(true);
      const symbol = `${coin.symbol.toUpperCase()}USDT`;
      await api('POST', '/api/crypto/watchlist', { symbol, name: coin.name });
      
      // Refresh watchlist
      const data = await api('GET', '/api/crypto/watchlist');
      setWatchlist(data.coins || []);
      setShowAddCoin(false);
      setSearchQuery('');
      setSearchResults([]);
    } catch (e) {
      alert(e.message);
    } finally {
      setLoading(false);
    }
  };
  
  // Remove coin
  const removeCoin = async (symbol) => {
    if (!window.confirm(`Remove ${symbol} from watchlist?`)) return;
    
    try {
      await api('DELETE', `/api/crypto/watchlist/${symbol}`);
      setWatchlist(prev => prev.filter(c => c.symbol !== symbol));
      if (selectedCoin?.symbol === symbol) setSelectedCoin(null);
    } catch (e) {
      alert(e.message);
    }
  };
  
  // Update coin settings
  const updateCoin = async (symbol, updates) => {
    try {
      await api('PUT', `/api/crypto/watchlist/${symbol}`, updates);
      
      // Update local state
      setWatchlist(prev => prev.map(c => 
        c.symbol === symbol ? { ...c, ...updates } : c
      ));
      
      if (selectedCoin?.symbol === symbol) {
        setSelectedCoin(prev => ({ ...prev, ...updates }));
      }
    } catch (e) {
      alert(e.message);
    }
  };
  
  // Format price
  const formatPrice = (usd, cad) => {
    if (currency === 'CAD') return `$${(cad || usd * cadRate).toFixed(2)} CAD`;
    return `$${(usd || 0).toFixed(2)} USD`;
  };
  
  // Format P&L
  const formatPnl = (pnl, percent) => {
    if (!pnl) return null;
    const isPositive = pnl >= 0;
    return (
      <span style={{ color: isPositive ? C.green : C.red }}>
        {isPositive ? '+' : ''}{pnl.toFixed(2)} ({isPositive ? '+' : ''}{percent.toFixed(1)}%)
      </span>
    );
  };
  
  // Login Screen
  if (!isLoggedIn) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: C.bg }}>
        <Styles />
        <div style={{ width: 340, padding: 32, background: C.surface, borderRadius: 16, border: `1px solid ${C.border}` }}>
          <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 8, color: C.text }}>
            Crypto Signal Engine
          </h1>
          <p style={{ color: C.textDim, fontSize: 13, marginBottom: 24 }}>
            Enter password to access dashboard
          </p>
          
          <form onSubmit={handleLogin}>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              style={{
                width: '100%', padding: '14px 16px', background: C.surface2,
                border: `1px solid ${C.border}`, borderRadius: 8,
                color: C.text, fontSize: 14, marginBottom: 16
              }}
            />
            
            {loginError && (
              <p style={{ color: C.red, fontSize: 12, marginBottom: 12 }}>{loginError}</p>
            )}
            
            <button type="submit" style={{
              width: '100%', padding: '14px 16px',
              background: `linear-gradient(135deg, ${C.primary}, #4f46e5)`,
              color: 'white', border: 'none', borderRadius: 8,
              fontSize: 14, fontWeight: 600, cursor: 'pointer'
            }}>
              Login
            </button>
          </form>
        </div>
      </div>
    );
  }
  
  return (
    <div style={{ minHeight: '100vh', background: C.bg }}>
      <Styles />
      
      {/* Header */}
      <header style={{
        padding: '16px 24px', borderBottom: `1px solid ${C.border}`,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
      }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600 }}>Crypto Signal Engine</h1>
          <p style={{ fontSize: 11, color: C.textDim }}>Real-time alerts & portfolio tracking</p>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Currency Toggle */}
          <div style={{ display: 'flex', background: C.surface2, borderRadius: 6, padding: 2 }}>
            {['CAD', 'USD'].map(c => (
              <button
                key={c}
                onClick={() => setCurrency(c)}
                style={{
                  padding: '6px 12px', borderRadius: 4, border: 'none',
                  background: currency === c ? C.primary : 'transparent',
                  color: currency === c ? 'white' : C.textDim,
                  fontSize: 11, fontWeight: 600, cursor: 'pointer'
                }}
              >
                {c}
              </button>
            ))}
          </div>
          
          <button onClick={handleLogout} style={{
            padding: '8px 16px', background: 'transparent',
            border: `1px solid ${C.border}`, borderRadius: 6,
            color: C.textDim, fontSize: 12, cursor: 'pointer'
          }}>
            Logout
          </button>
        </div>
      </header>
      
      <main style={{ display: 'flex', height: 'calc(100vh - 73px)' }}>
        {/* Left Panel - Watchlist */}
        <div style={{ width: 340, borderRight: `1px solid ${C.border}`, display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: 16, borderBottom: `1px solid ${C.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: 14, fontWeight: 600 }}>Watchlist ({watchlist.length})</h2>
            <button onClick={() => setShowAddCoin(true)} style={{
              padding: '6px 12px', background: C.primary,
              color: 'white', border: 'none', borderRadius: 6,
              fontSize: 11, fontWeight: 600, cursor: 'pointer'
            }}>
              + Add Coin
            </button>
          </div>
          
          <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
            {watchlist.length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: C.textDim }}>
                <p style={{ fontSize: 13 }}>No coins in watchlist</p>
                <p style={{ fontSize: 11, marginTop: 4 }}>Click "Add Coin" to get started</p>
              </div>
            ) : (
              watchlist.map(coin => {
                const priceData = prices[coin.symbol] || {};
                const price = currency === 'CAD' ? (priceData.cad || coin.price_cad) : (priceData.usd || coin.price_usd);
                
                return (
                  <div
                    key={coin.symbol}
                    onClick={() => setSelectedCoin(coin)}
                    style={{
                      padding: 12, marginBottom: 8, borderRadius: 10,
                      background: selectedCoin?.symbol === coin.symbol ? `${C.primary}22` : C.surface,
                      border: `1px solid ${selectedCoin?.symbol === coin.symbol ? C.primary : C.border}`,
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <p style={{ fontSize: 14, fontWeight: 600 }}>{coin.name}</p>
                        <p style={{ fontSize: 11, color: C.textDim }}>{coin.symbol}</p>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <p style={{ fontSize: 14, fontWeight: 600 }}>${price?.toFixed(2) || '—'}</p>
                        {coin.pnl !== undefined && coin.pnl !== 0 && (
                          <p style={{ fontSize: 11 }}>{formatPnl(coin.pnl, coin.pnl_percent)}</p>
                        )}
                      </div>
                    </div>
                    
                    {coin.holdings > 0 && (
                      <div style={{ marginTop: 8, padding: '6px 8px', background: C.surface2, borderRadius: 6, fontSize: 11 }}>
                        <span style={{ color: C.textDim }}>Holdings:</span> {coin.holdings} × ${coin.buy_price?.toFixed(2)} = <span style={{ color: C.gold }}>${coin.value_cad?.toFixed(2)}</span>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
        
        {/* Center Panel - Coin Settings or Signal Feed */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {selectedCoin ? (
            <CoinSettingsPanel 
              coin={selectedCoin} 
              onUpdate={updateCoin} 
              onRemove={removeCoin}
              onClose={() => setSelectedCoin(null)}
              currency={currency}
              cadRate={cadRate}
            />
          ) : (
            <SignalFeed signals={signals} />
          )}
        </div>
        
        {/* Right Panel - Signal History */}
        <div style={{ width: 320, borderLeft: `1px solid ${C.border}`, display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: 16, borderBottom: `1px solid ${C.border}` }}>
            <h2 style={{ fontSize: 14, fontWeight: 600 }}>Signal History</h2>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
            {signals.slice(0, 20).map((signal, i) => (
              <div key={signal.id || i} style={{
                padding: 10, marginBottom: 6, borderRadius: 8,
                background: C.surface, border: `1px solid ${C.border}`,
                fontSize: 12, animation: i === 0 ? 'slideIn 0.3s ease' : 'none'
              }}>
                <p style={{ lineHeight: 1.5 }}>{signal.message}</p>
                <p style={{ color: C.textDim, fontSize: 10, marginTop: 4 }}>
                  {new Date(signal.timestamp).toLocaleString()}
                </p>
              </div>
            ))}
            
            {signals.length === 0 && (
              <p style={{ padding: 24, textAlign: 'center', color: C.textDim, fontSize: 12 }}>
                No signals yet. Add coins and wait for alerts.
              </p>
            )}
          </div>
        </div>
      </main>
      
      {/* Add Coin Modal */}
      {showAddCoin && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div style={{
            width: 400, maxHeight: '80vh', background: C.surface,
            borderRadius: 16, border: `1px solid ${C.border}`, overflow: 'hidden'
          }}>
            <div style={{ padding: 16, borderBottom: `1px solid ${C.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: 16, fontWeight: 600 }}>Add Coin</h3>
              <button onClick={() => { setShowAddCoin(false); setSearchQuery(''); setSearchResults([]); }} style={{
                background: 'none', border: 'none', color: C.textDim, fontSize: 20, cursor: 'pointer'
              }}>×</button>
            </div>
            
            <div style={{ padding: 16 }}>
              <input
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); searchCoins(e.target.value); }}
                placeholder="Search by name or symbol..."
                style={{
                  width: '100%', padding: '12px 16px', background: C.surface2,
                  border: `1px solid ${C.border}`, borderRadius: 8,
                  color: C.text, fontSize: 14
                }}
              />
            </div>
            
            <div style={{ maxHeight: 300, overflowY: 'auto', padding: '0 16px 16px' }}>
              {searchResults.map(coin => (
                <div
                  key={coin.id}
                  onClick={() => !loading && addCoin(coin)}
                  style={{
                    padding: 12, marginBottom: 8, borderRadius: 8,
                    background: C.surface2, border: `1px solid ${C.border}`,
                    cursor: loading ? 'wait' : 'pointer',
                    display: 'flex', alignItems: 'center', gap: 12
                  }}
                >
                  {coin.thumb && <img src={coin.thumb} alt="" style={{ width: 24, height: 24, borderRadius: '50%' }} />}
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 500 }}>{coin.name}</p>
                    <p style={{ fontSize: 11, color: C.textDim }}>{coin.symbol}</p>
                  </div>
                </div>
              ))}
              
              {searchQuery.length >= 2 && searchResults.length === 0 && (
                <p style={{ padding: 16, textAlign: 'center', color: C.textDim, fontSize: 12 }}>
                  No results found
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Coin Settings Panel Component
function CoinSettingsPanel({ coin, onUpdate, onRemove, onClose, currency, cadRate }) {
  const [settings, setSettings] = useState(coin);
  
  useEffect(() => {
    setSettings(coin);
  }, [coin]);
  
  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };
  
  const handleSave = () => {
    onUpdate(coin.symbol, {
      price_change_percent: settings.price_change_percent,
      price_change_minutes: settings.price_change_minutes,
      volume_spike_percent: settings.volume_spike_percent,
      rsi_overbought: settings.rsi_overbought,
      rsi_oversold: settings.rsi_oversold,
      target_price_high: settings.target_price_high || null,
      target_price_low: settings.target_price_low || null,
      timeframe: settings.timeframe,
      notify_push: settings.notify_push,
      buy_price: settings.buy_price || null,
      holdings: settings.holdings || 0,
      enabled: settings.enabled
    });
  };
  
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: 16, borderBottom: `1px solid ${C.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600 }}>{coin.name}</h2>
          <p style={{ fontSize: 12, color: C.textDim }}>{coin.symbol}</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => onRemove(coin.symbol)} style={{
            padding: '8px 16px', background: `${C.red}22`,
            color: C.red, border: `1px solid ${C.red}44`, borderRadius: 6,
            fontSize: 12, cursor: 'pointer'
          }}>Remove</button>
          <button onClick={onClose} style={{
            padding: '8px 16px', background: C.surface2,
            color: C.textDim, border: `1px solid ${C.border}`, borderRadius: 6,
            fontSize: 12, cursor: 'pointer'
          }}>Close</button>
        </div>
      </div>
      
      <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {/* Enable/Disable */}
        <div style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
          <input
            type="checkbox"
            checked={settings.enabled}
            onChange={(e) => handleChange('enabled', e.target.checked)}
            style={{ width: 18, height: 18 }}
          />
          <label style={{ fontSize: 14 }}>Enable alerts for this coin</label>
        </div>
        
        {/* Portfolio Section */}
        <div style={{ marginBottom: 24, padding: 16, background: C.surface, borderRadius: 12, border: `1px solid ${C.border}` }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: C.gold }}>Portfolio Tracking</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: 11, color: C.textDim, display: 'block', marginBottom: 4 }}>Buy Price ({currency})</label>
              <input
                type="number"
                step="0.01"
                value={settings.buy_price || ''}
                onChange={(e) => handleChange('buy_price', parseFloat(e.target.value) || null)}
                placeholder="0.00"
                style={{
                  width: '100%', padding: '10px 12px', background: C.surface2,
                  border: `1px solid ${C.border}`, borderRadius: 6,
                  color: C.text, fontSize: 13
                }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: C.textDim, display: 'block', marginBottom: 4 }}>Holdings (Qty)</label>
              <input
                type="number"
                step="0.0001"
                value={settings.holdings || ''}
                onChange={(e) => handleChange('holdings', parseFloat(e.target.value) || 0)}
                placeholder="0"
                style={{
                  width: '100%', padding: '10px 12px', background: C.surface2,
                  border: `1px solid ${C.border}`, borderRadius: 6,
                  color: C.text, fontSize: 13
                }}
              />
            </div>
          </div>
        </div>
        
        {/* Alert Settings */}
        <div style={{ marginBottom: 24, padding: 16, background: C.surface, borderRadius: 12, border: `1px solid ${C.border}` }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Alert Settings</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <div>
              <label style={{ fontSize: 11, color: C.textDim, display: 'block', marginBottom: 4 }}>Price Change %</label>
              <input
                type="number"
                step="0.5"
                value={settings.price_change_percent}
                onChange={(e) => handleChange('price_change_percent', parseFloat(e.target.value))}
                style={{
                  width: '100%', padding: '10px 12px', background: C.surface2,
                  border: `1px solid ${C.border}`, borderRadius: 6,
                  color: C.text, fontSize: 13
                }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: C.textDim, display: 'block', marginBottom: 4 }}>Within Minutes</label>
              <input
                type="number"
                value={settings.price_change_minutes}
                onChange={(e) => handleChange('price_change_minutes', parseInt(e.target.value))}
                style={{
                  width: '100%', padding: '10px 12px', background: C.surface2,
                  border: `1px solid ${C.border}`, borderRadius: 6,
                  color: C.text, fontSize: 13
                }}
              />
            </div>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <div>
              <label style={{ fontSize: 11, color: C.textDim, display: 'block', marginBottom: 4 }}>RSI Overbought</label>
              <input
                type="number"
                value={settings.rsi_overbought}
                onChange={(e) => handleChange('rsi_overbought', parseFloat(e.target.value))}
                style={{
                  width: '100%', padding: '10px 12px', background: C.surface2,
                  border: `1px solid ${C.border}`, borderRadius: 6,
                  color: C.text, fontSize: 13
                }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: C.textDim, display: 'block', marginBottom: 4 }}>RSI Oversold</label>
              <input
                type="number"
                value={settings.rsi_oversold}
                onChange={(e) => handleChange('rsi_oversold', parseFloat(e.target.value))}
                style={{
                  width: '100%', padding: '10px 12px', background: C.surface2,
                  border: `1px solid ${C.border}`, borderRadius: 6,
                  color: C.text, fontSize: 13
                }}
              />
            </div>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <div>
              <label style={{ fontSize: 11, color: C.textDim, display: 'block', marginBottom: 4 }}>Target High ({currency})</label>
              <input
                type="number"
                step="0.01"
                value={settings.target_price_high || ''}
                onChange={(e) => handleChange('target_price_high', parseFloat(e.target.value) || null)}
                placeholder="Optional"
                style={{
                  width: '100%', padding: '10px 12px', background: C.surface2,
                  border: `1px solid ${C.border}`, borderRadius: 6,
                  color: C.text, fontSize: 13
                }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: C.textDim, display: 'block', marginBottom: 4 }}>Target Low ({currency})</label>
              <input
                type="number"
                step="0.01"
                value={settings.target_price_low || ''}
                onChange={(e) => handleChange('target_price_low', parseFloat(e.target.value) || null)}
                placeholder="Optional"
                style={{
                  width: '100%', padding: '10px 12px', background: C.surface2,
                  border: `1px solid ${C.border}`, borderRadius: 6,
                  color: C.text, fontSize: 13
                }}
              />
            </div>
          </div>
          
          <div>
            <label style={{ fontSize: 11, color: C.textDim, display: 'block', marginBottom: 4 }}>Timeframe</label>
            <select
              value={settings.timeframe}
              onChange={(e) => handleChange('timeframe', e.target.value)}
              style={{
                width: '100%', padding: '10px 12px', background: C.surface2,
                border: `1px solid ${C.border}`, borderRadius: 6,
                color: C.text, fontSize: 13
              }}
            >
              <option value="5m">5 minutes</option>
              <option value="15m">15 minutes</option>
              <option value="1h">1 hour</option>
              <option value="4h">4 hours</option>
              <option value="1D">1 day</option>
            </select>
          </div>
        </div>
        
        {/* Notifications */}
        <div style={{ marginBottom: 24, padding: 16, background: C.surface, borderRadius: 12, border: `1px solid ${C.border}` }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Notifications</h3>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <input
              type="checkbox"
              checked={settings.notify_push}
              onChange={(e) => handleChange('notify_push', e.target.checked)}
              style={{ width: 18, height: 18 }}
            />
            <label style={{ fontSize: 13 }}>Push Notifications</label>
          </div>
        </div>
        
        {/* Save Button */}
        <button onClick={handleSave} style={{
          width: '100%', padding: '14px 20px',
          background: `linear-gradient(135deg, ${C.primary}, #4f46e5)`,
          color: 'white', border: 'none', borderRadius: 8,
          fontSize: 14, fontWeight: 600, cursor: 'pointer'
        }}>
          Save Settings
        </button>
      </div>
    </div>
  );
}

// Signal Feed Component
function SignalFeed({ signals }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: 16, borderBottom: `1px solid ${C.border}` }}>
        <h2 style={{ fontSize: 16, fontWeight: 600 }}>Live Signal Feed</h2>
        <p style={{ fontSize: 11, color: C.textDim }}>Select a coin from watchlist to configure settings</p>
      </div>
      
      <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {signals.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%',
              background: C.surface, border: `1px solid ${C.border}`,
              margin: '0 auto 16px', display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <span style={{ fontSize: 28 }}>📡</span>
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>No signals yet</h3>
            <p style={{ color: C.textDim, fontSize: 13 }}>
              Add coins to your watchlist and configure alert thresholds.
              <br />Signals will appear here when triggered.
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {signals.slice(0, 30).map((signal, i) => (
              <div key={signal.id || i} style={{
                padding: 16, borderRadius: 12,
                background: C.surface, border: `1px solid ${C.border}`,
                animation: i === 0 ? 'slideIn 0.3s ease' : 'none'
              }}>
                <p style={{ fontSize: 14, lineHeight: 1.6, marginBottom: 8 }}>{signal.message}</p>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{
                    fontSize: 10, padding: '2px 8px', borderRadius: 4,
                    background: signal.signal_type?.includes('overbought') || signal.signal_type?.includes('high') ? `${C.red}22` : 
                               signal.signal_type?.includes('oversold') || signal.signal_type?.includes('low') ? `${C.green}22` : `${C.blue}22`,
                    color: signal.signal_type?.includes('overbought') || signal.signal_type?.includes('high') ? C.red :
                           signal.signal_type?.includes('oversold') || signal.signal_type?.includes('low') ? C.green : C.blue
                  }}>
                    {signal.signal_type?.replace(/_/g, ' ').toUpperCase() || 'ALERT'}
                  </span>
                  <span style={{ fontSize: 10, color: C.textDim }}>
                    {new Date(signal.timestamp).toLocaleString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
