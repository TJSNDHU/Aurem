/**
 * VoiceProfileEditor.jsx — iter 326ff-UI (Phase 3 P3.1 frontend)
 *
 * Admin UI for tuning a tenant's ORA voice (tone / formality /
 * signature / industry). Backed by:
 *   GET  /api/admin/ora/voice-profile/{tenant_id}
 *   PUT  /api/admin/ora/voice-profile/{tenant_id}
 *
 * Route: /admin/ora-voice
 */
import React, { useCallback, useEffect, useState } from "react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const _getAdminToken = () =>
  localStorage.getItem("aurem_admin_token") ||
  sessionStorage.getItem("aurem_admin_token") ||
  "";

const TONES = ["direct", "warm", "friendly", "precise", "balanced", "playful"];
const FORMALITY = ["casual", "professional", "formal"];
const INDUSTRIES = [
  "default", "roofing", "construction", "plumbing", "hvac",
  "landscaping", "dental", "medical", "clinic", "restaurant",
  "cafe", "salon", "spa", "accounting", "tax", "legal", "law",
  "real_estate", "fitness", "retail",
];

const _label = (s) => s.replace("_", " ");

export default function VoiceProfileEditor() {
  const [tenantId, setTenantId] = useState("");
  const [profile, setProfile] = useState(null);
  const [tone, setTone] = useState("balanced");
  const [formality, setFormality] = useState("professional");
  const [industry, setIndustry] = useState("default");
  const [signature, setSignature] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [savedAt, setSavedAt] = useState("");

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError("");
    try {
      const r = await fetch(
        `${API}/api/admin/ora/voice-profile/${encodeURIComponent(tenantId)}`,
        { headers: { Authorization: `Bearer ${_getAdminToken()}` } }
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setProfile(data);
      setTone(data.tone || "balanced");
      setFormality(data.formality || "professional");
      setIndustry(data.industry || "default");
      setSignature(data.signature || "");
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  const save = useCallback(async () => {
    if (!tenantId) return;
    setSaving(true);
    setError("");
    try {
      const r = await fetch(
        `${API}/api/admin/ora/voice-profile/${encodeURIComponent(tenantId)}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${_getAdminToken()}`,
          },
          body: JSON.stringify({ tone, formality, signature, industry }),
        }
      );
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data?.detail || data?.error || `HTTP ${r.status}`);
      setProfile(data);
      setSavedAt(new Date().toLocaleTimeString());
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setSaving(false);
    }
  }, [tenantId, tone, formality, signature, industry]);

  return (
    <div
      className="min-h-screen bg-zinc-950 text-zinc-100 p-4 md:p-8"
      data-testid="voice-profile-editor"
    >
      <div className="max-w-2xl mx-auto">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">
            ORA Voice Profile
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Tune how ORA talks to this tenant. Same brain, different register.
          </p>
        </header>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 mb-4">
          <label className="block text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
            Tenant ID
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value.trim())}
              placeholder="e.g. roofco-mississauga-001"
              data-testid="voice-tenant-input"
              className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-zinc-500"
            />
            <button
              type="button"
              onClick={load}
              disabled={!tenantId || loading}
              data-testid="voice-load-btn"
              className="px-4 py-2 rounded bg-zinc-100 text-zinc-900 text-sm font-medium disabled:opacity-40 hover:bg-white transition"
            >
              {loading ? "loading…" : "load"}
            </button>
          </div>
        </div>

        {profile ? (
          <div
            className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 space-y-4"
            data-testid="voice-form"
          >
            <div className="flex items-center gap-2 text-[11px] text-zinc-500">
              <span className="uppercase tracking-wider">Source:</span>
              <span
                data-testid="voice-source"
                className="text-zinc-300"
              >
                {profile.source || "—"}
              </span>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                Industry
              </label>
              <select
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                data-testid="voice-industry-select"
                className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-zinc-500"
              >
                {INDUSTRIES.map((i) => (
                  <option key={i} value={i}>{_label(i)}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                Tone
              </label>
              <div className="flex flex-wrap gap-2" data-testid="voice-tone-chips">
                {TONES.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTone(t)}
                    data-testid={`voice-tone-${t}`}
                    className={
                      "px-3 py-1.5 rounded text-xs font-medium border transition " +
                      (tone === t
                        ? "bg-zinc-100 text-zinc-900 border-zinc-100"
                        : "bg-transparent text-zinc-300 border-zinc-700 hover:border-zinc-500")
                    }
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                Formality
              </label>
              <div className="flex gap-2" data-testid="voice-formality-chips">
                {FORMALITY.map((f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setFormality(f)}
                    data-testid={`voice-formality-${f}`}
                    className={
                      "px-3 py-1.5 rounded text-xs font-medium border transition " +
                      (formality === f
                        ? "bg-zinc-100 text-zinc-900 border-zinc-100"
                        : "bg-transparent text-zinc-300 border-zinc-700 hover:border-zinc-500")
                    }
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                Signature (optional, max 200 chars)
              </label>
              <input
                type="text"
                value={signature}
                onChange={(e) => setSignature(e.target.value.slice(0, 200))}
                placeholder="— ORA, your AUREM CTO"
                data-testid="voice-signature-input"
                className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-zinc-500"
              />
            </div>

            {error ? (
              <div className="text-xs text-rose-300" data-testid="voice-error">
                {error}
              </div>
            ) : null}

            <div className="flex items-center justify-between pt-2 border-t border-zinc-800">
              {savedAt ? (
                <span
                  className="text-[11px] text-emerald-400"
                  data-testid="voice-saved-marker"
                >
                  saved {savedAt}
                </span>
              ) : (
                <span />
              )}
              <button
                type="button"
                onClick={save}
                disabled={saving}
                data-testid="voice-save-btn"
                className="px-5 py-2 rounded bg-emerald-500 text-zinc-900 text-sm font-semibold hover:bg-emerald-400 transition disabled:opacity-40"
              >
                {saving ? "saving…" : "Save voice"}
              </button>
            </div>
          </div>
        ) : (
          <div
            className="text-sm text-zinc-500 italic"
            data-testid="voice-empty-hint"
          >
            Enter a tenant ID and hit Load to start editing.
          </div>
        )}
      </div>
    </div>
  );
}
