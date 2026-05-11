/* eslint-disable react-hooks/exhaustive-deps */
/**
 * ORA PWA — V3 (iter 281.9)
 * ============================
 * Mobile-first AUREM ORA experience. Same chat, voice + files + history
 * all in one screen — WhatsApp-like flow.
 *
 *  - Splash → email/phone gate → chat
 *  - Real Web Speech API (Chrome auto-transcribes mic input → autosend)
 *  - Paperclip → photo/file attachment shown in chat
 *  - History tab → past conversations loaded from localStorage
 *  - Voice / send / paperclip / history all in the same screen
 *  - Responsive: full-screen on mobile, framed "phone" on desktop
 *  - Backend: /api/public/ora/chat (fast Claude demo)
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { VideoOraSession } from "./VideoOraSession";
import ORASelector from "../components/ORASelector";
import WakeWordIndicator from "../components/WakeWordIndicator";
import { LOCAL_STORAGE_KEY as ORA_AVATAR_KEY, getAvatarById } from "../config/ora_avatars.config";

const API = process.env.REACT_APP_BACKEND_URL || "";
const HISTORY_KEY = "aurem_ora_history_v1";
const MAX_SESSIONS = 30;

const ORA_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Cinzel+Decorative:wght@700&family=Jost:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
html,body{margin:0 !important;padding:0 !important;height:100% !important;width:100% !important;overflow:hidden !important;background:#050510 !important;}
#root{width:100% !important;height:100% !important;margin:0 !important;padding:0 !important;}
.orapwa-root,.orapwa-root *{margin:0;padding:0;box-sizing:border-box;}
.orapwa-root{font-family:'Jost',sans-serif;background:#050510;color:#F0EDE8;width:100vw;height:100vh;height:100dvh;height:-webkit-fill-available;display:flex;align-items:stretch;justify-content:center;overflow:hidden;position:fixed;inset:0;}
.orapwa-phone{width:100%;height:100%;height:100dvh;max-width:480px;background:#050510;border-radius:0;overflow:hidden;position:relative;display:flex;flex-direction:column;padding-top:env(safe-area-inset-top,0);padding-bottom:env(safe-area-inset-bottom,0);}
/* Subtle grid + radial glow background — matches portal aesthetic */
.orapwa-phone::before{content:'';position:absolute;inset:0;pointer-events:none;z-index:0;background:radial-gradient(ellipse 80% 50% at 50% 0%,rgba(249,115,22,0.10) 0%,transparent 60%),linear-gradient(rgba(249,115,22,0.04) 1px,transparent 1px) 0 0/40px 40px,linear-gradient(90deg,rgba(249,115,22,0.04) 1px,transparent 1px) 0 0/40px 40px;}
.orapwa-phone>*{position:relative;z-index:1;}
/* Legacy notch element — hidden; full-screen PWA never shows fake hardware */
.notch{display:none !important;}
.notch-pill{display:none !important;}

.screen{position:absolute;inset:0;display:flex;flex-direction:column;transition:transform 0.5s cubic-bezier(0.77,0,0.175,1);}
.screen.hidden{transform:translateX(100%);}

/* SPLASH */
#splash{background:transparent;align-items:center;justify-content:center;z-index:10;}
.splash-bg{position:absolute;inset:0;background:radial-gradient(ellipse 80% 60% at 50% 30%,rgba(249,115,22,0.12) 0%,transparent 60%),radial-gradient(ellipse 50% 50% at 80% 70%,rgba(201,162,39,0.06) 0%,transparent 50%);}
.splash-grid{position:absolute;inset:0;background-image:linear-gradient(rgba(249,115,22,0.04) 1px,transparent 1px),linear-gradient(90deg,rgba(249,115,22,0.04) 1px,transparent 1px);background-size:40px 40px;}
.splash-inner{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;padding:max(40px,env(safe-area-inset-top)) 24px 32px;width:100%;}
.ora-logo-wrap{position:relative;width:90px;height:90px;margin:32px 0 28px;}
.orbit-ring{position:absolute;inset:0;border-radius:50%;animation:spin 8s linear infinite;}
.orbit-ring:nth-child(1){border:1px solid rgba(201,168,76,0.3);animation-duration:8s;}
.orbit-ring:nth-child(2){inset:8px;border:1px solid rgba(255,107,0,0.2);animation-duration:12s;animation-direction:reverse;}
.orbit-ring:nth-child(3){inset:16px;border:1px solid rgba(201,168,76,0.15);animation-duration:6s;}
.orbit-ring:nth-child(4){inset:24px;border:1px solid rgba(255,107,0,0.1);animation-duration:4s;animation-direction:reverse;}
.orbit-ring:nth-child(5){inset:32px;border:1px solid rgba(201,168,76,0.2);animation-duration:10s;}
@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
.orbit-dot{position:absolute;width:4px;height:4px;background:#FF6B00;border-radius:50%;top:0;left:50%;transform:translateX(-50%) translateY(-2px);}
.ora-core{position:absolute;inset:38px;background:radial-gradient(circle,#FF6B00,#CC4400);border-radius:50%;box-shadow:0 0 20px rgba(255,107,0,0.6),0 0 40px rgba(255,107,0,0.3);}
.splash-name{font-family:'Cinzel Decorative',serif;font-size:32px;font-weight:700;letter-spacing:0.15em;margin-bottom:4px;}
.splash-name em{color:#FF6B00;font-style:normal;}
.splash-tag{font-size:12px;letter-spacing:0.25em;color:#7A7590;text-transform:uppercase;margin-bottom:40px;}
.splash-world{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:0.15em;color:#C9A84C;text-transform:uppercase;border:1px solid rgba(201,168,76,0.2);padding:4px 14px;border-radius:100px;margin-bottom:48px;}
.ooda-dots{display:flex;gap:8px;margin-bottom:48px;}
.od{width:8px;height:8px;border-radius:50%;background:#FF6B00;animation:oodaPulse 1.4s ease-in-out infinite;}
.od:nth-child(2){background:#C9A84C;animation-delay:0.2s;}
.od:nth-child(3){background:#FF6B00;animation-delay:0.4s;}
.od:nth-child(4){background:#C9A84C;animation-delay:0.6s;}
@keyframes oodaPulse{0%,100%{opacity:0.3;transform:scale(0.8)}50%{opacity:1;transform:scale(1.2)}}
.splash-form{width:100%;max-width:400px;margin:0 auto;display:flex;flex-direction:column;gap:12px;}
.splash-input{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.10);border-radius:12px;padding:16px;color:#F0EDE8;font-family:'Jost',sans-serif;font-size:16px;outline:none;width:100%;}
.splash-input:focus{border-color:rgba(249,115,22,0.5);background:rgba(255,255,255,0.08);}
.splash-input::placeholder{color:#6A6580;}
.splash-btn{width:100%;max-width:400px;background:#F97316;border:none;border-radius:12px;padding:16px;color:#000;font-family:'Jost',sans-serif;font-weight:800;font-size:15px;letter-spacing:0.06em;text-transform:uppercase;cursor:pointer;box-shadow:0 8px 24px rgba(249,115,22,0.35);transition:all 0.2s ease;}
.splash-btn:hover{transform:translateY(-2px);box-shadow:0 12px 32px rgba(249,115,22,0.5);}
.splash-btn:active{transform:translateY(0);}
.splash-skip{background:transparent;border:none;color:#7A7590;font-size:11px;letter-spacing:0.1em;cursor:pointer;margin-top:6px;text-decoration:underline;}
.splash-note{font-size:10px;color:#4A4560;letter-spacing:0.06em;text-align:center;margin-top:4px;}

/* CHAT — mobile-first fixed-grid layout (iter 305d — zoom-safe)
   Header 56 + chips 40 (top) · Input 56 + footer-nav 56 (bottom)
   All chrome uses position:absolute + explicit top/bottom + GPU layer
   so elements never collapse under pinch-zoom. */
#chat{background:#050510;z-index:5;}

/* Ticker hidden on chat screen — ambient noise cramped real estate. */
#chat .ticker{display:none;}

.chat-header{position:absolute;top:0;left:0;right:0;height:56px;padding:0 12px;background:#0D0D14;border-bottom:1px solid rgba(201,162,39,0.2);display:flex;align-items:center;justify-content:space-between;gap:10px;z-index:9999;padding-top:env(safe-area-inset-top,0);box-sizing:content-box;transform:translateZ(0);-webkit-transform:translateZ(0);backface-visibility:hidden;-webkit-backface-visibility:hidden;}
.hdr-left{display:flex;align-items:center;gap:10px;min-width:0;flex:1;}
.hdr-logo{width:32px;height:32px;position:relative;flex-shrink:0;}
.mini-ring{position:absolute;inset:0;border-radius:50%;border:1px solid rgba(249,115,22,0.4);animation:spin 6s linear infinite;}
.mini-ring:nth-child(2){inset:4px;border-color:rgba(201,162,39,0.3);animation-duration:9s;animation-direction:reverse;}
.mini-ring:nth-child(3){inset:8px;border-color:rgba(249,115,22,0.3);animation-duration:4s;}
.mini-core{position:absolute;inset:12px;background:#F97316;border-radius:50%;box-shadow:0 0 8px rgba(249,115,22,0.5);}
.hdr-id-block{display:flex;flex-direction:column;min-width:0;gap:3px;}
.hdr-user-name{font-size:14px;font-weight:600;color:#F5F5F0;letter-spacing:0.01em;line-height:1.15;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px;}
.hdr-bin{display:inline-block;align-self:flex-start;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;color:#C9A227;background:rgba(201,162,39,0.1);padding:2px 8px;border-radius:4px;letter-spacing:0.12em;}
.hdr-name{font-family:'Cinzel',serif;font-size:14px;font-weight:600;letter-spacing:0.1em;color:#F5F5F0;}
.hdr-name em{color:#F97316;font-style:normal;}
.hdr-sub{font-size:10px;letter-spacing:0.12em;color:#9A95B0;text-transform:uppercase;}
.hdr-right{display:flex;align-items:center;gap:8px;flex-shrink:0;}

/* Header icon buttons — 44×44 tap target with 32px visual */
.icon-btn-pwa,.icon-btn{min-width:44px;min-height:44px;background:transparent;border:none;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#9A95B0;position:relative;padding:0;border-radius:10px;transition:color 0.18s ease,background 0.18s ease;}
.icon-btn-pwa:hover,.icon-btn:hover{background:rgba(249,115,22,0.1);color:#F97316;}
.icon-btn-pwa.active,.icon-btn.active{background:rgba(249,115,22,0.15);color:#F97316;}
.icon-btn-pwa svg,.icon-btn svg{width:20px;height:20px;}
.bell-dot{position:absolute;top:10px;right:10px;width:8px;height:8px;border-radius:50%;background:#F97316;box-shadow:0 0 8px rgba(249,115,22,0.8);}

.sovereign-truth-chip{display:flex;align-items:center;gap:6px;padding:0 10px;height:32px;background:linear-gradient(180deg,#1a1512 0%,#241b14 100%);border:1px solid rgba(199,123,58,0.45);border-radius:7px;color:#E0B482;font-size:10px;font-weight:700;letter-spacing:1.5px;cursor:pointer;transition:all 0.18s ease;font-family:'SF Mono',ui-monospace,monospace;}
.sovereign-truth-chip:hover{background:linear-gradient(180deg,#241b14 0%,#302318 100%);border-color:#C77B3A;color:#F5C98A;}
.sovereign-truth-chip:disabled{opacity:0.5;cursor:wait;}
.sovereign-truth-chip .st-dot{width:6px;height:6px;border-radius:50%;background:#C77B3A;box-shadow:0 0 6px rgba(199,123,58,0.85);animation:stPulse 1.8s ease-in-out infinite;}
@keyframes stPulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.55;transform:scale(0.88)}}

.ooda-listen{display:flex;gap:3px;align-items:center;padding:0 4px;}
.ol-dot{width:4px;height:4px;background:#F97316;border-radius:50%;animation:oodaPulse 1.2s infinite;}
.ol-dot:nth-child(2){animation-delay:0.2s;}.ol-dot:nth-child(3){animation-delay:0.4s;}

/* Bell notification dropdown */
.notif-panel{position:fixed;top:calc(56px + env(safe-area-inset-top,0));right:12px;width:min(320px,92vw);max-height:60vh;background:rgba(13,13,22,0.97);backdrop-filter:blur(24px) saturate(180%);-webkit-backdrop-filter:blur(24px) saturate(180%);border:1px solid rgba(249,115,22,0.18);border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,0.6);z-index:10000;display:flex;flex-direction:column;overflow:hidden;}
.notif-hdr{padding:12px 14px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(249,115,22,0.1);}
.notif-title{font-family:'Cinzel',serif;font-size:11px;letter-spacing:0.15em;color:#F97316;text-transform:uppercase;}
.notif-mark{background:transparent;border:none;color:#9A95B0;font-size:11px;cursor:pointer;letter-spacing:0.06em;}
.notif-list{flex:1;overflow-y:auto;padding:6px 0;}
.notif-row{padding:12px 14px;display:flex;gap:10px;align-items:flex-start;border-bottom:1px solid rgba(249,115,22,0.04);font-size:13px;color:#E8E0D0;}
.notif-row:hover{background:rgba(249,115,22,0.04);}
.notif-icon{font-size:14px;flex-shrink:0;}
.notif-body{flex:1;min-width:0;}
.notif-text{line-height:1.45;}
.notif-time{font-size:10px;color:#5A5570;margin-top:3px;font-family:'JetBrains Mono',monospace;}
.notif-empty{padding:32px 16px;text-align:center;font-size:12px;color:#5A5570;}

/* Generic tab panel — reused for tab overlays above chat */
.tab-panel{position:absolute;top:calc(56px + env(safe-area-inset-top,0));bottom:calc(112px + env(safe-area-inset-bottom,0));left:0;right:0;overflow-y:auto;padding:14px 14px 20px;display:flex;flex-direction:column;gap:10px;background:#050510;z-index:9997;-webkit-overflow-scrolling:touch;}
.tab-panel::-webkit-scrollbar{width:2px;}
.tab-panel::-webkit-scrollbar-thumb{background:rgba(249,115,22,0.2);border-radius:2px;}
.tp-eyebrow{font-size:11px;letter-spacing:0.18em;color:#F97316;text-transform:uppercase;font-weight:600;margin-top:6px;}
.tp-title{font-family:'Cinzel',serif;font-size:20px;color:#FFF;letter-spacing:0.02em;margin:2px 0 8px;}
.tp-card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:14px 16px;}
.tp-card-strong{background:rgba(249,115,22,0.06);border:1px solid rgba(249,115,22,0.18);border-radius:14px;padding:14px 16px;}
.tp-stat-num{font-family:'Cinzel',serif;font-size:28px;font-weight:600;color:#F97316;text-shadow:0 0 14px rgba(249,115,22,0.4);line-height:1.1;}
.tp-stat-lbl{font-size:10px;letter-spacing:0.18em;color:#9A95B0;text-transform:uppercase;margin-top:4px;}
.tp-row{display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:14px;}
.tp-row:last-child{border-bottom:none;}
.tp-row-l{color:#E8E0D0;display:flex;align-items:center;gap:8px;flex:1;min-width:0;}
.tp-row-r{color:#F97316;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;flex-shrink:0;text-align:right;}
.tp-status-good{color:#86EFAC;}
.tp-status-bad{color:#FCA5A5;}
.tp-pill{display:inline-block;padding:3px 8px;border-radius:14px;font-size:10px;letter-spacing:0.08em;text-transform:uppercase;font-weight:700;font-family:'JetBrains Mono',monospace;}
.tp-pill.good{background:rgba(34,197,94,0.12);color:#86EFAC;}
.tp-pill.bad{background:rgba(252,165,165,0.12);color:#FCA5A5;}
.tp-empty{padding:32px 12px;text-align:center;font-size:13px;color:#5A5570;font-style:italic;}
.tp-action{margin-top:8px;padding:14px 18px;background:linear-gradient(135deg,#F97316 0%,#C9A227 100%);color:#000;border:none;border-radius:10px;font-weight:800;font-size:13px;letter-spacing:0.08em;text-transform:uppercase;cursor:pointer;box-shadow:0 4px 18px rgba(249,115,22,0.35);}
.tp-action:hover{transform:translateY(-2px);box-shadow:0 8px 26px rgba(249,115,22,0.5);}
.waveform{display:flex;gap:2px;align-items:center;height:16px;}
.wbar{width:2px;background:#FF6B00;border-radius:2px;animation:wave 0.6s ease-in-out infinite;}
.wbar:nth-child(1){height:4px}.wbar:nth-child(2){height:8px;animation-delay:.1s}.wbar:nth-child(3){height:14px;animation-delay:.2s}.wbar:nth-child(4){height:8px;animation-delay:.3s}.wbar:nth-child(5){height:4px;animation-delay:.4s}
@keyframes wave{0%,100%{transform:scaleY(0.5)}50%{transform:scaleY(1.3)}}

/* Agent chips — fixed below header */
.agent-strip{position:absolute;top:calc(56px + env(safe-area-inset-top,0));left:0;right:0;height:40px;padding:0 12px;gap:8px;background:#0D0D14;border-bottom:1px solid rgba(201,162,39,0.1);display:flex;align-items:center;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;scrollbar-width:none;z-index:9998;transform:translateZ(0);-webkit-transform:translateZ(0);backface-visibility:hidden;-webkit-backface-visibility:hidden;}
.agent-strip::-webkit-scrollbar{display:none;}
.agent{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 12px;border-radius:14px;font-size:12px;font-weight:600;letter-spacing:0.04em;white-space:nowrap;flex-shrink:0;border:1px solid transparent;background:rgba(255,255,255,0.03);color:#7A7590;cursor:pointer;}
.agent.active{background:rgba(249,115,22,0.12);border-color:rgba(249,115,22,0.35);color:#F97316;}
.a-dot{width:6px;height:6px;border-radius:50%;}
.agent.active .a-dot{background:#F97316;box-shadow:0 0 4px rgba(249,115,22,0.6);}
.agent:not(.active) .a-dot{background:#2A2A3A;}

/* Chat messages — scrollable fill between fixed chrome */
.chat-area{position:absolute;top:calc(96px + env(safe-area-inset-top,0));bottom:calc(112px + env(safe-area-inset-bottom,0));left:0;right:0;overflow-y:auto;overflow-x:hidden;padding:16px;display:flex;flex-direction:column;gap:12px;-webkit-overflow-scrolling:touch;}
.chat-area::-webkit-scrollbar{width:2px;}
.chat-area::-webkit-scrollbar-thumb{background:rgba(249,115,22,0.2);border-radius:2px;}
.date-div{text-align:center;margin:4px 0;font-size:10px;color:#5A5570;letter-spacing:0.1em;}

.msg-ora{display:flex;gap:10px;max-width:92%;}
.ora-av{width:28px;height:28px;background:linear-gradient(135deg,rgba(255,107,0,0.2),rgba(201,168,76,0.1));border:1px solid rgba(255,107,0,0.3);border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px;}
.msg-ora-hdr{display:flex;align-items:center;gap:8px;margin-bottom:4px;}
.ora-name-tag{font-family:'Cinzel',serif;font-size:10px;letter-spacing:0.12em;color:#FF6B00;}
.ora-time-tag{font-size:11px;color:rgba(138,138,154,0.6);}
.msg-ora-bubble{background:rgba(255,255,255,0.04);border:1px solid rgba(255,107,0,0.1);border-radius:12px 12px 12px 4px;padding:12px 16px;font-size:15px;line-height:1.6;color:#E8E0D0;white-space:pre-wrap;word-wrap:break-word;max-width:100%;}
.msg-ora-bubble strong{color:#F5F5F0;font-weight:600;}

.msg-user{align-self:flex-end;max-width:85%;margin-left:auto;}
.msg-user-bubble{background:rgba(255,107,0,0.1);border:1px solid rgba(255,107,0,0.2);border-radius:12px 12px 4px 12px;padding:12px 16px;font-size:15px;line-height:1.6;color:#F5F5F0;word-wrap:break-word;}
.msg-attach{margin-top:6px;display:flex;align-items:center;gap:6px;font-size:12px;color:#C9A84C;background:rgba(201,168,76,0.06);border-radius:6px;padding:6px 8px;}
.msg-attach img{max-width:160px;max-height:160px;border-radius:6px;display:block;}

/* Morning brief card */
.brief-card{background:rgba(201,168,76,0.06);border:1px solid rgba(201,168,76,0.15);border-radius:12px;padding:16px;margin-bottom:12px;}
.brief-hdr{display:flex;align-items:center;gap:8px;margin-bottom:12px;}
.brief-title{font-family:'Cinzel',serif;font-size:12px;letter-spacing:0.12em;color:#C9A84C;}
.brief-time{font-size:11px;color:rgba(138,138,154,0.6);margin-left:auto;font-family:'JetBrains Mono',monospace;}
.brief-row{display:flex;gap:10px;margin-bottom:10px;}
.brief-stat{flex:1;background:rgba(0,0,0,0.2);border-radius:8px;padding:12px;}
.bs-label{font-size:14px;color:#9A95B0;letter-spacing:0.02em;margin-bottom:4px;}
.bs-val{font-family:'Cinzel',serif;font-size:22px;font-weight:600;color:#F5F5F0;line-height:1.1;}
.bs-val.up{color:#50C878;}.bs-val.dn{color:#FF6060;}
.brief-action{font-size:13px;color:#C9A84C;margin-top:8px;}

.typing-bubble{background:rgba(255,255,255,0.04);border:1px solid rgba(255,107,0,0.1);border-radius:12px 12px 12px 4px;padding:14px 16px;}
.t-dots{display:flex;gap:4px;}
.t-dot{width:6px;height:6px;background:#C9A84C;border-radius:50%;animation:oodaPulse 1.2s infinite;}
.t-dot:nth-child(2){animation-delay:.2s;}.t-dot:nth-child(3){animation-delay:.4s;}

/* Listening bar */
.listen-bar{position:absolute;left:12px;right:12px;bottom:calc(120px + env(safe-area-inset-bottom,0));display:flex;align-items:center;gap:10px;padding:10px 14px;background:rgba(255,107,0,0.08);border:1px solid rgba(255,107,0,0.25);border-radius:10px;z-index:9998;}
.listen-text{font-size:13px;color:#FF6B00;font-weight:500;flex:1;}
.listen-stop{background:rgba(255,107,0,0.15);border:none;color:#FF6B00;padding:6px 14px;border-radius:6px;font-size:12px;cursor:pointer;min-height:32px;}

/* Input bar — fixed above footer nav */
.input-bar{position:absolute;left:0;right:0;bottom:calc(56px + env(safe-area-inset-bottom,0));height:56px;padding:8px 12px;background:#0D0D14;border-top:1px solid rgba(201,162,39,0.15);z-index:9998;transform:translateZ(0);-webkit-transform:translateZ(0);backface-visibility:hidden;-webkit-backface-visibility:hidden;}
.input-wrap{display:flex;align-items:center;gap:6px;height:100%;}
.chat-input{flex:1;min-width:0;height:40px;padding:0 14px;background:#1A1A24;border:1px solid rgba(201,162,39,0.2);border-radius:20px;outline:none;color:#F5F5F0;font-family:'Jost',sans-serif;font-size:15px;transition:border-color 0.15s ease,background 0.15s ease;}
.chat-input:focus{border-color:rgba(249,115,22,0.45);background:#20202C;}
.chat-input::placeholder{color:#6A6580;}
.icon-mini{min-width:44px;min-height:44px;border:none;background:transparent;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#9A95B0;border-radius:10px;padding:0;transition:color 0.18s ease,background 0.18s ease;}
.icon-mini:hover{color:#F97316;background:rgba(249,115,22,0.08);}
.icon-mini.recording{color:#F97316;background:rgba(249,115,22,0.12);}
.icon-mini svg{width:20px;height:20px;}
.send-btn{width:40px;height:40px;min-width:40px;flex-shrink:0;background:#C9A227;border:none;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#0A0A0A;transition:background 0.18s ease,transform 0.12s ease;}
.send-btn:hover{background:#D4B540;}
.send-btn:active{transform:scale(0.95);}
.send-btn:disabled{opacity:0.35;cursor:not-allowed;}
.send-btn svg{width:18px;height:18px;}

/* Footer nav — fixed bottom */
.bottom-nav{position:absolute;left:0;right:0;bottom:0;height:calc(56px + env(safe-area-inset-bottom,0));padding-bottom:env(safe-area-inset-bottom,0);background:#0D0D14;border-top:1px solid rgba(201,162,39,0.15);display:flex;align-items:stretch;z-index:9999;transform:translateZ(0);-webkit-transform:translateZ(0);backface-visibility:hidden;-webkit-backface-visibility:hidden;}
.nav-item{flex:1;min-height:44px;height:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;cursor:pointer;color:rgba(138,138,154,0.6);background:none;border:none;padding:0;font-family:inherit;transition:color 0.15s ease;}
.nav-item svg{width:18px;height:18px;}
.nav-item span,.nav-item .nav-lbl{font-size:10px;font-weight:500;letter-spacing:0.03em;text-transform:uppercase;}
.nav-item.active{color:#C9A227;}
.nav-item:hover{color:#F5F5F0;}
.nav-item.active:hover{color:#D4B540;}

/* History panel */
.history-overlay{position:absolute;inset:0;background:#0A0A0F;z-index:20;display:flex;flex-direction:column;}
.history-overlay.hidden{display:none;}
.history-hdr{padding:14px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(255,107,0,0.08);}
.history-hdr h3{font-family:'Cinzel',serif;font-size:14px;letter-spacing:0.12em;color:#F0EDE8;}
.history-list{flex:1;overflow-y:auto;padding:10px;}
.history-item{padding:12px;border:1px solid rgba(255,107,0,0.08);border-radius:8px;margin-bottom:8px;cursor:pointer;background:rgba(255,255,255,0.02);}
.history-item:hover{border-color:rgba(255,107,0,0.25);background:rgba(255,107,0,0.04);}
.history-item-title{font-size:13px;color:#F0EDE8;margin-bottom:4px;line-height:1.4;}
.history-item-meta{font-size:10px;color:#4A4560;font-family:'JetBrains Mono',monospace;}
.history-empty{text-align:center;padding:40px 20px;color:#4A4560;font-size:12px;}

.status-bar{padding:14px 20px 4px;display:flex;justify-content:space-between;align-items:center;flex-shrink:0;font-size:12px;}
@media(max-width:600px){.status-bar{display:none;}}

/* ────────────────────────────────────────────────────────────────
   iter 282al-19 — Bug fixes #4 #5 #6 #7 + Claude.ai-style polish
   ──────────────────────────────────────────────────────────────── */
/* Bug #5 — full-width on desktop (Claude.ai aesthetic, max 920px) */
@media(min-width:768px){
  .orapwa-phone{max-width:920px;border-left:1px solid rgba(255,255,255,0.04);border-right:1px solid rgba(255,255,255,0.04);}
}
/* Bug #5 — bars span the full container */
.orapwa-phone>*{box-sizing:border-box;}

/* Bug #6 — Copy button on ORA messages */
.msg-copy-btn{position:absolute;bottom:6px;right:6px;width:24px;height:24px;border:none;background:rgba(255,255,255,0.06);color:#9a948a;border-radius:6px;display:flex;align-items:center;justify-content:center;cursor:pointer;opacity:0;transition:opacity 0.15s ease,background 0.15s ease;padding:0;}
.msg-ora:hover .msg-copy-btn{opacity:1;}
.msg-copy-btn:hover{background:rgba(255,107,0,0.18);color:#FF6B00;}
.msg-copy-tip{position:absolute;bottom:28px;right:0;background:#1a1a1a;color:#F0EDE8;font-size:10px;letter-spacing:0.04em;padding:4px 8px;border-radius:6px;white-space:nowrap;border:1px solid rgba(255,107,0,0.2);}

/* Bug #7 — Settings slide-in drawer */
.settings-backdrop{position:fixed;inset:0;background:rgba(5,5,16,0.65);z-index:2147483640;animation:fadeIn 0.18s ease;}
.settings-drawer{position:fixed;top:0;right:0;bottom:0;width:min(360px,90vw);background:#0a0a14;border-left:1px solid rgba(255,107,0,0.18);z-index:2147483641;display:flex;flex-direction:column;box-shadow:-12px 0 36px rgba(0,0,0,0.5);animation:slideInR 0.22s cubic-bezier(0.22,1,0.36,1);}
@keyframes slideInR{from{transform:translateX(100%);}to{transform:translateX(0);}}
@keyframes fadeIn{from{opacity:0;}to{opacity:1;}}
.settings-hdr{padding:14px 18px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(255,107,0,0.08);}
.settings-hdr h3{font-family:'Cinzel',serif;font-size:14px;letter-spacing:0.14em;color:#F0EDE8;margin:0;}
.settings-body{padding:8px 0;overflow-y:auto;flex:1;}
.settings-row{padding:14px 18px;display:flex;align-items:center;justify-content:space-between;gap:14px;border-bottom:1px solid rgba(255,255,255,0.03);}
.settings-label{font-size:13px;color:#F0EDE8;font-weight:500;margin-bottom:3px;}
.settings-sub{font-size:11px;color:#7A7590;line-height:1.4;}
.settings-select{background:rgba(255,255,255,0.04);border:1px solid rgba(255,107,0,0.18);border-radius:8px;color:#F0EDE8;font-family:'Jost',sans-serif;font-size:12px;padding:6px 10px;cursor:pointer;outline:none;}
.toggle{width:38px;height:22px;border-radius:999px;border:1px solid rgba(255,255,255,0.12);background:rgba(255,255,255,0.06);position:relative;cursor:pointer;transition:all 0.18s ease;flex-shrink:0;padding:0;}
.toggle.on{background:rgba(255,107,0,0.6);border-color:rgba(255,107,0,0.8);}
.toggle-knob{position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:#F0EDE8;transition:transform 0.18s ease;}
.toggle.on .toggle-knob{transform:translateX(16px);}
.settings-danger{margin:18px;padding:12px 16px;background:transparent;border:1px solid rgba(255,80,80,0.3);color:#FF6060;border-radius:10px;font-family:'Jost',sans-serif;font-size:13px;font-weight:500;letter-spacing:0.04em;cursor:pointer;transition:all 0.15s ease;}
.settings-danger:hover{background:rgba(255,80,80,0.08);border-color:rgba(255,80,80,0.5);}
`;

const TICKER_ITEMS = [
  ["🇨🇦 CAD/USD", "0.7312", "▲0.18%", "up"],
  ["🏦 BoC Rate", "2.75%", "", ""],
  ["🥇 Gold", "$3,284", "▲0.42%", "up"],
  ["📈 TSX", "24,512", "▼0.31%", "dn"],
  ["₿ BTC", "$94,280", "▲1.2%", "up"],
  ["⛽ WTI Oil", "$68.14", "▼0.8%", "dn"],
];

const Logo24 = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
    <path d="M6 1L10 4V8L6 11L2 8V4Z" fill="#FF6B00" opacity="0.8" />
    <circle cx="6" cy="6" r="1.8" fill="#C9A84C" />
  </svg>
);

const fmtTime = (d) =>
  (d || new Date()).toLocaleTimeString("en", { hour: "2-digit", minute: "2-digit" });

const notifText = (e) => {
  const ev = e.event;
  if (ev === 'morning_armed')      return `Scout armed · ${e.leads_today ?? 0} leads in pipeline`;
  if (ev === 'scout_complete')     return `Scout found ${e.leads_real_count ?? 0} real leads`;
  if (ev === 'architect_complete') return `${e.http_verified ?? 0}/${e.rendered ?? 0} sites HTTP-verified`;
  if (ev === 'envoy_complete')     return `${e.emails_resend_confirmed ?? 0}/${e.emails_sent ?? 0} emails delivered`;
  if (ev === 'midday_check')       return `${e.opens ?? 0} opens · ${e.clicks ?? 0} clicks · ${e.signups_mongodb_count ?? 0} signups`;
  if (ev === 'end_of_day')         return `EOD · $${e.stripe_revenue_real ?? 0} revenue · ${e.signups_mongodb_count ?? 0} signups`;
  if (ev === 'end_of_day_email')   return `Daily report email sent`;
  if (ev === 'mismatch_alert')     return `${e.step}: claimed ${e.claimed} verified ${e.verified} (${Math.round((e.gap_pct || 0) * 100)}% gap)`;
  return ev;
};

const loadHistory = () => {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch (_) {
    return [];
  }
};
const saveHistory = (sessions) => {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(sessions.slice(-MAX_SESSIONS)));
  } catch (_) {}
};

const OraPWA = () => {
  const [showSplash, setShowSplash] = useState(() => !localStorage.getItem("aurem_ora_entered_v1"));
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [tab, setTab] = useState("ora");
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState(loadHistory);
  const [sessionId] = useState(() => `ora_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`);

  // ── ORA Avatar selection (Phase 2) ──────────────────────────
  // Lazy init from localStorage so existing visitors skip the selector
  // and new visitors see it once. setSelectedAvatar(null) anywhere
  // re-prompts (used by Settings → Change ORA).
  const [selectedAvatar, setSelectedAvatar] = useState(() => {
    try {
      const id = window.localStorage.getItem(ORA_AVATAR_KEY);
      return id ? getAvatarById(id) : null;
    } catch (_e) {
      return null;
    }
  });

  // ── User context (Fix 2 + 3 + 7) ─────────────────────────────
  const [userCtx, setUserCtx] = useState(null);  // {name, bin, business_name, plan, is_admin, email}

  // ── Notifications panel (Fix 5) ──────────────────────────────
  const [showNotif, setShowNotif] = useState(false);
  const [notifs, setNotifs] = useState([]);
  const [notifUnread, setNotifUnread] = useState(0);

  // ── Tab data caches (Fix 4) ─────────────────────────────────
  const [tabData, setTabData] = useState({ leads: null, scout: null, revenue: null, history: null });
  const [tabLoading, setTabLoading] = useState(false);

  const [messages, setMessages] = useState([
    {
      id: "brief",
      role: "ora-brief",
      time: "7:00 AM",
    },
    {
      id: "intro",
      role: "ora",
      time: fmtTime(),
      text:
        "Ready when you are. Ask me anything — leads, revenue, scout audits, or to fix something in your business.",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recState, setRecState] = useState("");
  const recRef = useRef(null);
  const fileInRef = useRef(null);
  // iter 282al-14 — Video session + emotion (face-api.js, in-browser)
  const [videoOpen, setVideoOpen] = useState(false);
  const emotionRef = useRef(null);
  const onEmotionChange = useCallback((emo, conf) => {
    emotionRef.current = { emotion: emo, confidence: conf, ts: Date.now() };
  }, []);
  // iter 282al-19 — settings drawer (Bug #7)
  const [showSettings, setShowSettings] = useState(false);
  // iter 282al-26 — Sovereign Truth (founder-only anti-sycophancy toggle)
  const [sovereignTruth, setSovereignTruth] = useState(false);
  const [sovereignTruthLoading, setSovereignTruthLoading] = useState(false);
  // iter 282al-19 — copy-to-clipboard tooltip per ORA message (Bug #6)
  const [copiedId, setCopiedId] = useState(null);
  const copyOraMsg = useCallback((id, text) => {
    try {
      navigator.clipboard.writeText(text || "");
      setCopiedId(id);
      setTimeout(() => setCopiedId((cur) => (cur === id ? null : cur)), 1500);
    } catch (_) {
      /* clipboard refused — silent */
    }
  }, []);
  const chatAreaRef = useRef(null);

  // iter 282al-2 — Dev Mode toggle. When ON, every message is sent with
  // `source:"dev"` so the backend routes through ORA's dev skill
  // pipeline (dev_aurem_codebase + keyword-matched dev_* skill).
  const [devMode, setDevMode] = useState(() => {
    try { return localStorage.getItem("aurem_ora_dev_mode") === "1"; } catch (_) { return false; }
  });
  const toggleDevMode = () => {
    setDevMode((v) => {
      const next = !v;
      try { localStorage.setItem("aurem_ora_dev_mode", next ? "1" : "0"); } catch (_) {}
      return next;
    });
  };

  // ── Auth token (used by chat + tabs + notif) ─────────────────
  const authToken = (() => {
    try {
      return (
        localStorage.getItem("aurem_platform_token") ||
        localStorage.getItem("platform_token") ||
        localStorage.getItem("admin_token") || ""
      );
    } catch (_) { return ""; }
  })();
  const authHeaders = authToken ? { Authorization: `Bearer ${authToken}` } : {};

  // ── ORA Voice (TTS) — speak ORA's replies aloud (iter 282t) ──
  const [ttsOn, setTtsOn] = useState(() => {
    try { return localStorage.getItem("aurem_ora_tts") === "1"; } catch (_) { return false; }
  });
  const audioRef = useRef(null);
  const ttsControllerRef = useRef(null);

  const stopTTS = useCallback(() => {
    try { ttsControllerRef.current?.abort?.(); } catch (_) {}
    if (audioRef.current) {
      try { audioRef.current.pause(); audioRef.current.src = ""; } catch (_) {}
    }
  }, []);

  const playTTS = useCallback(async (text) => {
    if (!ttsOn || !text) return;
    const cleanText = String(text)
      .replace(/<[^>]+>/g, " ")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\s+/g, " ")
      .trim();
    if (!cleanText) return;
    stopTTS();
    const ctrl = new AbortController();
    ttsControllerRef.current = ctrl;
    try {
      const r = await fetch(`${API}/api/ora/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}) },
        body: JSON.stringify({ text: cleanText.slice(0, 3500), voice: "shimmer" }),
        signal: ctrl.signal,
      });
      if (!r.ok) return;
      const data = await r.json();
      if (!data?.audio_base64) return;
      const a = audioRef.current || new Audio();
      a.src = `data:audio/mp3;base64,${data.audio_base64}`;
      audioRef.current = a;
      try { await a.play(); } catch (_) { /* user-gesture required first time */ }
    } catch (_) { /* aborted or network — no-op */ }
  }, [ttsOn, authToken, stopTTS]);

  const toggleTTS = useCallback(() => {
    setTtsOn((v) => {
      const next = !v;
      try { localStorage.setItem("aurem_ora_tts", next ? "1" : "0"); } catch (_) {}
      if (!next) stopTTS();
      return next;
    });
  }, [stopTTS]);

  // ── Biometric (Face ID / Fingerprint) — WebAuthn (iter 282t) ──
  const [bioSupported] = useState(
    () => typeof window !== "undefined" && !!window.PublicKeyCredential
  );
  const [bioEmail] = useState(() => {
    try {
      return (
        localStorage.getItem("biometric_email") ||
        localStorage.getItem("aurem_ora_email") ||
        ""
      );
    } catch (_) { return ""; }
  });
  const [bioBusy, setBioBusy] = useState(false);
  const [bioErr, setBioErr] = useState("");

  const _b64urlToBuffer = (s) => {
    const pad = "=".repeat((4 - (s.length % 4)) % 4);
    const b64 = (s + pad).replace(/-/g, "+").replace(/_/g, "/");
    const bin = atob(b64);
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    return buf.buffer;
  };
  const _bufferToB64url = (buf) => {
    const bytes = new Uint8Array(buf);
    let s = "";
    for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  };

  const handleBiometricLogin = useCallback(async () => {
    setBioErr("");
    if (!bioSupported) { setBioErr("This device doesn't support Face ID / Fingerprint."); return; }
    if (!bioEmail) { setBioErr("First sign in with email + password to enable biometric, then it'll auto-trigger next time."); return; }
    setBioBusy(true);
    try {
      const startRes = await fetch(`${API}/api/biometric/webauthn/auth/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: bioEmail }),
      });
      if (!startRes.ok) throw new Error("Biometric not registered for this account yet.");
      const { options } = await startRes.json();
      const publicKey = {
        ...options,
        challenge: _b64urlToBuffer(options.challenge),
        allowCredentials: (options.allowCredentials || []).map((c) => ({
          ...c, id: _b64urlToBuffer(c.id),
        })),
      };
      const cred = await navigator.credentials.get({ publicKey });
      if (!cred) throw new Error("Authentication cancelled.");
      const finishRes = await fetch(`${API}/api/biometric/webauthn/auth/finish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: bioEmail,
          credential: {
            id: cred.id,
            rawId: _bufferToB64url(cred.rawId),
            type: cred.type,
            response: {
              clientDataJSON: _bufferToB64url(cred.response.clientDataJSON),
              authenticatorData: _bufferToB64url(cred.response.authenticatorData),
              signature: _bufferToB64url(cred.response.signature),
              userHandle: cred.response.userHandle ? _bufferToB64url(cred.response.userHandle) : null,
            },
          },
        }),
      });
      const data = await finishRes.json();
      if (!finishRes.ok || !data?.token) throw new Error(data?.detail || "Verification failed");
      try {
        localStorage.setItem("aurem_platform_token", data.token);
        localStorage.setItem("biometric_email", bioEmail);
      } catch (_) {}
      setShowSplash(false);
      window.location.reload();
    } catch (e) {
      setBioErr(e.message || "Biometric sign-in failed.");
    } finally {
      setBioBusy(false);
    }
  }, [bioSupported, bioEmail]);

  // Load user context once on mount; redirect to login if no token
  useEffect(() => {
    if (!authToken) {
      // Auth gate — but allow showing splash for anonymous demo
      if (!showSplash) {
        try {
          const next = encodeURIComponent('/ora');
          window.location.href = `/platform/login?next=${next}`;
        } catch (_) { /* no-op */ }
      }
      return;
    }
    (async () => {
      // Single source of truth: /api/me/identity
      try {
        const r = await fetch(`${API}/api/me/identity`, { headers: authHeaders });
        if (r.ok) {
          const d = await r.json();
          setUserCtx({
            name: d.name,
            bin: d.bin,
            business_name: d.business_name,
            plan: d.plan,
            is_admin: !!d.is_admin,
            email: d.email,
            scope: d.scope,
            trial_days_left: d.trial_days_left,
          });
          return;
        }
        if (r.status === 401) {
          // Token invalid — bounce to login
          try { localStorage.removeItem('aurem_platform_token'); } catch (_) {}
          if (!showSplash) {
            const next = encodeURIComponent('/ora');
            window.location.href = `/platform/login?next=${next}`;
          }
        }
      } catch (_) { /* network blip */ }
    })();
  }, [authToken, showSplash]); // eslint-disable-line

  useEffect(() => {
    const el = chatAreaRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  // iter 282al-26 — Fetch Sovereign Truth state (founders only; others get 403)
  useEffect(() => {
    if (!authToken || !userCtx?.is_admin) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API}/api/founder/sovereign-truth/state`, {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (!r.ok || cancelled) return;
        const d = await r.json();
        setSovereignTruth(!!d.sovereign_truth);
      } catch (_) { /* silent — non-founders expected 403 */ }
    })();
    return () => { cancelled = true; };
  }, [authToken, userCtx?.is_admin]);

  const toggleSovereignTruth = useCallback(async () => {
    if (!authToken || sovereignTruthLoading) return;
    const next = !sovereignTruth;
    setSovereignTruthLoading(true);
    try {
      const r = await fetch(`${API}/api/founder/sovereign-truth/toggle`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ on: next }),
      });
      if (r.ok) {
        setSovereignTruth(next);
      } else if (r.status === 403) {
        // iter 282al-32 — Surface founder-only rejection so the user
        // knows the toggle isn't silently misbehaving.
        console.warn("[SovereignTruth] 403 — founder-only");
        try { alert("Sovereign Truth is founder-only. Check your login (needs founder email in JWT)."); } catch (_) { /* noop */ }
      } else {
        console.warn(`[SovereignTruth] HTTP ${r.status}`);
        try { alert(`Could not toggle Sovereign Truth (HTTP ${r.status})`); } catch (_) { /* noop */ }
      }
    } catch (e) {
      console.warn("[SovereignTruth] network error", e);
    } finally { setSovereignTruthLoading(false); }
  }, [authToken, sovereignTruth, sovereignTruthLoading]);

  // ── Web Speech API ────────────────────────────────────────────
  // iter 282al-4 — Voice-activated Dev Mode.
  // Phrases at the START of a transcript (or after "hey ora") flip the
  // Dev Mode toggle without sending to chat. False-positive guarded so
  // casual mentions of "dev mode" inside a normal question are ignored.
  const checkVoiceDevCommand = useCallback((raw) => {
    if (!raw) return null;
    const t = raw.toLowerCase().replace(/[.,!?]/g, "").trim();
    const startsOra = t.startsWith("hey ora") || t.startsWith("hey aura")
                       || t.startsWith("ora ") || t.startsWith("aura ");
    const startsDev = t.startsWith("dev mode") || t.startsWith("developer mode")
                       || t.startsWith("exit dev");
    if (!startsOra && !startsDev) return null;
    if (t.includes("dev mode on") || t.includes("developer mode on")
        || t.includes("turn on dev") || t.includes("switch to dev")
        || t === "dev mode") return "DEV_ON";
    if (t.includes("dev mode off") || t.includes("developer mode off")
        || t.includes("turn off dev") || t.includes("exit dev")
        || t.includes("back to normal")) return "DEV_OFF";
    return null;
  }, []);

  const [voiceToast, setVoiceToast] = useState("");
  const voiceContinuousRef = useRef(false);

  // ── Send message — MUST be declared BEFORE startVoice (TDZ guard,
  //                  iter 282al-9 hotfix). startVoice's dep array
  //                  reads sendMsg on first render.
  const sendMsg = useCallback(
    async (overrideText, opts = {}) => {
      const txt = (overrideText ?? chatInput).trim();
      if (!txt || sending) return;
      if (!opts.silent) setChatInput("");
      const userMsgId = `u_${Date.now()}`;
      const placeholderId = `t_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
      const userMsg = { id: userMsgId, role: "user", time: fmtTime(), text: txt };

      setMessages((p) => {
        const next = opts.silent ? [...p] : [...p, userMsg];
        next.push({ id: placeholderId, role: "ora", time: fmtTime(), typing: true });
        return next;
      });
      setSending(true);

      try {
        // iter 282al-14 — include current detected emotion (≤8s old) so
        // ORA can adapt tone. We send only the label, never the video.
        const emo = emotionRef.current;
        const fresh = emo && Date.now() - emo.ts < 8000;
        const r = await fetch(`${API}/api/public/ora/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders },
          body: JSON.stringify({
            text: txt,
            session_id: sessionId,
            ...(devMode ? { source: "dev" } : {}),
            ...(fresh ? {
              emotion: emo.emotion,
              emotion_confidence: emo.confidence,
            } : {}),
          }),
        });
        const body = await r.json().catch(() => ({}));
        const reply =
          (body?.reply || "").trim() ||
          // iter 322bo — softer fallback. If we land here it means backend
          // returned an empty body — usually a 502/timeout. Tell user it's
          // a connectivity blip, not a feature limitation.
          "One sec — connection blinked. Re-send your message and I'll pick up where we left off.";
        setMessages((p) =>
          p.map((m) => (m.id === placeholderId ? { ...m, text: reply, typing: false } : m))
        );
        // Speak ORA's reply if speaker is on (iter 282t)
        try { playTTS(reply); } catch (_) {}
      } catch (e) {
        setMessages((p) =>
          p.map((m) =>
            m.id === placeholderId
              ? { ...m, text: "Connection blinked — try again in a sec.", typing: false }
              : m
          )
        );
      } finally {
        setSending(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [chatInput, sending, sessionId, devMode]
  );

  const startVoice = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setRecState("Voice not supported on this browser. Try Chrome.");
      setTimeout(() => setRecState(""), 3000);
      return;
    }
    if (recRef.current) {
      try { recRef.current.stop(); } catch (_) {}
    }
    const r = new SR();
    r.lang = "en-US";
    r.continuous = voiceContinuousRef.current;  // set by DEV_ON command
    r.interimResults = true;
    let finalTxt = "";
    r.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalTxt += t;
        else interim += t;
      }
      setChatInput(finalTxt + interim);
      setRecState(`Listening… ${(finalTxt + interim).slice(0, 50)}`);

      // Voice-command interception on final transcript only
      if (e.results[e.results.length - 1]?.isFinal) {
        const cmd = checkVoiceDevCommand(finalTxt);
        if (cmd === "DEV_ON") {
          setDevMode(true);
          try { localStorage.setItem("aurem_ora_dev_mode", "1"); } catch (_) {}
          voiceContinuousRef.current = true;
          setVoiceToast("🟢 Dev Mode ON");
          setTimeout(() => setVoiceToast(""), 2000);
          playTTS("Dev mode activated. I'm now in developer mode.");
          finalTxt = ""; setChatInput("");
          return;
        }
        if (cmd === "DEV_OFF") {
          setDevMode(false);
          try { localStorage.setItem("aurem_ora_dev_mode", "0"); } catch (_) {}
          voiceContinuousRef.current = false;
          setVoiceToast("⚫ Dev Mode OFF");
          setTimeout(() => setVoiceToast(""), 2000);
          playTTS("Dev mode off. Back to normal mode.");
          finalTxt = ""; setChatInput("");
          // Stop continuous recognition
          try { r.stop(); } catch (_) {}
          return;
        }
        // Continuous mode: auto-send each final sentence and keep listening
        if (voiceContinuousRef.current && finalTxt.trim()) {
          const toSend = finalTxt.trim();
          finalTxt = "";
          setChatInput("");
          setTimeout(() => sendMsg(toSend), 50);
        }
      }
    };
    r.onerror = (e) => {
      setRecState(`Voice err: ${e.error}`);
      setTimeout(() => setRecState(""), 2500);
      setRecording(false);
    };
    r.onend = () => {
      setRecording(false);
      setRecState("");
      const txt = (finalTxt || chatInput).trim();
      if (txt && !voiceContinuousRef.current) {
        // tap-to-talk → auto-send on stop
        setChatInput(txt);
        setTimeout(() => sendMsg(txt), 50);
      }
      // If continuous mode is still active, restart recognition
      if (voiceContinuousRef.current) {
        try { r.start(); setRecording(true); setRecState("Listening…"); } catch (_) {}
      }
    };
    recRef.current = r;
    try {
      r.start();
      setRecording(true);
      setRecState("Listening…");
    } catch (e) {
      setRecState(`Mic err: ${e.message}`);
      setRecording(false);
    }
  }, [chatInput, checkVoiceDevCommand, playTTS, sendMsg]);

  const stopVoice = useCallback(() => {
    voiceContinuousRef.current = false;
    if (recRef.current) {
      try { recRef.current.stop(); } catch (_) {}
    }
    setRecording(false);
  }, []);

  const toggleVoice = () => (recording ? stopVoice() : startVoice());

  // ── File upload ──────────────────────────────────────────────
  const onFileSelect = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const isImg = f.type.startsWith("image/");
    let preview = null;
    if (isImg) {
      preview = URL.createObjectURL(f);
    }
    const id = `att_${Date.now()}`;
    setMessages((p) => [
      ...p,
      {
        id,
        role: "user",
        time: fmtTime(),
        text: `Sent ${isImg ? "an image" : "a file"}: ${f.name}`,
        attach: { name: f.name, size: f.size, type: f.type, preview },
      },
    ]);
    e.target.value = ""; // reset
    // Trigger an ORA reply that acknowledges the attachment
    setTimeout(() => {
      sendMsg(
        isImg
          ? `Analyze this image: ${f.name} (${Math.round(f.size / 1024)}KB)`
          : `Analyze this file: ${f.name} (${Math.round(f.size / 1024)}KB, ${f.type})`,
        { silent: true }
      );
    }, 200);
  };

  // ── Send message (declared above startVoice — see line ~552) ─────

  // ── Tab data loaders (Fix 4) — all BIN-scoped via /api/me/* ─────
  const loadTabData = useCallback(async (which) => {
    if (!authToken) return;
    setTabLoading(true);
    try {
      if (which === 'leads') {
        const r = await fetch(`${API}/api/me/leads/today`, { headers: authHeaders });
        if (r.ok) {
          const d = await r.json();
          setTabData(p => ({ ...p, leads: { items: d.leads || [], scope: d.scope, total: d.total } }));
        }
      } else if (which === 'scout') {
        const r = await fetch(`${API}/api/me/scout/status`, { headers: authHeaders });
        if (r.ok) {
          const d = await r.json();
          setTabData(p => ({ ...p, scout: d }));
        }
      } else if (which === 'revenue') {
        const r = await fetch(`${API}/api/me/billing/summary`, { headers: authHeaders });
        if (r.ok) {
          const d = await r.json();
          setTabData(p => ({ ...p, revenue: d }));
        }
      } else if (which === 'history') {
        const r = await fetch(`${API}/api/me/history?days=7`, { headers: authHeaders });
        if (r.ok) {
          const d = await r.json();
          setTabData(p => ({ ...p, history: d.days || [] }));
        }
      }
    } catch (_) { /* no-op */ }
    finally { setTabLoading(false); }
  }, [authToken]); // eslint-disable-line

  // ── Notifications loader (Fix 5) — BIN-scoped ──────────────────
  const loadNotifs = useCallback(async () => {
    if (!authToken) return;
    try {
      const r = await fetch(`${API}/api/me/notifications/today`, { headers: authHeaders });
      if (r.ok) {
        const d = await r.json();
        const events = (d.events || []).map(e => ({
          icon: e.event === 'mismatch_alert' ? '⚠️' :
                e.event === 'scout_complete' ? '🔍' :
                e.event === 'architect_complete' ? '🏗️' :
                e.event === 'envoy_complete' ? '📧' :
                e.event === 'midday_check' ? '📊' :
                e.event === 'end_of_day' ? '🌙' :
                e.event === 'end_of_day_email' ? '📨' :
                e.event === 'review_received' ? '⭐' :
                e.event === 'trial_warning' ? '⏳' : '✦',
          text: e.detail || notifText(e),
          time: (e.ts_utc || '').slice(11, 16) + ' UTC',
          id: (e.ts_utc || Math.random().toString()) + e.event,
        }));
        setNotifs(events);
        const lastSeen = parseInt(localStorage.getItem('ora_notif_last_seen') || '0', 10);
        const newCount = events.filter(e => {
          try {
            const t = new Date(e.id.split(/[A-Z_]/)[0]).getTime();
            return t > lastSeen;
          } catch (_) { return false; }
        }).length;
        setNotifUnread(newCount);
      }
    } catch (_) { /* no-op */ }
  }, [authToken]); // eslint-disable-line

  useEffect(() => { loadNotifs(); }, [loadNotifs]);

  useEffect(() => {
    if (tab === 'leads' || tab === 'scout' || tab === 'revenue' || tab === 'history') {
      loadTabData(tab);
    }
  }, [tab, loadTabData]);

  const markNotifsRead = () => {
    localStorage.setItem('ora_notif_last_seen', Date.now().toString());
    setNotifUnread(0);
  };

  // Persist this session on each turn
  useEffect(() => {
    if (messages.length <= 2) return;
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    const title = (lastUser.text || "").slice(0, 60);
    setHistory((prev) => {
      const filtered = prev.filter((s) => s.id !== sessionId);
      const next = [
        ...filtered,
        {
          id: sessionId,
          title,
          updated_at: new Date().toISOString(),
          turns: messages.filter((m) => m.role === "user" || m.role === "ora").length,
          msgs: messages.slice(-20),
        },
      ];
      saveHistory(next);
      return next;
    });
  }, [messages, sessionId]);

  const enter = () => {
    localStorage.setItem("aurem_ora_entered_v1", "1");
    if (email) localStorage.setItem("aurem_ora_email", email);
    if (phone) localStorage.setItem("aurem_ora_phone", phone);
    setShowSplash(false);
  };

  const renderMsg = (m) => {
    if (m.role === "user") {
      return (
        <div key={m.id} className="msg-user" data-testid={`ora-msg-user-${m.id}`}>
          <div className="msg-user-bubble">{m.text}</div>
          {m.attach && (
            <div className="msg-attach">
              {m.attach.preview ? (
                <img src={m.attach.preview} alt={m.attach.name} />
              ) : (
                <>📎 {m.attach.name}</>
              )}
            </div>
          )}
        </div>
      );
    }
    if (m.role === "ora-brief") {
      return (
        <div key={m.id} className="msg-ora">
          <div className="ora-av"><Logo24 /></div>
          <div>
            <div className="msg-ora-hdr">
              <span className="ora-name-tag">ORA AI</span>
              <span className="ora-time-tag">{m.time}</span>
            </div>
            <div className="brief-card">
              <div className="brief-hdr">
                <span style={{ fontSize: 14 }}>☀️</span>
                <span className="brief-title">MORNING BRIEF</span>
                <span className="brief-time">{new Date().toLocaleDateString("en", { month: "short", day: "numeric" }).toUpperCase()} · {m.time}</span>
              </div>
              <div className="brief-row">
                <div className="brief-stat"><div className="bs-label">Revenue Today</div><div className="bs-val up">$0</div></div>
                <div className="brief-stat"><div className="bs-label">Leads Found</div><div className="bs-val">25</div></div>
              </div>
              <div className="brief-row">
                <div className="brief-stat"><div className="bs-label">Auto-Fixes</div><div className="bs-val">2,224</div></div>
                <div className="brief-stat"><div className="bs-label">ORA Response</div><div className="bs-val">1.3s</div></div>
              </div>
              <div
                className="brief-action"
                role="button"
                tabIndex={0}
                onClick={() => setTab('leads')}
                onKeyDown={(e) => { if (e.key === 'Enter') setTab('leads'); }}
                data-testid="brief-action-leads-tap"
                style={{cursor:'pointer',textDecoration:'underline',textDecorationStyle:'dotted'}}
              >
                ✦ 3 leads need follow-up today  →
              </div>
            </div>
          </div>
        </div>
      );
    }
    // ora regular
    return (
      <div key={m.id} className="msg-ora" data-testid={`ora-msg-${m.id}`}>
        <div className="ora-av"><Logo24 /></div>
        <div>
          <div className="msg-ora-hdr">
            <span className="ora-name-tag">ORA AI</span>
            <span className="ora-time-tag">{m.time}</span>
          </div>
          {m.typing ? (
            <div className="typing-bubble"><div className="t-dots"><div className="t-dot" /><div className="t-dot" /><div className="t-dot" /></div></div>
          ) : (
            <div style={{ position: "relative" }}>
              <div className="msg-ora-bubble" dangerouslySetInnerHTML={{ __html: (m.text || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>") }} />
              {/* iter 282al-19 — copy button (Bug #6) */}
              <button
                className="msg-copy-btn"
                onClick={() => copyOraMsg(m.id, m.text)}
                data-testid={`ora-msg-copy-${m.id}`}
                aria-label="Copy message"
                title={copiedId === m.id ? "Copied!" : "Copy"}
              >
                {copiedId === m.id ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                ) : (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                )}
                {copiedId === m.id && <span className="msg-copy-tip">Copied</span>}
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  const restoreSession = (s) => {
    setMessages(s.msgs || []);
    setShowHistory(false);
    setTab("ora");
  };

  return (
    <div className="orapwa-root" data-testid="ora-pwa-root">
      <style>{ORA_CSS}</style>
      {/* PHASE 2 — Avatar selector. Mounted before the phone shell so it
          covers the entire viewport. Only shown after the user has
          entered (past splash) AND has not picked an avatar yet. */}
      {!showSplash && !selectedAvatar && (
        <ORASelector
          userId={userCtx?.email || email || "anon"}
          onSelect={(av) => setSelectedAvatar(av)}
          onSkip={() => {
            // session-only skip — re-prompts next visit
            try { window.localStorage.removeItem(ORA_AVATAR_KEY); } catch (_e) { /* noop */ }
            const fallback = getAvatarById("ora_female_1");
            setSelectedAvatar(fallback);
          }}
        />
      )}
      <div className="orapwa-phone">
        <div className="notch"><div className="notch-pill" /></div>

        {/* SPLASH */}
        <div className={`screen ${showSplash ? "" : "hidden"}`} id="splash">
          <div className="splash-bg" />
          <div className="splash-grid" />
          <div className="splash-inner">
            <div className="ora-logo-wrap">
              {[0, 1, 2, 3, 4].map((i) => (
                <div key={i} className="orbit-ring"><div className="orbit-dot" /></div>
              ))}
              <div className="ora-core" />
            </div>
            <div className="splash-name">ORA <em>AI</em></div>
            <div className="splash-tag">Automation Experts</div>
            <div className="splash-world">World's First Autonomous Intelligence</div>
            <div className="ooda-dots"><div className="od" /><div className="od" /><div className="od" /><div className="od" /></div>
            <div className="splash-form">
              {/* Biometric quick-sign-in (iter 282t) */}
              {bioSupported && bioEmail && (
                <button
                  className="splash-btn"
                  onClick={handleBiometricLogin}
                  disabled={bioBusy}
                  data-testid="ora-splash-biometric"
                  style={{
                    background: "linear-gradient(135deg,#1a1a2e 0%,#16213e 100%)",
                    color: "#F97316",
                    border: "1px solid rgba(249,115,22,0.4)",
                    boxShadow: "0 8px 24px rgba(249,115,22,0.15)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 10,
                  }}
                >
                  {/* fingerprint icon */}
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{flexShrink:0}}>
                    <path d="M2 12C2 6.5 6.5 2 12 2a10 10 0 0 1 8 4"></path>
                    <path d="M5 19.5C5.5 18 6 15 6 12a6 6 0 0 1 .34-2"></path>
                    <path d="M17.29 21.02c.12-.6.43-2.3.5-3.02"></path>
                    <path d="M12 10a2 2 0 0 0-2 2c0 1.02-.1 2.51-.26 4"></path>
                    <path d="M8.65 22c.21-.66.45-1.32.57-2"></path>
                    <path d="M14 13.12c0 2.38 0 6.38-1 8.88"></path>
                    <path d="M2 16h.01"></path>
                    <path d="M21.8 16c.2-2 .131-5.354 0-6"></path>
                    <path d="M8.65 22c.21-.66.45-1.32.57-2"></path>
                    <path d="M9 6.8a6 6 0 0 1 9 5.2c0 .47 0 1.17-.02 2"></path>
                  </svg>
                  {bioBusy ? "Verifying…" : `SIGN IN AS ${bioEmail.split("@")[0].toUpperCase()}`}
                </button>
              )}
              {bioErr && <div className="splash-note" style={{color:"#FF6060"}} data-testid="ora-bio-err">{bioErr}</div>}
              {bioSupported && bioEmail && (
                <div className="splash-note" style={{margin:"4px 0"}}>— or use credentials —</div>
              )}
              <input className="splash-input" type="email" placeholder="Email address" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="ora-splash-email" />
              <input className="splash-input" type="tel" placeholder="Phone number (+1...)" value={phone} onChange={(e) => setPhone(e.target.value)} data-testid="ora-splash-phone" />
              <button className="splash-btn" onClick={enter} data-testid="ora-splash-enter">GET ACCESS →</button>
              <button className="splash-skip" onClick={enter} data-testid="ora-splash-skip">Skip — try ORA anonymously</button>
              <p className="splash-note">Free 14-day trial · No credit card · Cancel anytime</p>
            </div>
          </div>
        </div>

        {/* CHAT */}
        <div className={`screen ${showSplash ? "hidden" : ""}`} id="chat">
          <div className="ticker">
            <div className="ticker-inner">
              {[...TICKER_ITEMS, ...TICKER_ITEMS].map(([l, v, ch, dir], i) => (
                <div key={i} className="tick-item">
                  {l} <span className="tick-val">{v}</span> {ch && <span className={`tick-${dir}`}>{ch}</span>}
                </div>
              ))}
            </div>
          </div>

          <div className="chat-header">
            <div className="hdr-left">
              <div className="hdr-logo">
                <div className="mini-ring" /><div className="mini-ring" /><div className="mini-ring" />
                <div className="mini-core" />
              </div>
              {userCtx ? (
                <div className="hdr-id-block" data-testid="ora-user-identity">
                  <div className="hdr-user-name">{userCtx.business_name || userCtx.name || userCtx.email}</div>
                  {userCtx.bin && <div className="hdr-bin" data-testid="ora-bin">{userCtx.bin}</div>}
                </div>
              ) : (
                <div>
                  <div className="hdr-name">ORA <em>AI</em></div>
                  <div className="hdr-sub">Automation Experts</div>
                </div>
              )}
            </div>
            <div className="hdr-right">
              {/* PHASE 3 — "Hey ORA" wake-word indicator */}
              <WakeWordIndicator
                paused={recording}
                onActivate={() => {
                  if (!recording) {
                    try { toggleVoice(); } catch (_e) { /* noop */ }
                  }
                }}
              />
              <div className="ooda-listen"><div className="ol-dot" /><div className="ol-dot" /><div className="ol-dot" /></div>
              <button className={`icon-btn ${recording ? "active" : ""}`} onClick={toggleVoice} data-testid="ora-voice-btn" aria-label="Voice"
                style={{width: 30, height: 30}}>
                {recording ? (
                  <div className="waveform"><div className="wbar" /><div className="wbar" /><div className="wbar" /><div className="wbar" /><div className="wbar" /></div>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 9.5C8.38 9.5 9.5 8.38 9.5 7V4C9.5 2.62 8.38 1.5 7 1.5C5.62 1.5 4.5 2.62 4.5 4V7C4.5 8.38 5.62 9.5 7 9.5Z" stroke="currentColor" strokeWidth="1.4" />
                    <path d="M11.5 6V7C11.5 9.49 9.49 11.5 7 11.5C4.51 11.5 2.5 9.49 2.5 7V6M7 11.5V13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  </svg>
                )}
              </button>
              {/* Speaker toggle — TTS for ORA replies (iter 282t) */}
              <button
                className={`icon-btn-pwa ${ttsOn ? 'active' : ''}`}
                onClick={toggleTTS}
                data-testid="ora-tts-toggle"
                aria-label={ttsOn ? "Mute ORA voice" : "Unmute ORA voice"}
                title={ttsOn ? "ORA voice ON — tap to mute" : "ORA voice OFF — tap to hear ORA speak"}
              >
                {ttsOn ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                    <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                    <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                    <line x1="23" y1="9" x2="17" y2="15"></line>
                    <line x1="17" y1="9" x2="23" y2="15"></line>
                  </svg>
                )}
              </button>
              {/* iter 282al-2 — Dev Mode toggle. Sets source:"dev" on
                 all outgoing chat messages so ORA routes through its
                 dev skill pipeline (AUREM codebase context + keyword
                 matched dev_* skill). Green dot = ON, grey = OFF. */}
              <button
                className={`icon-btn-pwa ${devMode ? 'active' : ''}`}
                onClick={toggleDevMode}
                data-testid="ora-dev-mode-toggle"
                aria-label={devMode ? "Disable Dev Mode" : "Enable Dev Mode"}
                title={devMode ? "Dev Mode ON — ORA answers as a code assistant" : "Dev Mode OFF — tap to switch ORA into code-assistant mode"}
                style={{ position: 'relative' }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="16 18 22 12 16 6"></polyline>
                  <polyline points="8 6 2 12 8 18"></polyline>
                </svg>
                <span
                  data-testid="ora-dev-mode-dot"
                  style={{
                    position: 'absolute',
                    bottom: 2,
                    right: 2,
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: devMode ? '#22c55e' : '#6b7280',
                    boxShadow: devMode ? '0 0 4px #22c55e' : 'none',
                  }}
                />
              </button>
              {/* iter 282al-26 — Sovereign Truth chip (founder-only, ON-only) */}
              {userCtx?.is_admin && sovereignTruth && (
                <button
                  className="sovereign-truth-chip"
                  onClick={toggleSovereignTruth}
                  disabled={sovereignTruthLoading}
                  data-testid="ora-sovereign-truth-chip"
                  aria-label="Sovereign Truth active — click to disable"
                  title="Sovereign Truth active · Data-grounded critique on strategy replies"
                >
                  <span className="st-dot" /> TRUTH
                </button>
              )}
              {/* Bell — Fix 5 */}
              <button
                className={`icon-btn-pwa ${showNotif ? 'active' : ''}`}
                onClick={() => { setShowNotif(s => !s); if (!showNotif) markNotifsRead(); }}
                data-testid="ora-bell-btn"
                aria-label="Notifications"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
                </svg>
                {notifUnread > 0 && <span className="bell-dot" data-testid="ora-bell-unread" />}
              </button>
              {/* Settings — iter 282al-19: opens slide-in drawer (Bug #7) */}
              <button
                className="icon-btn-pwa"
                onClick={() => setShowSettings(true)}
                data-testid="ora-settings-btn"
                aria-label="Settings"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3"></circle>
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                </svg>
              </button>
            </div>
          </div>

          {/* Notification panel — Fix 5 */}
          {showNotif && (
            <div className="notif-panel" data-testid="ora-notif-panel">
              <div className="notif-hdr">
                <span className="notif-title">Notifications</span>
                <button className="notif-mark" onClick={() => { markNotifsRead(); setShowNotif(false); }} data-testid="ora-notif-mark-read">Close</button>
              </div>
              <div className="notif-list">
                {notifs.length === 0 ? (
                  <div className="notif-empty" data-testid="ora-notif-empty">No notifications today.</div>
                ) : notifs.map(n => (
                  <div key={n.id} className="notif-row">
                    <span className="notif-icon">{n.icon}</span>
                    <div className="notif-body">
                      <div className="notif-text">{n.text}</div>
                      <div className="notif-time">{n.time}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="agent-strip">
            {[["Scout", true], ["Oracle", true], ["Envoy", true], ["Closer", false]].map(([n, on]) => (
              <div key={n} className={`agent ${on ? "active" : ""}`}>
                <div className="a-dot" />{n}
              </div>
            ))}
          </div>

          {/* TAB CONTENT — Fix 4 */}
          {tab !== 'ora' && tab !== 'history' && (
            <TabPanel
              tab={tab}
              data={tabData[tab]}
              loading={tabLoading}
              authToken={authToken}
              userCtx={userCtx}
              onLeadTap={() => setTab('leads')}
            />
          )}

          {tab === 'ora' && (
          <>
          <div className="chat-area" ref={chatAreaRef} data-testid="ora-chat-area">
            <div className="date-div">Today — OODA Session</div>
            {messages.map(renderMsg)}
          </div>

          {recState && (
            <div className="listen-bar" data-testid="ora-listen-bar">
              <div className="waveform"><div className="wbar" /><div className="wbar" /><div className="wbar" /><div className="wbar" /><div className="wbar" /></div>
              <div className="listen-text">{recState}</div>
              <button className="listen-stop" onClick={stopVoice} data-testid="ora-listen-stop">Stop</button>
            </div>
          )}

          {/* iter 282al-4 — voice-command toast (Dev Mode on/off confirmation) */}
          {voiceToast && (
            <div
              data-testid="ora-voice-toast"
              style={{
                position: 'fixed', bottom: 96, left: '50%',
                transform: 'translateX(-50%)', zIndex: 9999,
                background: 'rgba(0,0,0,0.88)',
                border: '1px solid rgba(212,175,55,0.3)',
                color: '#E8E0D0', padding: '12px 22px', borderRadius: 999,
                fontSize: 14, fontWeight: 600, letterSpacing: '0.02em',
                backdropFilter: 'blur(10px)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                animation: 'voiceToastPulse 0.25s ease-out',
              }}
            >
              {voiceToast}
            </div>
          )}

          <div className="input-bar">
            <div className="input-wrap">
              <button
                className={`icon-mini ${recording ? "recording" : ""}`}
                onClick={toggleVoice}
                data-testid="ora-mic-btn"
                aria-label={recording ? "Stop recording" : "Start voice"}
              >
                <svg width="16" height="16" viewBox="0 0 14 14" fill="none">
                  <rect x="4.5" y="0.5" width="5" height="8" rx="2.5" fill="currentColor" />
                  <path d="M1 6.5c0 3.3 2.7 6 6 6s6-2.7 6-6" stroke="currentColor" strokeWidth="1.3" fill="none" />
                  <line x1="7" y1="12.5" x2="7" y2="14" stroke="currentColor" strokeWidth="1.3" />
                </svg>
              </button>
              <button className="icon-mini" onClick={() => fileInRef.current?.click()} data-testid="ora-attach-btn" aria-label="Attach">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M11.5 6L6.5 11a2.121 2.121 0 0 1-3-3l5.5-5.5a3.182 3.182 0 0 1 4.5 4.5l-6 6a4.243 4.243 0 0 1-6-6L8.5 1.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              {/* iter 282al-14 — Video w/ emotion (face-api.js, in-browser) */}
              <button
                className={`icon-mini ${videoOpen ? "recording" : ""}`}
                onClick={() => setVideoOpen((v) => !v)}
                data-testid="ora-video-btn"
                aria-label={videoOpen ? "Stop video" : "Start video"}
                title="Talk to ORA on video (emotion-aware)"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <rect x="1" y="3" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.3" />
                  <path d="M11 6.5l4-2v7l-4-2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
                </svg>
              </button>
              <input
                type="file"
                ref={fileInRef}
                onChange={onFileSelect}
                accept="image/*,.pdf,.doc,.docx,.txt,.csv"
                style={{ display: "none" }}
                data-testid="ora-file-input"
              />
              <textarea
                className="chat-input"
                rows={1}
                value={chatInput}
                onChange={(e) => {
                  setChatInput(e.target.value);
                  // iter 322bp — auto-grow so pasted content is visible
                  e.target.style.height = 'auto';
                  e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';
                }}
                onKeyDown={(e) => {
                  // Enter = send. Shift+Enter = newline. So pasted/typed
                  // multi-line content doesn't trigger send mid-paste.
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMsg();
                  }
                }}
                onPaste={(e) => {
                  // iter 322bp — explicit paste logging so we can see the
                  // event hits the input. Native paste then continues.
                  try {
                    const pasted = e.clipboardData?.getData('text') || '';
                    console.debug('[ORA] paste:', pasted.length, 'chars');
                  } catch {}
                }}
                placeholder="Ask ORA anything… (paste freely · Shift+Enter for new line)"
                data-testid="ora-chat-input"
                style={{ resize: 'none', overflow: 'auto', maxHeight: 160 }}
              />
              <button className="send-btn" onClick={() => sendMsg()} disabled={sending || !chatInput.trim()} data-testid="ora-send-btn" aria-label="Send">
                <svg width="14" height="14" viewBox="0 0 12 12" fill="none">
                  <path d="M1 6L11 6M11 6L7 2M11 6L7 10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
          </>
          )}

          <div className="bottom-nav">
            {[
              ["ora", "ORA"],
              ["leads", "Leads"],
              ["scout", "Scout"],
              ["revenue", "Revenue"],
              ["history", "History"],
            ].map(([id, label]) => (
              <button
                key={id}
                className={`nav-item ${tab === id ? "active" : ""}`}
                onClick={() => {
                  setTab(id);
                  if (id === "history") setShowHistory(true);
                }}
                data-testid={`ora-nav-${id}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* iter 282al-14 — Video session popup (face-api.js, in-browser) */}
        {/* iter 282al-19 — when video opens, also auto-start STT (Bug #3) */}
        <VideoOraSession
          open={videoOpen}
          onClose={() => setVideoOpen(false)}
          onEmotionChange={onEmotionChange}
          onAudioStream={(stream) => {
            if (stream && !recording) {
              try { startVoice(); } catch (_) {}
            } else if (!stream && recording) {
              try { stopVoice(); } catch (_) {}
            }
          }}
        />

        {/* iter 282al-19 — Settings drawer (Bug #7) */}
        {showSettings && (
          <>
            <div
              className="settings-backdrop"
              onClick={() => setShowSettings(false)}
              data-testid="ora-settings-backdrop"
            />
            <div className="settings-drawer" data-testid="ora-settings-drawer">
              <div className="settings-hdr">
                <h3>Settings</h3>
                <button
                  className="icon-btn"
                  onClick={() => setShowSettings(false)}
                  data-testid="ora-settings-close"
                  aria-label="Close settings"
                >×</button>
              </div>
              <div className="settings-body">
                <div className="settings-row" data-testid="setting-model">
                  <div>
                    <div className="settings-label">Model preference</div>
                    <div className="settings-sub">Auto-routes between Claude / Gemini / GPT</div>
                  </div>
                  <select
                    className="settings-select"
                    defaultValue={(typeof window !== "undefined" && localStorage.getItem("aurem_ora_model")) || "auto"}
                    onChange={(e) => { try { localStorage.setItem("aurem_ora_model", e.target.value); } catch (_) {} }}
                    data-testid="setting-model-select"
                  >
                    <option value="auto">Auto (recommended)</option>
                    <option value="claude">Claude only</option>
                    <option value="gemini">Gemini only</option>
                    <option value="gpt">GPT only</option>
                  </select>
                </div>

                <div className="settings-row" data-testid="setting-voice">
                  <div>
                    <div className="settings-label">Voice replies</div>
                    <div className="settings-sub">Read ORA's responses aloud</div>
                  </div>
                  <button
                    className={`toggle ${ttsOn ? "on" : ""}`}
                    onClick={toggleTTS}
                    data-testid="setting-voice-toggle"
                    aria-label="Toggle voice replies"
                  ><span className="toggle-knob" /></button>
                </div>

                <div className="settings-row" data-testid="setting-dev">
                  <div>
                    <div className="settings-label">Dev mode</div>
                    <div className="settings-sub">Route through ORA's developer skill pipeline</div>
                  </div>
                  <button
                    className={`toggle ${devMode ? "on" : ""}`}
                    onClick={toggleDevMode}
                    data-testid="setting-dev-toggle"
                    aria-label="Toggle dev mode"
                  ><span className="toggle-knob" /></button>
                </div>

                {/* iter 282al-26 — Sovereign Truth (founder-only) */}
                {userCtx?.is_admin && (
                  <div className="settings-row" data-testid="setting-sovereign-truth">
                    <div>
                      <div className="settings-label">
                        Sovereign Truth
                        <span style={{
                          marginLeft: 8, padding: "1px 6px", borderRadius: 4,
                          fontSize: 9, letterSpacing: 1,
                          background: "rgba(184,115,51,0.18)",
                          color: "#C77B3A", fontWeight: 700,
                        }}>FOUNDER</span>
                      </div>
                      <div className="settings-sub">
                        Data-grounded critique on every strategy reply. Pulls from
                        real performance metrics — no hallucinated negatives.
                      </div>
                    </div>
                    <button
                      className={`toggle ${sovereignTruth ? "on" : ""}`}
                      onClick={toggleSovereignTruth}
                      disabled={sovereignTruthLoading}
                      data-testid="setting-sovereign-truth-toggle"
                      aria-label="Toggle Sovereign Truth mode"
                    ><span className="toggle-knob" /></button>
                  </div>
                )}

                <div className="settings-row" data-testid="setting-notif">
                  <div>
                    <div className="settings-label">Notifications</div>
                    <div className="settings-sub">Show in-app alerts when ORA pings you</div>
                  </div>
                  <button
                    className={`toggle ${(typeof window !== "undefined" && localStorage.getItem("aurem_ora_notif") !== "0") ? "on" : ""}`}
                    onClick={(e) => {
                      try {
                        const cur = localStorage.getItem("aurem_ora_notif") !== "0";
                        localStorage.setItem("aurem_ora_notif", cur ? "0" : "1");
                        e.currentTarget.classList.toggle("on", !cur);
                      } catch (_) {}
                    }}
                    data-testid="setting-notif-toggle"
                    aria-label="Toggle notifications"
                  ><span className="toggle-knob" /></button>
                </div>

                <button
                  className="settings-danger"
                  onClick={() => {
                    if (window.confirm("Clear chat history? This cannot be undone.")) {
                      try { localStorage.removeItem(HISTORY_KEY); } catch (_) {}
                      setMessages([]);
                      setShowSettings(false);
                    }
                  }}
                  data-testid="setting-clear-history"
                >Clear chat history</button>

                {authToken && (
                  <button
                    className="settings-danger"
                    onClick={() => {
                      if (!window.confirm("Sign out of ORA? You'll need to log in again to access your business data.")) return;
                      // Clear EVERY token + user key the app may have written
                      ['platform_token','aurem_admin_token','aurem_token','token','jwt_token','admin_token']
                        .forEach(k => { try { localStorage.removeItem(k); sessionStorage.removeItem(k); } catch(_){} });
                      ['platform_user','aurem_user','user'].forEach(k => {
                        try { localStorage.removeItem(k); sessionStorage.removeItem(k); } catch(_){}
                      });
                      try { localStorage.removeItem(HISTORY_KEY); } catch (_) {}
                      setMessages([]);
                      setShowSettings(false);
                      // Send back to landing so login UI can re-init cleanly
                      window.location.href = '/';
                    }}
                    data-testid="setting-sign-out"
                    style={{ marginTop: 8, borderColor: '#E0524A', color: '#E0524A' }}
                  >Sign out</button>
                )}
              </div>
            </div>
          </>
        )}

        {/* HISTORY OVERLAY — Fix 4: now shows last 7 days of daily verification log */}
        <div className={`history-overlay ${showHistory ? "" : "hidden"}`} data-testid="ora-history-overlay">
          <div className="history-hdr">
            <h3>LAST 7 DAYS</h3>
            <button className="icon-btn" onClick={() => { setShowHistory(false); setTab("ora"); }} data-testid="ora-history-close">✕</button>
          </div>
          <div className="history-list" data-testid="ora-history-days">
            {!authToken && (
              <div className="history-empty">Sign in to see your daily verification log.</div>
            )}
            {authToken && (tabData.history || []).length === 0 && (
              <div className="history-empty" data-testid="ora-history-empty">No daily logs yet. Cron jobs fire at 9 AM EST.</div>
            )}
            {(tabData.history || []).map((day) => {
              const eod = (day.events || []).find(e => e.event === 'end_of_day') || {};
              const scout = (day.events || []).find(e => e.event === 'scout_complete') || {};
              return (
                <div key={day.date} className="history-item" data-testid={`ora-history-day-${day.date}`}>
                  <div className="history-item-title">{day.date}</div>
                  <div className="history-item-meta" style={{display:'flex',gap:12,flexWrap:'wrap',marginTop:6}}>
                    <span>leads: <b style={{color:'#F97316'}}>{eod.leads_real_count ?? scout.leads_real_count ?? 0}</b></span>
                    <span>sites: <b style={{color:'#F97316'}}>{eod.http_verified ?? 0}/{eod.sites_rendered ?? eod.rendered ?? 0}</b></span>
                    <span>email: <b style={{color:'#F97316'}}>{eod.emails_resend_confirmed ?? 0}</b></span>
                    <span>$<b style={{color:'#86EFAC'}}>{eod.stripe_revenue_real ?? 0}</b></span>
                  </div>
                </div>
              );
            })}
            {authToken && (tabData.history || []).length === 0 && history.length > 0 && (
              <>
                <div style={{padding:'12px 14px',fontSize:10,color:'#5A5570',letterSpacing:'0.18em'}}>CHAT HISTORY</div>
                {[...history].reverse().map((s) => (
                  <div key={s.id} className="history-item" onClick={() => restoreSession(s)} data-testid={`ora-history-item-${s.id}`}>
                    <div className="history-item-title">{s.title || "(no preview)"}</div>
                    <div className="history-item-meta">{s.turns} turns · {new Date(s.updated_at).toLocaleString()}</div>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default OraPWA;

// ── Tab content panels (Fix 4) ───────────────────────────────────
function TabPanel({ tab, data, loading, authToken, userCtx, onLeadTap }) {
  if (!authToken) {
    return (
      <div className="tab-panel">
        <div className="tp-card">
          <div className="tp-eyebrow">Sign in required</div>
          <div className="tp-title">Live data needs your account</div>
          <p style={{fontSize:12.5,color:'#9A95B0',lineHeight:1.5,marginTop:6}}>
            Open <span style={{color:'#F97316'}}>aurem.live/my</span> in your browser, sign in,
            then come back here. Your leads, sites, and revenue will live-stream.
          </p>
        </div>
      </div>
    );
  }
  if (loading) {
    return <div className="tab-panel"><div className="tp-empty">Loading…</div></div>;
  }
  if (tab === 'leads') return <LeadsTab data={data} />;
  if (tab === 'scout') return <ScoutTab data={data} userCtx={userCtx} />;
  if (tab === 'revenue') return <RevenueTab data={data} />;
  return null;
}

function LeadsTab({ data }) {
  const items = (data && data.items) || [];
  const scope = data?.scope || 'admin';
  return (
    <div className="tab-panel" data-testid="ora-tab-leads">
      <div className="tp-eyebrow">{scope === 'admin' ? "Today's Outreach Targets" : 'Your Inbound Leads Today'}</div>
      <div className="tp-title">{items.length} {scope === 'admin' ? 'in pipeline' : 'received'}</div>
      {items.length === 0 ? (
        <div className="tp-empty">
          {scope === 'admin'
            ? "No outreach leads yet today. Scout fires at 9 AM EST."
            : "No new inbound leads today. Share your repair-quote link or run a campaign."}
        </div>
      ) : items.map((l) => {
        const isAdminLead = !!l.lead_id && (l.business_name !== undefined);
        if (isAdminLead) {
          const hasEmail = ((l.discovered_emails || []).length > 0) || l.discovered_emails_count > 0;
          const hasSite = !!(l.awb_built_at || l.awb_slug);
          return (
            <div key={l.lead_id} className="tp-card" data-testid={`ora-lead-${l.lead_id}`}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:10}}>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{fontSize:13.5,color:'#FFF',fontWeight:600,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
                    {l.business_name || l.lead_id}
                  </div>
                  <div style={{fontSize:11,color:'#9A95B0',marginTop:2}}>
                    {l.city || l.address || '—'}
                  </div>
                </div>
                <div style={{display:'flex',gap:4,flexShrink:0}}>
                  <span className={`tp-pill ${hasEmail ? 'good' : 'bad'}`}>{hasEmail ? 'EMAIL' : 'NO EMAIL'}</span>
                  <span className={`tp-pill ${hasSite ? 'good' : 'bad'}`}>{hasSite ? 'SITE' : 'NO SITE'}</span>
                </div>
              </div>
            </div>
          );
        }
        // Customer inbound lead
        return (
          <div key={l.lead_id || l.created_at} className="tp-card" data-testid={`ora-inbound-${l.lead_id || ''}`}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:10}}>
              <div style={{flex:1,minWidth:0}}>
                <div style={{fontSize:13.5,color:'#FFF',fontWeight:600}}>{l.name || 'Anonymous'}</div>
                <div style={{fontSize:11,color:'#9A95B0',marginTop:2}}>
                  {l.email || l.phone || '—'} · {l.source || 'web'}
                </div>
              </div>
              <span className={`tp-pill ${l.status === 'new' || !l.status ? 'good' : 'bad'}`}>{(l.status || 'NEW').toUpperCase()}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ScoutTab({ data, userCtx }) {
  const scope = data?.scope || 'admin';
  if (scope === 'customer') {
    return (
      <div className="tab-panel" data-testid="ora-tab-scout">
        <div className="tp-eyebrow">Scout — Your Listings</div>
        <div className="tp-title">Review monitoring active</div>
        <div className="tp-card-strong">
          <div className="tp-stat-num" data-testid="ora-scout-count">{data?.your_reviews_total ?? 0}</div>
          <div className="tp-stat-lbl">Total reviews tracked</div>
        </div>
        <div className="tp-card">
          <p style={{fontSize:12.5,color:'#9A95B0',lineHeight:1.5,margin:0}}>
            {data?.message || "AUREM Scout watches your Google reviews and citations. New reviews appear in your bell ⭐"}
          </p>
        </div>
      </div>
    );
  }
  const ev = data?.last_event;
  const leadCount = data?.leads_today ?? 0;
  const lastTime = ev ? (ev.ts_utc || '').slice(11, 16) + ' UTC' : 'No run today';
  return (
    <div className="tab-panel" data-testid="ora-tab-scout">
      <div className="tp-eyebrow">Scout Agent</div>
      <div className="tp-title">{ev ? 'Active' : 'Idle'}</div>
      <div className="tp-card-strong">
        <div className="tp-stat-num" data-testid="ora-scout-count">{leadCount}</div>
        <div className="tp-stat-lbl">Real leads found today</div>
      </div>
      <div className="tp-card">
        <div className="tp-row"><span className="tp-row-l">Last run</span><span className="tp-row-r">{lastTime}</span></div>
        <div className="tp-row"><span className="tp-row-l">Status</span><span className={`tp-row-r ${ev ? 'tp-status-good' : 'tp-status-bad'}`}>{ev ? '● Live' : '◌ Idle'}</span></div>
        <div className="tp-row"><span className="tp-row-l">Areas</span><span className="tp-row-r">Brampton · Mississauga</span></div>
        <div className="tp-row"><span className="tp-row-l">Next run</span><span className="tp-row-r">{data?.next_run || '9:00 AM EST'}</span></div>
      </div>
      {userCtx?.is_admin && (
        <button className="tp-action" data-testid="ora-scout-run-now" onClick={() => alert('Manual scout run kicks off campaign automation. Use /admin/daily-log to monitor.')}>
          Run Scout Now
        </button>
      )}
    </div>
  );
}

function RevenueTab({ data }) {
  const d = data || {};
  const isAdmin = d.scope === 'admin';
  if (isAdmin) {
    return (
      <div className="tab-panel" data-testid="ora-tab-revenue">
        <div className="tp-eyebrow">Platform Revenue Today</div>
        <div className="tp-title">Live Stripe</div>
        <div className="tp-card-strong">
          <div className="tp-stat-num" style={{color:'#86EFAC',textShadow:'0 0 14px rgba(34,197,94,0.4)'}} data-testid="ora-revenue-amount">${Number(d.revenue_today || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</div>
          <div className="tp-stat-lbl">Today's gross · all customers</div>
        </div>
        <div className="tp-card">
          <div className="tp-row"><span className="tp-row-l">Active subscribers</span><span className="tp-row-r">{d.active_subscribers ?? 0}</span></div>
          <div className="tp-row"><span className="tp-row-l">MRR estimate</span><span className="tp-row-r">${Number(d.mrr_estimate || 0).toLocaleString()}</span></div>
        </div>
      </div>
    );
  }
  // Customer view
  const status = (d.subscription_status || 'trial').toUpperCase();
  const trialDays = d.trial_days_left;
  return (
    <div className="tab-panel" data-testid="ora-tab-revenue">
      <div className="tp-eyebrow">Your Plan</div>
      <div className="tp-title">{d.plan || 'Free'}</div>
      <div className="tp-card-strong">
        <div className="tp-stat-num" data-testid="ora-revenue-amount">{status}</div>
        <div className="tp-stat-lbl">Subscription status</div>
      </div>
      <div className="tp-card">
        {trialDays != null && (
          <div className="tp-row"><span className="tp-row-l">Trial days left</span><span className={`tp-row-r ${trialDays > 3 ? 'tp-status-good' : 'tp-status-bad'}`}>{trialDays}</span></div>
        )}
        {d.last_payment && (
          <div className="tp-row"><span className="tp-row-l">Last payment</span><span className="tp-row-r tp-status-good">${d.last_payment.amount} {d.last_payment.currency}</span></div>
        )}
        {!d.last_payment && (
          <div className="tp-row"><span className="tp-row-l">Last payment</span><span className="tp-row-r">—</span></div>
        )}
      </div>
    </div>
  );
}
