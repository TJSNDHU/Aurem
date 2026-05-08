/**
 * SevenDayTrialPromo — iter 287.6 (animated mascot version)
 *
 * Video-inspired floating promo: AUREM animated robot mascot peeks out
 * from behind the card (blinking eyes + waving arm holding a mini-tablet
 * that reads "7 DAYS FREE"), next to the offer copy + countdown + CTA.
 *
 * Dismissal persists 48h. Countdown is rolling 7-day per device.
 */
import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ArrowRight, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AuremMascot from './AuremMascot';

const DISMISS_KEY = 'aurem_trial_promo_dismissed_at';
const DISMISS_TTL_MS = 48 * 60 * 60 * 1000;
const ENDTIME_KEY = 'aurem_trial_promo_ends_at';

const SevenDayTrialPromo = () => {
  const navigate = useNavigate();
  const [visible, setVisible] = useState(false);
  const [remaining, setRemaining] = useState(null);

  useEffect(() => {
    try {
      const d = localStorage.getItem(DISMISS_KEY);
      if (d && Date.now() - parseInt(d, 10) < DISMISS_TTL_MS) return;
    } catch {}

    let ends;
    try {
      const stored = localStorage.getItem(ENDTIME_KEY);
      if (stored) {
        ends = parseInt(stored, 10);
        if (isNaN(ends) || ends < Date.now()) {
          ends = Date.now() + 7 * 24 * 60 * 60 * 1000;
          localStorage.setItem(ENDTIME_KEY, String(ends));
        }
      } else {
        ends = Date.now() + 7 * 24 * 60 * 60 * 1000;
        localStorage.setItem(ENDTIME_KEY, String(ends));
      }
    } catch {
      ends = Date.now() + 7 * 24 * 60 * 60 * 1000;
    }

    const tick = () => {
      const diff = Math.max(0, ends - Date.now());
      const days = Math.floor(diff / (24 * 60 * 60 * 1000));
      const hrs = Math.floor((diff % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));
      setRemaining({ days, hrs, expired: diff === 0 });
    };
    tick();
    const iv = setInterval(tick, 60 * 1000);
    const t = setTimeout(() => setVisible(true), 800);
    return () => { clearTimeout(t); clearInterval(iv); };
  }, []);

  const dismiss = () => {
    setVisible(false);
    try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch {}
  };
  const claim = () => { dismiss(); navigate('/pricing'); };

  if (!remaining) return null;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          role="complementary"
          aria-label="7-day free trial offer"
          data-testid="seven-day-trial-promo"
          initial={{ opacity: 0, y: 30, x: 30, scale: 0.92 }}
          animate={{ opacity: 1, y: 0, x: 0, scale: 1 }}
          exit={{ opacity: 0, x: 60, transition: { duration: 0.3 } }}
          transition={{ type: 'spring', stiffness: 180, damping: 22 }}
          className="fixed bottom-6 right-6 z-[100]"
          style={{ fontFamily: 'Inter, system-ui, sans-serif' }}
        >
          {/* Outer glow ring */}
          <div className="relative" style={{ width: 340 }}>
            <div
              aria-hidden="true"
              className="absolute -inset-[1px] rounded-2xl opacity-60 blur-[3px]"
              style={{
                background: 'linear-gradient(135deg, #b87333 0%, #d4a557 50%, #7a5a2e 100%)',
              }}
            />
            {/* Card body */}
            <div
              className="relative rounded-2xl backdrop-blur-xl"
              style={{
                background:
                  'linear-gradient(140deg, rgba(18,14,10,0.96) 0%, rgba(26,20,14,0.94) 60%, rgba(30,22,12,0.95) 100%)',
                border: '1px solid rgba(212, 165, 87, 0.30)',
                boxShadow:
                  '0 20px 50px -12px rgba(0,0,0,0.7), 0 0 0 1px rgba(212, 165, 87, 0.08) inset',
                overflow: 'visible',
              }}
            >
              {/* Close */}
              <button
                data-testid="seven-day-trial-close"
                onClick={dismiss}
                aria-label="Dismiss offer"
                className="absolute top-3 left-3 w-7 h-7 flex items-center justify-center rounded-full transition-all hover:bg-white/10 active:scale-95 z-10"
                style={{ color: 'rgba(255,255,255,0.55)' }}
              >
                <X size={14} strokeWidth={2.5} />
              </button>

              {/* Mascot — peeks OUT of the card (top-right, overflows) */}
              <div
                aria-hidden="true"
                className="absolute"
                style={{
                  right: -18,
                  top: -52,
                  width: 130,
                  height: 130,
                  pointerEvents: 'none',
                  zIndex: 2,
                }}
              >
                <AuremMascot size={130} />
              </div>

              {/* Body — leaves right-side space free for mascot */}
              <div className="pl-12 pr-5 pt-4 pb-5" style={{ paddingRight: 110 }}>
                {/* Heading */}
                <div
                  className="text-[11px] font-semibold uppercase tracking-[0.14em] mb-1.5"
                  style={{ color: '#d4a557' }}
                >
                  Limited offer
                </div>

                {/* Main offer */}
                <div
                  className="text-[26px] font-bold leading-[1.05] tracking-tight"
                  style={{
                    color: '#f7e3b8',
                    textShadow: '0 1px 14px rgba(212,165,87,0.2)',
                  }}
                >
                  7 days
                  <br />free
                </div>

                {/* Body-width subtext (once mascot is above, reclaim width) */}
              </div>

              {/* Full-width sub + countdown + CTA below mascot */}
              <div className="pl-5 pr-5 pb-5">
                <div
                  className="text-[13px] mb-3"
                  style={{ color: 'rgba(255,255,255,0.62)' }}
                >
                  Full AUREM platform &middot; no card needed
                </div>

                {/* Countdown chip */}
                <div
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium mb-3"
                  style={{
                    background: 'rgba(184, 115, 51, 0.14)',
                    color: '#d4a557',
                    border: '1px solid rgba(212, 165, 87, 0.22)',
                  }}
                >
                  <Clock size={11} strokeWidth={2.5} />
                  {remaining.expired
                    ? 'Offer ending soon'
                    : remaining.days > 0
                    ? `${remaining.days}d ${remaining.hrs}h left to claim`
                    : `${remaining.hrs}h left to claim`}
                </div>

                {/* CTA */}
                <button
                  data-testid="seven-day-trial-cta"
                  onClick={claim}
                  className="group w-full flex items-center justify-center gap-1.5 rounded-xl py-2.5 text-[13px] font-semibold transition-all active:scale-[0.98]"
                  style={{
                    background: 'linear-gradient(135deg, #d4a557 0%, #b87333 100%)',
                    color: '#1a1108',
                    boxShadow:
                      '0 4px 16px -4px rgba(212,165,87,0.42), 0 0 0 1px rgba(212,165,87,0.35) inset',
                  }}
                >
                  Start free trial
                  <ArrowRight
                    size={15}
                    strokeWidth={2.75}
                    className="transition-transform group-hover:translate-x-0.5"
                  />
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default SevenDayTrialPromo;
