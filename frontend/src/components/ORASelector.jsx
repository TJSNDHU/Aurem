/**
 * AUREM — ORA Avatar Selector (Phase 2)
 * iter 322v · 2026-02-06
 *
 * First-time visitors see a 3×2 grid of active ORA avatars. Selection
 * persists to localStorage AND the backend (POST /api/ora/avatar-preference)
 * so subsequent visits skip this screen instantly.
 *
 * Defensive design:
 *   - thumbnail load failure → emoji fallback (no broken-image icon)
 *   - backend POST failure   → still saves to localStorage (offline-safe)
 *   - LocalStorage disabled  → simply re-show selector each visit
 *   - No TTS / no STT / no paid integrations needed for this phase.
 */
import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Check, Sparkles } from "lucide-react";
import {
  ORA_AVATARS,
  AVATAR_SETTINGS,
  LOCAL_STORAGE_KEY,
} from "../config/ora_avatars.config";

const API = process.env.REACT_APP_BACKEND_URL || "";

// ─────────────────────────────────────────────────────────────────────
// CSS — scoped under .ora-selector so it doesn't leak into other pages
// ─────────────────────────────────────────────────────────────────────
const SELECTOR_CSS = `
.ora-selector{
  position:fixed; inset:0; z-index:9999;
  background:#050505;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  padding:32px;
  font-family:'Outfit',system-ui,sans-serif; color:#FAFAFA;
  overflow-y:auto;
}
.ora-sel-eyebrow{
  font-family:'JetBrains Mono',ui-monospace,monospace;
  font-size:11px; letter-spacing:0.22em; text-transform:uppercase;
  color:#D4A646; margin-bottom:14px;
  display:inline-flex; align-items:center; gap:8px;
}
.ora-sel-h1{
  font-family:'Cabinet Grotesk',sans-serif; font-weight:800;
  font-size:clamp(28px,4.5vw,52px);
  letter-spacing:-0.03em; line-height:1.0;
  text-align:center; margin:0 0 12px;
}
.ora-sel-h1 em{
  font-style:normal;
  background:linear-gradient(135deg,#D4A646 0%,#F4C649 100%);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
}
.ora-sel-sub{
  font-size:15px; color:#A1A1AA; max-width:520px; line-height:1.6;
  text-align:center; margin:0 0 36px;
}
.ora-sel-grid{
  display:grid; grid-template-columns:repeat(3,1fr); gap:18px;
  width:min(820px,92vw);
}
@media(max-width:680px){.ora-sel-grid{grid-template-columns:repeat(2,1fr);}}
@media(max-width:420px){.ora-sel-grid{grid-template-columns:1fr;}}

.ora-sel-card{
  position:relative; aspect-ratio:3/4;
  background:linear-gradient(180deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01));
  border:1px solid rgba(255,255,255,0.08);
  border-radius:18px; overflow:hidden; cursor:pointer;
  transition:border-color 0.3s, transform 0.3s, box-shadow 0.3s;
}
.ora-sel-card:hover{
  border-color:rgba(212,166,70,0.55);
  transform:translateY(-3px);
  box-shadow:0 16px 48px rgba(212,166,70,0.18);
}
.ora-sel-card.selected{
  border-color:#D4A646;
  box-shadow:0 0 0 3px rgba(212,166,70,0.22), 0 16px 48px rgba(212,166,70,0.32);
}
.ora-sel-thumb{
  position:absolute; inset:0;
  display:flex; align-items:center; justify-content:center;
  font-size:120px;
  background:radial-gradient(ellipse 80% 60% at 50% 30%, rgba(212,166,70,0.14) 0%, transparent 65%);
}
.ora-sel-thumb img{
  position:absolute; inset:0; width:100%; height:100%;
  object-fit:cover; opacity:0; transition:opacity 0.3s;
}
.ora-sel-thumb img.loaded{opacity:1;}
.ora-sel-info{
  position:absolute; left:0; right:0; bottom:0; z-index:2;
  padding:18px 20px;
  background:linear-gradient(to top, rgba(5,5,5,0.95) 0%, rgba(5,5,5,0.45) 60%, transparent 100%);
}
.ora-sel-name{
  font-family:'Cabinet Grotesk',sans-serif; font-weight:800;
  font-size:22px; letter-spacing:-0.02em; margin:0 0 4px; color:#FAFAFA;
}
.ora-sel-meta{
  font-family:'JetBrains Mono',monospace; font-size:10px;
  letter-spacing:0.18em; text-transform:uppercase; color:#A1A1AA;
}
.ora-sel-check{
  position:absolute; top:14px; right:14px; z-index:3;
  width:30px; height:30px; border-radius:50%;
  background:#D4A646; color:#0A0A0B;
  display:flex; align-items:center; justify-content:center;
  box-shadow:0 4px 16px rgba(212,166,70,0.45);
}
.ora-sel-confirm{
  margin-top:32px; display:flex; gap:12px; align-items:center;
}
.ora-sel-cta{
  display:inline-flex; align-items:center; gap:10px;
  padding:14px 28px; border-radius:8px; border:none;
  background:linear-gradient(135deg,#F4C649,#D4A646);
  color:#0A0A0B; font-size:14px; font-weight:600; letter-spacing:0.02em;
  box-shadow:0 8px 28px rgba(212,166,70,0.35);
  cursor:pointer; transition:all 0.25s;
}
.ora-sel-cta:disabled{
  background:rgba(255,255,255,0.06); color:#71717A;
  box-shadow:none; cursor:not-allowed;
}
.ora-sel-cta:not(:disabled):hover{transform:translateY(-1px);}
.ora-sel-skip{
  background:transparent; border:none; color:#71717A;
  font-size:12px; cursor:pointer; padding:8px 12px;
  letter-spacing:0.06em;
}
.ora-sel-skip:hover{color:#A1A1AA;}
.ora-sel-error{
  margin-top:18px; padding:10px 16px; border-radius:6px;
  background:rgba(248,113,113,0.10); border:1px solid rgba(248,113,113,0.32);
  color:#FCA5A5; font-size:12px;
  font-family:'JetBrains Mono',monospace; letter-spacing:0.04em;
}
`;

function AvatarThumb({ avatar }) {
  const [loaded, setLoaded] = useState(false);
  const [errored, setErrored] = useState(false);
  return (
    <div className="ora-sel-thumb">
      <span aria-hidden style={{ visibility: loaded && !errored ? "hidden" : "visible" }}>
        {avatar.emoji || "🤖"}
      </span>
      {!errored && (
        <img
          src={avatar.thumbnail}
          alt=""
          className={loaded ? "loaded" : ""}
          onLoad={() => setLoaded(true)}
          onError={() => setErrored(true)}
        />
      )}
    </div>
  );
}

/**
 * Props:
 *   userId  — string identifier (any unique handle works; we don't crash without it)
 *   onSelect(avatar) — fired AFTER local + backend persistence
 *   onSkip() — optional; skip selection for this session only
 */
export default function ORASelector({ userId = "anon", onSelect, onSkip }) {
  const [picked, setPicked] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const visible = useMemo(
    () => ORA_AVATARS.filter((a) => a.status === "active").slice(0, AVATAR_SETTINGS.max_visible_in_picker),
    []
  );

  const handleConfirm = async () => {
    if (!picked || busy) return;
    setBusy(true);
    setErr("");
    // 1) Local persistence is the source of truth — never blocked on backend.
    try {
      window.localStorage.setItem(LOCAL_STORAGE_KEY, picked.id);
    } catch (_e) {
      /* localStorage disabled — selector will re-prompt next visit, that's fine */
    }
    // 2) Best-effort backend sync (analytics + admin stats).
    try {
      const r = await fetch(`${API}/api/ora/avatar-preference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, avatar_id: picked.id }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    } catch (e) {
      // Don't block the user — log and continue. The localStorage value still wins.
      // eslint-disable-next-line no-console
      console.warn("[ORASelector] preference sync failed:", e?.message || e);
    }
    setBusy(false);
    if (typeof onSelect === "function") onSelect(picked);
  };

  return (
    <div className="ora-selector" data-testid="ora-selector">
      <style dangerouslySetInnerHTML={{ __html: SELECTOR_CSS }} />

      <div className="ora-sel-eyebrow">
        <Sparkles size={12} /> Choose your ORA
      </div>
      <h1 className="ora-sel-h1">
        Meet the <em>autonomous</em> AI<br /> who'll run beside you.
      </h1>
      <p className="ora-sel-sub">
        Pick the ORA you want as your AI partner. Voice, tone and personality
        adapt to your selection. You can change this anytime in Settings.
      </p>

      <div className="ora-sel-grid">
        {visible.map((avatar) => {
          const sel = picked?.id === avatar.id;
          return (
            <motion.div
              key={avatar.id}
              className={`ora-sel-card${sel ? " selected" : ""}`}
              data-testid={`ora-sel-card-${avatar.id}`}
              onClick={() => setPicked(avatar)}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            >
              <AvatarThumb avatar={avatar} />
              {sel && (
                <div className="ora-sel-check" aria-hidden>
                  <Check size={16} strokeWidth={3} />
                </div>
              )}
              <div className="ora-sel-info">
                <h3 className="ora-sel-name">{avatar.name}</h3>
                <div className="ora-sel-meta">
                  {avatar.gender} · {String(avatar.ethnicity).replace(/_/g, " ")}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      <div className="ora-sel-confirm">
        <button
          className="ora-sel-cta"
          disabled={!picked || busy}
          onClick={handleConfirm}
          data-testid="ora-sel-confirm"
        >
          {busy ? "Saving…" : picked ? `Continue with ${picked.name}` : "Select an ORA"}
          <Check size={16} />
        </button>
        {typeof onSkip === "function" && (
          <button className="ora-sel-skip" onClick={onSkip} data-testid="ora-sel-skip">
            Maybe later
          </button>
        )}
      </div>

      {err && <div className="ora-sel-error">{err}</div>}
    </div>
  );
}
