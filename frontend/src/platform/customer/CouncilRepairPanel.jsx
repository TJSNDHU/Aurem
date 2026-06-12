/**
 * CouncilRepairPanel (iter D-84 §4) — "Initiate AUREM Repair" on /my/website.
 * Council-gated, rate-limited, scope-locked. Real flow:
 *   GET  /api/customer/repair/eligibility  → enable/disable + reason
 *   POST /api/customer/repair/initiate     → start (background job)
 *   GET  /api/customer/repair/{job_id}     → poll live phases
 * Honest: live-apply only on pixel-installed sites; otherwise an emailed plan.
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { ShieldCheck, Loader2, CheckCircle2, XCircle, Wand2 } from 'lucide-react';
import { GOLD, PANEL, STROKE, TEXT_HI, TEXT_MD } from '../luxe/tokens';
import { getPlatformToken } from '../../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const PHASES = ['queued', 'analyzing', 'council_review', 'applying', 'verifying', 'done'];
const PHASE_LABEL = {
  queued: 'Queued', analyzing: 'Analysing site', council_review: 'Council review',
  applying: 'Applying fixes', verifying: 'Verifying', done: 'Done', failed: 'Failed',
};

export default function CouncilRepairPanel() {
  const [elig, setElig] = useState(null);
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const poll = useRef(null);

  const tok = getPlatformToken();
  const call = useCallback(async (path, method = 'GET') => {
    const r = await fetch(`${API}${path}`, {
      method, headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
      body: method === 'POST' ? '{}' : undefined,
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
    return d;
  }, [tok]);

  const loadElig = useCallback(async () => {
    try { setElig(await call('/api/customer/repair/eligibility')); } catch (e) { setErr(String(e.message)); }
  }, [call]);

  useEffect(() => { loadElig(); return () => clearInterval(poll.current); }, [loadElig]);

  const startPolling = useCallback((jobId) => {
    clearInterval(poll.current);
    poll.current = setInterval(async () => {
      try {
        const j = await call(`/api/customer/repair/${jobId}`);
        setJob(j);
        if (['done', 'failed', 'rejected'].includes(j.status)) {
          clearInterval(poll.current); setBusy(false); loadElig();
        }
      } catch { /* keep polling */ }
    }, 2500);
  }, [call, loadElig]);

  const initiate = async () => {
    setBusy(true); setErr(''); setJob(null);
    try {
      const r = await call('/api/customer/repair/initiate', 'POST');
      setJob({ status: 'running', current_phase: 'queued', progress_pct: 0 });
      startPolling(r.job_id);
    } catch (e) { setErr(String(e.message)); setBusy(false); }
  };

  const phaseIdx = job ? PHASES.indexOf(job.current_phase) : -1;
  const failed = job && ['failed', 'rejected'].includes(job.status);
  const done = job && job.status === 'done';

  return (
    <div data-testid="council-repair-panel" style={{ background: PANEL, border: `1px solid ${STROKE}`, borderRadius: 16, padding: 20, marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <ShieldCheck size={20} color="#4AD4A0" />
        <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: TEXT_HI }}>AUREM Repair</h3>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: TEXT_MD }}>
          {elig ? `${elig.rate_used}/${elig.rate_limit} today` : ''}
        </span>
      </div>
      <p style={{ fontSize: 13, color: TEXT_MD, margin: '0 0 14px' }}>
        ORA's Council reviews each fix before it ships. Approved DOM fixes apply live on
        pixel-installed sites; the rest arrive as an actionable plan by email.
      </p>

      {!job && (
        <>
          <button data-testid="repair-initiate-btn" onClick={initiate}
            disabled={busy || !(elig && elig.eligible)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '11px 20px',
              borderRadius: 999, fontSize: 14, fontWeight: 700, cursor: (elig && elig.eligible) ? 'pointer' : 'not-allowed',
              background: (elig && elig.eligible) ? GOLD : 'rgba(255,255,255,0.06)',
              color: (elig && elig.eligible) ? '#0A0A0F' : TEXT_MD,
              border: `1px solid ${(elig && elig.eligible) ? GOLD : STROKE}` }}>
            {busy ? <Loader2 size={15} className="spin" /> : <Wand2 size={15} />} Initiate AUREM Repair
          </button>
          {elig && !elig.eligible && elig.reason && (
            <div data-testid="repair-reason" style={{ fontSize: 12.5, color: TEXT_MD, marginTop: 10 }}>{elig.reason}</div>
          )}
          {elig && elig.eligible && (
            <div style={{ fontSize: 12.5, color: TEXT_MD, marginTop: 10 }}>{elig.open_findings} open finding(s) ready to fix.</div>
          )}
        </>
      )}

      {job && (
        <div data-testid="repair-progress">
          {/* phase tracker */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
            {PHASES.map((p, i) => {
              const active = i === phaseIdx && !done && !failed;
              const passed = done || i < phaseIdx;
              return (
                <span key={p} style={{ fontSize: 11, padding: '4px 9px', borderRadius: 999,
                  background: passed ? 'rgba(74,212,160,0.14)' : active ? 'rgba(201,162,39,0.16)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${passed ? 'rgba(74,212,160,0.4)' : active ? 'rgba(201,162,39,0.5)' : STROKE}`,
                  color: passed ? '#4AD4A0' : active ? GOLD : TEXT_MD,
                  display: 'flex', alignItems: 'center', gap: 5 }}>
                  {active && <Loader2 size={10} className="spin" />}
                  {passed && <CheckCircle2 size={10} />}
                  {PHASE_LABEL[p]}
                </span>
              );
            })}
          </div>
          {/* progress bar */}
          <div style={{ height: 6, borderRadius: 4, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${job.progress_pct || 0}%`,
              background: failed ? '#E0574F' : '#4AD4A0', transition: 'width 400ms' }} />
          </div>

          {done && (
            <div data-testid="repair-result" style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <CheckCircle2 size={18} color="#4AD4A0" />
              <div style={{ fontSize: 13.5 }}>
                Repair complete.{' '}
                {job.applied_live > 0
                  ? `${job.applied_live} Council-approved fix(es) applied live via your pixel.`
                  : 'Your fix plan has been emailed — apply the items and re-scan to lift your score.'}
                {typeof job.score_before === 'number' && <span style={{ color: TEXT_MD }}> (score before: {job.score_before}/100)</span>}
              </div>
            </div>
          )}
          {failed && (
            <div data-testid="repair-failed" style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <XCircle size={18} color="#E0574F" />
              <div style={{ fontSize: 13.5, color: TEXT_HI }}>
                {job.status === 'rejected' ? 'Council declined this auto-fix — escalated to human review.' : `Repair failed: ${job.error || 'unknown error'}.`}
                {job.rolled_back ? ` ${job.rolled_back} patch(es) rolled back.` : ''}
              </div>
            </div>
          )}
          {(done || failed) && (
            <button data-testid="repair-again-btn" onClick={() => { setJob(null); setErr(''); }}
              style={{ marginTop: 14, fontSize: 12.5, color: GOLD, background: 'none', border: 'none', cursor: 'pointer' }}>
              ← Back
            </button>
          )}
        </div>
      )}

      {err && <div data-testid="repair-error" style={{ color: '#E0574F', fontSize: 12.5, marginTop: 10 }}>{err}</div>}
      <style>{`.spin{animation:rspin 1s linear infinite}@keyframes rspin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
