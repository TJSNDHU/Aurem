/**
 * BugCatchWidget.jsx — iter D-60
 *
 * Floating bug-report button visible ONLY inside the admin shell. On
 * click it opens a modal that:
 *   • grabs a DOM screenshot via html2canvas
 *   • lets the founder annotate (pen / arrow / text)
 *   • collects last 200 console logs + 50 network calls + URL + viewport
 *   • POSTs to /api/admin/bug-reports
 *
 * Console + network capture starts on mount via global patches with
 * cleanup-safe wrappers.
 */
import React, { useEffect, useRef, useState, useCallback } from "react";
import html2canvas from "html2canvas";
import { Bug, X, Camera, Pen, ArrowUpRight, Type as TypeIcon,
         Trash2, Send, CheckCircle2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const MAX_LOGS = 200;
const MAX_NET  = 50;


function adminHeaders() {
  let token = "";
  try {
    token = sessionStorage.getItem("platform_token") ||
            localStorage.getItem("platform_token") ||
            localStorage.getItem("aurem_admin_token") ||
            sessionStorage.getItem("aurem_admin_token") ||
            localStorage.getItem("token") ||
            "";
  } catch { /* ignore */ }
  return token ? { Authorization: `Bearer ${token}` } : {};
}


/* ── Global recorder singleton (mounts once at module load) ── */

const _logs    = [];
const _network = [];

function _recordLog(level, args) {
  try {
    const msg = args.map(a => {
      if (typeof a === "string") return a;
      try { return JSON.stringify(a).slice(0, 400); }
      catch { return String(a).slice(0, 400); }
    }).join(" ").slice(0, 600);
    _logs.push({ level, msg, ts: new Date().toISOString() });
    if (_logs.length > MAX_LOGS) _logs.shift();
  } catch { /* ignore */ }
}

(function patchConsoleAndFetch() {
  if (typeof window === "undefined" || window.__bugcatch_patched) return;
  window.__bugcatch_patched = true;
  const orig = {
    log:   console.log,   info: console.info,
    warn:  console.warn,  error: console.error,
  };
  ["log", "info", "warn", "error"].forEach(lvl => {
    console[lvl] = function (...args) {
      _recordLog(lvl, args);
      try { orig[lvl].apply(console, args); } catch { /* ignore */ }
    };
  });
  window.addEventListener("error", e => {
    _recordLog("error", [e.message || "window-error", e.filename || "",
                          e.lineno || ""]);
  });
  window.addEventListener("unhandledrejection", e => {
    _recordLog("error", ["unhandled-promise",
                          (e.reason && (e.reason.message || e.reason)) || ""]);
  });

  // fetch interceptor
  const origFetch = window.fetch;
  window.fetch = async function (...args) {
    const started = Date.now();
    let url = "";
    let method = "GET";
    try {
      const input = args[0];
      const init  = args[1] || {};
      url = (typeof input === "string") ? input : (input.url || "");
      method = (init.method || (typeof input === "object" && input.method)
                  || "GET").toUpperCase();
    } catch { /* ignore */ }
    try {
      const resp = await origFetch.apply(this, args);
      _network.push({ method, url: String(url).slice(0, 240),
                       status: resp.status,
                       latency_ms: Date.now() - started,
                       ts: new Date().toISOString() });
      if (_network.length > MAX_NET) _network.shift();
      return resp;
    } catch (err) {
      _network.push({ method, url: String(url).slice(0, 240),
                       status: 0, error: String(err.message || err).slice(0, 200),
                       latency_ms: Date.now() - started,
                       ts: new Date().toISOString() });
      if (_network.length > MAX_NET) _network.shift();
      throw err;
    }
  };
})();


/* ── Annotation canvas ── */

function AnnotationCanvas({ baseImg, tool, color, strokes, setStrokes }) {
  const canvasRef = useRef(null);
  const [drawing, setDrawing] = useState(false);
  const [current, setCurrent] = useState(null);

  // Redraw every change
  useEffect(() => {
    const c = canvasRef.current; if (!c) return;
    const ctx = c.getContext("2d");
    const img = new Image();
    img.onload = () => {
      // Fit canvas to image (capped width 1100)
      const maxW = 1100;
      const scale = Math.min(1, maxW / img.width);
      c.width  = img.width * scale;
      c.height = img.height * scale;
      ctx.drawImage(img, 0, 0, c.width, c.height);
      strokes.forEach(s => drawStroke(ctx, s, scale));
      if (current) drawStroke(ctx, current, scale);
    };
    img.src = baseImg;
  }, [baseImg, strokes, current]);

  function drawStroke(ctx, s, scale = 1) {
    ctx.strokeStyle = s.color || "#FF8C35";
    ctx.fillStyle   = s.color || "#FF8C35";
    ctx.lineWidth   = 3;
    ctx.lineCap     = "round";
    if (s.kind === "pen" && s.points?.length > 1) {
      ctx.beginPath();
      ctx.moveTo(s.points[0].x, s.points[0].y);
      for (let i = 1; i < s.points.length; i++) {
        ctx.lineTo(s.points[i].x, s.points[i].y);
      }
      ctx.stroke();
    } else if (s.kind === "arrow" && s.from && s.to) {
      const { from, to } = s;
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.stroke();
      const angle = Math.atan2(to.y - from.y, to.x - from.x);
      const head = 12;
      ctx.beginPath();
      ctx.moveTo(to.x, to.y);
      ctx.lineTo(to.x - head * Math.cos(angle - 0.4),
                  to.y - head * Math.sin(angle - 0.4));
      ctx.lineTo(to.x - head * Math.cos(angle + 0.4),
                  to.y - head * Math.sin(angle + 0.4));
      ctx.closePath();
      ctx.fill();
    } else if (s.kind === "text" && s.at && s.text) {
      ctx.font = "bold 16px 'JetBrains Mono', monospace";
      const pad = 4;
      const w = ctx.measureText(s.text).width;
      ctx.fillStyle = "rgba(0,0,0,0.70)";
      ctx.fillRect(s.at.x - pad, s.at.y - 16, w + pad * 2, 22);
      ctx.fillStyle = s.color || "#FF8C35";
      ctx.fillText(s.text, s.at.x, s.at.y);
    }
  }

  function pos(e) {
    const c = canvasRef.current;
    const r = c.getBoundingClientRect();
    return { x: (e.clientX - r.left) * (c.width / r.width),
              y: (e.clientY - r.top)  * (c.height / r.height) };
  }

  function onDown(e) {
    if (!canvasRef.current) return;
    const p = pos(e);
    if (tool === "pen")   setCurrent({ kind: "pen",   color, points: [p] });
    if (tool === "arrow") setCurrent({ kind: "arrow", color, from: p, to: p });
    if (tool === "text") {
      const text = window.prompt("Annotation text:");
      if (text) setStrokes(s => [...s, { kind: "text", color, at: p, text }]);
      return;
    }
    setDrawing(true);
  }
  function onMove(e) {
    if (!drawing || !current) return;
    const p = pos(e);
    if (current.kind === "pen") {
      setCurrent({ ...current, points: [...current.points, p] });
    } else if (current.kind === "arrow") {
      setCurrent({ ...current, to: p });
    }
  }
  function onUp() {
    if (drawing && current) setStrokes(s => [...s, current]);
    setDrawing(false);
    setCurrent(null);
  }

  return (
    <canvas ref={canvasRef}
            data-testid="bugcatch-annot-canvas"
            onMouseDown={onDown}
            onMouseMove={onMove}
            onMouseUp={onUp}
            onMouseLeave={onUp}
            style={{ width: "100%", border: "1px solid rgba(255,255,255,0.10)",
                     borderRadius: 4, cursor: tool === "text" ? "text" : "crosshair",
                     background: "#000" }} />
  );
}


/* ── Main widget ── */

export default function BugCatchWidget() {
  const [open, setOpen]         = useState(false);
  const [step, setStep]         = useState("idle"); // idle|capturing|annotate|sending|done|error
  const [shot, setShot]         = useState("");
  const [strokes, setStrokes]   = useState([]);
  const [desc, setDesc]         = useState("");
  const [sev, setSev]           = useState("med");
  const [tool, setTool]         = useState("pen");
  const [color, setColor]       = useState("#FF8C35");
  const [error, setError]       = useState("");
  const [doneInfo, setDoneInfo] = useState(null);

  const openModal = useCallback(async () => {
    setOpen(true); setStep("capturing"); setError("");
    setStrokes([]); setDesc("");
    // give the modal a tick to fade before capturing — but actually
    // we want to capture the page BEFORE the modal renders, so do it
    // in the *same* tick (modal is portalled below this in DOM)
    try {
      const canvas = await html2canvas(document.body, {
        useCORS: true, scale: Math.min(window.devicePixelRatio || 1, 1.5),
        ignoreElements: el =>
          el?.dataset?.testid === "bugcatch-modal" ||
          el?.dataset?.testid === "bugcatch-fab",
        backgroundColor: "#0a0a0a",
      });
      // Compress to ~85% quality jpeg
      const dataUrl = canvas.toDataURL("image/jpeg", 0.78);
      setShot(dataUrl); setStep("annotate");
    } catch (e) {
      setError(`screenshot_failed: ${e.message || e}`);
      setStep("error");
    }
  }, []);

  async function send() {
    setStep("sending"); setError("");
    try {
      // Bake annotations into final image
      let finalImg = shot;
      try {
        const c = document.createElement("canvas");
        const img = new Image();
        img.src = shot;
        await new Promise(r => { img.onload = r; });
        c.width = img.width; c.height = img.height;
        const ctx = c.getContext("2d");
        ctx.drawImage(img, 0, 0);
        strokes.forEach(s => drawStrokeFinal(ctx, s));
        finalImg = c.toDataURL("image/jpeg", 0.78);
      } catch { /* keep raw shot */ }

      const payload = {
        description: desc,
        severity:    sev,
        screenshot_b64: finalImg,
        url: window.location.pathname + window.location.search,
        viewport: { w: window.innerWidth, h: window.innerHeight },
        user_agent: navigator.userAgent || "",
        console_logs: _logs.slice(-MAX_LOGS),
        network_calls: _network.slice(-MAX_NET),
        annotations: strokes,
      };
      const r = await fetch(`${API}/api/admin/bug-reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...adminHeaders() },
        body: JSON.stringify(payload),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "submit_failed");
      setDoneInfo(j.report || {});
      setStep("done");
    } catch (e) {
      setError(String(e.message || e));
      setStep("error");
    }
  }

  function drawStrokeFinal(ctx, s) {
    ctx.strokeStyle = s.color || "#FF8C35";
    ctx.fillStyle   = s.color || "#FF8C35";
    ctx.lineWidth   = 3;
    ctx.lineCap     = "round";
    if (s.kind === "pen" && s.points?.length > 1) {
      ctx.beginPath();
      ctx.moveTo(s.points[0].x, s.points[0].y);
      for (let i = 1; i < s.points.length; i++)
        ctx.lineTo(s.points[i].x, s.points[i].y);
      ctx.stroke();
    } else if (s.kind === "arrow" && s.from && s.to) {
      ctx.beginPath();
      ctx.moveTo(s.from.x, s.from.y);
      ctx.lineTo(s.to.x, s.to.y);
      ctx.stroke();
      const angle = Math.atan2(s.to.y - s.from.y, s.to.x - s.from.x);
      const head  = 14;
      ctx.beginPath();
      ctx.moveTo(s.to.x, s.to.y);
      ctx.lineTo(s.to.x - head * Math.cos(angle - 0.4),
                  s.to.y - head * Math.sin(angle - 0.4));
      ctx.lineTo(s.to.x - head * Math.cos(angle + 0.4),
                  s.to.y - head * Math.sin(angle + 0.4));
      ctx.closePath();
      ctx.fill();
    } else if (s.kind === "text" && s.at && s.text) {
      ctx.font = "bold 18px 'JetBrains Mono', monospace";
      const pad = 5;
      const w = ctx.measureText(s.text).width;
      ctx.fillStyle = "rgba(0,0,0,0.75)";
      ctx.fillRect(s.at.x - pad, s.at.y - 18, w + pad * 2, 24);
      ctx.fillStyle = s.color || "#FF8C35";
      ctx.fillText(s.text, s.at.x, s.at.y);
    }
  }

  function reset() {
    setOpen(false); setStep("idle"); setShot("");
    setStrokes([]); setDesc(""); setError("");
    setDoneInfo(null);
  }

  return (
    <>
      {/* Floating button (always visible inside admin shell) */}
      <button data-testid="bugcatch-fab"
              onClick={openModal}
              title="Report a bug · BugCatch"
              style={{ position: "fixed", right: 22, bottom: 22,
                       width: 48, height: 48, borderRadius: "50%",
                       background: "linear-gradient(135deg,#FF6B00,#FF8C35)",
                       border: "none", color: "#fff",
                       boxShadow: "0 6px 18px rgba(255,107,0,0.45)",
                       cursor: "pointer", zIndex: 9000,
                       display: "flex", alignItems: "center",
                       justifyContent: "center" }}>
        <Bug size={20} />
      </button>

      {open && (
        <div data-testid="bugcatch-modal"
             style={{ position: "fixed", inset: 0,
                      background: "rgba(0,0,0,0.78)",
                      zIndex: 9001, display: "flex",
                      alignItems: "flex-start", justifyContent: "center",
                      padding: 24, overflow: "auto" }}>
          <div style={{ width: "100%", maxWidth: 1180,
                        background: "#13110d",
                        border: "1px solid rgba(255,255,255,0.10)",
                        borderRadius: 8, padding: 18,
                        color: "#F0EDE8" }}>
            <div style={{ display: "flex", alignItems: "center",
                           gap: 10, marginBottom: 12 }}>
              <Bug size={16} style={{ color: "#FF8C35" }} />
              <strong style={{ fontFamily: "'Cinzel', serif",
                                color: "#E8C86A", fontSize: 16 }}>
                BugCatch · report a bug
              </strong>
              <button onClick={reset}
                      data-testid="bugcatch-close"
                      style={{ marginLeft: "auto", background: "transparent",
                               border: "none", color: "#a1958a",
                               cursor: "pointer" }}>
                <X size={16} />
              </button>
            </div>

            {step === "capturing" && (
              <div data-testid="bugcatch-capturing"
                   style={{ padding: 30, textAlign: "center",
                            fontFamily: "'JetBrains Mono', monospace",
                            color: "#a1958a", fontSize: 12 }}>
                <Camera size={20} style={{ marginBottom: 6 }} /><br />
                grabbing screenshot…
              </div>
            )}

            {step === "annotate" && (
              <>
                {/* Toolbar */}
                <div style={{ display: "flex", gap: 6, alignItems: "center",
                               marginBottom: 8, fontSize: 11,
                               fontFamily: "'JetBrains Mono', monospace" }}>
                  {[
                    { id: "pen",   label: "Pen",   icon: <Pen size={12} /> },
                    { id: "arrow", label: "Arrow", icon: <ArrowUpRight size={12} /> },
                    { id: "text",  label: "Text",  icon: <TypeIcon size={12} /> },
                  ].map(t => (
                    <button key={t.id} onClick={() => setTool(t.id)}
                            data-testid={`bugcatch-tool-${t.id}`}
                            style={{ padding: "5px 10px",
                                     background: tool === t.id
                                       ? "rgba(255,140,53,0.18)"
                                       : "rgba(255,255,255,0.02)",
                                     border: `1px solid ${tool === t.id
                                       ? "#FF8C35" : "rgba(255,255,255,0.10)"}`,
                                     color: tool === t.id ? "#FF8C35" : "#a1958a",
                                     borderRadius: 4, cursor: "pointer",
                                     display: "inline-flex",
                                     alignItems: "center", gap: 4 }}>
                      {t.icon} {t.label}
                    </button>
                  ))}
                  {["#FF8C35", "#FF6060", "#4ade80", "#E8C86A"].map(c => (
                    <button key={c} onClick={() => setColor(c)}
                            data-testid={`bugcatch-color-${c}`}
                            style={{ width: 18, height: 18, borderRadius: "50%",
                                     background: c, marginLeft: 4,
                                     border: color === c
                                       ? "2px solid #fff"
                                       : "1px solid rgba(255,255,255,0.20)",
                                     cursor: "pointer" }} />
                  ))}
                  <button onClick={() => setStrokes([])}
                          data-testid="bugcatch-clear"
                          style={{ marginLeft: "auto",
                                   background: "rgba(255,96,96,0.10)",
                                   border: "1px solid rgba(255,96,96,0.40)",
                                   color: "#FF6060",
                                   padding: "5px 10px",
                                   borderRadius: 4, cursor: "pointer",
                                   display: "inline-flex",
                                   alignItems: "center", gap: 4 }}>
                    <Trash2 size={11} /> Clear
                  </button>
                </div>

                <AnnotationCanvas baseImg={shot} tool={tool}
                                   color={color}
                                   strokes={strokes}
                                   setStrokes={setStrokes} />

                <div style={{ marginTop: 10 }}>
                  <label style={{ fontSize: 11, color: "#a1958a",
                                   fontFamily: "'JetBrains Mono', monospace" }}>
                    What went wrong?
                  </label>
                  <textarea value={desc}
                            onChange={e => setDesc(e.target.value)}
                            data-testid="bugcatch-desc"
                            placeholder="2 lines · what you did + what you expected vs saw"
                            rows={3}
                            style={{ width: "100%", marginTop: 4,
                                     padding: 8,
                                     background: "rgba(0,0,0,0.30)",
                                     border: "1px solid rgba(255,255,255,0.10)",
                                     color: "#F0EDE8", borderRadius: 4,
                                     fontFamily: "'JetBrains Mono', monospace",
                                     fontSize: 12 }} />
                </div>

                <div style={{ marginTop: 8, display: "flex",
                               alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 11, color: "#a1958a",
                                  fontFamily: "'JetBrains Mono', monospace" }}>
                    severity:
                  </span>
                  {["low", "med", "high"].map(s => (
                    <button key={s} onClick={() => setSev(s)}
                            data-testid={`bugcatch-sev-${s}`}
                            style={{ padding: "4px 12px",
                                     background: sev === s
                                       ? "rgba(255,140,53,0.18)"
                                       : "rgba(255,255,255,0.02)",
                                     border: `1px solid ${sev === s
                                       ? "#FF8C35" : "rgba(255,255,255,0.10)"}`,
                                     color: sev === s ? "#FF8C35" : "#a1958a",
                                     borderRadius: 4, cursor: "pointer",
                                     fontSize: 11 }}>
                      {s}
                    </button>
                  ))}
                  <button onClick={send}
                          disabled={!desc.trim()}
                          data-testid="bugcatch-send"
                          style={{ marginLeft: "auto",
                                   background: "linear-gradient(135deg,#FF6B00,#FF8C35)",
                                   border: "none", color: "#fff",
                                   padding: "8px 18px", borderRadius: 4,
                                   fontSize: 12, fontWeight: 500,
                                   cursor: desc.trim() ? "pointer" : "not-allowed",
                                   opacity: desc.trim() ? 1 : 0.5,
                                   display: "inline-flex",
                                   alignItems: "center", gap: 6 }}>
                    <Send size={12} /> Send report
                  </button>
                </div>
                <div style={{ marginTop: 6, fontSize: 10, color: "#7a7468",
                               fontFamily: "'JetBrains Mono', monospace" }}>
                  captures: {_logs.length} console entries · {_network.length} network calls
                </div>
              </>
            )}

            {step === "sending" && (
              <div style={{ padding: 30, textAlign: "center",
                             fontFamily: "'JetBrains Mono', monospace",
                             color: "#a1958a", fontSize: 12 }}>
                sending to AUREM backend…
              </div>
            )}

            {step === "done" && doneInfo && (
              <div data-testid="bugcatch-done"
                   style={{ padding: 18, textAlign: "left",
                            fontFamily: "'JetBrains Mono', monospace",
                            color: "#4ade80", fontSize: 12 }}>
                <div style={{ display: "flex", alignItems: "center",
                               gap: 8, marginBottom: 8 }}>
                  <CheckCircle2 size={16} />
                  <strong>Report submitted · {doneInfo.report_id}</strong>
                </div>
                <div style={{ color: "#a1958a", marginBottom: 8 }}>
                  AI root cause: {doneInfo.ai_root_cause
                    ? doneInfo.ai_root_cause
                    : `(skipped — ${doneInfo.ai_model || "no_llm"})`}
                </div>
                <div style={{ color: "#a1958a" }}>
                  emailed to founder · status: open · view at /admin/bug-reports
                </div>
                <button onClick={reset} data-testid="bugcatch-done-close"
                        style={{ marginTop: 12,
                                 background: "rgba(74,222,128,0.10)",
                                 border: "1px solid #4ade80",
                                 color: "#4ade80",
                                 padding: "6px 16px", borderRadius: 4,
                                 cursor: "pointer", fontSize: 11 }}>
                  Done
                </button>
              </div>
            )}

            {step === "error" && (
              <div data-testid="bugcatch-error"
                   style={{ padding: 18,
                            fontFamily: "'JetBrains Mono', monospace",
                            color: "#FF6060", fontSize: 12 }}>
                error: {error}
                <div style={{ marginTop: 12 }}>
                  <button onClick={reset}
                          style={{ background: "rgba(255,96,96,0.10)",
                                   border: "1px solid #FF6060",
                                   color: "#FF6060",
                                   padding: "6px 16px", borderRadius: 4,
                                   cursor: "pointer", fontSize: 11 }}>
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
