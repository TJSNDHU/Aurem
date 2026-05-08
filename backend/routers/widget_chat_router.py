"""
ORA Website Chat Widget — iter 282al-8 (Prompt 10).

Embeddable chat widget for AUREM clients. Usage on a client site:

    <script async src="https://aurem.live/api/widget.js?bin=AURE-XYZ123"></script>

Backend surface:
  GET  /api/widget.js               → emits embeddable JS snippet
  GET  /api/widget/config/{bin}     → brand config (color, biz name, welcome)
  POST /api/widget/chat             → AI reply via llm_gateway cascade
  GET  /api/widget/health           → pillar chip probe

Conversations are stored in `db.widget_conversations` with TTL 60d.

ORA's persona is identical to /api/aurem/chat — Canadian-built, value-first,
CASL-aware. The system prompt is *augmented* with the client's business
context (BIN, business_name, services, city) so visitors get answers grounded
in the actual business.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server  # noqa: WPS433
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


# ─────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────
class WidgetChatRequest(BaseModel):
    bin: str
    session_id: Optional[str] = None
    message: str
    page_url: Optional[str] = None
    visitor_email: Optional[str] = None


class WidgetChatResponse(BaseModel):
    session_id: str
    reply: str
    business_name: str
    cta_url: Optional[str] = None
    timestamp: str


class WidgetConfig(BaseModel):
    bin: str
    business_name: str
    welcome_message: str
    color_primary: str
    color_accent: str
    cta_url: Optional[str] = None
    casl_footer: str


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
DEFAULT_PRIMARY = "#FF6B00"
DEFAULT_ACCENT = "#C9A84C"
CASL_FOOTER = (
    "Powered by AUREM — Canadian-built. "
    "Reply STOP to opt out of any messages."
)


def _safe_bin(s: str) -> str:
    """Sanitize BIN to avoid header / template injection."""
    return re.sub(r"[^A-Za-z0-9_\-]", "", s or "")[:64]


async def _resolve_client(bin_raw: str) -> dict:
    """Look up the client by BIN. Returns a dict with business_name,
    color tokens, services, city. Falls back to AUREM defaults."""
    bin_safe = _safe_bin(bin_raw)
    db = _get_db()
    if not bin_safe or db is None:
        return {
            "bin": bin_safe or "DEMO",
            "business_name": "AUREM Demo",
            "city": "Mississauga",
            "category": "general",
            "services": [],
            "color_primary": DEFAULT_PRIMARY,
            "color_accent": DEFAULT_ACCENT,
            "welcome_message": "Hi! Ask me anything — I'm here to help.",
            "cta_url": None,
        }

    # Try platform_users first (paying clients), then auto_built_sites
    # (lead demo sites), then a generic AUREM persona.
    try:
        u = await db.platform_users.find_one(
            {"bin": bin_safe},
            projection={
                "_id": 0, "business_name": 1, "city": 1,
                "category": 1, "color_primary": 1, "color_accent": 1,
                "widget_welcome": 1, "cta_url": 1, "services": 1,
            },
        )
        if u:
            return {
                "bin": bin_safe,
                "business_name": u.get("business_name") or "your business",
                "city": u.get("city") or "Mississauga",
                "category": u.get("category") or "general",
                "services": u.get("services") or [],
                "color_primary": u.get("color_primary") or DEFAULT_PRIMARY,
                "color_accent": u.get("color_accent") or DEFAULT_ACCENT,
                "welcome_message": (
                    u.get("widget_welcome")
                    or f"Hi! Ask anything about {u.get('business_name') or 'us'}."
                ),
                "cta_url": u.get("cta_url"),
            }
    except Exception as e:
        logger.debug(f"[widget] platform_users lookup failed: {e}")

    try:
        s = await db.auto_built_sites.find_one(
            {"bin": bin_safe},
            projection={
                "_id": 0, "business_name": 1, "city": 1, "category": 1,
                "preview_url": 1, "services_used": 1,
            },
            sort=[("ts", -1)],
        )
        if s:
            return {
                "bin": bin_safe,
                "business_name": s.get("business_name") or "your business",
                "city": s.get("city") or "Mississauga",
                "category": s.get("category") or "general",
                "services": s.get("services_used") or [],
                "color_primary": DEFAULT_PRIMARY,
                "color_accent": DEFAULT_ACCENT,
                "welcome_message": (
                    f"Hi! Ask anything about "
                    f"{s.get('business_name') or 'us'} — "
                    f"happy to help."
                ),
                "cta_url": s.get("preview_url"),
            }
    except Exception as e:
        logger.debug(f"[widget] auto_built_sites lookup failed: {e}")

    return {
        "bin": bin_safe,
        "business_name": "AUREM",
        "city": "Mississauga",
        "category": "general",
        "services": [],
        "color_primary": DEFAULT_PRIMARY,
        "color_accent": DEFAULT_ACCENT,
        "welcome_message": "Hi! Ask me anything about AUREM.",
        "cta_url": "https://aurem.live",
    }


def _build_system_prompt(client: dict) -> str:
    biz = client.get("business_name") or "this business"
    city = client.get("city") or "Canada"
    cat = client.get("category") or "general services"
    svc_list = client.get("services") or []
    if isinstance(svc_list, list) and svc_list and isinstance(svc_list[0], dict):
        svc_blob = ", ".join(
            (s.get("name") or "") for s in svc_list[:6] if s.get("name")
        )
    else:
        svc_blob = ", ".join(str(s) for s in (svc_list or [])[:6])
    return (
        f"You are ORA, the AI concierge for {biz}, a "
        f"{cat} business in {city}, Canada.\n\n"
        "VALUE-FIRST RULES:\n"
        "  1. OBSERVE — show you understand what the visitor is asking.\n"
        "  2. OFFER VALUE — answer the question or share a useful insight\n"
        "     before asking for anything.\n"
        "  3. SOFT CTA — if relevant, offer a next step (book, call, "
        "request quote). Never push.\n"
        "  4. OPT-OUT — if collecting any contact info, mention it's\n"
        "     optional and the visitor can stop anytime.\n\n"
        "TONE: friendly, helpful, knowledgeable Canadian neighbour. "
        "Use Canadian spelling (colour, neighbour, centre). "
        "Use Celsius, km. Reference Canadian context where relevant.\n\n"
        f"BUSINESS CONTEXT — Business: {biz} | Location: {city} | "
        f"Category: {cat}"
        + (f" | Services: {svc_blob}" if svc_blob else "")
        + ".\n\nHARD RULES:\n"
        "  - Never invent services, pricing, or guarantees not provided "
        "in the business context.\n"
        "  - If asked something you don't know, offer to take a name "
        "+ phone so the team can follow up.\n"
        "  - Keep responses under 80 words. Conversational, not robotic.\n"
        "  - Never use hard sales CTAs ('buy now', 'sign up today').\n"
        "  - Powered by AUREM (Canadian-built, Mississauga ON)."
    )


async def _llm_reply(system_prompt: str, history: list[dict],
                     user_msg: str) -> dict:
    """Route through llm_gateway cascade. Returns {ok, content, provider}."""
    try:
        from services.llm_gateway import call_llm_with_meta
    except Exception as e:
        return {"ok": False, "content": "", "provider": "import-fail",
                "error": str(e)}
    # Compose final user prompt with last 4 turns of history for context.
    convo = ""
    for turn in (history or [])[-4:]:
        role = turn.get("role") or "user"
        content = (turn.get("content") or "").strip()
        if content:
            convo += f"\n{role.upper()}: {content}"
    final = f"{convo}\nUSER: {user_msg.strip()}\nORA:"
    try:
        gw = await call_llm_with_meta(system_prompt, final, max_tokens=300)
        return gw
    except Exception as e:
        return {"ok": False, "content": "", "provider": "exc",
                "error": str(e)[:160]}


def _hardcoded_fallback(client: dict, user_msg: str) -> str:
    biz = client.get("business_name") or "the team"
    return (
        f"Hi! Thanks for reaching out about {biz}. I'm having a quick "
        f"hiccup pulling that info — leave your name + phone and we'll "
        f"get right back to you. (Powered by AUREM — Canadian-built. "
        f"Optional, opt-out anytime.)"
    )


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────
@router.get("/api/widget/health")
async def widget_health() -> dict:
    db = _get_db()
    return {
        "ok": True,
        "service": "widget_chat",
        "db_attached": db is not None,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/widget/config/{bin}")
async def widget_config(bin: str) -> WidgetConfig:
    client = await _resolve_client(bin)
    return WidgetConfig(
        bin=client["bin"],
        business_name=client["business_name"],
        welcome_message=client["welcome_message"],
        color_primary=client["color_primary"],
        color_accent=client["color_accent"],
        cta_url=client.get("cta_url"),
        casl_footer=CASL_FOOTER,
    )


@router.post("/api/widget/chat", response_model=WidgetChatResponse)
async def widget_chat(req: WidgetChatRequest) -> WidgetChatResponse:
    if not (req.message or "").strip():
        raise HTTPException(status_code=400, detail="message required")
    if len(req.message) > 2000:
        raise HTTPException(status_code=400,
                            detail="message too long (>2000 chars)")
    client = await _resolve_client(req.bin)
    session_id = req.session_id or f"wgt-{uuid.uuid4().hex[:12]}"

    db = _get_db()
    history: list[dict] = []
    if db is not None:
        try:
            cur = db.widget_conversations.find(
                {"session_id": session_id},
                projection={"_id": 0, "role": 1, "content": 1, "ts": 1},
                sort=[("ts", 1)],
            ).limit(20)
            async for t in cur:
                history.append(t)
        except Exception as e:
            logger.debug(f"[widget] history load failed: {e}")

    system_prompt = _build_system_prompt(client)
    gw = await _llm_reply(system_prompt, history, req.message)
    if gw.get("ok") and (gw.get("content") or "").strip():
        reply = gw["content"].strip()
    else:
        reply = _hardcoded_fallback(client, req.message)

    # Trim runaway replies.
    if len(reply) > 1200:
        reply = reply[:1200].rstrip() + "…"

    now = datetime.now(timezone.utc)
    if db is not None:
        try:
            await db.widget_conversations.insert_many([
                {
                    "session_id": session_id, "bin": client["bin"],
                    "role": "user", "content": req.message[:2000],
                    "page_url": (req.page_url or "")[:500],
                    "visitor_email": (req.visitor_email or "")[:200],
                    "ts": now,
                },
                {
                    "session_id": session_id, "bin": client["bin"],
                    "role": "assistant", "content": reply,
                    "provider": gw.get("provider"),
                    "ts": now,
                },
            ])
        except Exception as e:
            logger.debug(f"[widget] insert failed: {e}")

    return WidgetChatResponse(
        session_id=session_id,
        reply=reply,
        business_name=client["business_name"],
        cta_url=client.get("cta_url"),
        timestamp=now.isoformat(),
    )


@router.get("/api/widget.js")
async def widget_js(request: Request) -> Response:
    """Emit the embeddable widget snippet. Usage:

        <script async src="https://aurem.live/api/widget.js?bin=XYZ"></script>

    The script reads `bin` from its own src URL and bootstraps a floating
    chat bubble that calls /api/widget/config/{bin} + /api/widget/chat.
    """
    backend_origin = (
        os.environ.get("AUREM_PUBLIC_API")
        or str(request.base_url).rstrip("/")
    )
    js = WIDGET_JS_TEMPLATE.replace("__BACKEND__", backend_origin)
    return Response(
        content=js,
        media_type="application/javascript; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=300",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─────────────────────────────────────────────────────────────────────
# Embeddable widget JS — pure vanilla, ~6KB
# ─────────────────────────────────────────────────────────────────────
WIDGET_JS_TEMPLATE = r"""(function(){
  var BACKEND = "__BACKEND__";
  var script = document.currentScript;
  if(!script){ var s=document.getElementsByTagName('script'); script=s[s.length-1]; }
  var src = (script && script.src) || "";
  var binMatch = src.match(/[?&]bin=([^&]+)/);
  var BIN = binMatch ? decodeURIComponent(binMatch[1]) : "DEMO";

  if(window.__AUREM_WIDGET_LOADED__) return;
  window.__AUREM_WIDGET_LOADED__ = true;

  var sessionId = (function(){
    try {
      var k = "aurem_widget_session_" + BIN;
      var v = window.sessionStorage.getItem(k);
      if(!v){ v = "wgt-" + Math.random().toString(36).slice(2,14); window.sessionStorage.setItem(k,v); }
      return v;
    } catch(e){ return "wgt-" + Math.random().toString(36).slice(2,14); }
  })();

  var cfg = {
    business_name: "AUREM",
    welcome_message: "Hi! Ask me anything.",
    color_primary: "#FF6B00",
    color_accent: "#C9A84C",
    cta_url: null,
    casl_footer: "Powered by AUREM — Canadian-built. Reply STOP to opt out."
  };

  function injectStyles(){
    var css = ""
      + ".aurem-bubble{position:fixed;bottom:24px;right:24px;width:60px;height:60px;border-radius:50%;background:"+cfg.color_primary+";color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 8px 24px rgba(0,0,0,0.2);font-size:28px;z-index:2147483646;border:none;font-family:system-ui,sans-serif;}"
      + ".aurem-bubble:hover{transform:scale(1.05);transition:transform .15s ease;}"
      + ".aurem-panel{position:fixed;bottom:96px;right:24px;width:360px;max-width:calc(100vw - 32px);height:520px;max-height:calc(100vh - 120px);background:#0d0d0d;color:#f5f5f5;border:1px solid "+cfg.color_accent+";border-radius:14px;box-shadow:0 16px 48px rgba(0,0,0,0.35);display:none;flex-direction:column;font-family:system-ui,-apple-system,sans-serif;z-index:2147483647;overflow:hidden;}"
      + ".aurem-panel.open{display:flex;}"
      + ".aurem-head{padding:14px 16px;background:linear-gradient(90deg,"+cfg.color_primary+",#9b3a00);font-weight:600;font-size:14px;letter-spacing:0.04em;display:flex;align-items:center;justify-content:space-between;}"
      + ".aurem-head .x{cursor:pointer;font-size:20px;line-height:1;background:transparent;border:none;color:#fff;}"
      + ".aurem-msgs{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;font-size:13px;line-height:1.45;}"
      + ".aurem-msg{padding:10px 12px;border-radius:10px;max-width:85%;white-space:pre-wrap;word-wrap:break-word;}"
      + ".aurem-msg.user{align-self:flex-end;background:"+cfg.color_primary+";color:#fff;}"
      + ".aurem-msg.bot{align-self:flex-start;background:#1c1c1c;border:1px solid #2a2a2a;}"
      + ".aurem-input-row{display:flex;gap:8px;padding:10px;border-top:1px solid #1f1f1f;background:#0a0a0a;}"
      + ".aurem-input{flex:1;background:#151515;border:1px solid #2a2a2a;color:#f5f5f5;padding:10px 12px;border-radius:8px;font-size:13px;outline:none;font-family:inherit;}"
      + ".aurem-input:focus{border-color:"+cfg.color_accent+";}"
      + ".aurem-send{background:"+cfg.color_accent+";color:#000;border:none;border-radius:8px;padding:0 14px;cursor:pointer;font-weight:600;font-size:13px;}"
      + ".aurem-send:disabled{opacity:0.5;cursor:not-allowed;}"
      + ".aurem-footer{font-size:10px;color:#777;padding:6px 12px 10px;text-align:center;letter-spacing:0.04em;}";
    var style = document.createElement("style");
    style.id = "aurem-widget-styles";
    style.textContent = css;
    document.head.appendChild(style);
  }

  function el(tag, attrs, text){
    var e = document.createElement(tag);
    if(attrs) for(var k in attrs){ e.setAttribute(k, attrs[k]); }
    if(text != null) e.textContent = text;
    return e;
  }

  function renderMessage(role, text){
    var m = el("div", {"class":"aurem-msg "+role, "data-testid":"aurem-msg-"+role}, text);
    return m;
  }

  function bootstrap(){
    injectStyles();
    var bubble = el("button", {"class":"aurem-bubble","aria-label":"Open chat","data-testid":"aurem-widget-bubble"}, "💬");
    var panel = el("div", {"class":"aurem-panel","data-testid":"aurem-widget-panel"});
    var head = el("div", {"class":"aurem-head"});
    head.appendChild(el("span", null, cfg.business_name));
    var x = el("button", {"class":"x","aria-label":"Close","data-testid":"aurem-widget-close"}, "×");
    head.appendChild(x);
    var msgs = el("div", {"class":"aurem-msgs","data-testid":"aurem-widget-msgs"});
    msgs.appendChild(renderMessage("bot", cfg.welcome_message));
    var inputRow = el("div", {"class":"aurem-input-row"});
    var input = el("input", {"class":"aurem-input","placeholder":"Type a message…","data-testid":"aurem-widget-input"});
    var send = el("button", {"class":"aurem-send","data-testid":"aurem-widget-send"}, "Send");
    inputRow.appendChild(input); inputRow.appendChild(send);
    var foot = el("div", {"class":"aurem-footer"}, cfg.casl_footer);
    panel.appendChild(head); panel.appendChild(msgs); panel.appendChild(inputRow); panel.appendChild(foot);
    document.body.appendChild(bubble);
    document.body.appendChild(panel);

    function open(){ panel.classList.add("open"); input.focus(); }
    function close(){ panel.classList.remove("open"); }
    bubble.addEventListener("click", function(){ panel.classList.contains("open") ? close() : open(); });
    x.addEventListener("click", close);

    function postMessage(){
      var text = (input.value || "").trim();
      if(!text) return;
      msgs.appendChild(renderMessage("user", text));
      input.value = ""; send.disabled = true;
      msgs.scrollTop = msgs.scrollHeight;
      var typing = renderMessage("bot", "…");
      typing.setAttribute("data-typing","1");
      msgs.appendChild(typing); msgs.scrollTop = msgs.scrollHeight;

      fetch(BACKEND + "/api/widget/chat", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
          bin: BIN, session_id: sessionId, message: text,
          page_url: window.location.href
        })
      }).then(function(r){ return r.json(); })
        .then(function(j){
          typing.remove();
          msgs.appendChild(renderMessage("bot", j.reply || "(no reply)"));
          msgs.scrollTop = msgs.scrollHeight;
        })
        .catch(function(){
          typing.remove();
          msgs.appendChild(renderMessage("bot", "Connection hiccup — try again in a moment."));
        })
        .then(function(){ send.disabled = false; input.focus(); });
    }
    send.addEventListener("click", postMessage);
    input.addEventListener("keydown", function(e){ if(e.key === "Enter") postMessage(); });
  }

  function loadConfig(){
    fetch(BACKEND + "/api/widget/config/" + encodeURIComponent(BIN))
      .then(function(r){ return r.json(); })
      .then(function(j){ if(j && j.business_name){ cfg = Object.assign(cfg, j); } })
      .catch(function(){})
      .then(bootstrap);
  }

  if(document.readyState === "complete" || document.readyState === "interactive"){
    loadConfig();
  } else {
    document.addEventListener("DOMContentLoaded", loadConfig);
  }
})();
"""


# ─────────────────────────────────────────────────────────────────────
# Indexes
# ─────────────────────────────────────────────────────────────────────
async def ensure_widget_indexes(db) -> None:
    if db is None:
        return
    try:
        await db.widget_conversations.create_index(
            [("ts", 1)], expireAfterSeconds=60 * 24 * 3600,
            name="ts_ttl_60d",
        )
        await db.widget_conversations.create_index(
            [("session_id", 1), ("ts", 1)], name="session_ts",
        )
        await db.widget_conversations.create_index(
            [("bin", 1), ("ts", -1)], name="bin_ts",
        )
    except Exception as e:
        logger.debug(f"[widget] index skipped: {e}")
