import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL;

// Convert HTTP URL to WebSocket URL - with validation
const getWebSocketUrl = () => {
  if (!API) return null;
  try {
    const baseUrl = API.replace(/^http/, 'ws').replace(/\/$/, '');
    return `${baseUrl}/api/ws`;
  } catch {
    return null;
  }
};

// Check if WebSocket should be enabled (only on production domains with working backend)
const shouldEnableWebSocket = () => {
  // Disable WebSocket on production reroots.ca to prevent console errors
  // The main app functionality works without real-time updates
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    // Disable on production - the emergent.host backend doesn't support WSS
    if (host === 'reroots.ca' || host === 'www.reroots.ca') {
      return false;
    }
    // Enable on preview/development environments
    if (host.includes('preview.emergentagent.com') || host === 'localhost') {
      return true;
    }
  }
  return false;
};

const WebSocketContext = createContext(null);

export const WebSocketProvider = ({ children }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('disabled');
  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const eventListenersRef = useRef({});
  const wsEnabled = shouldEnableWebSocket();
  
  // Event listener management
  const addEventListener = useCallback((eventType, callback) => {
    if (!eventListenersRef.current[eventType]) {
      eventListenersRef.current[eventType] = [];
    }
    eventListenersRef.current[eventType].push(callback);
    
    // Return unsubscribe function
    return () => {
      eventListenersRef.current[eventType] = eventListenersRef.current[eventType]
        .filter(cb => cb !== callback);
    };
  }, []);
  
  const removeEventListener = useCallback((eventType, callback) => {
    if (eventListenersRef.current[eventType]) {
      eventListenersRef.current[eventType] = eventListenersRef.current[eventType]
        .filter(cb => cb !== callback);
    }
  }, []);
  
  // Broadcast event to all listeners
  const broadcastEvent = useCallback((eventType, data) => {
    if (eventListenersRef.current[eventType]) {
      eventListenersRef.current[eventType].forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          // Silently ignore listener errors
        }
      });
    }
    
    // Also broadcast to wildcard listeners
    if (eventListenersRef.current['*']) {
      eventListenersRef.current['*'].forEach(callback => {
        try {
          callback({ type: eventType, data });
        } catch (error) {
          // Silently ignore listener errors
        }
      });
    }
  }, []);
  
  const connect = useCallback(() => {
    // Skip connection if WebSocket is disabled
    if (!wsEnabled) {
      setConnectionStatus('disabled');
      return;
    }
    
    const wsUrl = getWebSocketUrl();
    if (!wsUrl) {
      setConnectionStatus('disabled');
      return;
    }
    
    // Get auth token from localStorage
    const token = localStorage.getItem('token');
    const fullUrl = `${wsUrl}${token ? `?token=${token}` : ''}`;
    
    try {
      setConnectionStatus('connecting');
      socketRef.current = new WebSocket(fullUrl);
      
      socketRef.current.onopen = () => {
        // Silent connection success
        setIsConnected(true);
        setConnectionStatus('connected');
        
        // Start ping interval to keep connection alive
        pingIntervalRef.current = setInterval(() => {
          if (socketRef.current?.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000); // Ping every 30 seconds
      };
      
      socketRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          setLastMessage(message);
          
          // Handle specific message types
          if (message.type === 'pong') {
            // Ping response, connection is healthy
            return;
          }
          
          if (message.type === 'connection_established') {
            // Connection confirmed
            return;
          }
          
          // Broadcast to event listeners
          if (message.type) {
            broadcastEvent(message.type, message.data);
          }
        } catch {
          // Silently ignore parse errors
        }
      };
      
      socketRef.current.onclose = (event) => {
        setIsConnected(false);
        setConnectionStatus('disconnected');
        
        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        // Attempt to reconnect after 5 seconds (unless intentionally closed or disabled)
        if (event.code !== 1000 && wsEnabled) {
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, 5000);
        }
      };
      
      socketRef.current.onerror = () => {
        // Silent error handling - WebSocket errors are logged by browser anyway
        setConnectionStatus('error');
      };
    } catch {
      // Silent error handling
      setConnectionStatus('error');
    }
  }, [broadcastEvent, wsEnabled]);
  
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
    if (socketRef.current) {
      socketRef.current.close(1000, 'User disconnected');
    }
  }, []);
  
  const sendMessage = useCallback((message) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(message));
      return true;
    }
    // Silent when not connected
    return false;
  }, []);
  
  const subscribe = useCallback((channel) => {
    return sendMessage({ type: 'subscribe', channel });
  }, [sendMessage]);
  
  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connect();
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);
  
  // Reconnect when token changes
  useEffect(() => {
    const handleStorageChange = (event) => {
      if (event.key === 'token') {
        disconnect();
        setTimeout(connect, 100);
      }
    };
    
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [connect, disconnect]);
  
  const value = {
    isConnected,
    connectionStatus,
    lastMessage,
    sendMessage,
    subscribe,
    addEventListener,
    removeEventListener,
    connect,
    disconnect,
  };
  
  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

// Custom hook to use WebSocket context
export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

// Custom hook to subscribe to specific events
export const useWebSocketEvent = (eventType, callback) => {
  const { addEventListener } = useWebSocket();
  
  useEffect(() => {
    if (!callback) return;
    
    const unsubscribe = addEventListener(eventType, callback);
    return unsubscribe;
  }, [eventType, callback, addEventListener]);
};

export default WebSocketContext;
