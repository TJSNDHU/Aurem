import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import * as serviceWorkerRegistration from "@/serviceWorkerRegistration";

// Import brand config for initial logging
import brandConfig from "@/brandConfig";

// Log active brand on startup
console.log(`[Brand] Runtime detection: ${brandConfig.name} (${brandConfig.id})`);
console.log(`[Brand] Hostname: ${window.location.hostname}`);

// Expose brand config globally for debugging
window.__BRAND_CONFIG__ = brandConfig;

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Register service worker for PWA "Add to Home Screen" functionality
serviceWorkerRegistration.register({
  onSuccess: () => {
    console.log('[PWA] App is ready to work offline');
  },
  onUpdate: (registration) => {
    console.log('[PWA] New version available');
    // Optional: Show update notification to user
  }
});

// Also register sw.js for PWABuilder compatibility
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/app' })
      .then(reg => console.log('[PWA] sw.js registered:', reg.scope))
      .catch(err => console.log('[PWA] sw.js registration failed:', err));
  });
}
