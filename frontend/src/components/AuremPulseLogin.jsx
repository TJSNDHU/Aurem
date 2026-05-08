/**
 * AuremPulseLogin — "Scientific-Luxe" Login Animation
 * Sequence: Dim → Particle Convergence → Logo Pulse → Glass Card Reveal
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';

const COPPER = { r: 212, g: 163, b: 115 };
const PARTICLE_COUNT = 140;
const CONVERGENCE_DURATION = 500;
const PULSE_DELAY = 550;
const CARD_DELAY = 600;

const AuremPulseLogin = ({ onAnimationComplete }) => {
  const canvasRef = useRef(null);
  const [phase, setPhase] = useState('converging'); // converging → pulsing → revealed
  const animFrameRef = useRef(null);
  const startTimeRef = useRef(null);
  const particlesRef = useRef([]);
  const pulseRef = useRef({ scale: 0, opacity: 0, active: false });

  const initParticles = useCallback((w, h) => {
    const cx = w / 2;
    const cy = h / 2 - 40;
    const particles = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const angle = Math.random() * Math.PI * 2;
      const dist = Math.max(w, h) * 0.5 + Math.random() * 300;
      // Inner cluster (60%) orbits tight, outer (40%) spreads wider
      const isInner = i < PARTICLE_COUNT * 0.6;
      const targetSpread = isInner ? 45 : 120;
      particles.push({
        x: cx + Math.cos(angle) * dist,
        y: cy + Math.sin(angle) * dist,
        targetX: cx + (Math.random() - 0.5) * targetSpread,
        targetY: cy + (Math.random() - 0.5) * targetSpread,
        startX: cx + Math.cos(angle) * dist,
        startY: cy + Math.sin(angle) * dist,
        size: isInner ? 1.2 + Math.random() * 2 : 1 + Math.random() * 1.5,
        opacity: 0,
        delay: Math.random() * 0.35,
        speed: 0.65 + Math.random() * 0.35,
        floatPhase: Math.random() * Math.PI * 2,
        floatRadius: 2 + Math.random() * 5,
        floatSpeed: 0.3 + Math.random() * 0.4,
      });
    }
    particlesRef.current = particles;
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    const resize = () => {
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = window.innerWidth + 'px';
      canvas.style.height = window.innerHeight + 'px';
      ctx.scale(dpr, dpr);
      initParticles(window.innerWidth, window.innerHeight);
    };

    resize();
    window.addEventListener('resize', resize);
    startTimeRef.current = performance.now();

    // Trigger phases
    const pulseTimer = setTimeout(() => {
      pulseRef.current.active = true;
      setPhase('pulsing');
    }, PULSE_DELAY);

    const cardTimer = setTimeout(() => {
      setPhase('revealed');
      if (onAnimationComplete) onAnimationComplete();
    }, CARD_DELAY);

    const draw = (now) => {
      const elapsed = now - startTimeRef.current;
      const progress = Math.min(elapsed / CONVERGENCE_DURATION, 1);
      const w = window.innerWidth;
      const h = window.innerHeight;
      const cx = w / 2;
      const cy = h / 2 - 40;

      ctx.clearRect(0, 0, w, h);

      // Draw connecting lines between nearby particles
      const particles = particlesRef.current;
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        const t = Math.max(0, Math.min(1, (progress - p.delay) / (1 - p.delay)));
        const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

        if (progress < 1) {
          p.x = p.startX + (p.targetX - p.startX) * ease * p.speed;
          p.y = p.startY + (p.targetY - p.startY) * ease * p.speed;
        } else {
          // Persistent ambient float after convergence
          const ft = (elapsed - CONVERGENCE_DURATION) / 1000;
          p.x = p.targetX + Math.sin(ft * p.floatSpeed + p.floatPhase) * p.floatRadius;
          p.y = p.targetY + Math.cos(ft * p.floatSpeed * 0.8 + p.floatPhase) * p.floatRadius;
        }
        p.opacity = Math.min(1, t * 2.5);

        for (let j = i + 1; j < particles.length; j++) {
          const q = particles[j];
          const dx = p.x - q.x;
          const dy = p.y - q.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 100) {
            const lineOpacity = (1 - dist / 100) * p.opacity * q.opacity * 0.25;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = `rgba(${COPPER.r},${COPPER.g},${COPPER.b},${lineOpacity})`;
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }
      }

      // Draw particles
      for (const p of particles) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${COPPER.r},${COPPER.g},${COPPER.b},${p.opacity * 0.8})`;
        ctx.fill();

        // Glow
        if (p.opacity > 0.3) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
          const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 3);
          grad.addColorStop(0, `rgba(${COPPER.r},${COPPER.g},${COPPER.b},${p.opacity * 0.15})`);
          grad.addColorStop(1, 'transparent');
          ctx.fillStyle = grad;
          ctx.fill();
        }
      }

      // Central logo glow (grows as particles converge)
      if (progress > 0.3) {
        const logoGlow = (progress - 0.3) / 0.7;
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 50 + logoGlow * 30);
        grad.addColorStop(0, `rgba(${COPPER.r},${COPPER.g},${COPPER.b},${logoGlow * 0.25})`);
        grad.addColorStop(0.5, `rgba(${COPPER.r},${COPPER.g},${COPPER.b},${logoGlow * 0.08})`);
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, 80, 0, Math.PI * 2);
        ctx.fill();
      }

      // Pulse ring
      if (pulseRef.current.active) {
        const pulseElapsed = elapsed - PULSE_DELAY;
        if (pulseElapsed > 0) {
          const pulseProgress = Math.min(pulseElapsed / 1200, 1);
          const scale = 0.8 + pulseProgress * 3;
          const opacity = (1 - pulseProgress) * 0.5;
          if (opacity > 0.01) {
            ctx.beginPath();
            ctx.arc(cx, cy, 40 * scale, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(${COPPER.r},${COPPER.g},${COPPER.b},${opacity})`;
            ctx.lineWidth = 2 - pulseProgress * 1.5;
            ctx.stroke();
          }

          // Second ring
          const p2 = Math.max(0, pulseProgress - 0.15);
          const s2 = 0.8 + p2 * 3;
          const o2 = (1 - p2) * 0.3;
          if (o2 > 0.01 && p2 > 0) {
            ctx.beginPath();
            ctx.arc(cx, cy, 40 * s2, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(${COPPER.r},${COPPER.g},${COPPER.b},${o2})`;
            ctx.lineWidth = 1.5 - p2;
            ctx.stroke();
          }
        }
      }

      animFrameRef.current = requestAnimationFrame(draw);
    };

    animFrameRef.current = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animFrameRef.current);
      clearTimeout(pulseTimer);
      clearTimeout(cardTimer);
    };
  }, [initParticles, onAnimationComplete]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 1,
        pointerEvents: 'none',
      }}
    />
  );
};

export default AuremPulseLogin;
