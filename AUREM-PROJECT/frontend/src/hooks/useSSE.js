// src/hooks/useSSE.js
// Server-Sent Events hook — more reliable than WebSocket on Emergent platform

import { useState, useEffect, useRef, useCallback } from "react";

const API_URL = process.env.REACT_APP_BACKEND_URL || "";

export function useSSE(onMessage) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const eventSourceRef = useRef(null);
  const clientId = useRef(`sse-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  const reconnectTimeout = useRef(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    
    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    const url = `${API_URL}/api/admin/events/${clientId.current}`;
    
    try {
      eventSourceRef.current = new EventSource(url);
      
      eventSourceRef.current.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        setError(null);
      };
      
      eventSourceRef.current.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          if (onMessage) onMessage(data);
        } catch (e) {
          console.warn("SSE parse error:", e);
        }
      };
      
      eventSourceRef.current.onerror = () => {
        if (!mountedRef.current) return;
        setConnected(false);
        setError("Connection lost");
        eventSourceRef.current?.close();
        
        // Auto-reconnect after 3 seconds
        reconnectTimeout.current = setTimeout(() => {
          if (mountedRef.current) connect();
        }, 3000);
      };
    } catch (e) {
      setError(e.message);
    }
  }, [onMessage]);

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimeout.current);
    eventSourceRef.current?.close();
    setConnected(false);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    
    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimeout.current);
      eventSourceRef.current?.close();
    };
  }, [connect]);

  return { connected, error, disconnect, reconnect: connect };
}

export default useSSE;
