/**
 * AuremMascot — animated SVG robot mascot for promo popup.
 *
 * Features:
 *   • Eyes blink every 3.2s (both eyelids close in sync, ~150ms blink)
 *   • Subtle idle float (body gently bobs up/down)
 *   • Antenna gold dot pulses softly
 *   • Hand/arm holding mini-screen with "7 DAYS FREE" (waves)
 *   • Copper/gold AUREM palette
 *   • Pure inline SVG — no external assets
 *   • Respects prefers-reduced-motion
 */
import React from 'react';

const AuremMascot = ({ size = 140 }) => {
  return (
    <div
      style={{ width: size, height: size, display: 'inline-block' }}
      aria-hidden="true"
    >
      <style>{`
        @keyframes aurem-mascot-float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-4px); }
        }
        @keyframes aurem-mascot-blink {
          0%, 92%, 100% { transform: scaleY(1); }
          94%, 98% { transform: scaleY(0.08); }
        }
        @keyframes aurem-mascot-antenna-pulse {
          0%, 100% { opacity: 0.85; filter: drop-shadow(0 0 2px #d4a557); }
          50% { opacity: 1; filter: drop-shadow(0 0 8px #d4a557); }
        }
        @keyframes aurem-mascot-wave {
          0%, 60%, 100% { transform: rotate(-4deg); }
          30% { transform: rotate(6deg); }
        }
        .aurem-mascot-body { animation: aurem-mascot-float 3.4s ease-in-out infinite; transform-origin: center; }
        .aurem-eye-lid { animation: aurem-mascot-blink 3.2s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
        .aurem-antenna-dot { animation: aurem-mascot-antenna-pulse 2.2s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
        .aurem-arm { animation: aurem-mascot-wave 2.8s ease-in-out infinite; transform-origin: 60px 100px; }
        @media (prefers-reduced-motion: reduce) {
          .aurem-mascot-body, .aurem-eye-lid, .aurem-antenna-dot, .aurem-arm {
            animation: none !important;
          }
        }
      `}</style>
      <svg
        viewBox="0 0 160 160"
        xmlns="http://www.w3.org/2000/svg"
        style={{ width: '100%', height: '100%', overflow: 'visible' }}
      >
        <defs>
          {/* Body gradient — obsidian with warm rim light */}
          <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#2a2018" />
            <stop offset="60%" stopColor="#1a1108" />
            <stop offset="100%" stopColor="#3a2a14" />
          </linearGradient>
          <linearGradient id="bellyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#d4a557" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#b87333" stopOpacity="0.08" />
          </linearGradient>
          <linearGradient id="screenGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#d4a557" />
            <stop offset="100%" stopColor="#b87333" />
          </linearGradient>
          <radialGradient id="eyeGrad" cx="50%" cy="40%" r="60%">
            <stop offset="0%" stopColor="#ffe6a8" />
            <stop offset="100%" stopColor="#d4a557" />
          </radialGradient>
          {/* Soft underneath shadow */}
          <radialGradient id="shadowGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#000" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#000" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Shadow under the character */}
        <ellipse cx="80" cy="148" rx="38" ry="5" fill="url(#shadowGrad)" />

        {/* WHOLE BODY FLOAT GROUP */}
        <g className="aurem-mascot-body">

          {/* Antenna */}
          <line x1="80" y1="35" x2="80" y2="18" stroke="#7a5a2e" strokeWidth="2" strokeLinecap="round" />
          <circle className="aurem-antenna-dot" cx="80" cy="15" r="4" fill="#d4a557" />

          {/* Head (rounded square) */}
          <rect x="38" y="30" width="84" height="70" rx="22" ry="22"
                fill="url(#bodyGrad)"
                stroke="#d4a557" strokeWidth="1.2" strokeOpacity="0.45" />

          {/* Face-plate (slightly recessed belly panel on head) */}
          <rect x="48" y="45" width="64" height="44" rx="14" ry="14"
                fill="url(#bellyGrad)"
                stroke="#d4a557" strokeWidth="0.8" strokeOpacity="0.3" />

          {/* Eyes — outer glow + eyeball + blinking lid */}
          {/* Left eye */}
          <g>
            <circle cx="64" cy="65" r="8" fill="url(#eyeGrad)"
                    filter="drop-shadow(0 0 3px #d4a55788)" />
            <circle cx="66" cy="63" r="2.2" fill="#fff9ea" opacity="0.9" />
            {/* Blink lid */}
            <rect className="aurem-eye-lid" x="54" y="57" width="20" height="16" rx="8"
                  fill="#1a1108" />
          </g>
          {/* Right eye */}
          <g>
            <circle cx="96" cy="65" r="8" fill="url(#eyeGrad)"
                    filter="drop-shadow(0 0 3px #d4a55788)" />
            <circle cx="98" cy="63" r="2.2" fill="#fff9ea" opacity="0.9" />
            <rect className="aurem-eye-lid" x="86" y="57" width="20" height="16" rx="8"
                  fill="#1a1108" />
          </g>

          {/* Mouth — small friendly smile */}
          <path d="M 68 82 Q 80 88 92 82" stroke="#d4a557" strokeWidth="2"
                strokeLinecap="round" fill="none" opacity="0.8" />

          {/* Body/torso — small rounded below head */}
          <rect x="54" y="98" width="52" height="34" rx="14" ry="14"
                fill="url(#bodyGrad)"
                stroke="#d4a557" strokeWidth="1.2" strokeOpacity="0.45" />
          {/* Chest glow */}
          <circle cx="80" cy="114" r="5" fill="#d4a557" opacity="0.85"
                  filter="drop-shadow(0 0 4px #d4a557)" />

          {/* Right arm — static, by side */}
          <ellipse cx="108" cy="112" rx="5" ry="9"
                   fill="url(#bodyGrad)" stroke="#d4a557" strokeWidth="0.8" strokeOpacity="0.4" />

          {/* LEFT ARM (waving, holds the screen) */}
          <g className="aurem-arm">
            {/* Arm */}
            <path d="M 55 108 Q 35 95 22 80"
                  stroke="url(#bodyGrad)" strokeWidth="9"
                  strokeLinecap="round" fill="none" />
            <path d="M 55 108 Q 35 95 22 80"
                  stroke="#d4a557" strokeWidth="1" strokeOpacity="0.35"
                  strokeLinecap="round" fill="none" />
            {/* Mini tablet/screen held up */}
            <rect x="4" y="64" width="30" height="22" rx="4" ry="4"
                  fill="url(#screenGrad)"
                  stroke="#7a5a2e" strokeWidth="1.2" />
            {/* Screen inner */}
            <rect x="6" y="66" width="26" height="18" rx="2" ry="2"
                  fill="#1a1108" />
            {/* "7 DAYS" text on screen */}
            <text x="19" y="74" fontSize="6.2" fontWeight="800"
                  textAnchor="middle"
                  fill="#d4a557"
                  style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
              7 DAYS
            </text>
            <text x="19" y="82" fontSize="6.2" fontWeight="800"
                  textAnchor="middle"
                  fill="#d4a557"
                  style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
              FREE
            </text>
          </g>

        </g>
      </svg>
    </div>
  );
};

export default AuremMascot;
