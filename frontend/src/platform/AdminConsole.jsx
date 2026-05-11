/**
 * Founders Console — /admin/console (iter 296)
 * Chat with ORA Brain. Routes through Council → A2A → ORA Learning.
 * Mobile-first responsive (PWA-ready).
 */
import React, { useEffect, useRef, useState } from 'react';
import { Send, Loader2, Check, AlertTriangle, Shield, Activity, Brain, Mic, MicOff, Zap, Copy, Printer } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const GOLD = '#C9A227';

const VERDICT_COLOR = { approve: '#22C55E', veto: '#EF4444', escalate: '#F59E0B' };

export default function AdminConsole() {
  const token = getPlatformToken();
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const [sessionId, setSessionId] = useState(() => localStorage.getItem('console_session') || null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [spine, setSpine] = useState(null);
  const [healthCounts, setHealthCounts] = useState(null);  // {healthy,degraded,critical}
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [chips, setChips] = useState([]);
  const [chipModal, setChipModal] = useState(null);   // {chip_id,label,form_fields}
  const [chipFormValues, setChipFormValues] = useState({});
  const [megaOpen, setMegaOpen] = useState(false);
  const [megaForm, setMegaForm] = useState({
    topic: '', business_context: 'AUREM', goal: 'Revenue', urgency: 'This month',
  });
  const [megaRunning, setMegaRunning] = useState(false);
  const scrollRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);

  // Load chip catalog
  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/admin/console/chips`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.chips) setChips(d.chips); })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Load history if existing session
  useEffect(() => {
    if (!sessionId || !token) return;
    fetch(`${API}/api/admin/console/history?session_id=${sessionId}`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.messages) setMessages(d.messages); })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, token]);

  // Spine health poll (10s)
  useEffect(() => {
    if (!token) return;
    const poll = () => fetch(`${API}/api/admin/platform/spine/health`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setSpine(d); }).catch(() => {});
    poll();
    const t = setInterval(poll, 10000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Customer-health summary poll (30s — matches scheduler cadence)
  useEffect(() => {
    if (!token) return;
    const poll = () => fetch(`${API}/api/admin/diagnostics/summary`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.counts) setHealthCounts(d.counts); })
      .catch(() => {});
    poll();
    const t = setInterval(poll, 30000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, sending]);

  const send = async () => {
    const msg = input.trim();
    if (!msg || sending) return;
    setSending(true);
    setMessages(m => [...m, { role: 'user', message: msg, ts: new Date().toISOString() }]);
    setInput('');
    try {
      // Iter 305 — try the new 6-stage propose pipeline first
      const pr = await fetch(`${API}/api/admin/console/propose`, {
        method: 'POST', headers,
        body: JSON.stringify({ message: msg, session_id: sessionId }),
      });
      if (pr.ok) {
        const proposal = await pr.json();
        if (proposal.session_id && proposal.session_id !== sessionId) {
          setSessionId(proposal.session_id);
          localStorage.setItem('console_session', proposal.session_id);
        }
        // iter 322ap — Business action short-circuit. Render the action
        // outcome as a normal assistant message instead of a ProposalCard.
        if (proposal.kind === 'business_action' && proposal.action) {
          const a = proposal.action;
          setMessages(m => [...m, {
            role: 'assistant',
            message: a.summary || `Action ${a.intent} executed.`,
            intent: a.intent,
            action_result: a,
            elapsed_s: proposal.elapsed_s,
            ts: new Date().toISOString(),
          }]);
        } else {
          setMessages(m => [...m, {
            role: 'assistant', kind: 'proposal',
            proposal, ts: new Date().toISOString(),
          }]);
        }
        setSending(false);
        return;
      }
      // Fallback to legacy /message
      const r = await fetch(`${API}/api/admin/console/message`, {
        method: 'POST', headers,
        body: JSON.stringify({ message: msg, session_id: sessionId }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'send failed');
      if (d.session_id && d.session_id !== sessionId) {
        setSessionId(d.session_id);
        localStorage.setItem('console_session', d.session_id);
      }
      setMessages(m => [...m, {
        role: 'assistant', message: d.reply,
        intent: d.intent, decision_id: d.decision_id,
        decision: d.decision, confidence: d.confidence,
        task_ids: d.task_ids || [],
        requires_approval: d.requires_approval,
        ts: new Date().toISOString(),
      }]);
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', message: `Error: ${e.message}`, error: true, ts: new Date().toISOString() }]);
    }
    setSending(false);
  };

  const decideProposal = async (proposalId, approve, idx) => {
    setMessages(m => m.map((x, i) => i === idx ? { ...x, _deciding: true } : x));
    try {
      const r = await fetch(`${API}/api/admin/console/approve`, {
        method: 'POST', headers,
        body: JSON.stringify({ proposal_id: proposalId, confirm: approve }),
      });
      const d = await r.json();
      setMessages(m => m.map((x, i) => i === idx
        ? { ...x, _deciding: false, _result: d, _decided: approve ? 'approved' : 'rejected' }
        : x));
    } catch (e) {
      setMessages(m => m.map((x, i) => i === idx
        ? { ...x, _deciding: false, _result: { ok: false, error: e.message } }
        : x));
    }
  };

  const copyToClipboard = (text) => {
    try {
      navigator.clipboard?.writeText(text);
    } catch { /* ignore */ }
  };

  // ─── Iter 309 — Quick Chips (Content + Wealth Strategy) ──────────────
  const fireChipImmediate = async (chip_id, inputs = null) => {
    const placeholder = { role: 'assistant', kind: 'chip_loading', chip_id,
      ts: new Date().toISOString() };
    setMessages(m => [...m, placeholder]);
    try {
      const r = await fetch(`${API}/api/admin/console/chip/fire`, {
        method: 'POST', headers,
        body: JSON.stringify({ chip_id, inputs }),
      });
      const d = await r.json();
      setMessages(m => m.map(x => x === placeholder
        ? { role: 'assistant', kind: 'chip_output', chip_run: d,
            ts: new Date().toISOString() }
        : x));
    } catch (e) {
      setMessages(m => m.map(x => x === placeholder
        ? { role: 'assistant', message: `Chip error: ${e.message}`,
            error: true, ts: new Date().toISOString() }
        : x));
    }
  };

  const onChipClick = (chip) => {
    if (chip.needs_form) {
      const init = {};
      (chip.form_fields || []).forEach(f => {
        init[f.name] = f.default || '';
      });
      setChipFormValues(init);
      setChipModal(chip);
    } else {
      fireChipImmediate(chip.chip_id, null);
    }
  };

  const submitChipForm = () => {
    if (!chipModal) return;
    const inputs = { ...chipFormValues };
    setChipModal(null);
    setChipFormValues({});
    fireChipImmediate(chipModal.chip_id, inputs);
  };

  // ─── Iter 310 — MEGA Console / Full Intelligence Scan ───────────────
  const pollScan = async (scan_id, placeholder, attempt = 0) => {
    if (attempt > 60) {  // ~3 min cap
      setMessages(m => m.map(x => x === placeholder
        ? { role: 'assistant', message: 'Intelligence scan timed out',
            error: true, ts: new Date().toISOString() }
        : x));
      setMegaRunning(false);
      return;
    }
    try {
      const r = await fetch(`${API}/api/admin/console/intelligence/${scan_id}`,
        { headers });
      if (r.ok) {
        const d = await r.json();
        if (d.status === 'done') {
          setMessages(m => m.map(x => x === placeholder
            ? { role: 'assistant', kind: 'intel_report', report: d,
                inputs: d.inputs, ts: new Date().toISOString() }
            : x));
          setMegaRunning(false);
          return;
        }
        if (d.status === 'error') {
          setMessages(m => m.map(x => x === placeholder
            ? { role: 'assistant', message: `Scan error: ${d.error || 'unknown'}`,
                error: true, ts: new Date().toISOString() }
            : x));
          setMegaRunning(false);
          return;
        }
      }
    } catch { /* network blip — keep polling */ }
    setTimeout(() => pollScan(scan_id, placeholder, attempt + 1), 3000);
  };

  const fireIntelligenceScan = async () => {
    if (!megaForm.topic.trim() || megaRunning) return;
    const payload = { ...megaForm, topic: megaForm.topic.trim() };
    setMegaRunning(true);
    setMegaOpen(false);
    const placeholder = {
      role: 'assistant', kind: 'intel_loading',
      topic: payload.topic, ts: new Date().toISOString(),
    };
    setMessages(m => [...m, placeholder]);
    try {
      const r = await fetch(`${API}/api/admin/console/intelligence`, {
        method: 'POST', headers, body: JSON.stringify(payload),
      });
      const d = await r.json();
      if (!r.ok || !d.scan_id) {
        throw new Error(d.detail || 'kick-off failed');
      }
      pollScan(d.scan_id, placeholder, 0);
    } catch (e) {
      setMessages(m => m.map(x => x === placeholder
        ? { role: 'assistant', message: `Intelligence scan error: ${e.message}`,
            error: true, ts: new Date().toISOString() }
        : x));
      setMegaRunning(false);
    }
    setMegaForm(f => ({ ...f, topic: '' }));
  };

  const newSession = () => {
    setSessionId(null); setMessages([]); localStorage.removeItem('console_session');
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus' : 'audio/webm';
      const rec = new MediaRecorder(stream, { mimeType: mime });
      chunksRef.current = [];
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: mime });
        if (blob.size < 800) { setRecording(false); return; }
        setTranscribing(true);
        try {
          const fd = new FormData();
          fd.append('audio', blob, 'voice.webm');
          const r = await fetch(`${API}/api/admin/console/voice`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            body: fd,
          });
          const d = await r.json();
          if (r.ok && d.transcript) {
            setInput((prev) => (prev ? prev + ' ' : '') + d.transcript);
          } else {
            setMessages(m => [...m, { role: 'assistant', error: true,
              message: `Voice error: ${d.detail || 'no transcript'}`,
              ts: new Date().toISOString() }]);
          }
        } catch (e) {
          setMessages(m => [...m, { role: 'assistant', error: true,
            message: `Voice error: ${e.message}`, ts: new Date().toISOString() }]);
        }
        setTranscribing(false);
        setRecording(false);
      };
      rec.start();
      recorderRef.current = rec;
      setRecording(true);
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', error: true,
        message: `Mic blocked: ${e.message}`, ts: new Date().toISOString() }]);
    }
  };

  const stopRecording = () => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop();
    }
  };

  return (
    <div data-testid="admin-console-page"
      style={{ display: 'flex', flexDirection: 'column', height: '100%',
               minHeight: '100vh', background: '#0A0A0B', color: '#F2EDE4',
               fontFamily: "'DM Sans', system-ui, sans-serif" }}>

      {/* Header */}
      <header style={{ padding: '14px 20px',
                       borderBottom: '1px solid rgba(201,162,39,0.15)',
                       display: 'flex', alignItems: 'center', gap: 12,
                       position: 'sticky', top: 0, background: '#0A0A0B', zIndex: 5 }}>
        <Brain style={{ width: 18, height: 18, color: GOLD }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 22, fontWeight: 400 }}>
            Founders Console
          </div>
          <div style={{ fontSize: 10, color: '#8A8279',
                        fontFamily: "'DM Mono',monospace", letterSpacing: 1.5 }}>
            ORA BRAIN · COUNCIL · A2A · ORA LEARNING
          </div>
        </div>
        <button data-testid="console-new-session" onClick={newSession}
          style={btnSec}>NEW SESSION</button>
        {/* iter 322bg — 1-click ORA PWA jump for founder/admins */}
        <a
          href="/ora"
          data-testid="console-open-ora"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 14px',
            borderRadius: 10,
            background: 'linear-gradient(135deg,#F97316,#C9A227)',
            color: '#0A0A00',
            fontFamily: "'DM Mono',monospace",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.12em',
            textDecoration: 'none',
            textTransform: 'uppercase',
            boxShadow: '0 6px 18px rgba(249,115,22,0.35)',
          }}
        >
          <span style={{width:6,height:6,borderRadius:'50%',background:'#0A0A00'}}/>
          Open ORA
        </a>
      </header>

      {/* Spine HUD */}
      {spine && (
        <div data-testid="console-spine-hud"
          style={{ padding: '8px 20px', display: 'flex', gap: 16, flexWrap: 'wrap',
                   background: 'rgba(255,255,255,0.02)',
                   borderBottom: '1px solid rgba(201,162,39,0.08)',
                   fontFamily: "'DM Mono',monospace", fontSize: 10 }}>
          <Stat label="A2A queued" value={spine.a2a?.queued ?? 0} dot={(spine.a2a?.queued || 0) > 0 ? '#22C55E' : '#7A7468'} />
          <Stat label="A2A done" value={spine.a2a?.complete ?? 0} dot="#22C55E" />
          <Stat label="A2A failed" value={spine.a2a?.failed ?? 0} dot={(spine.a2a?.failed || 0) > 0 ? '#EF4444' : '#7A7468'} />
          <Stat label="Council escalations" value={spine.council?.pending_escalations ?? 0}
                dot={(spine.council?.pending_escalations || 0) > 0 ? '#F59E0B' : '#22C55E'} />
          <Stat label="ORA outcomes" value={Object.values(spine.ora?.outcomes || {}).reduce((a,b)=>a+b,0)} dot="#22C55E" />
          <Stat label="Until finetune" value={spine.ora?.until_finetune ?? 100} dot="#7A7468" />
          <CustomerHealthWidget counts={healthCounts} />
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} data-testid="console-messages"
        style={{ flex: 1, overflowY: 'auto', padding: '20px',
                 maxWidth: 880, width: '100%', margin: '0 auto', alignSelf: 'center' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#7A7468', fontSize: 13, marginTop: 60 }}>
            <p style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 24,
                        color: '#F2EDE4', marginBottom: 8 }}>
              Hey TJ. What do you want to ship today?
            </p>
            <p style={{ fontSize: 12 }}>
              Type any instruction. ORA Brain interprets, Council deliberates,
              A2A executes, every outcome logged.
            </p>
            <div style={{ marginTop: 24, display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
              {['Run scout for auto-repair shops in Mississauga',
                'Status — kitne leads aaj?',
                'Pause outreach',
                'Leads pipeline kya hai?'].map((s, i) => (
                <button key={i}
                  onClick={() => { setInput(s); setTimeout(() => send(), 0); }}
                  data-testid={`console-suggest-${i}`}
                  style={chipBtn}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => {
          if (m.kind === 'proposal') {
            return <ProposalCard key={i} m={m} index={i}
              onApprove={() => decideProposal(m.proposal.proposal_id, true, i)}
              onReject={() => decideProposal(m.proposal.proposal_id, false, i)}
              onCopyPrompt={() => copyToClipboard(m.proposal.council?.optimized_prompt || '')}
            />;
          }
          if (m.kind === 'intel_loading') {
            return <IntelLoading key={i} topic={m.topic} index={i} />;
          }
          if (m.kind === 'intel_report') {
            return <IntelligenceReport key={i} m={m} index={i}
              onCopy={copyToClipboard} />;
          }
          if (m.kind === 'chip_loading') {
            return <ChipLoading key={i} chip_id={m.chip_id} index={i} />;
          }
          if (m.kind === 'chip_output') {
            return <ChipOutput key={i} m={m} index={i} onCopy={copyToClipboard} />;
          }
          return <MessageBubble key={i} m={m} index={i} />;
        })}
        {sending && (
          <div data-testid="console-sending"
            style={{ display: 'flex', gap: 8, alignItems: 'center', color: '#8A8279', fontSize: 12, padding: 14 }}>
            <Loader2 className="animate-spin" style={{ width: 14, height: 14 }} />
            <span>Council deliberating…</span>
          </div>
        )}
      </div>

      {/* MEGA Console + Quick Chips strip */}
      <div data-testid="console-action-strip"
        style={{ borderTop: '1px solid rgba(201,162,39,0.15)',
                 background: 'rgba(0,0,0,0.4)', padding: '12px 20px' }}>
        <div style={{ maxWidth: 880, margin: '0 auto' }}>
          <button data-testid="mega-intel-button"
            onClick={() => setMegaOpen(true)} disabled={megaRunning}
            style={{
              width: '100%', padding: '12px 18px', borderRadius: 10,
              background: 'linear-gradient(90deg,#C9A227 0%,#E8C353 50%,#C9A227 100%)',
              color: '#0A0A0A', fontWeight: 800, fontSize: 12,
              letterSpacing: 2, border: 'none',
              cursor: megaRunning ? 'wait' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
              boxShadow: '0 0 24px rgba(201,162,39,0.25)',
              opacity: megaRunning ? 0.6 : 1,
            }}>
            {megaRunning
              ? <><Loader2 className="animate-spin" style={{ width: 16, height: 16 }} /> RUNNING 7-LENS SCAN…</>
              : <><Zap style={{ width: 16, height: 16 }} /> ⚡ FULL INTELLIGENCE SCAN</>}
          </button>

          {/* Chip rows by category */}
          {chips.length > 0 && (
            <div data-testid="console-chip-rows" style={{ marginTop: 12 }}>
              <ChipRow label="CONTENT STRATEGY · Seth Godin"
                tint="#C9A227"
                items={chips.filter(c => c.category === 'content')}
                onClick={onChipClick} />
              <ChipRow label="WEALTH STRATEGY · Naval Ravikant"
                tint="#5B8DEF"
                items={chips.filter(c => c.category === 'wealth')}
                onClick={onChipClick} />
            </div>
          )}
        </div>
      </div>

      {/* Input */}
      <div style={{ padding: '14px 20px', borderTop: '1px solid rgba(201,162,39,0.15)',
                    background: '#0A0A0B', position: 'sticky', bottom: 0 }}>
        <div style={{ maxWidth: 880, margin: '0 auto', display: 'flex', gap: 10 }}>
          <textarea
            data-testid="console-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
            }}
            placeholder="Type or hold mic… (Enter to send, Shift+Enter for newline)"
            rows={2}
            style={{
              flex: 1, padding: '12px 14px', fontSize: 14,
              background: 'rgba(255,255,255,0.03)', color: '#F2EDE4',
              border: '1px solid rgba(201,162,39,0.25)',
              borderRadius: 8, outline: 'none', resize: 'none',
              fontFamily: 'inherit',
            }} />
          <button
            data-testid="console-mic"
            onClick={recording ? stopRecording : startRecording}
            disabled={transcribing}
            title={recording ? 'Stop recording' : 'Start voice input'}
            style={{
              padding: '0 16px', borderRadius: 8,
              background: recording ? '#EF4444' : 'rgba(255,255,255,0.04)',
              color: recording ? '#fff' : GOLD,
              border: '1px solid ' + (recording ? '#EF4444' : 'rgba(201,162,39,0.35)'),
              fontWeight: 700, fontSize: 12, cursor: transcribing ? 'wait' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
              animation: recording ? 'pulse 1.2s ease-in-out infinite' : 'none',
            }}>
            {transcribing ? <Loader2 className="animate-spin" style={{ width: 14, height: 14 }} />
              : recording ? <MicOff style={{ width: 14, height: 14 }} />
              : <Mic style={{ width: 14, height: 14 }} />}
          </button>
          <button data-testid="console-send" onClick={send} disabled={!input.trim() || sending}
            style={{
              padding: '0 22px', borderRadius: 8, background: GOLD,
              color: '#0A0A0A', fontWeight: 700, fontSize: 12,
              border: 'none', cursor: (!input.trim() || sending) ? 'not-allowed' : 'pointer',
              opacity: (!input.trim() || sending) ? 0.5 : 1,
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
            {sending ? <Loader2 className="animate-spin" style={{ width: 14, height: 14 }} />
                     : <Send style={{ width: 14, height: 14 }} />}
            SEND
          </button>
        </div>
      </div>

      {/* MEGA Intelligence Scan modal */}
      {megaOpen && (
        <div data-testid="mega-modal"
          onClick={() => setMegaOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.78)',
                   display: 'flex', alignItems: 'center', justifyContent: 'center',
                   zIndex: 50, padding: 20 }}>
          <div onClick={(e) => e.stopPropagation()}
            style={{ width: '100%', maxWidth: 560, background: '#13110D',
                     border: '1px solid rgba(201,162,39,0.4)', borderRadius: 14,
                     padding: 26, color: '#F2EDE4',
                     boxShadow: '0 0 60px rgba(201,162,39,0.15)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10,
                          marginBottom: 4 }}>
              <Zap style={{ width: 20, height: 20, color: GOLD }} />
              <div style={{ fontFamily: "'Cormorant Garamond',serif",
                            fontSize: 26, fontWeight: 500 }}>
                Full Intelligence Scan
              </div>
            </div>
            <div style={{ fontSize: 11, color: '#8A8279',
                          fontFamily: "'DM Mono',monospace",
                          letterSpacing: 1.4, marginBottom: 18 }}>
              GODIN · NAVAL · AGENT OPS · CONTENT · PRICING · ORA · NVIDIA · COUNCIL
            </div>

            <ModalField label="Topic / Task" required>
              <textarea data-testid="mega-topic"
                value={megaForm.topic}
                onChange={e => setMegaForm(f => ({ ...f, topic: e.target.value }))}
                placeholder="What do you want to build / solve?"
                rows={3} style={inputBox} />
            </ModalField>

            <ModalField label="Business Context">
              <select data-testid="mega-business"
                value={megaForm.business_context}
                onChange={e => setMegaForm(f => ({ ...f, business_context: e.target.value }))}
                style={inputBox}>
                <option>AUREM</option><option>Reroots</option>
                <option>Personal</option><option>Polaris Built</option>
              </select>
            </ModalField>

            <ModalField label="Goal">
              <select data-testid="mega-goal"
                value={megaForm.goal}
                onChange={e => setMegaForm(f => ({ ...f, goal: e.target.value }))}
                style={inputBox}>
                <option>Revenue</option><option>Brand</option>
                <option>System</option><option>Agent</option>
              </select>
            </ModalField>

            <ModalField label="Urgency">
              <select data-testid="mega-urgency"
                value={megaForm.urgency}
                onChange={e => setMegaForm(f => ({ ...f, urgency: e.target.value }))}
                style={inputBox}>
                <option>This week</option><option>This month</option>
                <option>Long term</option>
              </select>
            </ModalField>

            <div style={{ display: 'flex', gap: 10, marginTop: 18 }}>
              <button data-testid="mega-cancel"
                onClick={() => setMegaOpen(false)} style={btnSec}>CANCEL</button>
              <div style={{ flex: 1 }} />
              <button data-testid="mega-submit"
                onClick={fireIntelligenceScan}
                disabled={!megaForm.topic.trim()}
                style={{
                  padding: '10px 22px', borderRadius: 8, fontSize: 11,
                  fontWeight: 800, letterSpacing: 1.5,
                  background: GOLD, color: '#0A0A0A', border: 'none',
                  cursor: megaForm.topic.trim() ? 'pointer' : 'not-allowed',
                  opacity: megaForm.topic.trim() ? 1 : 0.5,
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                <Zap style={{ width: 14, height: 14 }} /> FIRE 6 LENSES
              </button>
            </div>
            <div style={{ fontSize: 10, color: '#7A7468', marginTop: 12,
                          fontFamily: "'DM Mono',monospace", letterSpacing: 1 }}>
              ~30-50s · all 7 frameworks fire in parallel (incl. NVIDIA NIM free tier)
            </div>
          </div>
        </div>
      )}

      {/* Chip form modal */}
      {chipModal && (
        <div data-testid="chip-modal"
          onClick={() => setChipModal(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.78)',
                   display: 'flex', alignItems: 'center', justifyContent: 'center',
                   zIndex: 50, padding: 20 }}>
          <div onClick={(e) => e.stopPropagation()}
            style={{ width: '100%', maxWidth: 480, background: '#13110D',
                     border: '1px solid rgba(201,162,39,0.4)', borderRadius: 12,
                     padding: 22, color: '#F2EDE4' }}>
            <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 22,
                          marginBottom: 4 }}>
              {chipModal.icon} {chipModal.label}
            </div>
            <div style={{ fontSize: 10, color: '#8A8279',
                          fontFamily: "'DM Mono',monospace",
                          letterSpacing: 1.4, marginBottom: 14 }}>
              QUICK CHIP · BYPASSES COUNCIL
            </div>
            {(chipModal.form_fields || []).map(f => (
              <ModalField key={f.name} label={f.label}
                required={!!f.required}>
                {f.type === 'select' ? (
                  <select data-testid={`chip-field-${f.name}`}
                    value={chipFormValues[f.name] || f.default || ''}
                    onChange={e => setChipFormValues(v => ({ ...v, [f.name]: e.target.value }))}
                    style={inputBox}>
                    {(f.options || []).map(o => <option key={o}>{o}</option>)}
                  </select>
                ) : f.type === 'textarea' ? (
                  <textarea data-testid={`chip-field-${f.name}`}
                    value={chipFormValues[f.name] || ''}
                    onChange={e => setChipFormValues(v => ({ ...v, [f.name]: e.target.value }))}
                    placeholder={f.placeholder || ''}
                    rows={3} style={inputBox} />
                ) : (
                  <input data-testid={`chip-field-${f.name}`}
                    value={chipFormValues[f.name] || ''}
                    onChange={e => setChipFormValues(v => ({ ...v, [f.name]: e.target.value }))}
                    placeholder={f.placeholder || ''}
                    style={inputBox} />
                )}
              </ModalField>
            ))}
            <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
              <button data-testid="chip-cancel"
                onClick={() => setChipModal(null)} style={btnSec}>CANCEL</button>
              <div style={{ flex: 1 }} />
              <button data-testid="chip-submit"
                onClick={submitChipForm}
                style={{
                  padding: '8px 18px', borderRadius: 6, fontSize: 11,
                  fontWeight: 700, letterSpacing: 1.5,
                  background: GOLD, color: '#0A0A0A', border: 'none', cursor: 'pointer',
                }}>FIRE</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const Stat = ({ label, value, dot }) => (
  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
    <span style={{ width: 6, height: 6, borderRadius: '50%', background: dot, display: 'inline-block' }} />
    <span style={{ color: '#7A7468' }}>{label}</span>
    <span style={{ color: GOLD, fontWeight: 600 }}>{value}</span>
  </span>
);

// ─── Customer Health widget — live counts + glowing red dot if critical
const CustomerHealthWidget = ({ counts }) => {
  if (!counts) return null;
  const { healthy = 0, degraded = 0, critical = 0 } = counts;
  const hasCritical = critical > 0;
  const hasDegraded = degraded > 0;
  const dotColor = hasCritical ? '#EF4444' : (hasDegraded ? '#F59E0B' : '#22C55E');
  return (
    <a
      href="/admin/customer-health"
      data-testid="console-customer-health-widget"
      title={`${healthy} healthy · ${degraded} degraded · ${critical} critical · click for details`}
      style={{
        display: 'flex', alignItems: 'center', gap: 6, textDecoration: 'none',
        cursor: 'pointer',
        marginLeft: 'auto',
        padding: '2px 8px',
        borderRadius: 4,
        border: hasCritical
          ? '1px solid rgba(239,68,68,0.35)'
          : '1px solid rgba(255,255,255,0.06)',
        background: hasCritical ? 'rgba(239,68,68,0.08)' : 'transparent',
      }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%', background: dotColor,
        display: 'inline-block',
        boxShadow: hasCritical ? '0 0 6px 1px rgba(239,68,68,0.85)' : 'none',
        animation: hasCritical ? 'aurem-customer-pulse 1.4s ease-in-out infinite' : 'none',
      }} />
      <span style={{ color: '#7A7468' }}>Customers</span>
      <span style={{ color: '#22C55E', fontWeight: 600 }}>{healthy}</span>
      <span style={{ color: '#7A7468' }}>·</span>
      <span style={{ color: hasDegraded ? '#F59E0B' : '#7A7468', fontWeight: 600 }}>{degraded}</span>
      <span style={{ color: '#7A7468' }}>·</span>
      <span style={{ color: hasCritical ? '#EF4444' : '#7A7468', fontWeight: 600 }}>{critical}</span>
      <style>{`
        @keyframes aurem-customer-pulse {
          0%, 100% { box-shadow: 0 0 4px 1px rgba(239,68,68,0.55); }
          50%      { box-shadow: 0 0 10px 3px rgba(239,68,68,0.95); }
        }
      `}</style>
    </a>
  );
};

const MessageBubble = ({ m, index }) => {
  const isUser = m.role === 'user';
  return (
    <div data-testid={`console-msg-${index}`}
      style={{ marginBottom: 14, display: 'flex',
               flexDirection: isUser ? 'row-reverse' : 'row' }}>
      <div style={{
        maxWidth: '78%', padding: '12px 16px', borderRadius: 12,
        background: isUser ? 'rgba(201,162,39,0.18)' : 'rgba(255,255,255,0.04)',
        border: '1px solid ' + (isUser ? 'rgba(201,162,39,0.35)' : 'rgba(255,255,255,0.06)'),
        fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap',
        color: m.error ? '#EF4444' : '#F2EDE4',
      }}>
        {m.message}
        {!isUser && m.decision && (
          <div style={{ marginTop: 10, paddingTop: 10,
                        borderTop: '1px solid rgba(255,255,255,0.06)',
                        display: 'flex', flexWrap: 'wrap', gap: 10,
                        fontFamily: "'DM Mono',monospace", fontSize: 10 }}>
            <Pill icon={Shield} label="Council" value={m.decision} color={VERDICT_COLOR[m.decision] || '#7A7468'} />
            {m.confidence != null && (
              <Pill icon={Brain} label="Conf" value={`${Math.round(m.confidence*100)}%`} color="#7A7468" />
            )}
            {m.task_ids?.length > 0 && (
              <Pill icon={Activity} label="A2A" value={`${m.task_ids.length} task${m.task_ids.length>1?'s':''}`} color="#22C55E" />
            )}
            {m.intent && (
              <Pill icon={Check} label="" value={m.intent} color="#7A7468" />
            )}
            {m.requires_approval && (
              <Pill icon={AlertTriangle} label="" value="needs approval" color="#F59E0B" />
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const Pill = ({ icon: Icon, label, value, color }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4,
                 padding: '2px 8px', borderRadius: 4,
                 background: `${color}15`, border: `1px solid ${color}30`,
                 color, fontSize: 9, letterSpacing: 1 }}>
    <Icon style={{ width: 10, height: 10 }} />
    {label && <span style={{ opacity: 0.7 }}>{label}</span>}
    <span style={{ fontWeight: 700 }}>{String(value).toUpperCase()}</span>
  </span>
);

const btnSec = {
  padding: '6px 12px', borderRadius: 4, fontSize: 9, fontWeight: 600,
  letterSpacing: 1.5, background: 'transparent', color: '#8A8279',
  border: '1px solid rgba(255,255,255,0.12)', cursor: 'pointer',
  fontFamily: 'inherit',
};

const chipBtn = {
  padding: '8px 14px', borderRadius: 20, fontSize: 11,
  background: 'rgba(201,162,39,0.08)', color: '#C9A227',
  border: '1px solid rgba(201,162,39,0.25)', cursor: 'pointer',
  fontFamily: 'inherit',
};

const inputBox = {
  width: '100%', padding: '10px 12px', fontSize: 13,
  background: 'rgba(255,255,255,0.04)', color: '#F2EDE4',
  border: '1px solid rgba(201,162,39,0.25)', borderRadius: 6,
  outline: 'none', fontFamily: 'inherit', resize: 'vertical',
};

const ModalField = ({ label, required, children }) => (
  <div style={{ marginBottom: 12 }}>
    <div style={{ fontSize: 10, color: '#8A8279',
                  fontFamily: "'DM Mono',monospace",
                  letterSpacing: 1.2, marginBottom: 6 }}>
      {label.toUpperCase()}{required && <span style={{ color: '#EF4444' }}> *</span>}
    </div>
    {children}
  </div>
);

const ChipRow = ({ label, tint, items, onClick }) => {
  if (!items || items.length === 0) return null;
  return (
    <div data-testid={`chip-row-${label.split(' ')[0].toLowerCase()}`}
      style={{ marginTop: 10 }}>
      <div style={{ fontSize: 9, color: tint, letterSpacing: 1.6,
                    fontFamily: "'DM Mono',monospace", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {items.map(c => (
          <button key={c.chip_id} data-testid={`chip-${c.chip_id}`}
            onClick={() => onClick(c)}
            style={{
              padding: '6px 12px', borderRadius: 16, fontSize: 11,
              background: `${tint}15`, color: tint,
              border: `1px solid ${tint}45`, cursor: 'pointer',
              fontFamily: 'inherit', fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: 5,
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = `${tint}28`}
            onMouseLeave={e => e.currentTarget.style.background = `${tint}15`}>
            <span>{c.icon}</span>
            <span>{c.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

const ChipLoading = ({ chip_id, index }) => (
  <div data-testid={`chip-loading-${index}`}
    style={{ margin: '14px 0', padding: 14, borderRadius: 10,
             background: 'rgba(201,162,39,0.05)',
             border: '1px solid rgba(201,162,39,0.2)',
             display: 'flex', alignItems: 'center', gap: 10,
             fontFamily: "'DM Mono',monospace", fontSize: 11, color: '#C9A227' }}>
    <Loader2 className="animate-spin" style={{ width: 14, height: 14 }} />
    Firing chip <span style={{ color: '#F2EDE4' }}>{chip_id}</span>… ORA thinking.
  </div>
);

const ChipOutput = ({ m, index, onCopy }) => {
  const cr = m.chip_run || {};
  const ok = cr.ok !== false;
  return (
    <div data-testid={`chip-output-${index}`}
      style={{ margin: '14px 0', padding: 18, borderRadius: 10,
               background: 'rgba(201,162,39,0.04)',
               border: `1px solid ${ok ? 'rgba(201,162,39,0.35)' : 'rgba(239,68,68,0.4)'}`,
               borderLeft: `3px solid ${ok ? '#C9A227' : '#EF4444'}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', marginBottom: 8 }}>
        <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10,
                      letterSpacing: 1.4, color: '#C9A227' }}>
          QUICK CHIP · {cr.label || cr.chip_id}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 10, color: '#8A8279' }}>{cr.duration_s}s</span>
          <button onClick={() => onCopy(cr.output_markdown || '')}
            data-testid={`chip-copy-${index}`}
            style={{ ...btnSec, padding: '4px 10px', fontSize: 9,
                     display: 'flex', alignItems: 'center', gap: 4 }}>
            <Copy style={{ width: 10, height: 10 }} /> COPY
          </button>
        </div>
      </div>
      <pre style={{ margin: 0, padding: 0, fontSize: 13, lineHeight: 1.6,
                    color: '#E8E0D0', whiteSpace: 'pre-wrap',
                    fontFamily: "'DM Sans',system-ui,sans-serif",
                    wordBreak: 'break-word' }}>
        {cr.output_markdown || cr.error || '(empty)'}
      </pre>
    </div>
  );
};

const IntelLoading = ({ topic, index }) => (
  <div data-testid={`intel-loading-${index}`}
    style={{ margin: '14px 0', padding: 18, borderRadius: 12,
             background: 'linear-gradient(135deg,rgba(201,162,39,0.08) 0%,rgba(201,162,39,0.02) 100%)',
             border: '1px solid rgba(201,162,39,0.3)' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10,
                  marginBottom: 8, color: GOLD,
                  fontFamily: "'DM Mono',monospace", fontSize: 11,
                  letterSpacing: 1.4 }}>
      <Loader2 className="animate-spin" style={{ width: 14, height: 14 }} />
      ⚡ FULL INTELLIGENCE SCAN · IN FLIGHT
    </div>
    <div style={{ fontSize: 14, color: '#F2EDE4', marginBottom: 6 }}>{topic}</div>
    <div style={{ fontSize: 11, color: '#8A8279',
                  fontFamily: "'DM Mono',monospace", letterSpacing: 1 }}>
      7 frameworks firing in parallel · ~30-50s
    </div>
  </div>
);

const GOLD_C = '#C9A227';

const IntelligenceReport = ({ m, index, onCopy }) => {
  const r = m.report || {};
  const lenses = r.lenses || [];
  const council = r.council || {};
  const verdict = council.verdict || 'MODIFY';
  const verdictColor = verdict === 'BUILD' ? '#22C55E'
                        : verdict === 'SKIP' ? '#EF4444' : '#F59E0B';

  const buildMarkdown = () => {
    const lines = [];
    lines.push(`# ⚡ Full Intelligence Report`);
    lines.push(`**Topic:** ${m.inputs?.topic || ''}`);
    lines.push(`**Business:** ${m.inputs?.business_context} · **Goal:** ${m.inputs?.goal} · **Urgency:** ${m.inputs?.urgency}`);
    lines.push(`**Generated:** ${r.ts || ''} · **Duration:** ${r.duration_s}s\n`);
    lenses.forEach(L => {
      lines.push(`\n## ${L.icon} ${L.title}\n${L.output || ''}`);
    });
    lines.push(`\n## ✅ Council Verdict\n${council.raw_markdown || ''}`);
    return lines.join('\n');
  };

  const exportPdf = () => {
    const md = buildMarkdown();
    const html = `<html><head><title>Intelligence Report — ${m.inputs?.topic || ''}</title>
<style>
body{font-family:Georgia,serif;max-width:780px;margin:30px auto;padding:0 20px;color:#222;line-height:1.55}
h1{color:#8a6d1c;border-bottom:2px solid #C9A227;padding-bottom:8px}
h2{color:#5a4810;margin-top:28px;border-bottom:1px solid #ddd;padding-bottom:4px}
strong{color:#000}
pre{white-space:pre-wrap;word-break:break-word;background:#faf6e8;padding:10px;border-left:3px solid #C9A227}
</style></head><body><pre>${md.replace(/[<>]/g, c => ({'<':'&lt;','>':'&gt;'}[c]))}</pre>
<script>setTimeout(()=>window.print(),300)</script></body></html>`;
    const w = window.open('', '_blank');
    if (w) { w.document.write(html); w.document.close(); }
  };

  return (
    <div data-testid={`intel-report-${index}`}
      style={{ margin: '14px 0', padding: 22, borderRadius: 14,
               background: 'linear-gradient(135deg,rgba(201,162,39,0.08) 0%,rgba(0,0,0,0.4) 100%)',
               border: `1px solid ${verdictColor}55`,
               borderLeft: `4px solid ${verdictColor}`,
               boxShadow: '0 0 30px rgba(201,162,39,0.08)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'flex-start', marginBottom: 14, gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10,
                        letterSpacing: 1.6, color: GOLD_C, marginBottom: 4 }}>
            ⚡ FULL INTELLIGENCE REPORT · {r.duration_s}s
          </div>
          <div style={{ fontFamily: "'Cormorant Garamond',serif",
                        fontSize: 22, color: '#F2EDE4', fontWeight: 500 }}>
            {m.inputs?.topic || 'Intelligence Scan'}
          </div>
          <div style={{ fontSize: 10, color: '#8A8279',
                        fontFamily: "'DM Mono',monospace",
                        letterSpacing: 1, marginTop: 4 }}>
            {m.inputs?.business_context} · {m.inputs?.goal} · {m.inputs?.urgency}
            {r.failed_lenses?.length > 0 && (
              <span style={{ color: '#EF4444', marginLeft: 10 }}>
                · {r.failed_lenses.length} failed
              </span>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button data-testid={`intel-copy-${index}`}
            onClick={() => onCopy(buildMarkdown())}
            style={{ ...btnSec, padding: '5px 10px', fontSize: 9,
                     display: 'flex', alignItems: 'center', gap: 4 }}>
            <Copy style={{ width: 10, height: 10 }} /> COPY MD
          </button>
          <button data-testid={`intel-export-${index}`} onClick={exportPdf}
            style={{ ...btnSec, padding: '5px 10px', fontSize: 9,
                     display: 'flex', alignItems: 'center', gap: 4 }}>
            <Printer style={{ width: 10, height: 10 }} /> EXPORT PDF
          </button>
        </div>
      </div>

      {/* 7 lens sections (Godin · Naval · Agent Ops · Content · Pricing · ORA · NVIDIA) */}
      <div style={{ display: 'grid', gap: 10 }}>
        {lenses.map((L, j) => (
          <div key={j} data-testid={`intel-lens-${L.key}`}
            style={{ padding: 12, borderRadius: 8,
                     background: 'rgba(0,0,0,0.35)',
                     border: `1px solid ${L.ok ? 'rgba(201,162,39,0.18)' : 'rgba(239,68,68,0.3)'}`,
                     borderLeft: `2px solid ${L.ok ? GOLD_C : '#EF4444'}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between',
                          alignItems: 'center', marginBottom: 6 }}>
              <div style={{ fontSize: 11, color: GOLD_C,
                            fontFamily: "'DM Mono',monospace",
                            letterSpacing: 1.2 }}>
                {L.icon} {L.title}
              </div>
              <button onClick={() => onCopy(L.output || '')}
                data-testid={`intel-lens-copy-${L.key}`}
                style={{ background: 'transparent', border: 'none',
                         color: '#7A7468', cursor: 'pointer',
                         fontSize: 10, padding: 2,
                         display: 'flex', alignItems: 'center', gap: 3 }}>
                <Copy style={{ width: 10, height: 10 }} />
              </button>
            </div>
            <pre style={{ margin: 0, fontSize: 12, lineHeight: 1.55,
                          color: '#E8E0D0', whiteSpace: 'pre-wrap',
                          fontFamily: "'DM Sans',system-ui,sans-serif",
                          wordBreak: 'break-word' }}>
              {L.output || '(empty)'}
            </pre>
          </div>
        ))}
      </div>

      {/* Council verdict */}
      <div data-testid={`intel-council-${index}`}
        style={{ marginTop: 14, padding: 14, borderRadius: 10,
                 background: `${verdictColor}10`,
                 border: `1px solid ${verdictColor}50`,
                 borderLeft: `3px solid ${verdictColor}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between',
                      alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
          <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10,
                        letterSpacing: 1.6, color: verdictColor }}>
            ✅ COUNCIL VERDICT
          </div>
          <div style={{ display: 'flex', gap: 10, fontSize: 11,
                        fontFamily: "'DM Mono',monospace" }}>
            <span style={{ color: verdictColor, fontWeight: 800,
                           fontSize: 14, letterSpacing: 2 }}>
              {verdict}
            </span>
            <span style={{ color: '#8A8279' }}>
              RISK <span style={{ color: '#F2EDE4', fontWeight: 700 }}>{council.risk}/10</span>
            </span>
            <span style={{ color: '#8A8279' }}>
              CONF <span style={{ color: '#F2EDE4', fontWeight: 700 }}>{council.confidence}%</span>
            </span>
          </div>
        </div>
        <pre style={{ margin: 0, fontSize: 12, lineHeight: 1.55,
                      color: '#E8E0D0', whiteSpace: 'pre-wrap',
                      fontFamily: "'DM Sans',system-ui,sans-serif",
                      wordBreak: 'break-word' }}>
          {council.raw_markdown || '(no synthesis)'}
        </pre>
      </div>

      <div style={{ fontSize: 9, color: '#7A7468', marginTop: 10,
                    fontFamily: "'DM Mono',monospace", letterSpacing: 1.2 }}>
        SCAN_ID {r.scan_id} · saved to ora_learnings
      </div>
    </div>
  );
};



// ─── Iter 305 — Approval Card (6-stage Founders Console) ──────────────────
const ProposalCard = ({ m, index, onApprove, onReject, onCopyPrompt }) => {
  const [showPrompt, setShowPrompt] = React.useState(false);
  const p = m.proposal || {};
  const council = p.council || {};
  const race = p.race || {};
  const task = p.task || {};
  const verdict = council.verdict || 'PENDING';
  const eligible = !!council.auto_build_eligible;
  const blockers = council.auto_build_blockers || [];
  const decided = m._decided;
  const result = m._result;

  const verdictColor = verdict === 'APPROVED' ? '#22C55E'
                       : verdict === 'NEEDS_CLARIFICATION' ? '#F59E0B' : '#EF4444';
  const verdictIcon = verdict === 'APPROVED' ? '✅'
                       : verdict === 'NEEDS_CLARIFICATION' ? '⚠️' : '❌';

  const fileList = (race.gemini_plan?.files) || task.affected_files || [];
  const risks = (race.claude_analysis?.risks) || [];

  return (
    <div data-testid={`console-proposal-${index}`}
      style={{
        margin: '14px 0', padding: 18,
        background: 'rgba(201,162,39,0.04)',
        border: `1px solid ${verdictColor}40`,
        borderLeft: `3px solid ${verdictColor}`,
        borderRadius: 10, fontSize: 13, color: '#E8E0D0',
      }}>
      <div style={{ display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: 10, fontFamily: 'JetBrains Mono, monospace',
        fontSize: 10, letterSpacing: 1.4, color: GOLD }}>
        <span>COUNCIL DECISION</span>
        <span style={{ color: '#8A8279' }}>{p.elapsed_s}s</span>
      </div>

      <div style={{ fontSize: 16, fontWeight: 600, color: '#F2EDE4',
        marginBottom: 8 }} data-testid="proposal-title">
        {task.title || 'Untitled task'}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))',
        gap: 8, marginBottom: 14, fontSize: 12 }}>
        <div>
          <div style={{ color: '#8A8279', fontSize: 10, letterSpacing: 1 }}>VERDICT</div>
          <div style={{ color: verdictColor, fontWeight: 700 }}
            data-testid="proposal-verdict">
            {verdictIcon} {verdict}
          </div>
        </div>
        <div>
          <div style={{ color: '#8A8279', fontSize: 10, letterSpacing: 1 }}>CONFIDENCE</div>
          <div style={{ color: '#F2EDE4', fontWeight: 700 }}>
            {Math.round((council.avg_confidence || 0) * 100)}%
          </div>
        </div>
        <div>
          <div style={{ color: '#8A8279', fontSize: 10, letterSpacing: 1 }}>RISK</div>
          <div style={{ color: '#F2EDE4', fontWeight: 700 }}
            data-testid="proposal-risk">
            {council.risk_score || '—'}/10
          </div>
        </div>
        <div>
          <div style={{ color: '#8A8279', fontSize: 10, letterSpacing: 1 }}>AUTO-BUILD</div>
          <div style={{ color: eligible ? '#22C55E' : '#F59E0B', fontWeight: 700 }}
            data-testid="proposal-auto-build">
            {eligible ? 'YES (Self-Edit)' : 'NO (Stub)'}
          </div>
        </div>
      </div>

      {race.gemini_plan?.approach && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ color: '#8A8279', fontSize: 10, letterSpacing: 1.2,
            marginBottom: 4 }}>APPROACH</div>
          <div style={{ color: '#D4CCC0', lineHeight: 1.55 }}>
            {race.gemini_plan.approach}
          </div>
        </div>
      )}

      {fileList.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ color: '#8A8279', fontSize: 10, letterSpacing: 1.2,
            marginBottom: 4 }}>FILES</div>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12,
            color: '#C9A227' }}>
            {fileList.slice(0, 5).map((f, j) => <div key={j}>· {f}</div>)}
          </div>
        </div>
      )}

      {risks.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ color: '#8A8279', fontSize: 10, letterSpacing: 1.2,
            marginBottom: 4 }}>RISKS</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: '#D4CCC0', lineHeight: 1.5 }}>
            {risks.slice(0, 4).map((r, j) => <li key={j}>{r}</li>)}
          </ul>
        </div>
      )}

      {!eligible && blockers.length > 0 && (
        <div style={{ marginBottom: 10, padding: 8,
          background: 'rgba(245,158,11,0.06)',
          border: '1px solid rgba(245,158,11,0.25)', borderRadius: 6 }}>
          <div style={{ color: '#F59E0B', fontSize: 10, letterSpacing: 1.2,
            marginBottom: 4 }}>STUB PATH (auto-build blocked)</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: '#D4CCC0', fontSize: 12 }}>
            {blockers.map((b, j) => <li key={j}>{b}</li>)}
          </ul>
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <button onClick={() => setShowPrompt(s => !s)}
          data-testid="proposal-toggle-prompt"
          style={{ ...btnSec, padding: '4px 10px', fontSize: 9 }}>
          {showPrompt ? 'HIDE' : 'SHOW'} OPTIMIZED PROMPT
        </button>
        {showPrompt && (
          <pre data-testid="proposal-optimized-prompt"
            style={{ marginTop: 8, padding: 10, fontSize: 11,
              background: 'rgba(0,0,0,0.4)', color: '#A8A099',
              borderRadius: 6, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              fontFamily: 'JetBrains Mono, monospace', maxHeight: 220,
              overflow: 'auto' }}>
            {council.optimized_prompt || '(empty)'}
          </pre>
        )}
      </div>

      {!decided && verdict === 'APPROVED' && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={onApprove} disabled={m._deciding}
            data-testid="proposal-approve"
            style={{ padding: '8px 16px', borderRadius: 6, fontSize: 11,
              fontWeight: 700, letterSpacing: 1, background: '#22C55E',
              color: '#0A0A0A', border: 'none', cursor: 'pointer',
              fontFamily: 'inherit' }}>
            {m._deciding ? 'BUILDING…' : '✅ APPROVE & BUILD'}
          </button>
          <button onClick={onReject} disabled={m._deciding}
            data-testid="proposal-reject"
            style={{ padding: '8px 16px', borderRadius: 6, fontSize: 11,
              fontWeight: 700, letterSpacing: 1, background: 'transparent',
              color: '#EF4444', border: '1px solid #EF4444', cursor: 'pointer',
              fontFamily: 'inherit' }}>
            ❌ REJECT
          </button>
          {!eligible && (
            <button onClick={onCopyPrompt}
              data-testid="proposal-copy-prompt"
              style={{ ...btnSec, fontSize: 10 }}>
              📋 COPY PROMPT
            </button>
          )}
        </div>
      )}

      {decided && (
        <div data-testid="proposal-result"
          style={{ marginTop: 12, padding: 10, borderRadius: 6,
            background: result?.ok ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
            border: `1px solid ${result?.ok ? '#22C55E' : '#EF4444'}40`,
            fontSize: 12, color: '#D4CCC0' }}>
          <div style={{ fontWeight: 700, color: result?.ok ? '#22C55E' : '#EF4444' }}>
            {result?.ok ? '✅ ' : '❌ '}
            {decided === 'rejected' ? 'REJECTED'
              : result?.build_path === 'self_edit'
                ? (result?.ok ? 'SELF-EDIT BUILT & RESTARTED' : 'ROLLED BACK')
                : result?.build_path === 'stub'
                  ? '📋 PROMPT READY — paste into Emergent'
                  : 'PROCESSED'}
          </div>
          {result?.duration_s && (
            <div style={{ color: '#8A8279', fontSize: 11, marginTop: 4 }}>
              Duration: {result.duration_s}s · learning: {result.learning_id || '—'}
            </div>
          )}
          {result?.result?.files_changed?.length > 0 && (
            <div style={{ marginTop: 6, fontFamily: 'JetBrains Mono, monospace',
              fontSize: 11, color: '#C9A227' }}>
              {result.result.files_changed.map((f, j) => <div key={j}>+ {f}</div>)}
            </div>
          )}
          {result?.result?.error && (
            <div style={{ marginTop: 6, color: '#EF4444', fontSize: 11 }}>
              {result.result.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
