import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { Handshake, ArrowRight, CheckCircle, XCircle, Clock, Loader2, ChevronDown, ChevronUp, DollarSign, Send } from 'lucide-react';
import { motion, StaggerGrid, MotionCard, ExpandSection, cardVariant } from './motion-system';

const API = process.env.REACT_APP_BACKEND_URL;

export default function NegotiationDashboard({ token }) {
  const [sessions, setSessions] = useState([]);
  const [expandedSession, setExpandedSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newNeg, setNewNeg] = useState({ product_ids: '', quantities: '', discount: 5 });
  const [starting, setStarting] = useState(false);
  const [countering, setCountering] = useState({ session: null, discount: 0 });

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/negotiate/sessions/recent?limit=20`, { headers });
      if (res.ok) { const d = await res.json(); setSessions(d.sessions || []); }
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const startNegotiation = async () => {
    setStarting(true);
    try {
      const pids = newNeg.product_ids.split(',').map(s => s.trim()).filter(Boolean);
      const qtys = newNeg.quantities.split(',').map(s => parseInt(s.trim()) || 1);
      const res = await fetch(`${API}/api/negotiate/start`, {
        method: 'POST', headers,
        body: JSON.stringify({
          buyer_agent_id: 'dashboard_buyer',
          product_ids: pids.length ? pids : ['demo_product'],
          quantities: qtys.length ? qtys : [10],
          proposed_discount_pct: newNeg.discount,
          justification: 'Dashboard negotiation test',
        }),
      });
      if (res.ok) {
        setNewNeg({ product_ids: '', quantities: '', discount: 5 });
        fetchSessions();
      }
    } catch (e) { console.error(e); }
    setStarting(false);
  };

  const sendCounter = async (sessionId, discount) => {
    try {
      const res = await fetch(`${API}/api/negotiate/${sessionId}/counter`, {
        method: 'POST', headers,
        body: JSON.stringify({ proposed_discount_pct: discount }),
      });
      if (res.ok) {
        setCountering({ session: null, discount: 0 });
        fetchSessions();
      }
    } catch (e) { console.error(e); }
  };

  const acceptOffer = async (sessionId) => {
    try {
      const res = await fetch(`${API}/api/negotiate/${sessionId}/accept`, { method: 'POST', headers });
      if (res.ok) fetchSessions();
    } catch (e) { console.error(e); }
  };

  const statusColor = (s) => s === 'accepted' ? '#22C55E' : s === 'negotiating' ? '#EAB308' : s === 'final_offer' ? '#F97316' : '#EF4444';

  return (
    <div className="flex-1 overflow-auto p-6" style={{ background: 'transparent' }} data-testid="negotiation-dashboard">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center justify-between mb-6"
      >
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>AgenticPay Negotiation</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>5-round AI buyer/seller price negotiation engine</p>
        </div>
      </motion.div>

      {/* Start New Negotiation */}
      <MotionCard className="aurem-glass-card p-5 mb-6" data-testid="new-negotiation-form">
        <div className="text-xs font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>Start New Negotiation</div>
        <div className="grid grid-cols-4 gap-3">
          <input placeholder="Product IDs (comma sep)"
            className="px-3 py-2 rounded-lg text-[11px]"
            style={{ background: 'rgba(45,122,74,0.05)', border: '1px solid rgba(255,107,0,0.1)', color: 'var(--aurem-heading)' }}
            value={newNeg.product_ids}
            onChange={(e) => setNewNeg({ ...newNeg, product_ids: e.target.value })}
            data-testid="neg-product-ids"
          />
          <input placeholder="Quantities (comma sep)"
            className="px-3 py-2 rounded-lg text-[11px]"
            style={{ background: 'rgba(45,122,74,0.05)', border: '1px solid rgba(255,107,0,0.1)', color: 'var(--aurem-heading)' }}
            value={newNeg.quantities}
            onChange={(e) => setNewNeg({ ...newNeg, quantities: e.target.value })}
            data-testid="neg-quantities"
          />
          <input type="number" placeholder="Discount %"
            className="px-3 py-2 rounded-lg text-[11px]"
            style={{ background: 'rgba(45,122,74,0.05)', border: '1px solid rgba(255,107,0,0.1)', color: 'var(--aurem-heading)' }}
            value={newNeg.discount}
            onChange={(e) => setNewNeg({ ...newNeg, discount: parseFloat(e.target.value) || 0 })}
            data-testid="neg-discount"
          />
          <motion.button onClick={startNegotiation} disabled={starting}
            className="px-4 py-2 rounded-lg text-[11px] font-bold flex items-center justify-center gap-2"
            style={{ background: 'linear-gradient(135deg, #FF6B00, #B8956A)', color: '#fff' }}
            whileHover={{ scale: 1.04, boxShadow: '0 4px 20px rgba(212,163,115,0.4)' }}
            whileTap={{ scale: 0.96 }}
            data-testid="neg-start-btn"
          >
            {starting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Handshake className="w-3 h-3" />}
            Start
          </motion.button>
        </div>
      </MotionCard>

      {/* Sessions List */}
      <div className="aurem-glass-card overflow-hidden" data-testid="negotiation-sessions">
        <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: 'rgba(61,58,57,0.25)', background: 'rgba(212,163,115,0.03)' }}>
          <DollarSign className="w-4 h-4" style={{ color: '#FF6B00' }} />
          <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>Negotiation Sessions</span>
          <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>{sessions.length} sessions</span>
        </div>
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--aurem-body-secondary)' }} /></div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center py-12">
            <Handshake className="w-8 h-8 mb-2" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.3 }} />
            <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>No negotiation sessions yet</p>
          </div>
        ) : (
          <div className="max-h-[500px] overflow-y-auto aurem-scroll">
            {sessions.map((session) => {
              const isExp = expandedSession === session.session_id;
              return (
                <div key={session.session_id}>
                  <div className="px-5 py-3 border-b cursor-pointer hover:bg-[rgba(255,107,0,0.03)] transition-colors"
                    style={{ borderColor: 'rgba(255,107,0,0.05)' }}
                    onClick={() => setExpandedSession(isExp ? null : session.session_id)}
                    data-testid={`session-${session.session_id}`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full" style={{ background: statusColor(session.status) }} />
                      <span className="text-xs font-mono font-medium" style={{ color: 'var(--aurem-heading)' }}>{session.session_id}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: `${statusColor(session.status)}15`, color: statusColor(session.status) }}>
                        {session.status}
                      </span>
                      <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                        ${session.order_value?.toFixed(2)} | Round {session.current_round}/5
                      </span>
                      {session.final_discount_pct && (
                        <span className="text-[10px] font-bold" style={{ color: '#22C55E' }}>
                          {session.final_discount_pct}% off
                        </span>
                      )}
                      <span className="ml-auto">{isExp ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}</span>
                    </div>
                  </div>
                  {isExp && (
                    <div className="px-5 py-3 border-b" style={{ borderColor: 'rgba(255,107,0,0.05)', background: 'rgba(45,122,74,0.02)' }}>
                      {session.rounds?.map((round, ri) => (
                        <div key={ri} className="flex items-center gap-3 py-2 border-b" style={{ borderColor: 'rgba(255,107,0,0.04)' }}>
                          <span className="text-[10px] font-bold w-8" style={{ color: 'var(--aurem-body-secondary)' }}>R{round.round}</span>
                          <span className="text-[10px]" style={{ color: '#3B82F6' }}>Buyer: {round.buyer_proposed}%</span>
                          <ArrowRight className="w-3 h-3" style={{ color: 'var(--aurem-body-secondary)' }} />
                          <span className="text-[10px]" style={{ color: '#FF6B00' }}>Seller: {round.seller_max}%</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded" style={{
                            background: round.decision === 'accepted' ? 'rgba(34,197,94,0.1)' : round.decision === 'counter' ? 'rgba(234,179,8,0.1)' : 'rgba(239,68,68,0.1)',
                            color: round.decision === 'accepted' ? '#22C55E' : round.decision === 'counter' ? '#EAB308' : '#EF4444',
                          }}>{round.decision}</span>
                          <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>{round.message?.substring(0, 60)}...</span>
                        </div>
                      ))}
                      {(session.status === 'negotiating' || session.status === 'final_offer') && (
                        <div className="flex items-center gap-2 mt-3">
                          {countering.session === session.session_id ? (
                            <>
                              <input type="number" className="px-2 py-1 rounded text-[10px] w-20"
                                style={{ background: 'rgba(61,58,57,0.15)', border: '1px solid rgba(255,107,0,0.12)', color: 'var(--aurem-heading)' }}
                                value={countering.discount}
                                onChange={(e) => setCountering({ ...countering, discount: parseFloat(e.target.value) || 0 })}
                                placeholder="%"
                              />
                              <button onClick={() => sendCounter(session.session_id, countering.discount)}
                                className="px-2 py-1 rounded text-[10px] font-bold"
                                style={{ background: 'rgba(59,130,246,0.15)', color: '#3B82F6' }}
                              ><Send className="w-3 h-3 inline" /> Send</button>
                            </>
                          ) : (
                            <button onClick={() => setCountering({ session: session.session_id, discount: 0 })}
                              className="px-3 py-1 rounded text-[10px] font-bold"
                              style={{ background: 'rgba(234,179,8,0.1)', color: '#EAB308' }}
                              data-testid={`counter-btn-${session.session_id}`}
                            >Counter Offer</button>
                          )}
                          <button onClick={() => acceptOffer(session.session_id)}
                            className="px-3 py-1 rounded text-[10px] font-bold"
                            style={{ background: 'rgba(34,197,94,0.1)', color: '#22C55E' }}
                            data-testid={`accept-btn-${session.session_id}`}
                          >Accept Current Offer</button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
