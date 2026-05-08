/**
 * usePushNotifications — registers the ORA service worker,
 * subscribes to VAPID push, and stores the subscription on the backend.
 *
 * Usage:  const { isSubscribed, subscribe, unsubscribe } = usePushNotifications(token);
 */
import { useState, useEffect, useCallback } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';
const VAPID_KEY = process.env.REACT_APP_VAPID_PUBLIC_KEY || '';

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export default function usePushNotifications(token) {
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [registration, setRegistration] = useState(null);
  const [supported, setSupported] = useState(false);

  useEffect(() => {
    const ok = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
    setSupported(ok);
    if (!ok) return;

    navigator.serviceWorker
      .register('/ora-sw.js')
      .then((reg) => {
        setRegistration(reg);
        return reg.pushManager.getSubscription();
      })
      .then((sub) => {
        if (sub) setIsSubscribed(true);
      })
      .catch((err) => console.warn('[Push] SW registration failed:', err));
  }, []);

  const subscribe = useCallback(async () => {
    if (!registration || !supported) return false;

    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return false;

    try {
      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_KEY),
      });

      const subJson = sub.toJSON();
      await fetch(`${API_URL}/api/push/subscribe`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          endpoint: subJson.endpoint,
          keys: subJson.keys,
        }),
      });

      setIsSubscribed(true);
      return true;
    } catch (err) {
      console.error('[Push] Subscribe failed:', err);
      return false;
    }
  }, [registration, supported, token]);

  const unsubscribe = useCallback(async () => {
    if (!registration) return;
    const sub = await registration.pushManager.getSubscription();
    if (!sub) return;

    const subJson = sub.toJSON();
    await sub.unsubscribe();

    await fetch(`${API_URL}/api/push/unsubscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ endpoint: subJson.endpoint, keys: subJson.keys }),
    }).catch(() => {});

    setIsSubscribed(false);
  }, [registration]);

  return { supported, isSubscribed, subscribe, unsubscribe };
}
