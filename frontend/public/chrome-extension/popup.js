/**
 * AUREM Lead Scraper — Popup Logic
 */

let currentLeads = [];

document.addEventListener('DOMContentLoaded', async () => {
  const scrapeBtn = document.getElementById('scrape-btn');
  const copyBtn = document.getElementById('copy-btn');
  const csvBtn = document.getElementById('csv-btn');
  const syncBtn = document.getElementById('sync-btn');
  const settingsToggle = document.getElementById('settings-toggle');
  const saveSettingsBtn = document.getElementById('save-settings-btn');

  // Load saved settings
  const settings = await getSettings();
  document.getElementById('api-url').value = settings.apiUrl || '';
  document.getElementById('auth-token').value = settings.token || '';
  updateConnectionStatus(settings.apiUrl && settings.token);

  // Load stored leads count
  updateStoredCount();

  // Detect current page
  detectPage();

  // Event listeners
  scrapeBtn.addEventListener('click', handleScrape);
  copyBtn.addEventListener('click', handleCopy);
  csvBtn.addEventListener('click', handleCSV);
  syncBtn.addEventListener('click', handleSync);
  settingsToggle.addEventListener('click', toggleSettings);
  saveSettingsBtn.addEventListener('click', saveSettings);
});

async function detectPage() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = tab.url || '';
    document.getElementById('page-url').textContent = url.length > 50 ? url.substring(0, 50) + '...' : url;

    let pageType = 'General';
    if (url.includes('linkedin.com')) pageType = 'LinkedIn';
    else if (url.includes('facebook.com')) pageType = 'Facebook';
    else if (url.includes('instagram.com')) pageType = 'Instagram';
    else if (url.includes('twitter.com') || url.includes('x.com')) pageType = 'X / Twitter';
    else if (url.includes('youtube.com')) pageType = 'YouTube';

    const badge = document.getElementById('page-type');
    badge.textContent = pageType;
    badge.className = 'page-type-badge type-' + pageType.toLowerCase().replace(/[\s\/]/g, '');
  } catch {
    document.getElementById('page-type').textContent = 'Unknown';
  }
}

async function handleScrape() {
  const btn = document.getElementById('scrape-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Scanning...';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    const result = await chrome.tabs.sendMessage(tab.id, { action: 'scrape' });

    if (result && result.leads && result.leads.length > 0) {
      currentLeads = result.leads;
      displayLeads(result.leads);
      // Save to local storage
      await saveLeadsLocal(result.leads);
      updateStoredCount();
    } else {
      showNoResults();
    }
  } catch (err) {
    // Content script might not be injected
    showError('Could not scan this page. Try refreshing first.');
  }

  btn.disabled = false;
  btn.innerHTML = '<span class="btn-icon">&#9889;</span> Scrape This Page';
}

function displayLeads(leads) {
  const container = document.getElementById('results');
  const list = document.getElementById('leads-list');
  const count = document.getElementById('results-count');

  container.classList.remove('hidden');
  count.textContent = `${leads.length} lead${leads.length !== 1 ? 's' : ''} found`;

  list.innerHTML = leads.map((l, i) => `
    <div class="lead-card" data-index="${i}">
      <div class="lead-avatar">${(l.name || '?')[0].toUpperCase()}</div>
      <div class="lead-info">
        <div class="lead-name">${escapeHtml(l.name || 'Unknown')}</div>
        ${l.title ? `<div class="lead-title">${escapeHtml(l.title)}</div>` : ''}
        ${l.company ? `<div class="lead-company">${escapeHtml(l.company)}</div>` : ''}
        <div class="lead-details">
          ${l.email ? `<span class="lead-tag email">${escapeHtml(l.email)}</span>` : ''}
          ${l.phone ? `<span class="lead-tag phone">${escapeHtml(l.phone)}</span>` : ''}
          ${l.location ? `<span class="lead-tag location">${escapeHtml(l.location)}</span>` : ''}
        </div>
      </div>
      <div class="lead-source">${escapeHtml(l.source || 'web')}</div>
    </div>
  `).join('');
}

function showNoResults() {
  const container = document.getElementById('results');
  const list = document.getElementById('leads-list');
  const count = document.getElementById('results-count');

  container.classList.remove('hidden');
  count.textContent = '0 leads found';
  list.innerHTML = '<div class="no-results">No leads detected on this page. Try a LinkedIn profile, company page, or contact page.</div>';
}

function showError(msg) {
  const container = document.getElementById('results');
  const list = document.getElementById('leads-list');
  const count = document.getElementById('results-count');

  container.classList.remove('hidden');
  count.textContent = 'Error';
  list.innerHTML = `<div class="no-results error">${msg}</div>`;
}

async function handleCopy() {
  if (!currentLeads.length) return;
  const text = currentLeads.map(l =>
    `${l.name}\t${l.title || ''}\t${l.company || ''}\t${l.email || ''}\t${l.phone || ''}\t${l.location || ''}`
  ).join('\n');

  await navigator.clipboard.writeText('Name\tTitle\tCompany\tEmail\tPhone\tLocation\n' + text);
  flashButton('copy-btn', 'Copied!');
}

function handleCSV() {
  if (!currentLeads.length) return;
  const header = 'Name,Title,Company,Email,Phone,Location,Source,URL\n';
  const rows = currentLeads.map(l =>
    [l.name, l.title, l.company, l.email, l.phone, l.location, l.source, l.source_url]
      .map(v => `"${(v || '').replace(/"/g, '""')}"`)
      .join(',')
  ).join('\n');

  const blob = new Blob([header + rows], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `aurem-leads-${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  flashButton('csv-btn', 'Done!');
}

async function handleSync() {
  const settings = await getSettings();
  if (!settings.apiUrl || !settings.token) {
    toggleSettings();
    document.getElementById('settings-msg').textContent = 'Set your AUREM URL and token first';
    return;
  }

  const syncBtn = document.getElementById('sync-btn');
  syncBtn.disabled = true;
  syncBtn.textContent = 'Syncing...';

  // Get all stored leads
  const data = await chrome.storage.local.get(['leads']);
  const allLeads = data.leads || [];

  if (allLeads.length === 0) {
    syncBtn.textContent = 'No leads';
    setTimeout(() => { syncBtn.textContent = 'Sync'; syncBtn.disabled = false; }, 1500);
    return;
  }

  chrome.runtime.sendMessage(
    { action: 'syncToAurem', leads: allLeads, apiUrl: settings.apiUrl, token: settings.token },
    (response) => {
      if (response && response.success) {
        syncBtn.textContent = 'Synced!';
        currentLeads = [];
        document.getElementById('leads-list').innerHTML = '<div class="no-results">All leads synced to AUREM dashboard</div>';
        updateStoredCount();
      } else {
        syncBtn.textContent = 'Failed';
        document.getElementById('settings-msg').textContent = response?.error || 'Sync failed — check URL/token';
      }
      setTimeout(() => { syncBtn.textContent = 'Sync'; syncBtn.disabled = false; }, 2000);
    }
  );
}

// ── Settings ──
function toggleSettings() {
  document.getElementById('settings-panel').classList.toggle('hidden');
}

async function saveSettings() {
  const apiUrl = document.getElementById('api-url').value.trim().replace(/\/$/, '');
  const token = document.getElementById('auth-token').value.trim();
  await chrome.storage.local.set({ auremApiUrl: apiUrl, auremToken: token });
  document.getElementById('settings-msg').textContent = 'Saved!';
  updateConnectionStatus(apiUrl && token);
  setTimeout(() => document.getElementById('settings-msg').textContent = '', 2000);
}

async function getSettings() {
  const data = await chrome.storage.local.get(['auremApiUrl', 'auremToken']);
  return { apiUrl: data.auremApiUrl || '', token: data.auremToken || '' };
}

function updateConnectionStatus(connected) {
  const dot = document.getElementById('status-dot');
  dot.className = connected ? 'status-dot connected' : 'status-dot';
  dot.title = connected ? 'Connected to AUREM' : 'Not connected — open Settings';
}

// ── Storage ──
async function saveLeadsLocal(newLeads) {
  const data = await chrome.storage.local.get(['leads']);
  const existing = data.leads || [];
  // Dedupe by name+email
  const seen = new Set(existing.map(l => `${l.name}|${l.email}`.toLowerCase()));
  const unique = newLeads.filter(l => {
    const key = `${l.name}|${l.email}`.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  await chrome.storage.local.set({ leads: [...existing, ...unique] });
  chrome.runtime.sendMessage({ action: 'updateBadge' });
}

async function updateStoredCount() {
  const data = await chrome.storage.local.get(['leads']);
  const count = (data.leads || []).length;
  document.getElementById('stored-count').textContent = `${count} lead${count !== 1 ? 's' : ''} stored locally`;
}

// ── Helpers ──
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function flashButton(id, text) {
  const btn = document.getElementById(id);
  const orig = btn.textContent;
  btn.textContent = text;
  setTimeout(() => btn.textContent = orig, 1500);
}
