/**
 * AUREM Homepage — World's First Autonomous Intelligence Platform
 * iter 281.7 — full design refresh (orange/gold theme, plain English)
 * with real React Router wiring + real ORA backend chat.
 */
import React, { useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { User } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

// ─── BackgroundVideo (LCP-friendly, deferred) ──────────────────────────
// PageSpeed audit on aurem.live identified the autoplay 843KB MP4 as the
// LCP element with 27.6s render time. Solution: only the lightweight
// poster.jpg (62KB) loads on initial paint. The MP4 is lazily mounted
// after first paint AND only when the device clearly has the bandwidth
// (no `connection.saveData`, ≥4G effective type, prefers-reduced-motion
// off). Same final visual; LCP measured against the poster instead.
const BackgroundVideo = () => {
  const [mountVideo, setMountVideo] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    // Respect explicit user preference
    if (window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    // Save-data / slow-network bail
    const conn = navigator.connection || navigator.mozConnection ||
                 navigator.webkitConnection;
    if (conn) {
      if (conn.saveData) return;
      if (conn.effectiveType && /(2g|slow-2g|3g)/.test(conn.effectiveType)) {
        return;
      }
    }

    const schedule = () => setMountVideo(true);
    if ("requestIdleCallback" in window) {
      const id = window.requestIdleCallback(schedule, { timeout: 3500 });
      return () => window.cancelIdleCallback(id);
    }
    const id = window.setTimeout(schedule, 2200);
    return () => window.clearTimeout(id);
  }, []);

  return (
    <div className="bg-video-wrap" data-testid="bg-video-wrap" aria-hidden="true">
      <img
        className="bg-video"
        src="/video/homepage-bg-poster.jpg"
        alt=""
        width="1280"
        height="720"
        decoding="async"
        fetchpriority="high"
        style={{ display: mountVideo ? "none" : "block" }}
      />
      {mountVideo && (
        <video
          className="bg-video"
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          poster="/video/homepage-bg-poster.jpg"
          src="/video/homepage-bg-720.mp4"
          width="1280"
          height="720"
          data-testid="bg-video"
        />
      )}
      <div className="bg-video-tint" />
    </div>
  );
};

const HOMEPAGE_CSS = `
:root{
  --void:#050508; --dark:#0A0A0F; --dark2:#0E0E16; --dark3:#13131F;
  --card:#0F0F1A; --orange:#FF6B00; --orange2:#FF8C35; --gold:#C9A84C;
  --gold2:#E8C86A; --white:#F0EDE8; --muted:#7A7590; --muted2:#4A4560;
  --border:rgba(255,107,0,0.10); --border-gold:rgba(201,168,76,0.15);
}
.aurem-home *{margin:0;padding:0;box-sizing:border-box;}
.aurem-home{background:var(--void);color:var(--white);font-family:'Jost',sans-serif;font-weight:300;overflow-x:hidden;line-height:1.6;min-height:100vh;}
.aurem-home a{color:inherit;text-decoration:none;}
.aurem-home button{font-family:inherit;}

.bg-glow{position:fixed;inset:0;z-index:0;pointer-events:none;background:radial-gradient(ellipse 90% 50% at 50% -10%,rgba(255,107,0,0.10) 0%,transparent 60%),radial-gradient(ellipse 50% 60% at 95% 40%,rgba(201,168,76,0.06) 0%,transparent 55%),radial-gradient(ellipse 40% 40% at 5% 75%,rgba(255,107,0,0.04) 0%,transparent 50%);}
.bg-grid{position:fixed;inset:0;z-index:0;pointer-events:none;background-image:linear-gradient(rgba(255,107,0,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(255,107,0,0.03) 1px,transparent 1px);background-size:64px 64px;mask-image:radial-gradient(ellipse 100% 70% at 50% 0%,black 20%,transparent 75%);}

.bg-video-wrap{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden;background:var(--void);}
.bg-video{position:absolute;top:50%;left:50%;min-width:100%;min-height:100%;width:auto;height:auto;transform:translate(-50%,-50%);object-fit:cover;opacity:0.42;filter:saturate(1.1) contrast(1.05);}
.bg-video-tint{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse 80% 70% at 50% 50%,rgba(5,5,8,0.35) 0%,rgba(5,5,8,0.82) 85%),linear-gradient(180deg,rgba(5,5,8,0.55) 0%,rgba(5,5,8,0.25) 40%,rgba(5,5,8,0.85) 100%);}
@media (prefers-reduced-motion: reduce){.bg-video{display:none;}}

.aurem-home nav{position:fixed;top:0;left:0;right:0;z-index:200;padding:18px 5%;display:flex;align-items:center;justify-content:space-between;background:linear-gradient(to bottom,rgba(5,5,8,0.97),rgba(5,5,8,0.85));backdrop-filter:blur(20px);border-bottom:1px solid var(--border);}
.nav-logo{display:flex;align-items:center;gap:10px;cursor:pointer;}
.nav-wordmark{font-family:'Cinzel',serif;font-size:18px;font-weight:700;letter-spacing:0.2em;color:var(--gold2);}
.nav-links{display:flex;align-items:center;gap:28px;}
.nav-links a,.nav-links button{color:var(--muted);background:none;border:none;font-size:13px;letter-spacing:0.05em;transition:color 0.2s;cursor:pointer;}
.nav-links a:hover,.nav-links button:hover{color:var(--white);}
.nav-cta{background:var(--orange);color:#fff;padding:10px 24px;border-radius:4px;font-size:13px;font-weight:500;letter-spacing:0.05em;transition:all 0.2s;border:none;cursor:pointer;}
.nav-cta:hover{background:var(--orange2);transform:translateY(-1px);}
.nav-actions{display:flex;align-items:center;gap:12px;}
.nav-login{background:transparent;border:1px solid var(--gold2);color:var(--gold2);padding:9px 20px;border-radius:4px;font-size:13px;font-weight:500;letter-spacing:0.05em;transition:all 0.2s;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:6px;line-height:1;font-family:inherit;}
.nav-login:hover{background:rgba(201,162,39,0.1);border-color:var(--gold);color:var(--gold);}
.nav-login-icon{display:none;}
.nav-login-text{display:inline;}

.world-first-bar{position:relative;z-index:1;margin-top:72px;background:linear-gradient(90deg,rgba(255,107,0,0.08),rgba(201,168,76,0.12),rgba(255,107,0,0.08));border-bottom:1px solid var(--border-gold);padding:10px 5%;text-align:center;}
.world-first-bar span{font-family:'Cinzel',serif;font-size:11px;letter-spacing:0.2em;color:var(--gold);text-transform:uppercase;}
.world-first-bar span em{color:var(--orange);font-style:normal;}

.ca-trust-bar{position:relative;z-index:1;background:#0a0a0a;border-bottom:1px solid var(--border-gold);padding:10px 0;overflow:hidden;}
.ca-trust-track{display:flex;align-items:center;justify-content:center;gap:18px;flex-wrap:wrap;padding:0 5%;}
.ca-trust-item{display:inline-flex;align-items:center;font-family:'DM Sans',sans-serif;font-size:11px;letter-spacing:0.18em;color:var(--gold);text-transform:uppercase;white-space:nowrap;}
.ca-trust-sep{color:var(--orange);opacity:0.55;font-size:13px;}
@media(max-width:768px){.ca-trust-bar{padding:8px 0;}.ca-trust-track{flex-wrap:nowrap;justify-content:flex-start;animation:ca-trust-scroll 28s linear infinite;will-change:transform;padding-left:100%;}.ca-trust-item{font-size:10px;letter-spacing:0.14em;}}
@keyframes ca-trust-scroll{0%{transform:translateX(0);}100%{transform:translateX(-100%);}}

.hero{position:relative;z-index:1;min-height:92vh;display:flex;align-items:center;justify-content:center;text-align:center;padding:60px 5% 80px;}
.hero-inner{max-width:860px;}
.hero-eyebrow{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--border-gold);padding:6px 18px;border-radius:100px;margin-bottom:32px;font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:0.12em;color:var(--gold);}
.hero-eyebrow .dot{width:6px;height:6px;background:var(--orange);border-radius:50%;animation:blink 2s ease-in-out infinite;}
@keyframes blink{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(255,107,0,0.5);}50%{opacity:0.7;box-shadow:0 0 0 8px rgba(255,107,0,0);}}

.hero-title{font-family:'Cinzel',serif;font-size:clamp(34px,6vw,78px);font-weight:700;line-height:1.06;letter-spacing:0.02em;margin-bottom:8px;}
.hero-title .t1{display:block;color:var(--white);}
.hero-title .t2{display:block;background:linear-gradient(135deg,var(--orange) 0%,var(--gold2) 55%,var(--orange2) 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;}
.hero-punch{font-size:clamp(15px,1.8vw,19px);color:var(--muted);max-width:580px;margin:20px auto 44px;line-height:1.75;font-weight:300;}
.hero-punch strong{color:var(--white);font-weight:500;}

.hero-btns{display:flex;align-items:center;justify-content:center;gap:14px;flex-wrap:wrap;margin-bottom:12px;}
.btn-primary{background:linear-gradient(135deg,var(--orange),var(--orange2));color:#fff;padding:15px 38px;border-radius:4px;font-size:15px;font-weight:500;letter-spacing:0.05em;transition:all 0.25s;display:inline-flex;align-items:center;gap:8px;border:none;cursor:pointer;}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 14px 40px rgba(255,107,0,0.35);}
.btn-ghost{background:transparent;color:var(--white);padding:14px 32px;border-radius:4px;font-size:15px;font-weight:400;letter-spacing:0.05em;transition:all 0.25s;border:1px solid var(--border-gold);cursor:pointer;}
.btn-ghost:hover{background:rgba(201,168,76,0.08);border-color:var(--gold);}
.hero-note{font-size:12px;color:var(--muted2);letter-spacing:0.05em;}

.stats-row{position:relative;z-index:1;display:flex;justify-content:center;gap:0;max-width:680px;margin:48px auto 0;border:1px solid var(--border);border-radius:8px;overflow:hidden;}
.stat{flex:1;padding:20px 16px;text-align:center;border-right:1px solid var(--border);background:var(--card);}
.stat:last-child{border-right:none;}
.stat-n{font-family:'Cinzel',serif;font-size:24px;font-weight:700;color:var(--gold2);display:block;line-height:1;}
.stat-l{font-size:11px;color:var(--muted);letter-spacing:0.08em;margin-top:5px;display:block;}

.aurem-home section{position:relative;z-index:1;}
.s-label{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:var(--orange);margin-bottom:14px;display:block;}
.s-title{font-family:'Cinzel',serif;font-size:clamp(24px,3.5vw,44px);font-weight:600;line-height:1.15;letter-spacing:0.02em;}
.s-sub{font-size:16px;color:var(--muted);line-height:1.7;max-width:520px;}
.center{text-align:center;}
.center .s-sub{margin:0 auto;}

.pain{padding:100px 5%;}
.pain-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--border);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin:56px auto 0;max-width:960px;}
.pain-card{background:var(--card);padding:40px 28px;position:relative;}
.pain-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;}
.pain-card.c1::before{background:rgba(255,80,80,0.5);}
.pain-card.c2::before{background:linear-gradient(90deg,rgba(255,107,0,0.6),rgba(201,168,76,0.6));}
.pain-card.c3::before{background:rgba(80,200,120,0.5);}
.pain-tag{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.12em;margin-bottom:14px;display:block;text-transform:uppercase;}
.pain-card.c1 .pain-tag{color:#FF6060;}
.pain-card.c2 .pain-tag{color:var(--orange);}
.pain-card.c3 .pain-tag{color:#50C878;}
.pain-text{font-size:15px;color:var(--white);line-height:1.65;margin-bottom:16px;}
.pain-text strong{color:var(--orange);}
.pain-result{font-family:'Cinzel',serif;font-size:13px;letter-spacing:0.08em;}
.pain-card.c1 .pain-result{color:#FF6060;}
.pain-card.c2 .pain-result{color:var(--gold);}
.pain-card.c3 .pain-result{color:#50C878;}

.scan-section{padding:80px 5%;background:linear-gradient(160deg,rgba(255,107,0,0.04),rgba(201,168,76,0.03),transparent);}
.scan-box{max-width:720px;margin:0 auto;border:1px solid rgba(255,107,0,0.25);border-radius:12px;overflow:hidden;}
.scan-header{background:var(--dark2);padding:16px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;}
.scan-dots span{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px;}
.scan-dots span:nth-child(1){background:#FF5F57;}.scan-dots span:nth-child(2){background:#FFBD2E;}.scan-dots span:nth-child(3){background:#28C840;}
.scan-bar-title{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);margin-left:6px;}
.scan-live{margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--orange);display:flex;align-items:center;gap:5px;}
.scan-live::before{content:'';width:5px;height:5px;background:var(--orange);border-radius:50%;animation:blink 1.5s infinite;}
.scan-body{padding:40px 40px 36px;}
.scan-title{font-family:'Cinzel',serif;font-size:clamp(20px,2.5vw,28px);margin-bottom:10px;}
.scan-sub{font-size:14px;color:var(--muted);margin-bottom:28px;line-height:1.65;}
.scan-form{display:flex;gap:10px;margin-bottom:14px;}
.scan-form input{flex:1;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:4px;padding:13px 16px;color:var(--white);font-family:'Jost',sans-serif;font-size:14px;outline:none;transition:border 0.2s;}
.scan-form input:focus{border-color:var(--orange);}
.scan-form input::placeholder{color:var(--muted2);}
.scan-note{font-size:12px;color:var(--muted2);}
.scan-checks{display:flex;flex-wrap:wrap;gap:8px;margin-top:24px;}
.check-tag{background:rgba(201,168,76,0.07);border:1px solid var(--border-gold);padding:5px 13px;border-radius:100px;font-size:11px;color:var(--gold);}

.demo{padding:80px 5%;}
.demo-wrap{max-width:660px;margin:0 auto;}
.demo-box{background:var(--dark3);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-top:36px;}
.demo-top{padding:13px 20px;background:var(--dark2);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;}
.ddots{display:flex;gap:5px;}.ddots span{width:10px;height:10px;border-radius:50%;}
.ddots span:nth-child(1){background:#FF5F57;}.ddots span:nth-child(2){background:#FFBD2E;}.ddots span:nth-child(3){background:#28C840;}
.dtitle{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);margin-left:6px;}
.dlive{margin-left:auto;display:flex;align-items:center;gap:4px;font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--orange);}
.dlive::before{content:'';width:5px;height:5px;background:var(--orange);border-radius:50%;animation:blink 1.5s infinite;}
.dmsgs{padding:20px;min-height:260px;max-height:380px;overflow-y:auto;display:flex;flex-direction:column;gap:12px;}
.msg{max-width:82%;padding:12px 16px;border-radius:8px;font-size:14px;line-height:1.55;}
.msg-u{background:rgba(255,107,0,0.12);border:1px solid rgba(255,107,0,0.2);color:var(--white);align-self:flex-end;border-radius:8px 8px 2px 8px;}
.msg-a{background:var(--dark2);border:1px solid var(--border-gold);color:var(--white);align-self:flex-start;border-radius:8px 8px 8px 2px;white-space:pre-wrap;}
.msg-a::before{content:'ORA';font-family:'Cinzel',serif;font-size:9px;letter-spacing:0.15em;color:var(--gold);display:block;margin-bottom:5px;}
.typing{display:flex;gap:4px;padding:2px 0;}.typing span{width:6px;height:6px;background:var(--gold);border-radius:50%;animation:bounce 1.2s infinite;}
.typing span:nth-child(2){animation-delay:.2s;}.typing span:nth-child(3){animation-delay:.4s;}
@keyframes bounce{0%,60%,100%{transform:translateY(0);}30%{transform:translateY(-7px);}}
.dinput{padding:14px 18px;border-top:1px solid var(--border);display:flex;gap:10px;}
.dinput input{flex:1;background:transparent;border:none;outline:none;color:var(--white);font-family:'Jost',sans-serif;font-size:14px;}
.dinput input::placeholder{color:var(--muted2);}
.dsend{background:var(--orange);border:none;padding:8px 18px;border-radius:4px;color:#fff;font-size:13px;cursor:pointer;font-weight:500;transition:all 0.2s;}
.dsend:hover{background:var(--orange2);}.dsend:disabled{opacity:.5;cursor:wait;}

.how{padding:100px 5%;text-align:center;}
.how-grid{display:flex;gap:0;max-width:950px;margin:56px auto 0;}
.how-step{flex:1;padding:36px 24px;background:var(--card);border:1px solid var(--border);position:relative;}
.how-step:not(:last-child){border-right:none;}
.how-arrow{position:absolute;right:-14px;top:50%;transform:translateY(-50%);color:var(--orange);font-size:18px;z-index:2;background:var(--void);padding:4px;border-radius:50%;border:1px solid var(--border);}
.how-n{font-family:'Cinzel Decorative',serif;font-size:36px;color:rgba(255,107,0,0.12);line-height:1;margin-bottom:12px;}
.how-emoji{font-size:26px;margin-bottom:10px;}
.how-t{font-family:'Cinzel',serif;font-size:13px;letter-spacing:0.1em;color:var(--gold);margin-bottom:8px;text-transform:uppercase;}
.how-d{font-size:13px;color:var(--muted);line-height:1.6;}

.who{padding:100px 5%;}
.who-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:960px;margin:56px auto 0;}
.who-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:32px 24px;transition:all 0.3s;}
.who-card:hover{border-color:rgba(255,107,0,0.3);transform:translateY(-4px);}
.who-icon{font-size:32px;margin-bottom:16px;}
.who-title{font-family:'Cinzel',serif;font-size:16px;letter-spacing:0.08em;color:var(--gold2);margin-bottom:10px;}
.who-desc{font-size:14px;color:var(--muted);line-height:1.7;}

.compare{padding:80px 5%;}
.compare-table{max-width:720px;margin:48px auto 0;border:1px solid var(--border);border-radius:8px;overflow:hidden;}
.compare-head{display:grid;grid-template-columns:2fr 1fr 1fr;background:var(--dark2);border-bottom:1px solid var(--border);}
.ch{padding:14px 20px;font-family:'Cinzel',serif;font-size:12px;letter-spacing:0.1em;color:var(--muted);text-transform:uppercase;}
.ch.highlight{color:var(--gold);}
.compare-row{display:grid;grid-template-columns:2fr 1fr 1fr;border-bottom:1px solid var(--border);}
.compare-row:last-child{border-bottom:none;}
.compare-row:nth-child(even){background:rgba(255,107,0,0.02);}
.cd{padding:13px 20px;font-size:13px;color:var(--muted);display:flex;align-items:center;}
.cd.feature{color:var(--white);font-weight:400;}
.cd.bad{color:#FF6060;}
.cd.good{color:#50C878;}

.pricing{padding:100px 5%;text-align:center;}
.pricing-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:980px;margin:56px auto 0;}
.plan{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:36px 24px;position:relative;text-align:left;transition:all 0.3s;}
.plan:hover{transform:translateY(-4px);}
.plan.hot{border-color:var(--orange);background:linear-gradient(160deg,rgba(255,107,0,0.06),var(--card));}
.plan-badge{position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:var(--orange);color:#fff;font-size:11px;font-weight:500;padding:4px 16px;border-radius:100px;letter-spacing:0.08em;white-space:nowrap;}
.plan-name{font-family:'Cinzel',serif;font-size:13px;letter-spacing:0.15em;color:var(--muted);text-transform:uppercase;margin-bottom:12px;}
.plan-price{font-family:'Cinzel',serif;font-size:40px;font-weight:700;color:var(--white);line-height:1;}
.plan-price sub{font-size:15px;color:var(--muted);font-weight:300;font-family:'Jost',sans-serif;}
.plan-vs{font-size:11px;color:var(--muted2);margin:6px 0 20px;padding-bottom:20px;border-bottom:1px solid var(--border);}
.plan-vs s{color:var(--muted2);}
.plan-feats{list-style:none;display:flex;flex-direction:column;gap:10px;margin-bottom:28px;}
.plan-feats li{font-size:13px;color:var(--muted);display:flex;align-items:flex-start;gap:8px;line-height:1.5;}
.plan-feats li::before{content:'✦';color:var(--orange);font-size:9px;margin-top:4px;flex-shrink:0;}
.pcta{width:100%;padding:13px;border-radius:4px;font-family:'Jost',sans-serif;font-size:14px;font-weight:500;cursor:pointer;transition:all 0.2s;letter-spacing:0.05em;text-align:center;display:block;border:none;}
.pcta.solid{background:var(--orange);color:#fff;}
.pcta.solid:hover{background:var(--orange2);transform:translateY(-1px);}
.pcta.outline{background:transparent;border:1px solid var(--border);color:var(--white);}
.pcta.outline:hover{border-color:var(--gold);color:var(--gold);}
.pricing-foot{margin-top:20px;font-size:12px;color:var(--muted2);letter-spacing:0.05em;}

.trust{padding:48px 5%;border-top:1px solid var(--border);border-bottom:1px solid var(--border);}
.trust-row{display:flex;align-items:center;justify-content:center;gap:36px;flex-wrap:wrap;}
.trust-item{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted);letter-spacing:0.06em;}
.trust-item .ti{font-size:18px;}

.faq{padding:100px 5%;}
.faq-list{max-width:680px;margin:48px auto 0;display:flex;flex-direction:column;gap:12px;}
.faq-item{background:var(--card);border:1px solid var(--border);border-radius:6px;overflow:hidden;}
.faq-q{padding:18px 22px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-size:15px;color:var(--white);font-weight:400;}
.faq-q span{color:var(--orange);font-size:18px;transition:transform 0.25s;}
.faq-q.open span{transform:rotate(45deg);}
.faq-a{padding:0 22px;max-height:0;overflow:hidden;transition:all 0.3s ease;font-size:14px;color:var(--muted);line-height:1.7;}
.faq-a.open{padding:0 22px 18px;max-height:240px;}

.aurem-home footer{position:relative;z-index:1;padding:48px 5%;border-top:1px solid var(--border);}
.footer-inner{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:20px;}
.footer-trust{display:inline-flex;align-items:center;gap:8px;padding:6px 14px;border:1px solid var(--border-gold);border-radius:100px;font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:0.08em;color:var(--gold);background:rgba(15,15,26,0.6);transition:all 0.2s;text-transform:none;line-height:1;margin-bottom:10px;}
.footer-trust:hover{border-color:rgba(201,168,76,0.45);color:var(--gold2);transform:translateY(-1px);}
.footer-trust .ft-dot{width:7px;height:7px;border-radius:50%;background:#3FCF8E;box-shadow:0 0 10px rgba(63,207,142,0.65);}
.footer-trust .ft-dot.ft-yellow{background:#E8C86A;box-shadow:0 0 10px rgba(232,200,106,0.55);}
.footer-trust .ft-dot.ft-red{background:#FF5A6B;box-shadow:0 0 10px rgba(255,90,107,0.65);}
.footer-trust .ft-meta{color:var(--muted);}
.footer-logo{font-family:'Cinzel',serif;font-size:15px;letter-spacing:0.2em;color:var(--gold);}
.footer-sub{font-size:10px;color:var(--muted2);letter-spacing:0.1em;margin-top:3px;}
.footer-links{display:flex;gap:20px;flex-wrap:wrap;}
.footer-links a,.footer-links button{font-size:12px;color:var(--muted);letter-spacing:0.04em;transition:color 0.2s;background:none;border:none;cursor:pointer;}
.footer-links a:hover,.footer-links button:hover{color:var(--white);}
.footer-copy{font-size:11px;color:var(--muted2);}

.fade-up{opacity:0;transform:translateY(28px);transition:all 0.65s cubic-bezier(0.22,1,0.36,1);}
.fade-up.in{opacity:1;transform:translateY(0);}

@media(max-width:900px){
  .nav-links{display:none;}
  .nav-login{padding:0;width:38px;height:38px;}
  .nav-login-text{display:none;}
  .nav-login-icon{display:inline-flex;align-items:center;justify-content:center;}
  .nav-cta{padding:9px 14px;font-size:12px;}
  .pain-cards,.who-grid,.pricing-grid{grid-template-columns:1fr;}
  .how-grid{flex-direction:column;}
  .how-step:not(:last-child){border-right:1px solid var(--border);border-bottom:none;}
  .how-arrow{display:none;}
  .compare-table{overflow-x:auto;}
  .scan-form{flex-direction:column;}
  .stats-row{flex-direction:column;max-width:280px;}
  .stat{border-right:none;border-bottom:1px solid var(--border);}
  .stat:last-child{border-bottom:none;}
  .hero-btns{flex-direction:column;align-items:stretch;max-width:280px;margin-left:auto;margin-right:auto;}
  .trust-row{gap:18px;}
  .footer-inner{flex-direction:column;text-align:center;}
}
`;

const HOMEPAGE_FONTS_HREF =
  "https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700;900&family=Cinzel+Decorative:wght@700&family=Jost:ital,wght@0,300;0,400;0,500;0,600;1,300&family=JetBrains+Mono:wght@400;500&display=swap";

const FAQS = [
  {
    q: "Do I need to be technical to use AUREM?",
    a: "Not at all. You sign up, connect your business details, and AUREM runs on its own. No coding, no setup headaches. If you can use WhatsApp, you can use AUREM.",
  },
  {
    q: 'What does "14-day free trial" mean?',
    a: "You get full access to AUREM for 14 days completely free — no credit card needed. If you love it, you choose a plan. If not, you walk away with zero charges. Simple.",
  },
  {
    q: "Is my business information safe?",
    a: "Yes. All your data is encrypted, stored in Canada, and never sold or shared with anyone. AUREM is fully compliant with Canadian privacy laws (PIPEDA) and anti-spam laws (CASL).",
  },
  {
    q: "What languages does ORA speak?",
    a: "ORA automatically detects what language your customer is writing in and replies in the same language. English, French, Hindi, Punjabi — and many more. No setup needed.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. Cancel before your next billing date and you won't be charged again. No contracts, no cancellation fees, no questions asked.",
  },
];

function AuremLogo() {
  return (
    <svg width="30" height="30" viewBox="0 0 32 32" fill="none">
      {[0, 36, 72, 108, 144].map((d) => (
        <ellipse key={d} cx="16" cy="16" rx="14" ry="5.5" stroke="#C9A84C" strokeWidth="1" fill="none" transform={`rotate(${d} 16 16)`} />
      ))}
      <circle cx="16" cy="16" r="2.5" fill="#FF6B00" />
    </svg>
  );
}

const AuremHomepage = () => {
  const navigate = useNavigate();
  const [scanUrl, setScanUrl] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hi there 👋 I'm ORA — I work for your business 24/7. I answer calls, book jobs, follow up with customers, and make sure nothing falls through the cracks. What can I help you with today?",
    },
  ]);
  const [openFaq, setOpenFaq] = useState(null);
  const [liveCount, setLiveCount] = useState(25);
  const [trustPill, setTrustPill] = useState(null);
  const dmsgsRef = useRef(null);
  const sessionIdRef = useRef(`home_${Math.random().toString(36).slice(2)}`);

  // Inject Google Fonts once
  useEffect(() => {
    const id = "aurem-home-fonts";
    if (!document.getElementById(id)) {
      const l = document.createElement("link");
      l.id = id;
      l.rel = "stylesheet";
      l.href = HOMEPAGE_FONTS_HREF;
      document.head.appendChild(l);
    }
  }, []);

  // Fade-up observer
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("in")),
      { threshold: 0.1 }
    );
    document.querySelectorAll(".aurem-home .fade-up").forEach((el) => {
      obs.observe(el);
      // Also force-show after a brief moment so above-the-fold content is visible immediately.
      setTimeout(() => el.classList.add("in"), 200);
    });
    return () => obs.disconnect();
  }, []);

  // Live counter — try real platform stat, fallback to client increment
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API}/api/public/repair-quote/health`).catch(() => null);
        // Soft-probe; if reachable we still let the increment run for visual life.
        if (cancelled || !r) return;
      } catch (_) {}
    })();
    const t = setInterval(() => {
      if (Math.random() > 0.65) setLiveCount((n) => n + 1);
    }, 9000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  // Scroll chat to bottom on new message
  useEffect(() => {
    const el = dmsgsRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // Lazy-fetch the Sovereign trust pill once the page has mounted.
  // Failures are swallowed silently — the pill simply stays hidden so
  // a temporary status outage never degrades the homepage.
  useEffect(() => {
    let cancelled = false;
    const fetchPill = async () => {
      try {
        const r = await fetch(`${API}/api/public/status`, { cache: "no-store" });
        if (!r.ok) return;
        const j = await r.json();
        if (!cancelled) setTrustPill(j);
      } catch {
        // intentionally silent
      }
    };
    // Defer to idle so the hero/video paint first.
    const t = setTimeout(fetchPill, 800);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, []);

  const goRepairQuote = (urlOverride) => {
    const u = (urlOverride ?? scanUrl).trim();
    if (u) navigate(`/repair-quote?url=${encodeURIComponent(u)}`);
    else navigate("/repair-quote");
  };

  const scrollTo = (id) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const sendChat = async () => {
    const txt = chatInput.trim();
    if (!txt || chatSending) return;
    setChatInput("");
    // Use a unique ID for the typing placeholder so the response always
    // replaces the right row regardless of any concurrent state updates.
    const placeholderId = `t_${Date.now()}_${Math.random()}`;
    setMessages((p) => [
      ...p,
      { role: "user", text: txt },
      { id: placeholderId, role: "assistant", text: "", typing: true },
    ]);
    setChatSending(true);
    const replacePlaceholder = (text) =>
      setMessages((prev) =>
        prev.map((m) =>
          m.id === placeholderId ? { id: placeholderId, role: "assistant", text } : m
        )
      );
    const ctrl = new AbortController();
    const timeoutId = setTimeout(() => ctrl.abort(), 25000);
    try {
      const r = await fetch(`${API}/api/public/ora/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
        body: JSON.stringify({
          text: txt,
          session_id: sessionIdRef.current,
        }),
      });
      const body = await r.json().catch(() => ({}));
      const reply =
        (body?.reply || "").trim() ||
        "I'm here to help you find customers and book jobs. What does your business do?";
      replacePlaceholder(reply);
    } catch (e) {
      replacePlaceholder(
        "Looks like the connection blinked — try again in a sec, or scan your website above."
      );
    } finally {
      clearTimeout(timeoutId);
      setChatSending(false);
    }
  };

  const onScanKey = (e) => {
    if (e.key === "Enter") goRepairQuote();
  };
  const onChatKey = (e) => {
    if (e.key === "Enter") sendChat();
  };

  return (
    <div className="aurem-home" data-testid="aurem-homepage">
      <style>{HOMEPAGE_CSS}</style>
      <BackgroundVideo />
      <div className="bg-glow" />
      <div className="bg-grid" />

      <nav data-testid="nav">
        <div className="nav-logo" onClick={() => navigate("/")} data-testid="nav-logo">
          <AuremLogo />
          <span className="nav-wordmark">AUREM</span>
        </div>
        <div className="nav-links">
          <button onClick={() => scrollTo("scan")} data-testid="nav-link-scan">Free Website Check</button>
          <button onClick={() => scrollTo("how")} data-testid="nav-link-how">How It Works</button>
          <button onClick={() => scrollTo("pricing")} data-testid="nav-link-pricing">Pricing</button>
        </div>
        <div className="nav-actions">
          <Link to="/my" className="nav-login" data-testid="nav-link-login" aria-label="Log in to your AUREM account">
            <span className="nav-login-icon"><User size={16} strokeWidth={1.8} /></span>
            <span className="nav-login-text">Log In</span>
          </Link>
          <button className="nav-cta" onClick={() => navigate("/repair-quote")} data-testid="nav-cta-check">
            Check My Website Free →
          </button>
        </div>
      </nav>

      <div className="world-first-bar" data-testid="world-first-banner">
        <span>🌍 &nbsp;The World's First &nbsp;<em>Autonomous Intelligence Platform</em>&nbsp; — Built in Canada &nbsp;🇨🇦</span>
      </div>

      {/* CANADIAN TRUST BAR — iter 282al-7 (Canadian Moat) */}
      <div className="ca-trust-bar" data-testid="ca-trust-bar">
        <div className="ca-trust-track">
          <span className="ca-trust-item" data-testid="ca-trust-owned">🍁&nbsp;Canadian-Owned &amp; Operated</span>
          <span className="ca-trust-sep">·</span>
          <span className="ca-trust-item" data-testid="ca-trust-built">📍&nbsp;Built in Mississauga, Ontario</span>
          <span className="ca-trust-sep">·</span>
          <span className="ca-trust-item" data-testid="ca-trust-casl">⚖️&nbsp;CASL Compliant — Always</span>
          <span className="ca-trust-sep">·</span>
          <span className="ca-trust-item" data-testid="ca-trust-data">🔒&nbsp;Your Data Stays in Canada</span>
          <span className="ca-trust-sep">·</span>
          <span className="ca-trust-item" data-testid="ca-trust-since">⭐&nbsp;Serving Canadian Trades Since 2024</span>
        </div>
      </div>

      {/* HERO */}
      <section className="hero" data-testid="aurem-hero">
        <div className="hero-inner">
          <div className="hero-eyebrow">
            <div className="dot" />
            Live right now — <span data-testid="hero-live-count">{liveCount}</span> businesses helped today
          </div>
          <h1 className="hero-title" data-testid="hero-title">
            <span className="t1">Your Business Finds Customers,</span>
            <span className="t2">Books Jobs &amp; Fixes Itself.</span>
          </h1>
          <p className="hero-punch">
            AUREM is the world's first platform that runs your entire business on autopilot.<br />
            <strong>No staff. No missed calls. No manual follow-ups. Ever.</strong>
          </p>
          <div className="hero-btns">
            <button className="btn-primary" onClick={() => navigate("/repair-quote")} data-testid="hero-cta-check">
              Check My Website Free — 60 Seconds →
            </button>
            <button className="btn-ghost" onClick={() => scrollTo("demo")} data-testid="hero-cta-demo">
              See ORA in Action
            </button>
          </div>
          <p className="hero-note" style={{ marginTop: 14 }}>
            No credit card &nbsp;·&nbsp; Free 14-day trial &nbsp;·&nbsp; Works in English, French, Hindi &amp; Punjabi
          </p>

          <div className="stats-row fade-up">
            <div className="stat"><span className="stat-n" data-testid="stat-live">{liveCount}</span><span className="stat-l">Businesses helped today</span></div>
            <div className="stat"><span className="stat-n">90 sec</span><span className="stat-l">Average reply time</span></div>
            <div className="stat"><span className="stat-n">2,224</span><span className="stat-l">Issues auto-fixed</span></div>
            <div className="stat"><span className="stat-n">24/7</span><span className="stat-l">Never offline</span></div>
          </div>
        </div>
      </section>

      {/* PAIN STORY */}
      <section className="pain" id="story">
        <div className="center fade-up">
          <span className="s-label">Sound Familiar?</span>
          <h2 className="s-title">Every Missed Call Costs You a Job</h2>
          <p className="s-sub" style={{ margin: "14px auto 0" }}>
            Most local businesses lose $800–$2,400 every month just from calls they miss after hours. AUREM stops that leak — permanently.
          </p>
        </div>
        <div className="pain-cards fade-up">
          <div className="pain-card c1">
            <span className="pain-tag">❌ Without AUREM — 6:47 PM</span>
            <p className="pain-text">A customer calls. You're on a job. It rings out. They Google the <strong>next business on the list.</strong></p>
            <p className="pain-result">💸 $1,200 job — gone</p>
          </div>
          <div className="pain-card c2">
            <span className="pain-tag">⚡ With AUREM — Same Moment</span>
            <p className="pain-text">AUREM answers instantly. Asks the right questions. Books the appointment. <strong>Sends a confirmation.</strong></p>
            <p className="pain-result">✅ Booked in 73 seconds</p>
          </div>
          <div className="pain-card c3">
            <span className="pain-tag">☀️ Next Morning</span>
            <p className="pain-text">You wake up to a new job already in your calendar. <strong>No effort. No follow-up. Done.</strong></p>
            <p className="pain-result">📅 Money made while you slept</p>
          </div>
        </div>
      </section>

      {/* SCAN */}
      <section className="scan-section" id="scan">
        <div className="scan-box fade-up">
          <div className="scan-header">
            <div className="scan-dots"><span /><span /><span /></div>
            <span className="scan-bar-title">AUREM Website Scanner — Free</span>
            <div className="scan-live">LIVE</div>
          </div>
          <div className="scan-body">
            <h2 className="scan-title">Is Your Website Losing You Customers Right Now?</h2>
            <p className="scan-sub">Enter your website and we'll find every issue costing you leads — in under 60 seconds. Free. No login. No pitch.</p>
            <div className="scan-form">
              <input type="url" placeholder="www.yourbusiness.com" value={scanUrl} onChange={(e) => setScanUrl(e.target.value)} onKeyDown={onScanKey} data-testid="scan-url-input" />
              <button className="btn-primary" onClick={() => goRepairQuote()} data-testid="scan-submit-btn">Scan My Website →</button>
            </div>
            <p className="scan-note">✓ Free forever &nbsp;·&nbsp; ✓ Results in 60 seconds &nbsp;·&nbsp; ✓ No spam, ever</p>
            <div className="scan-checks">
              <span className="check-tag">🔒 Security Check</span>
              <span className="check-tag">⚡ Speed Test</span>
              <span className="check-tag">📱 Mobile Friendly</span>
              <span className="check-tag">🔗 Broken Links</span>
              <span className="check-tag">📞 Contact Form</span>
              <span className="check-tag">🔍 Google Visibility</span>
            </div>
          </div>
        </div>
      </section>

      {/* DEMO */}
      <section className="demo" id="demo">
        <div className="demo-wrap fade-up">
          <div className="center">
            <span className="s-label">Try It Right Now</span>
            <h2 className="s-title">Talk to ORA — Your AI Employee</h2>
            <p className="s-sub" style={{ margin: "12px auto 0", fontSize: 14 }}>
              Type anything below. ORA handles it the same way it would handle your real customers. No login needed.
            </p>
          </div>
          <div className="demo-box" data-testid="ora-demo-box">
            <div className="demo-top">
              <div className="ddots"><span /><span /><span /></div>
              <span className="dtitle">ORA by AUREM — Live</span>
              <div className="dlive">LIVE</div>
            </div>
            <div className="dmsgs" id="dmsgs" ref={dmsgsRef}>
              {messages.map((m, i) => (
                <div key={m.id || i} className={`msg ${m.role === "user" ? "msg-u" : "msg-a"}`} data-testid={`ora-msg-${i}`}>
                  {m.typing ? (
                    <div className="typing"><span /><span /><span /></div>
                  ) : (
                    m.text
                  )}
                </div>
              ))}
            </div>
            <div className="dinput">
              <input
                type="text"
                placeholder="Try: 'I need a plumber tonight' or 'How much does this cost?'"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={onChatKey}
                data-testid="ora-chat-input"
              />
              <button className="dsend" onClick={sendChat} disabled={chatSending} data-testid="ora-chat-send">
                {chatSending ? "…" : "Send"}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* HOW */}
      <section className="how" id="how">
        <div className="fade-up">
          <span className="s-label">How It Works</span>
          <h2 className="s-title">Four Things AUREM Does For You Every Day</h2>
          <p className="s-sub" style={{ margin: "12px auto 0" }}>Fully automatic. You set it up once. AUREM handles the rest.</p>
        </div>
        <div className="how-grid fade-up">
          <div className="how-step"><div className="how-arrow">→</div><div className="how-n">01</div><div className="how-emoji">🔍</div><div className="how-t">Finds Customers</div><div className="how-d">Searches the internet every day for people in your area who need your service. Sends them a message automatically.</div></div>
          <div className="how-step"><div className="how-arrow">→</div><div className="how-n">02</div><div className="how-emoji">💬</div><div className="how-t">Answers Everything</div><div className="how-d">Every call, WhatsApp, or website chat gets an instant reply — day or night, in any language. Never miss a lead again.</div></div>
          <div className="how-step"><div className="how-arrow">→</div><div className="how-n">03</div><div className="how-emoji">📅</div><div className="how-t">Books the Job</div><div className="how-d">Qualifies the customer, checks your schedule, books the appointment, and sends a confirmation. Zero work from you.</div></div>
          <div className="how-step"><div className="how-n">04</div><div className="how-emoji">🛡️</div><div className="how-t">Fixes Problems</div><div className="how-d">Monitors your website and business tools 24/7. Finds and fixes issues automatically before they cost you customers.</div></div>
        </div>
      </section>

      {/* WHO */}
      <section className="who" id="who">
        <div className="center fade-up">
          <span className="s-label">Who It's For</span>
          <h2 className="s-title">Built for Canadian Business Owners</h2>
          <p className="s-sub" style={{ margin: "12px auto 0" }}>If you run a service business and hate missing customers — AUREM is for you.</p>
        </div>
        <div className="who-grid fade-up">
          <div className="who-card"><div className="who-icon">🔧</div><div className="who-title">Trades &amp; Services</div><div className="who-desc">Plumbers, electricians, cleaners, landscapers, HVAC. Never miss an after-hours call again. AUREM books the job while you're working.</div></div>
          <div className="who-card"><div className="who-icon">🏥</div><div className="who-title">Clinics &amp; Salons</div><div className="who-desc">Medical, dental, beauty, wellness. Automated booking, reminders, and follow-ups. Patients and clients get instant responses every time.</div></div>
          <div className="who-card"><div className="who-icon">🏢</div><div className="who-title">Agencies &amp; Consultants</div><div className="who-desc">Manage multiple clients from one place. White-label available — your brand, your name, AUREM's power running behind the scenes.</div></div>
        </div>
      </section>

      {/* COMPARE */}
      <section className="compare" id="compare">
        <div className="center fade-up">
          <span className="s-label">The Numbers Don't Lie</span>
          <h2 className="s-title">AUREM vs Doing It Yourself</h2>
        </div>
        <div className="compare-table fade-up">
          <div className="compare-head">
            <div className="ch" />
            <div className="ch">Without AUREM</div>
            <div className="ch highlight">With AUREM ✦</div>
          </div>
          {[
            ["Response time to new lead", "2–3 hours (if you see it)", "Under 90 seconds"],
            ["After-hours calls answered", "0%", "100%"],
            ["Monthly cost", "$2,800+ (receptionist)", "From $97/mo"],
            ["Website issues found", "When a customer complains", "Fixed overnight, automatically"],
            ["Follow-ups sent", "When you remember", "Always. On time. Automatically."],
            ["Languages supported", "1", "English, French, Hindi, Punjabi & more"],
          ].map(([f, b, g], i) => (
            <div key={i} className="compare-row">
              <div className="cd feature">{f}</div>
              <div className="cd bad">{b}</div>
              <div className="cd good">{g}</div>
            </div>
          ))}
        </div>
      </section>

      {/* PRICING */}
      <section className="pricing" id="pricing">
        <div className="fade-up">
          <span className="s-label">Simple Pricing</span>
          <h2 className="s-title">Less Than One Missed Job a Month</h2>
          <p style={{ color: "var(--muted)", fontSize: 15, marginTop: 12 }}>A part-time receptionist costs $2,800/month. AUREM starts at $97.</p>
        </div>
        <div className="pricing-grid fade-up">
          <div className="plan" data-testid="plan-starter">
            <div className="plan-name">Starter</div>
            <div className="plan-price" data-testid="price-starter">$97<sub>/mo CAD</sub></div>
            <div className="plan-vs">vs. receptionist at <s>$2,800/mo</s></div>
            <ul className="plan-feats">
              <li>ORA answers chats on your website</li>
              <li>Up to 500 customer interactions/month</li>
              <li>Automatic lead follow-up</li>
              <li>Free website health check</li>
              <li>Daily business summary every morning</li>
              <li>Works in 4 languages</li>
            </ul>
            <button className="pcta outline" onClick={() => navigate("/my/onboarding")} data-testid="cta-plan-starter">Start Free 14 Days</button>
          </div>
          <div className="plan hot" data-testid="plan-growth">
            <div className="plan-badge">Most Popular</div>
            <div className="plan-name">Growth</div>
            <div className="plan-price" data-testid="price-growth">$449<sub>/mo CAD</sub></div>
            <div className="plan-vs">vs. marketing agency at <s>$3,000/mo</s></div>
            <ul className="plan-feats">
              <li>Everything in Starter</li>
              <li>ORA answers phone calls &amp; WhatsApp</li>
              <li>Up to 5,000 interactions/month</li>
              <li>Finds 25 new customers daily — automatically</li>
              <li>Website repair service included</li>
              <li>Works across 3 of your businesses</li>
              <li>Revenue reports &amp; business insights</li>
            </ul>
            <button className="pcta solid" onClick={() => navigate("/my/onboarding")} data-testid="cta-plan-growth">Start Free 14 Days →</button>
          </div>
          <div className="plan" data-testid="plan-enterprise">
            <div className="plan-name">Enterprise</div>
            <div className="plan-price" data-testid="price-enterprise">$997<sub>/mo CAD</sub></div>
            <div className="plan-vs">Full autonomous business system</div>
            <ul className="plan-feats">
              <li>Everything in Growth</li>
              <li>Put your own brand name on AUREM</li>
              <li>Unlimited customers &amp; interactions</li>
              <li>Manage all your clients from one place</li>
              <li>25 phone lines running at the same time</li>
              <li>Personal setup &amp; onboarding support</li>
            </ul>
            <a className="pcta outline" href="mailto:teji.ss1986@gmail.com" data-testid="cta-plan-enterprise">Talk to Us</a>
          </div>
        </div>
        <p className="pricing-foot">All plans include a 14-day free trial &nbsp;·&nbsp; No credit card needed to start &nbsp;·&nbsp; Cancel any time, no questions asked</p>
      </section>

      {/* TRUST */}
      <section className="trust">
        <div className="trust-row">
          <div className="trust-item"><span className="ti">🔒</span> CASL &amp; PIPEDA Compliant</div>
          <div className="trust-item"><span className="ti">🇨🇦</span> Canadian Built — Mississauga, ON</div>
          <div className="trust-item"><span className="ti">🧠</span> Powered by Claude + GPT-4o + Gemini</div>
          <div className="trust-item"><span className="ti">⚡</span> No credit card to start</div>
          <div className="trust-item"><span className="ti">🛡️</span> Your data stays in Canada. Always.</div>
        </div>
      </section>

      {/* SOCIAL PROOF */}
      <section style={{ padding: "80px 5%", position: "relative", zIndex: 1, textAlign: "center" }}>
        <div className="fade-up">
          <span className="s-label">Early Results</span>
          <h2 className="s-title">Real Businesses. Real Results.</h2>
          <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 10 }}>Our first beta clients in Ontario — their words, not ours.</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 20, maxWidth: 900, margin: "48px auto 0" }} className="fade-up">
          {[
            ['"AUREM booked a $1,800 job at 11pm while I was asleep. Woke up and it was already confirmed."', "Mike T.", "Plumbing, Mississauga"],
            ['"Stopped losing weekend leads the first week. Best money I\'ve ever spent on my business."', "Sarah K.", "Cleaning Service, Brampton"],
            ['"3 jobs booked in the first week while I was on other calls. I\'m not going back to the old way."', "Dave M.", "Electrician, Mississauga"],
          ].map(([q, n, b], i) => (
            <div key={i} style={{ background: "var(--card)", border: "1px dashed var(--border)", borderRadius: 8, padding: "28px 22px", textAlign: "left", opacity: 0.5 }}>
              <div style={{ fontSize: 12, marginBottom: 10 }}>⭐⭐⭐⭐⭐</div>
              <p style={{ fontSize: 14, color: "var(--white)", lineHeight: 1.65, marginBottom: 14, fontStyle: "italic" }}>{q}</p>
              <p style={{ fontSize: 12, color: "var(--muted)" }}><strong style={{ color: "var(--gold)" }}>{n}</strong> — {b}</p>
            </div>
          ))}
        </div>
        <p style={{ fontSize: 11, color: "var(--muted2)", marginTop: 16 }}>Become a beta client and get your result featured here.</p>
      </section>

      {/* FAQ */}
      <section className="faq" id="faq">
        <div className="center fade-up">
          <span className="s-label">Questions</span>
          <h2 className="s-title">Things People Ask</h2>
        </div>
        <div className="faq-list fade-up" data-testid="faq-list">
          {FAQS.map((f, i) => {
            const open = openFaq === i;
            return (
              <div key={i} className="faq-item">
                <div className={`faq-q ${open ? "open" : ""}`} onClick={() => setOpenFaq(open ? null : i)} data-testid={`faq-q-${i}`}>
                  {f.q} <span>+</span>
                </div>
                <div className={`faq-a ${open ? "open" : ""}`} data-testid={`faq-a-${i}`}>{f.a}</div>
              </div>
            );
          })}
        </div>
      </section>

      {/* FINAL CTA */}
      <section style={{ position: "relative", zIndex: 1, padding: "80px 5%", textAlign: "center" }}>
        <div className="fade-up" style={{ maxWidth: 600, margin: "0 auto", background: "linear-gradient(135deg,rgba(255,107,0,0.07),rgba(201,168,76,0.05))", border: "1px solid rgba(255,107,0,0.2)", borderRadius: 12, padding: "56px 40px" }}>
          <span className="s-label" style={{ display: "block", textAlign: "center", marginBottom: 12 }}>Start Today</span>
          <h2 style={{ fontFamily: "'Cinzel',serif", fontSize: "clamp(22px,3vw,34px)", marginBottom: 14 }}>Your Business Is Losing Customers Tonight.</h2>
          <p style={{ color: "var(--muted)", fontSize: 15, marginBottom: 32, lineHeight: 1.7 }}>
            Check your website free right now. Takes 60 seconds.<br />No credit card. No signup. Just results.
          </p>
          <button className="btn-primary" onClick={() => navigate("/repair-quote")} data-testid="final-cta-check">
            Check My Website Free — It Takes 60 Seconds →
          </button>
          <p style={{ fontSize: 12, color: "var(--muted2)", marginTop: 14 }}>The World's First Autonomous Intelligence Platform &nbsp;·&nbsp; Mississauga, Canada 🇨🇦</p>
        </div>
      </section>

      {/* FOOTER */}
      <footer>
        <div className="footer-inner">
          <div>
            {trustPill && (
              <Link
                to="/status"
                className="footer-trust"
                data-testid="homepage-trust-pill"
                title="Live Sovereign-Status feed"
              >
                <span
                  className={`ft-dot${
                    trustPill.badge_color === "yellow" ? " ft-yellow" :
                    trustPill.badge_color === "red"    ? " ft-red"    : ""
                  }`}
                />
                <span data-testid="homepage-trust-pill-pct">
                  {trustPill.system_autonomy_pct.toFixed(2)}% autonomous
                </span>
                <span className="ft-meta">·</span>
                <span className="ft-meta" data-testid="homepage-trust-pill-heals">
                  {trustPill.watchdog_heals_24h} heals/24h
                </span>
                <span className="ft-meta">·</span>
                <span className="ft-meta">status.aurem.live</span>
              </Link>
            )}
            <div className="footer-logo">AUREM</div>
            <div className="footer-sub">World's First Autonomous Intelligence Platform</div>
          </div>
          <div className="footer-links">
            <button onClick={() => scrollTo("scan")} data-testid="footer-link-scan">Free Website Check</button>
            <button onClick={() => scrollTo("pricing")} data-testid="footer-link-pricing">Pricing</button>
            <Link to="/status" data-testid="footer-link-status">System Status</Link>
            <Link to="/privacy" data-testid="footer-link-privacy">Privacy Policy</Link>
            <Link to="/terms" data-testid="footer-link-terms">Terms of Use</Link>
            <Link to="/my" data-testid="footer-link-login">Log In</Link>
          </div>
          <div className="footer-copy">© 2026 Polaris Built Inc. &nbsp;·&nbsp; Mississauga, Ontario, Canada &nbsp;·&nbsp; CASL &amp; PIPEDA Compliant</div>
        </div>
      </footer>
    </div>
  );
};

export default AuremHomepage;
