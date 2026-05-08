/**
 * emitWidgetSignal.js — iter 285.5
 *
 * Lightweight helper any widget frontend can call to record a
 * widget-level activation event onto the A2A bus. This feeds Hermes RAG
 * + Learning Bus so ORA learns "kaunse widgets kab use hote hain".
 *
 * Usage:
 *   import { emitWidgetSignal } from '../lib/emitWidgetSignal';
 *   await emitWidgetSignal('global_pulse', 'refresh', { range: '7d' });
 */

const API = process.env.REACT_APP_BACKEND_URL || '';

export async function emitWidgetSignal(widget, action = 'activated', context = {}) {
  try {
    const token =
      localStorage.getItem('token') ||
      localStorage.getItem('aurem_token') ||
      sessionStorage.getItem('platform_token') ||
      sessionStorage.getItem('aurem_platform_token') ||
      '';
    if (!token) return { ok: false, reason: 'no_token' };

    const r = await fetch(`${API}/api/admin/a2a/widget-signal`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ widget, action, context }),
    });
    if (!r.ok) return { ok: false, status: r.status };
    return await r.json();
  } catch (e) {
    // Fire-and-forget — never block UI on A2A emit failure
    return { ok: false, error: String(e).slice(0, 120) };
  }
}

export default emitWidgetSignal;
