/**
 * AUREM — Admin Avatar Manager (Phase 8)
 * iter 322v · 2026-02-06
 *
 * Lists all 6 ORA avatars from the source-of-truth config, merges with
 * any backend overrides + selection stats, and lets the founder:
 *   • Toggle status: draft ↔ active (instant)
 *   • Add a new avatar (defaults to draft)
 *   • Preview by jumping to /ora with that avatar pre-selected
 *
 * Backend: /api/admin/avatars  (GET / POST / PATCH)
 * Source:  frontend/src/config/ora_avatars.config.js
 */
import React, { useEffect, useMemo, useState, useCallback } from "react";
import { Plus, Eye, ToggleLeft, ToggleRight, BarChart3, RefreshCcw, X } from "lucide-react";
import {
  ORA_AVATARS,
  LOCAL_STORAGE_KEY as ORA_AVATAR_KEY,
} from "../../config/ora_avatars.config";

const API = process.env.REACT_APP_BACKEND_URL || "";

const STYLE = `
.am-wrap{padding:24px 32px; max-width:1280px; margin:0 auto; color:#FAFAFA; font-family:'Outfit',system-ui,sans-serif;}
.am-head{display:flex; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; gap:14px; margin-bottom:24px;}
.am-h1{font-family:'Cabinet Grotesk',sans-serif; font-weight:800; letter-spacing:-0.02em; font-size:32px; margin:0;}
.am-sub{font-size:13px; color:#A1A1AA; margin-top:6px;}
.am-actions{display:flex; gap:10px;}
.am-btn{display:inline-flex; align-items:center; gap:8px; padding:10px 16px; border-radius:8px; border:1px solid rgba(255,255,255,0.10); background:rgba(255,255,255,0.04); color:#FAFAFA; font-size:13px; cursor:pointer; transition:all .2s;}
.am-btn:hover{border-color:rgba(212,166,70,0.55); color:#D4A646;}
.am-btn.primary{background:linear-gradient(135deg,#F4C649,#D4A646); color:#0A0A0B; border-color:transparent; font-weight:600;}
.am-btn.primary:hover{transform:translateY(-1px); color:#0A0A0B;}

.am-grid{display:grid; grid-template-columns:repeat(3,1fr); gap:18px;}
@media(max-width:1100px){.am-grid{grid-template-columns:repeat(2,1fr);}}
@media(max-width:680px){.am-grid{grid-template-columns:1fr;}}

.am-card{background:rgba(255,255,255,0.025); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:20px; transition:border-color .2s;}
.am-card:hover{border-color:rgba(212,166,70,0.32);}
.am-card-top{display:flex; align-items:center; gap:14px; margin-bottom:14px;}
.am-thumb{width:64px; height:64px; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:36px; background:linear-gradient(180deg,rgba(212,166,70,0.12),rgba(212,166,70,0.03)); border:1px solid rgba(212,166,70,0.2); flex-shrink:0;}
.am-card-id{font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:0.18em; color:#71717A; margin-bottom:4px;}
.am-card-name{font-family:'Cabinet Grotesk',sans-serif; font-weight:800; font-size:20px; letter-spacing:-0.02em;}
.am-card-meta{font-family:'JetBrains Mono',monospace; font-size:11px; color:#A1A1AA; letter-spacing:0.04em; margin-top:4px;}

.am-status-row{display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:8px; background:rgba(0,0,0,0.32); margin-bottom:10px;}
.am-toggle{display:inline-flex; align-items:center; gap:8px; cursor:pointer; user-select:none;}
.am-status-pill{font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:0.18em; padding:3px 10px; border-radius:999px; text-transform:uppercase;}
.am-status-pill.active{background:rgba(52,211,153,0.14); color:#34D399; border:1px solid rgba(52,211,153,0.32);}
.am-status-pill.draft{background:rgba(212,166,70,0.10); color:#D4A646; border:1px solid rgba(212,166,70,0.28);}

.am-stats{display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:10px 0; padding:10px 12px; background:rgba(0,0,0,0.32); border-radius:8px;}
.am-stat-label{font-family:'JetBrains Mono',monospace; font-size:9px; letter-spacing:0.16em; color:#71717A; text-transform:uppercase;}
.am-stat-val{font-family:'Cabinet Grotesk',sans-serif; font-weight:800; font-size:20px; color:#FAFAFA;}

.am-card-cta{display:flex; gap:8px; margin-top:12px;}
.am-card-cta .am-btn{flex:1; justify-content:center;}

.am-modal-bg{position:fixed; inset:0; z-index:9999; background:rgba(0,0,0,0.78); display:flex; align-items:center; justify-content:center; padding:24px;}
.am-modal{background:#0D0D14; border:1px solid rgba(255,255,255,0.10); border-radius:14px; max-width:520px; width:100%; padding:28px;}
.am-modal h2{font-family:'Cabinet Grotesk',sans-serif; font-weight:800; font-size:24px; letter-spacing:-0.02em; margin:0 0 18px;}
.am-modal-form{display:flex; flex-direction:column; gap:12px;}
.am-modal-form label{font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:0.18em; color:#A1A1AA; text-transform:uppercase; margin-bottom:4px;}
.am-modal-form input, .am-modal-form select{padding:10px 12px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.10); border-radius:8px; color:#FAFAFA; font-family:'Outfit',sans-serif; font-size:14px; outline:none;}
.am-modal-form input:focus, .am-modal-form select:focus{border-color:rgba(212,166,70,0.55);}
.am-modal-cta-row{display:flex; gap:10px; justify-content:flex-end; margin-top:8px;}

.am-empty{padding:60px 24px; text-align:center; color:#71717A; font-size:14px; background:rgba(255,255,255,0.025); border:1px dashed rgba(255,255,255,0.10); border-radius:14px;}
`;

function mergeWithOverrides(configList, overrides, stats) {
  const ovById = Object.fromEntries((overrides || []).map((o) => [o.avatar_id, o]));
  const known = new Set(configList.map((c) => c.id));
  const merged = configList.map((c) => {
    const ov = ovById[c.id] || {};
    return {
      ...c,
      ...Object.fromEntries(Object.entries(ov).filter(([k, v]) => v != null && k !== "avatar_id")),
      stats: stats?.[c.id] || { times_selected: 0 },
    };
  });
  // Append any admin-added avatars not in the config
  (overrides || []).forEach((o) => {
    if (!known.has(o.avatar_id)) {
      merged.push({
        id: o.avatar_id,
        name: o.name || o.avatar_id,
        gender: o.gender || "—",
        ethnicity: o.ethnicity || "—",
        emoji: "🤖",
        status: o.status || "draft",
        glb_url: o.glb_url || "",
        thumbnail: o.thumbnail || "",
        voice_id: o.voice_id || "",
        elevenlabs_voice_id: o.elevenlabs_voice_id || "",
        stats: stats?.[o.avatar_id] || { times_selected: 0 },
      });
    }
  });
  return merged;
}

export default function AvatarManager() {
  const [overrides, setOverrides] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [savingId, setSavingId] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const r = await fetch(`${API}/api/admin/avatars`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setOverrides(j.overrides || []);
      setStats(j.stats || {});
    } catch (e) {
      setErr(`Could not load: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const merged = useMemo(() => mergeWithOverrides(ORA_AVATARS, overrides, stats), [overrides, stats]);

  const toggleStatus = async (avatar) => {
    const newStatus = avatar.status === "active" ? "draft" : "active";
    setSavingId(avatar.id);
    try {
      const r = await fetch(`${API}/api/admin/avatars/${encodeURIComponent(avatar.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      // Optimistic refresh
      await load();
    } catch (e) {
      setErr(`Toggle failed: ${e.message}`);
    } finally {
      setSavingId("");
    }
  };

  const previewAvatar = (avatar) => {
    try { window.localStorage.setItem(ORA_AVATAR_KEY, avatar.id); } catch (_e) { /* noop */ }
    window.open("/ora", "_blank", "noopener,noreferrer");
  };

  return (
    <div className="am-wrap" data-testid="avatar-manager">
      <style dangerouslySetInnerHTML={{ __html: STYLE }} />

      <div className="am-head">
        <div>
          <h1 className="am-h1">ORA Avatar Manager</h1>
          <div className="am-sub">
            6 avatars · {merged.filter((a) => a.status === "active").length} active ·
            {" "}{merged.reduce((s, a) => s + (a.stats?.times_selected || 0), 0)} total selections
          </div>
        </div>
        <div className="am-actions">
          <button className="am-btn" onClick={load} data-testid="am-refresh">
            <RefreshCcw size={14} /> Refresh
          </button>
          <button className="am-btn primary" onClick={() => setShowAdd(true)} data-testid="am-add">
            <Plus size={14} /> New Avatar
          </button>
        </div>
      </div>

      {err && (
        <div style={{ padding: "10px 14px", borderRadius: 8, background: "rgba(248,113,113,0.10)", border: "1px solid rgba(248,113,113,0.32)", color: "#FCA5A5", fontFamily: "JetBrains Mono, monospace", fontSize: 12, marginBottom: 18 }}>
          {err}
        </div>
      )}

      {loading ? (
        <div className="am-empty">Loading avatars…</div>
      ) : merged.length === 0 ? (
        <div className="am-empty">No avatars configured.</div>
      ) : (
        <div className="am-grid">
          {merged.map((avatar) => (
            <div className="am-card" key={avatar.id} data-testid={`am-card-${avatar.id}`}>
              <div className="am-card-top">
                <div className="am-thumb">{avatar.emoji || "🤖"}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="am-card-id">{avatar.id}</div>
                  <div className="am-card-name">{avatar.name}</div>
                  <div className="am-card-meta">
                    {avatar.gender} · {String(avatar.ethnicity || "—").replace(/_/g, " ")}
                  </div>
                </div>
              </div>

              <div className="am-status-row">
                <span className={`am-status-pill ${avatar.status === "active" ? "active" : "draft"}`}>
                  {avatar.status}
                </span>
                <button
                  className="am-toggle"
                  onClick={() => toggleStatus(avatar)}
                  disabled={savingId === avatar.id}
                  style={{ marginLeft: "auto", color: avatar.status === "active" ? "#34D399" : "#71717A", background: "none", border: "none", cursor: "pointer" }}
                  data-testid={`am-toggle-${avatar.id}`}
                >
                  {avatar.status === "active" ? <ToggleRight size={26} /> : <ToggleLeft size={26} />}
                </button>
              </div>

              <div className="am-stats">
                <div>
                  <div className="am-stat-label">Selections</div>
                  <div className="am-stat-val">{avatar.stats?.times_selected || 0}</div>
                </div>
                <div>
                  <div className="am-stat-label">Voice</div>
                  <div className="am-stat-val" style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", letterSpacing: "0.04em", color: "#A1A1AA" }}>
                    {(avatar.voice_id || "—").replace(/^cartesia_/, "").replace(/_/g, " ")}
                  </div>
                </div>
              </div>

              <div className="am-card-cta">
                <button className="am-btn" onClick={() => previewAvatar(avatar)} data-testid={`am-preview-${avatar.id}`}>
                  <Eye size={13} /> Preview
                </button>
                <button className="am-btn" data-testid={`am-stats-${avatar.id}`}>
                  <BarChart3 size={13} /> Stats
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showAdd && <AddAvatarModal onClose={() => setShowAdd(false)} onCreated={load} />}
    </div>
  );
}

function AddAvatarModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    avatar_id: "",
    name: "ORA",
    gender: "female",
    ethnicity: "",
    glb_url: "",
    thumbnail: "",
    voice_id: "",
    elevenlabs_voice_id: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      const r = await fetch(`${API}/api/admin/avatars`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      if (onCreated) await onCreated();
      onClose();
    } catch (e2) {
      setErr(e2.message || String(e2));
    } finally {
      setSaving(false);
    }
  };

  const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="am-modal-bg" onClick={onClose}>
      <div className="am-modal" onClick={(e) => e.stopPropagation()} data-testid="am-modal">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <h2>New Avatar</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#71717A", cursor: "pointer" }}>
            <X size={20} />
          </button>
        </div>
        <form className="am-modal-form" onSubmit={submit}>
          <div>
            <label>ID (must start with `ora_`)</label>
            <input required pattern="^ora_[a-z0-9_]+$" value={form.avatar_id} onChange={update("avatar_id")} placeholder="ora_female_4" data-testid="am-form-id" />
          </div>
          <div>
            <label>Name</label>
            <input required value={form.name} onChange={update("name")} data-testid="am-form-name" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label>Gender</label>
              <select value={form.gender} onChange={update("gender")} data-testid="am-form-gender">
                <option value="female">Female</option>
                <option value="male">Male</option>
              </select>
            </div>
            <div>
              <label>Ethnicity</label>
              <input value={form.ethnicity} onChange={update("ethnicity")} placeholder="south_asian" data-testid="am-form-ethnicity" />
            </div>
          </div>
          <div>
            <label>Thumbnail URL</label>
            <input value={form.thumbnail} onChange={update("thumbnail")} placeholder="/avatars/thumbs/..." data-testid="am-form-thumb" />
          </div>
          <div>
            <label>GLB URL (optional)</label>
            <input value={form.glb_url} onChange={update("glb_url")} placeholder="/avatars/..." data-testid="am-form-glb" />
          </div>
          <div>
            <label>Voice ID</label>
            <input value={form.voice_id} onChange={update("voice_id")} placeholder="cartesia_warm_female_en_ca" data-testid="am-form-voice" />
          </div>
          <div>
            <label>ElevenLabs Voice ID (optional)</label>
            <input value={form.elevenlabs_voice_id} onChange={update("elevenlabs_voice_id")} data-testid="am-form-elevenlabs" />
          </div>
          {err && <div style={{ color: "#FCA5A5", fontSize: 12, fontFamily: "JetBrains Mono, monospace" }}>{err}</div>}
          <div className="am-modal-cta-row">
            <button type="button" className="am-btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="am-btn primary" disabled={saving} data-testid="am-form-submit">
              {saving ? "Creating…" : "Create as Draft"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
