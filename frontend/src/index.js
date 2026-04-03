import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";

console.log('[AUREM] Autonomous AI Workforce Platform Starting...');

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Register service worker for PWA functionality
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then(reg => console.log('[AUREM] Service Worker registered'))
      .catch(err => console.log('[AUREM] Service Worker registration failed:', err));
  });
}
