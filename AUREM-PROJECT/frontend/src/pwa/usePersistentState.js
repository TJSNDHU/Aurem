/**
 * ReRoots AI Persistent State Hook
 * Bi-Directional Sync between IndexedDB (local) and MongoDB (cloud)
 * 
 * Features:
 * - Instant local save to IndexedDB
 * - Background sync to MongoDB when online
 * - Deep Sync on app launch
 * - Circuit Breaker fallback to REST polling
 * - Lead capture for every interaction
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';
const WS_URL = API_URL.replace('https://', 'wss://').replace('http://', 'ws://');
const SYNC_INTERVAL = 30000; // 30 seconds fallback polling
const HEARTBEAT_INTERVAL = 25000; // 25 seconds heartbeat

// IndexedDB Configuration
const DB_NAME = 'reroots-sync';
const DB_VERSION = 1;
const STATE_STORE = 'persistent-state';

/**
 * usePersistentState - Main hook for bi-directional sync
 */
export function usePersistentState(userId, initialState = {}) {
  const [state, setState] = useState(initialState);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSynced, setLastSynced] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  
  const wsRef = useRef(null);
  const dbRef = useRef(null);
  const syncQueueRef = useRef([]);
  const heartbeatRef = useRef(null);
  const fallbackIntervalRef = useRef(null);

  // Initialize IndexedDB
  const initDB = useCallback(() => {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      
      request.onerror = () => reject(request.error);
      
      request.onsuccess = () => {
        dbRef.current = request.result;
        resolve(request.result);
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STATE_STORE)) {
          db.createObjectStore(STATE_STORE, { keyPath: 'key' });
        }
      };
    });
  }, []);

  // Save state to IndexedDB (instant local save)
  const saveToLocal = useCallback(async (key, value) => {
    if (!dbRef.current) return;
    
    return new Promise((resolve, reject) => {
      const tx = dbRef.current.transaction(STATE_STORE, 'readwrite');
      const store = tx.objectStore(STATE_STORE);
      
      store.put({ 
        key, 
        value, 
        updatedAt: Date.now(),
        synced: false 
      });
      
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }, []);

  // Load state from IndexedDB
  const loadFromLocal = useCallback(async (key) => {
    if (!dbRef.current) return null;
    
    return new Promise((resolve) => {
      const tx = dbRef.current.transaction(STATE_STORE, 'readonly');
      const store = tx.objectStore(STATE_STORE);
      const request = store.get(key);
      
      request.onsuccess = () => resolve(request.result?.value || null);
      request.onerror = () => resolve(null);
    });
  }, []);

  // Initialize WebSocket connection
  const initWebSocket = useCallback(() => {
    if (!userId) return;
    
    const clientId = `pwa_${userId}_${Date.now()}`;
    const wsUrl = `${WS_URL}/api/live/ws/${clientId}?type=pwa&user_id=${userId}`;
    
    try {
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log('[LiveSync] WebSocket connected');
        setWsConnected(true);
        
        // Request current state from server (Deep Sync)
        wsRef.current.send(JSON.stringify({ type: 'get_state' }));
        
        // Start heartbeat
        heartbeatRef.current = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'heartbeat' }));
          }
        }, HEARTBEAT_INTERVAL);
      };
      
      wsRef.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
      };
      
      wsRef.current.onclose = () => {
        console.log('[LiveSync] WebSocket disconnected');
        setWsConnected(false);
        clearInterval(heartbeatRef.current);
        
        // Circuit Breaker: fallback to REST polling
        startFallbackPolling();
        
        // Attempt reconnect after 5 seconds
        setTimeout(() => {
          if (isOnline && !wsRef.current?.readyState === WebSocket.OPEN) {
            initWebSocket();
          }
        }, 5000);
      };
      
      wsRef.current.onerror = (error) => {
        console.error('[LiveSync] WebSocket error:', error);
      };
      
    } catch (error) {
      console.error('[LiveSync] WebSocket init error:', error);
      startFallbackPolling();
    }
  }, [userId, isOnline]);

  // Handle messages from server
  const handleServerMessage = useCallback((data) => {
    switch (data.type) {
      case 'state_data':
        // Deep Sync: merge server state with local
        if (data.state && data.found) {
          setState(prev => ({ ...prev, ...data.state }));
          setLastSynced(new Date());
        }
        break;
      
      case 'sync_result':
        if (data.success) {
          setLastSynced(new Date());
          setIsSyncing(false);
        }
        break;
      
      case 'ui_refresh':
        // Admin made changes - trigger UI refresh
        window.dispatchEvent(new CustomEvent('reroots-ui-refresh', {
          detail: {
            resource: data.resource,
            action: data.action
          }
        }));
        break;
      
      case 'typing_indicator':
        // Support chat typing indicator
        window.dispatchEvent(new CustomEvent('reroots-typing', {
          detail: data
        }));
        break;
      
      default:
        break;
    }
  }, []);

  // Start fallback REST polling (Circuit Breaker)
  const startFallbackPolling = useCallback(() => {
    if (fallbackIntervalRef.current) return;
    
    console.log('[LiveSync] Starting fallback polling (Circuit Breaker)');
    
    fallbackIntervalRef.current = setInterval(async () => {
      if (!userId || !isOnline) return;
      
      try {
        // Sync state via REST
        const localState = await loadFromLocal(`user_${userId}`);
        if (localState) {
          await fetch(`${API_URL}/api/live/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, state: localState })
          });
        }
        
        // Get latest state
        const response = await fetch(`${API_URL}/api/live/state/${userId}`);
        if (response.ok) {
          const data = await response.json();
          if (data.success && data.state) {
            setState(prev => ({ ...prev, ...data.state }));
            setLastSynced(new Date());
          }
        }
      } catch (error) {
        console.error('[LiveSync] Fallback polling error:', error);
      }
    }, SYNC_INTERVAL);
  }, [userId, isOnline, loadFromLocal]);

  // Stop fallback polling
  const stopFallbackPolling = useCallback(() => {
    if (fallbackIntervalRef.current) {
      clearInterval(fallbackIntervalRef.current);
      fallbackIntervalRef.current = null;
    }
  }, []);

  // Sync state to server
  const syncToServer = useCallback(async (newState) => {
    if (!userId) return;
    
    setIsSyncing(true);
    
    // Save locally first (instant)
    await saveToLocal(`user_${userId}`, newState);
    
    // Sync to server
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Use WebSocket
      wsRef.current.send(JSON.stringify({
        type: 'sync_state',
        state: newState
      }));
    } else if (isOnline) {
      // Fallback to REST
      try {
        await fetch(`${API_URL}/api/live/sync`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId, state: newState })
        });
        setLastSynced(new Date());
      } catch (error) {
        console.error('[LiveSync] REST sync error:', error);
        // Queue for later sync
        syncQueueRef.current.push(newState);
      }
    } else {
      // Queue for when back online
      syncQueueRef.current.push(newState);
    }
    
    setIsSyncing(false);
  }, [userId, isOnline, saveToLocal]);

  // Update state with automatic sync
  const updateState = useCallback((updates) => {
    setState(prev => {
      const newState = typeof updates === 'function' 
        ? updates(prev) 
        : { ...prev, ...updates };
      
      // Trigger sync
      syncToServer(newState);
      
      return newState;
    });
  }, [syncToServer]);

  // Log activity (for lead capture)
  const logActivity = useCallback(async (activityType, data = {}) => {
    const activity = {
      user_id: userId,
      session_id: localStorage.getItem('reroots_session_id'),
      activity_type: activityType,
      data,
      timestamp: new Date().toISOString()
    };
    
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'activity',
        payload: activity
      }));
    } else {
      // Fallback to REST
      try {
        await fetch(`${API_URL}/api/live/activity`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(activity)
        });
      } catch (error) {
        console.error('[LiveSync] Activity log error:', error);
      }
    }
  }, [userId]);

  // Monitor online status
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      // Process queued syncs
      if (syncQueueRef.current.length > 0) {
        const latestState = syncQueueRef.current[syncQueueRef.current.length - 1];
        syncToServer(latestState);
        syncQueueRef.current = [];
      }
      // Reconnect WebSocket
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        initWebSocket();
      }
    };
    
    const handleOffline = () => {
      setIsOnline(false);
    };
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [syncToServer, initWebSocket]);

  // Initialize on mount
  useEffect(() => {
    const init = async () => {
      // Initialize IndexedDB
      await initDB();
      
      // Load local state first (instant)
      if (userId) {
        const localState = await loadFromLocal(`user_${userId}`);
        if (localState) {
          setState(prev => ({ ...prev, ...localState }));
        }
      }
      
      // Connect WebSocket for live sync
      if (isOnline) {
        initWebSocket();
      }
    };
    
    init();
    
    // Cleanup
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      clearInterval(heartbeatRef.current);
      stopFallbackPolling();
    };
  }, [userId, initDB, loadFromLocal, initWebSocket, isOnline, stopFallbackPolling]);

  // When WebSocket connects, stop fallback polling
  useEffect(() => {
    if (wsConnected) {
      stopFallbackPolling();
    }
  }, [wsConnected, stopFallbackPolling]);

  return {
    state,
    updateState,
    isOnline,
    isSyncing,
    lastSynced,
    wsConnected,
    logActivity,
    
    // Granular state setters
    setCartState: (cart) => updateState({ cart }),
    setSkinProfile: (profile) => updateState({ skinProfile: profile }),
    setQuizProgress: (progress) => updateState({ quizProgress: progress }),
    setPreferences: (prefs) => updateState({ preferences: prefs })
  };
}

/**
 * useLiveUpdates - Hook to listen for Admin broadcasts
 */
export function useLiveUpdates(onRefresh) {
  useEffect(() => {
    const handleRefresh = (event) => {
      if (onRefresh) {
        onRefresh(event.detail);
      }
    };
    
    window.addEventListener('reroots-ui-refresh', handleRefresh);
    
    return () => {
      window.removeEventListener('reroots-ui-refresh', handleRefresh);
    };
  }, [onRefresh]);
}

/**
 * useTypingIndicator - Hook for live chat typing indicator
 */
export function useTypingIndicator(onTyping) {
  useEffect(() => {
    const handleTyping = (event) => {
      if (onTyping) {
        onTyping(event.detail);
      }
    };
    
    window.addEventListener('reroots-typing', handleTyping);
    
    return () => {
      window.removeEventListener('reroots-typing', handleTyping);
    };
  }, [onTyping]);
}

export default usePersistentState;
