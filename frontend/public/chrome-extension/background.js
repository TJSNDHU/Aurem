/**
 * AUREM Lead Scraper — Background Service Worker
 * Manages storage, sync, and badge updates
 */

// Update badge with lead count
async function updateBadge() {
  const data = await chrome.storage.local.get(['leads']);
  const count = (data.leads || []).length;
  chrome.action.setBadgeText({ text: count > 0 ? String(count) : '' });
  chrome.action.setBadgeBackgroundColor({ color: '#D4AF37' });
}

// Listen for messages
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'updateBadge') {
    updateBadge();
    sendResponse({ ok: true });
  }

  if (msg.action === 'syncToAurem') {
    syncLeadsToAurem(msg.leads, msg.apiUrl, msg.token)
      .then(result => sendResponse(result))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // async response
  }

  if (msg.action === 'getStoredLeads') {
    chrome.storage.local.get(['leads'], data => {
      sendResponse({ leads: data.leads || [] });
    });
    return true;
  }

  if (msg.action === 'clearLeads') {
    chrome.storage.local.set({ leads: [] }, () => {
      updateBadge();
      sendResponse({ ok: true });
    });
    return true;
  }
});

// Sync leads to AUREM backend
async function syncLeadsToAurem(leads, apiUrl, token) {
  try {
    const response = await fetch(`${apiUrl}/api/extension/leads/bulk`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ leads })
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    // Clear synced leads from local storage
    if (data.success) {
      await chrome.storage.local.set({ leads: [] });
      updateBadge();
    }

    return data;
  } catch (err) {
    return { success: false, error: err.message };
  }
}

// Initialize badge on install
chrome.runtime.onInstalled.addListener(() => {
  updateBadge();
});
