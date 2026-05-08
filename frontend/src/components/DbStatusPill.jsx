/**
 * DbStatusPill — Universal "is this toggle actually persisted to DB?" indicator
 * ───────────────────────────────────────────────────────────────────────────
 *
 * Anywhere in AUREM where we have an ON/OFF toggle whose state lives in DB,
 * use this pill next to the label. It visually distinguishes:
 *   • DB confirmed ON      → pulsing 🟢 green dot + "DB ON"
 *   • DB confirmed OFF     → static 🔴 red dot + "DB OFF"
 *   • Unknown / not synced → grey dot + "DB …" (fetch pending / failed)
 *
 * Also shows a small timestamp of the last successful DB read on hover.
 *
 * Usage:
 *   <DbStatusPill
 *     verified={autoBlastDbVerified}      // boolean | null
 *     lastSync={autoBlastLastSync}        // Date | null
 *     error={autoBlastError}              // string | null
 *     labelOn="DB ON"                     // optional override
 *     labelOff="DB OFF"
 *     testid="auto-blast-db-status"
 *   />
 */
import React from 'react';

export default function DbStatusPill({
  verified,           // boolean | null — true/false/null
  lastSync = null,    // Date | null
  error = null,       // string | null
  labelOn = 'DB ON',
  labelOff = 'DB OFF',
  labelUnknown = 'DB …',
  size = 'sm',        // 'xs' | 'sm' | 'md'
  testid = null,
  className = '',
}) {
  const isOn = verified === true;
  const isOff = verified === false;
  const isUnknown = verified === null || verified === undefined;

  const bg = isUnknown
    ? 'rgba(255,255,255,0.08)'
    : isOn
      ? 'rgba(34,197,94,0.18)'
      : 'rgba(239,68,68,0.15)';
  const border = isUnknown
    ? 'rgba(255,255,255,0.15)'
    : isOn
      ? 'rgba(34,197,94,0.40)'
      : 'rgba(239,68,68,0.35)';
  const color = isUnknown
    ? 'rgba(255,255,255,0.6)'
    : isOn
      ? '#22c55e'
      : '#ef4444';
  const dotColor = isUnknown
    ? 'rgba(255,255,255,0.4)'
    : isOn
      ? '#22c55e'
      : '#ef4444';
  const dotShadow = isOn
    ? '0 0 6px #22c55e'
    : isOff
      ? '0 0 6px #ef4444'
      : 'none';

  const sizeCfg = {
    xs: { text: 'text-[8px]', padX: 'px-1.5', padY: 'py-[1px]', dot: 'w-[5px] h-[5px]' },
    sm: { text: 'text-[9px]', padX: 'px-2', padY: 'py-0.5', dot: 'w-1.5 h-1.5' },
    md: { text: 'text-[10px]', padX: 'px-2.5', padY: 'py-1', dot: 'w-2 h-2' },
  }[size] || { text: 'text-[9px]', padX: 'px-2', padY: 'py-0.5', dot: 'w-1.5 h-1.5' };

  const title = error
    ? `⚠ ${error}`
    : `DB last synced: ${lastSync ? lastSync.toLocaleTimeString() : 'never'}`;

  const label = isUnknown ? labelUnknown : isOn ? labelOn : labelOff;

  return (
    <span
      data-testid={testid || 'db-status-pill'}
      title={title}
      className={`inline-flex items-center gap-1 ${sizeCfg.text} font-bold tracking-wider ${sizeCfg.padX} ${sizeCfg.padY} rounded-full ${className}`}
      style={{ background: bg, border: `1px solid ${border}`, color }}
    >
      <span
        className={`${sizeCfg.dot} rounded-full ${isOn ? 'animate-pulse' : ''}`}
        style={{ background: dotColor, boxShadow: dotShadow }}
      />
      {label}
    </span>
  );
}
