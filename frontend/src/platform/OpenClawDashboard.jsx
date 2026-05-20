import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { Users, Shield, Heart, DollarSign, Palette, RefreshCw, Loader2, CheckCircle, ChevronDown, ChevronUp, Save, Edit3 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function OpenClawDashboard({ token, tenantId }) {
  const [tab, setTab] = useState('persona');
  const [persona, setPersona] = useState(null);
  const [permissions, setPermissions] = useState(null);
  const [heartbeat, setHeartbeat] = useState(null);
  const [cost, setCost] = useState(null);
  const [branding, setBranding] = useState(null);
  const [tiers, setTiers] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editPersona, setEditPersona] = useState(false);
  const [personaForm, setPersonaForm] = useState({});

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);
  const tid = tenantId || 'default';

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, permRes, hbRes, costRes, brandRes, tierRes] = await Promise.all([
        fetch(`${API}/api/openclaw/persona/${tid}`, { headers }),
        fetch(`${API}/api/openclaw/permissions/${tid}`, { headers }),
        fetch(`${API}/api/openclaw/heartbeat/${tid}`, { headers }),
        fetch(`${API}/api/openclaw/cost/${tid}`, { headers }),
        fetch(`${API}/api/openclaw/branding/${tid}`, { headers }),
        fetch(`${API}/api/openclaw/tiers`, { headers }),
      ]);
      if (pRes.ok) { const d = await pRes.json(); setPersona(d.persona); setPersonaForm(d.persona || {}); }
      if (permRes.ok) setPermissions(await permRes.json());
      if (hbRes.ok) setHeartbeat(await hbRes.json());
      if (costRes.ok) setCost(await costRes.json());
      if (brandRes.ok) setBranding(await brandRes.json());
      if (tierRes.ok) setTiers(await tierRes.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [tid, headers]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const savePersona = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/openclaw/persona/${tid}`, {
        method: 'PUT', headers,
        body: JSON.stringify(personaForm),
      });
      if (res.ok) { const d = await res.json(); setPersona(d.persona); setEditPersona(false); }
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const tabs = [
    { id: 'persona', label: 'Persona', icon: Users, color: '#FF6B00' },
    { id: 'permissions', label: 'Tool Permissions', icon: Shield, color: '#3B82F6' },
    { id: 'heartbeat', label: 'Heartbeat', icon: Heart, color: '#EF4444' },
    { id: 'cost', label: 'Cost Tracker', icon: DollarSign, color: '#22C55E' },
    { id: 'whitelabel', label: 'White Label', icon: Palette, color: '#8B5CF6' },
  ];

  const inputStyle = {
    background: 'rgba(45,122,74,0.05)',
    border: '1px solid rgba(255,107,0,0.1)',
    color: 'var(--aurem-heading)',
    borderRadius: '8px',
    padding: '6px 10px',
    fontSize: '11px',
    width: '100%',
  };

  return (
    <div className="flex-1 overflow-auto p-6" style={{ background: 'transparent' }} data-testid="openclaw-dashboard">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>OpenClaw Command Center</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            Per-tenant persona, permissions, heartbeat, cost tracking, and white-label
          </p>
        </div>
        <button onClick={fetchAll} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-[1.02]"
          style={{ background: 'rgba(61,58,57,0.25)', color: 'var(--aurem-heading)' }}
          data-testid="openclaw-refresh-btn">
          <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {tabs.map(({ id, label, icon: Icon, color }) => (
          <button key={id}
            onClick={() => setTab(id)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-[11px] font-semibold whitespace-nowrap transition-all"
            style={{
              background: tab === id ? `${color}15` : 'transparent',
              color: tab === id ? color : 'var(--aurem-body-secondary)',
              border: tab === id ? `1px solid ${color}30` : '1px solid transparent',
            }}
            data-testid={`tab-${id}`}
          >
            <Icon className="size-3.5" /> {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="size-6 animate-spin" style={{ color: 'var(--aurem-body-secondary)' }} />
        </div>
      ) : (
        <>
          {/* PERSONA TAB */}
          {tab === 'persona' && persona && (
            <div className="aurem-glass-card p-6" data-testid="persona-section">
              <div className="flex items-center justify-between mb-4">
                <div className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>
                  ORA Personality Profile, SOUL.md
                </div>
                <button onClick={() => editPersona ? savePersona() : setEditPersona(true)}
                  disabled={saving}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-[10px] font-semibold"
                  style={{ background: 'rgba(212,163,115,0.15)', color: '#FF6B00' }}
                  data-testid="persona-edit-btn"
                >
                  {saving ? <Loader2 className="size-3 animate-spin" /> : editPersona ? <Save className="size-3" /> : <Edit3 className="size-3" />}
                  {editPersona ? 'Save' : 'Edit'}
                </button>
              </div>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { key: 'ora_name', label: 'ORA Name' },
                  { key: 'business_name', label: 'Business Name' },
                  { key: 'industry', label: 'Industry' },
                  { key: 'tone', label: 'Tone' },
                  { key: 'greeting', label: 'Greeting' },
                  { key: 'sign_off', label: 'Sign-off' },
                  { key: 'language_style', label: 'Language Style' },
                ].map(({ key, label }) => (
                  <div key={key}>
                    <label className="text-[10px] font-medium block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>{label}</label>
                    {editPersona ? (
                      <input style={inputStyle} value={personaForm[key] || ''}
                        onChange={(e) => setPersonaForm({ ...personaForm, [key]: e.target.value })}
                        data-testid={`persona-input-${key}`}
                      />
                    ) : (
                      <div className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>{persona[key] || '-'}</div>
                    )}
                  </div>
                ))}
              </div>
              {/* Words lists */}
              <div className="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <label className="text-[10px] font-medium block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Preferred Words</label>
                  {editPersona ? (
                    <input style={inputStyle}
                      value={(personaForm.preferred_words || []).join(', ')}
                      onChange={(e) => setPersonaForm({ ...personaForm, preferred_words: e.target.value.split(',').map(w => w.trim()).filter(Boolean) })}
                      placeholder="investment, results, clinical"
                      data-testid="persona-input-preferred"
                    />
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {(persona.preferred_words || []).map((w, i) => (
                        <span key={i} className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(34,197,94,0.1)', color: '#22C55E' }}>{w}</span>
                      ))}
                      {(!persona.preferred_words || persona.preferred_words.length === 0) && <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>None set</span>}
                    </div>
                  )}
                </div>
                <div>
                  <label className="text-[10px] font-medium block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Avoid Words</label>
                  {editPersona ? (
                    <input style={inputStyle}
                      value={(personaForm.avoid_words || []).join(', ')}
                      onChange={(e) => setPersonaForm({ ...personaForm, avoid_words: e.target.value.split(',').map(w => w.trim()).filter(Boolean) })}
                      placeholder="cheap, deal"
                      data-testid="persona-input-avoid"
                    />
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {(persona.avoid_words || []).map((w, i) => (
                        <span key={i} className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(239,68,68,0.1)', color: '#EF4444' }}>{w}</span>
                      ))}
                      {(!persona.avoid_words || persona.avoid_words.length === 0) && <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>None set</span>}
                    </div>
                  )}
                </div>
              </div>
              {/* Custom knowledge */}
              <div className="mt-4">
                <label className="text-[10px] font-medium block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Custom Business Knowledge</label>
                {editPersona ? (
                  <textarea style={{ ...inputStyle, minHeight: '60px' }}
                    value={personaForm.custom_knowledge || ''}
                    onChange={(e) => setPersonaForm({ ...personaForm, custom_knowledge: e.target.value })}
                    data-testid="persona-input-knowledge"
                  />
                ) : (
                  <div className="text-xs" style={{ color: 'var(--aurem-heading)' }}>{persona.custom_knowledge || 'No custom knowledge set'}</div>
                )}
              </div>
            </div>
          )}

          {/* PERMISSIONS TAB */}
          {tab === 'permissions' && permissions && (
            <div data-testid="permissions-section">
              <div className="aurem-glass-card p-5 mb-4">
                <div className="flex items-center gap-3 mb-3">
                  <div className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>
                    Current Tier: <span style={{ color: '#3B82F6' }}>{permissions.tier?.toUpperCase()}</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(59,130,246,0.1)', color: '#3B82F6' }}>
                    {permissions.total_allowed === 'unlimited' ? 'All tools' : `${permissions.total_allowed} tools`}
                  </span>
                </div>
                {/* Tier comparison */}
                {tiers && (
                  <div className="grid grid-cols-3 gap-3 mt-4">
                    {['starter', 'growth', 'enterprise'].map(tier => {
                      const t = tiers.tiers?.[tier];
                      const isCurrent = permissions.tier === tier;
                      return (
                        <div key={tier} className="p-3 rounded-xl" style={{
                          background: isCurrent ? 'rgba(59,130,246,0.08)' : 'rgba(255,107,0,0.03)',
                          border: isCurrent ? '1px solid rgba(59,130,246,0.2)' : '1px solid rgba(61,58,57,0.15)',
                        }}>
                          <div className="text-[10px] font-bold mb-2" style={{ color: isCurrent ? '#3B82F6' : 'var(--aurem-heading)' }}>
                            {tier.toUpperCase()} {isCurrent && '(current)'}
                          </div>
                          <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                            {t?.total_allowed === 'unlimited' ? 'All tools' : `${t?.total_allowed || 0} tools`}
                          </div>
                          {t?.denied?.length > 0 && (
                            <div className="mt-2">
                              <div className="text-[9px] font-medium" style={{ color: '#EF4444' }}>Denied:</div>
                              {t.denied.map((d, i) => (
                                <div key={i} className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>{d}</div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
              {/* Allowed tools */}
              <div className="aurem-glass-card p-5">
                <div className="text-xs font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>Allowed Tools</div>
                <div className="flex flex-wrap gap-2">
                  {(permissions.allowed || []).map((tool, i) => (
                    <span key={i} className="text-[10px] px-2 py-1 rounded-lg" style={{ background: 'rgba(34,197,94,0.08)', color: '#22C55E', border: '1px solid rgba(34,197,94,0.15)' }}>
                      {tool}
                    </span>
                  ))}
                </div>
                {permissions.denied?.length > 0 && (
                  <>
                    <div className="text-xs font-bold mt-4 mb-3" style={{ color: '#EF4444' }}>Denied Tools (Upgrade Required)</div>
                    <div className="flex flex-wrap gap-2">
                      {permissions.denied.map((tool, i) => (
                        <span key={i} className="text-[10px] px-2 py-1 rounded-lg" style={{ background: 'rgba(239,68,68,0.08)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.15)' }}>
                          {tool}
                        </span>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* HEARTBEAT TAB */}
          {tab === 'heartbeat' && heartbeat && (
            <div className="aurem-glass-card p-6" data-testid="heartbeat-section">
              <div className="flex items-center gap-4 mb-6">
                <div className="size-16 rounded-2xl flex items-center justify-center" style={{
                  background: heartbeat.health_score >= 70 ? 'rgba(34,197,94,0.15)' : heartbeat.health_score >= 40 ? 'rgba(234,179,8,0.15)' : 'rgba(239,68,68,0.15)',
                }}>
                  <Heart className="size-8" style={{
                    color: heartbeat.health_score >= 70 ? '#22C55E' : heartbeat.health_score >= 40 ? '#EAB308' : '#EF4444',
                    animation: 'pulse 1.5s infinite',
                  }} />
                </div>
                <div>
                  <div className="text-3xl font-bold" style={{ color: 'var(--aurem-heading)' }}>{heartbeat.health_score}/100</div>
                  <div className="text-xs" style={{
                    color: heartbeat.status === 'healthy' ? '#22C55E' : heartbeat.status === 'degraded' ? '#EAB308' : '#EF4444',
                  }}>{heartbeat.status?.toUpperCase()}</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 rounded-xl" style={{ background: 'rgba(255,107,0,0.04)' }}>
                  <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Pipeline</div>
                  <div className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{heartbeat.pipeline_status}</div>
                </div>
                <div className="p-3 rounded-xl" style={{ background: 'rgba(255,107,0,0.04)' }}>
                  <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Knowledge Entries</div>
                  <div className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{heartbeat.knowledge_entries || 0}</div>
                </div>
                <div className="p-3 rounded-xl" style={{ background: 'rgba(255,107,0,0.04)' }}>
                  <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Knowledge Age</div>
                  <div className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{heartbeat.knowledge_age_hours}h</div>
                </div>
                <div className="p-3 rounded-xl" style={{ background: 'rgba(255,107,0,0.04)' }}>
                  <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Last Session</div>
                  <div className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{heartbeat.last_session || 'N/A'}</div>
                </div>
              </div>
              {heartbeat.issues?.length > 0 && (
                <div className="mt-4 p-3 rounded-xl" style={{ background: 'rgba(234,179,8,0.05)', border: '1px solid rgba(234,179,8,0.15)' }}>
                  <div className="text-[10px] font-bold mb-2" style={{ color: '#EAB308' }}>Issues Detected</div>
                  {heartbeat.issues.map((issue, i) => (
                    <div key={i} className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{issue}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* COST TAB */}
          {tab === 'cost' && cost && (
            <div className="aurem-glass-card p-6" data-testid="cost-section">
              <div className="text-sm font-bold mb-4" style={{ color: 'var(--aurem-heading)' }}>
                Cost Report — {cost.month || 'Current Month'}
              </div>
              <div className="grid grid-cols-4 gap-4 mb-6">
                {[
                  { label: 'Total Requests', value: cost.total_requests || 0, color: '#3B82F6' },
                  { label: 'Estimated Cost', value: `$${(cost.estimated_cost_usd || 0).toFixed(2)}`, color: '#EAB308' },
                  { label: 'Actual Cost', value: `$${(cost.actual_cost_usd || 0).toFixed(2)}`, color: '#22C55E' },
                  { label: 'You Saved', value: `$${(cost.savings_usd || 0).toFixed(2)}`, color: '#FF6B00' },
                ].map(({ label, value, color }) => (
                  <div key={label} className="p-3 rounded-xl text-center" style={{ background: `${color}08`, border: `1px solid ${color}15` }}>
                    <div className="text-lg font-bold" style={{ color }}>{value}</div>
                    <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{label}</div>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-4">
                <div className="flex-1 h-3 rounded-full overflow-hidden" style={{ background: 'rgba(61,58,57,0.15)' }}>
                  <div className="h-full rounded-full" style={{
                    width: `${cost.free_pct || 100}%`,
                    background: 'linear-gradient(90deg, #22C55E, #16A34A)',
                  }} />
                </div>
                <div className="text-[10px] whitespace-nowrap" style={{ color: 'var(--aurem-body-secondary)' }}>
                  <span style={{ color: '#22C55E' }}>{cost.free_pct || 100}% free</span> / <span style={{ color: '#EAB308' }}>{cost.paid_pct || 0}% paid</span>
                </div>
              </div>
              <div className="mt-4 p-3 rounded-xl text-[10px]" style={{ background: 'rgba(34,197,94,0.05)', color: 'var(--aurem-body-secondary)' }}>
                Monthly retention email preview: "Your AUREM AI saved you ${(cost.savings_usd || 0).toFixed(2)} this month across {cost.total_requests || 0} AI actions."
              </div>
            </div>
          )}

          {/* WHITE-LABEL TAB */}
          {tab === 'whitelabel' && branding && (
            <div data-testid="whitelabel-section">
              <div className="aurem-glass-card p-6 mb-4">
                <div className="flex items-center gap-3 mb-4">
                  <Palette className="size-5" style={{ color: '#8B5CF6' }} />
                  <div className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>White-Label Command Center</div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(139,92,246,0.1)', color: '#8B5CF6' }}>
                    Enterprise Only
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  {[
                    { key: 'brand_name', label: 'Brand Name' },
                    { key: 'tagline', label: 'Tagline' },
                    { key: 'primary_color', label: 'Primary Color' },
                    { key: 'sidebar_bg', label: 'Sidebar Background' },
                    { key: 'domain', label: 'Custom Domain (CNAME)' },
                    { key: 'logo_url', label: 'Logo URL' },
                  ].map(({ key, label }) => (
                    <div key={key}>
                      <label className="text-[10px] font-medium block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>{label}</label>
                      <div className="flex items-center gap-2">
                        {key.includes('color') && branding[key] && (
                          <div className="size-5 rounded" style={{ background: branding[key], border: '1px solid rgba(255,255,255,0.1)' }} />
                        )}
                        <div className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>{branding[key] || '(not set)'}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              {/* CNAME Instructions */}
              <div className="aurem-glass-card p-6">
                <div className="text-xs font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>CNAME Setup Instructions</div>
                <div className="space-y-2 text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                  <div>1. Go to your DNS provider for <strong>{branding.domain || 'yourdomain.com'}</strong></div>
                  <div>2. Create a CNAME record:</div>
                  <div className="ml-4 font-mono p-2 rounded" style={{ background: 'rgba(45,122,74,0.05)' }}>
                    Host: ai &nbsp;&nbsp; Points to: aurem.live &nbsp;&nbsp; TTL: 300
                  </div>
                  <div>3. Wait 5-10 minutes for DNS propagation</div>
                  <div>4. Contact support@aurem.ai to activate SSL</div>
                </div>
                <div className="mt-4 p-3 rounded-xl text-[10px]" style={{ background: 'rgba(139,92,246,0.05)', border: '1px solid rgba(139,92,246,0.15)', color: '#8B5CF6' }}>
                  Enterprise pitch: "Your clients never know they're using AUREM. They log into your branded AI command center, with your colors, your domain, your name."
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
