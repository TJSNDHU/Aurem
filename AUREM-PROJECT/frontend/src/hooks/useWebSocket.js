// src/hooks/useWebSocket.js
// Auto-reconnecting WebSocket hook with polling fallback

import { useState, useEffect, useRef, useCallback } from "react";

const API_URL = process.env.REACT_APP_BACKEND_URL || "";

// Derive WebSocket URL from API URL
const getWsUrl = () => {
  const baseUrl = API_URL || window.location.origin;
  return baseUrl.replace(/^http/, "ws") + "/api";
};

export function useWebSocket(room = "admin", options = {}) {
  const {
    onMessage,
    reconnectDelay = 2000,
    maxReconnectDelay = 30000,
    token = null,
  } = options;

  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const reconnectDelay_ = useRef(reconnectDelay);
  const clientId = useRef(`client-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  const mounted = useRef(true);

  const connect = useCallback(() => {
    if (!mounted.current) return;

    const wsBase = getWsUrl();
    let url = `${wsBase}/ws`;
    if (token) {
      url += `?token=${token}`;
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mounted.current) return;
        setConnected(true);
        setError(null);
        reconnectDelay_.current = reconnectDelay;
      };

      ws.onmessage = (event) => {
        if (!mounted.current) return;
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "ping") {
            ws.send(JSON.stringify({ type: "pong" }));
            return;
          }
          if (msg.type === "connection_established" || msg.type === "pong") {
            return;
          }
          setLastMessage(msg);
          if (onMessage) onMessage(msg);
        } catch (e) {
          console.warn("WS parse error:", e);
        }
      };

      ws.onerror = () => setError("WebSocket error");

      ws.onclose = (event) => {
        if (!mounted.current) return;
        setConnected(false);
        wsRef.current = null;

        // Normal close
        if (event.code === 1000) return;

        // Exponential backoff reconnect
        const delay = Math.min(reconnectDelay_.current, maxReconnectDelay);
        reconnectDelay_.current = delay * 1.5;
        reconnectTimer.current = setTimeout(() => {
          if (mounted.current) connect();
        }, delay);
      };

    } catch (e) {
      setError(e.message);
    }
  }, [onMessage, reconnectDelay, maxReconnectDelay, token]);

  const send = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current);
    wsRef.current?.close(1000);
    setConnected(false);
  }, []);

  useEffect(() => {
    mounted.current = true;
    connect();
    return () => {
      mounted.current = false;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close(1000);
    };
  }, [connect]);

  return { connected, lastMessage, error, send, disconnect, reconnect: connect };
}

export default useWebSocket;
