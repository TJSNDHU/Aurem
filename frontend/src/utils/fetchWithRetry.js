const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Fetch with automatic retry and exponential backoff.
 * Retries on network errors, 502, 503, and 504 responses.
 */
export async function fetchWithRetry(url, options = {}, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url, options);
      if (res.ok) return res;
      if (res.status === 502 || res.status === 503 || res.status === 504) {
        if (i < retries - 1) {
          await new Promise(r => setTimeout(r, 2000 * (i + 1)));
          continue;
        }
      }
      return res;
    } catch (e) {
      if (i === retries - 1) throw e;
      await new Promise(r => setTimeout(r, 2000 * (i + 1)));
    }
  }
}

/**
 * Check if the backend API is reachable.
 * Returns true when /api/health responds 200.
 * Has a hard 3-second timeout per request to prevent hanging.
 */
export async function checkBackendHealth() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    const res = await fetch(`${API_URL}/api/health`, {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal,
    });
    clearTimeout(timeout);
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Wait for backend to become available with polling.
 * Resolves true when healthy, false after maxAttempts.
 */
export async function waitForBackend(maxAttempts = 3, intervalMs = 1500) {
  for (let i = 0; i < maxAttempts; i++) {
    const healthy = await checkBackendHealth();
    if (healthy) return true;
    if (i < maxAttempts - 1) {
      await new Promise(r => setTimeout(r, intervalMs));
    }
  }
  return false;
}
