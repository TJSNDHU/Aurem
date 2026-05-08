/**
 * AUREM Economic Ticker — Rotating Economic Indicators
 * Rotation: 4s per item | Pause on hover | Frosted glass style
 * Content: CAD/USD + change, BoC policy rate, Next economic date, Repeat
 * Compliance: Economic data for business context only. Not investment advice.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus, DollarSign, Calendar, Percent } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ROTATION_MS = 4000;

const iconMap = {
  exchange: DollarSign,
  rate: Percent,
  date: Calendar,
};

export default function EconomicTicker({ token, visible = true }) {
  const [items, setItems] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const intervalRef = useRef(null);

  const fetchTicker = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/api/global-pulse/ticker`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        if (data.items && data.items.length > 0) {
          setItems(data.items);
        }
      }
    } catch (e) {
      console.debug('Ticker fetch:', e);
    }
  }, [token]);

  useEffect(() => {
    if (token && visible) fetchTicker();
    const refresh = setInterval(fetchTicker, 300000);
    return () => clearInterval(refresh);
  }, [token, visible, fetchTicker]);

  useEffect(() => {
    if (items.length === 0 || paused) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(() => {
      setCurrentIndex(prev => (prev + 1) % items.length);
    }, ROTATION_MS);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [items.length, paused]);

  if (!visible || items.length === 0) return null;

  const current = items[currentIndex] || {};
  const Icon = iconMap[current.type] || DollarSign;
  const changePct = current.change_pct;

  return (
    <div
      data-testid="economic-ticker"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className="relative overflow-hidden"
      style={{
        height: '35px',
        background: 'rgba(15,15,18,0.6)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(201,168,76,0.12)',
      }}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={currentIndex}
          initial={{ x: 60, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -60, opacity: 0 }}
          transition={{ duration: 0.35, ease: 'easeInOut' }}
          className="absolute inset-0 flex items-center px-6 gap-4"
          style={{ width: '100%' }}
        >
          <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: '#C9A84C' }} />
          <span
            className="text-[11px] font-semibold tracking-wide flex-1"
            style={{ color: '#C9A84C', fontFamily: 'Cinzel, Georgia, serif' }}
            data-testid={`ticker-item-${current.id}`}
          >
            {current.label}
          </span>
          {changePct !== null && changePct !== undefined && current.type === 'exchange' && (
            <span className="flex items-center gap-0.5 text-[10px] font-bold">
              {changePct > 0 ? (
                <TrendingUp className="w-2.5 h-2.5 text-[#22C55E]" />
              ) : changePct < 0 ? (
                <TrendingDown className="w-2.5 h-2.5 text-[#EF4444]" />
              ) : (
                <Minus className="w-2.5 h-2.5 text-[#C9A84C]" />
              )}
            </span>
          )}
          {/* Dot indicators */}
          <div className="flex items-center gap-1 ml-3">
            {items.map((_, i) => (
              <div
                key={i}
                className="rounded-full transition-all duration-300"
                style={{
                  width: i === currentIndex ? '12px' : '4px',
                  height: '4px',
                  background: i === currentIndex ? '#C9A84C' : 'rgba(201,168,76,0.25)',
                }}
              />
            ))}
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
