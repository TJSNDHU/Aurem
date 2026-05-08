/**
 * AUREM Proximity Blast — Local Domination Module
 * Geofenced lead discovery with radius targeting
 * $49/month add-on for Starter/Growth tiers
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Target, MapPin, Zap, Users, Phone, Mail,
  ChevronRight, RefreshCw, Sliders, Search,
  ArrowRight, Building2, Star, Activity, Lock, Send, Rocket,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const RADIUS_MARKS = [5, 10, 15, 20, 25, 30, 40, 50];

const STATUS_COLORS = {
  new: { bg: 'rgba(255,107,0,0.1)', text: '#FF6B00', label: 'NEW' },
  contacted: { bg: 'rgba(59,130,246,0.1)', text: '#3b82f6', label: 'CONTACTED' },
  interested: { bg: 'rgba(74,222,128,0.1)', text: '#4ade80', label: 'INTERESTED' },
};

export const ProximityBlast = ({ token }) => {
  const [config, setConfig] = useState(null);
  const [leads, setLeads] = useState([]);
  const [radius, setRadius] = useState(10);
  const [loading, setLoading] = useState(false);
  const [blastRunning, setBlastRunning] = useState(false);
  const [campaigns, setCampaigns] = useState([]);
  const [totalFound, setTotalFound] = useState(0);
  const [envoyDeploying, setEnvoyDeploying] = useState(false);
  const [envoyDeployed, setEnvoyDeployed] = useState(false);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/proximity/config`, { headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } });
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
        setRadius(data.default_radius_km || 10);
      }
    } catch (e) { console.error('Config fetch error:', e); }
  }, [token]);

  const fetchCampaigns = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/proximity/campaigns`, { headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } });
      if (res.ok) {
        const data = await res.json();
        setCampaigns(data.campaigns || []);
      }
    } catch (e) { console.error('Campaigns fetch error:', e); }
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchConfig();
      fetchCampaigns();
    }
  }, [token, fetchConfig, fetchCampaigns]);

  const runBlast = async () => {
    setBlastRunning(true);
    setLeads([]);
    try {
      const lat = config?.business_lat || 43.6532;
      const lng = config?.business_lng || -79.3832;
      const res = await fetch(`${API_URL}/api/proximity/blast`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ lat, lng, radius_km: radius, count: 25 }),
      });
      if (res.ok) {
        const data = await res.json();
        setLeads(data.leads || []);
        setTotalFound(data.total || 0);
        fetchCampaigns();
      }
    } catch (e) { console.error('Blast error:', e); }
    setBlastRunning(false);
  };

  const deployEnvoy = async () => {
    setEnvoyDeploying(true);
    try {
      // Send leads to Envoy for automated outreach
      const res = await fetch(`${API_URL}/api/proximity/deploy-envoy`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          leads: leads.map(l => ({
            lead_id: l.lead_id,
            business_name: l.business_name,
            owner_name: l.owner_name,
            email: l.email,
            phone: l.phone,
            business_type: l.business_type,
            distance_km: l.distance_km,
          })),
          radius_km: radius,
        }),
      });
      if (res.ok) {
        setEnvoyDeployed(true);
        setTimeout(() => setEnvoyDeployed(false), 5000);
      }
    } catch (e) { console.error('Envoy deploy error:', e); }
    setEnvoyDeploying(false);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6" data-testid="proximity-blast">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold" style={{ color: 'var(--aurem-heading)', fontFamily: 'Cinzel, Georgia, serif' }}
            data-testid="proximity-title">
            Proximity Blast
          </h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
            Local lead discovery — find businesses within your radius
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-full text-[9px] font-bold tracking-wider" style={{
            background: config?.data_source === 'live' ? 'rgba(74,222,128,0.1)' : 'rgba(255,107,0,0.1)',
            color: config?.data_source === 'live' ? '#4ade80' : '#FF6B00',
            border: `1px solid ${config?.data_source === 'live' ? 'rgba(74,222,128,0.2)' : 'rgba(255,107,0,0.2)'}`,
          }} data-testid="data-source-badge">
            {config?.data_source === 'live' ? 'LIVE DATA' : 'SIMULATED'}
          </span>
          <span className="px-2.5 py-1 rounded-full text-[9px] font-bold tracking-wider" style={{
            background: 'rgba(212,185,119,0.1)',
            color: '#D4B977',
            border: '1px solid rgba(212,185,119,0.2)',
          }}>
            ADD-ON $49/mo
          </span>
        </div>
      </div>

      {/* Radius Control */}
      <div className="aurem-glass-card p-6" data-testid="radius-control">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{
            background: 'rgba(255,107,0,0.1)',
            border: '1px solid rgba(255,107,0,0.15)',
          }}>
            <Target className="w-5 h-5 text-[#FF6B00]" />
          </div>
          <div>
            <h3 className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>Target Radius</h3>
            <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
              Select how far to search for potential leads
            </p>
          </div>
        </div>

        {/* Slider */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono font-bold" style={{ color: '#FF6B00' }} data-testid="radius-value">
              {radius} km
            </span>
            <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
              ~{Math.round(radius * 0.621)} miles
            </span>
          </div>
          <input
            type="range"
            min={5}
            max={50}
            step={1}
            value={radius}
            onChange={(e) => setRadius(parseInt(e.target.value))}
            data-testid="radius-slider"
            className="w-full h-2 rounded-full appearance-none cursor-pointer"
            style={{
              background: `linear-gradient(to right, #FF6B00 ${(radius - 5) / 45 * 100}%, rgba(255,255,255,0.1) ${(radius - 5) / 45 * 100}%)`,
              accentColor: '#FF6B00',
            }}
          />
          <div className="flex justify-between mt-1">
            {RADIUS_MARKS.map(m => (
              <button
                key={m}
                onClick={() => setRadius(m)}
                className={`text-[9px] font-mono transition-colors ${radius === m ? 'text-[#FF6B00] font-bold' : ''}`}
                style={{ color: radius === m ? '#FF6B00' : 'var(--aurem-body-secondary)' }}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        {/* Blast Button */}
        <button
          onClick={runBlast}
          disabled={blastRunning}
          data-testid="blast-btn"
          className="w-full py-3 rounded-xl text-xs font-bold tracking-[2px] transition-all hover:scale-[1.01] disabled:opacity-50"
          style={{
            background: 'linear-gradient(135deg, #FF6B00, #CC5500)',
            color: '#050507',
            boxShadow: '0 4px 20px rgba(255,107,0,0.2)',
          }}
        >
          {blastRunning ? (
            <><RefreshCw className="w-4 h-4 inline mr-2 animate-spin" /> SCANNING AREA...</>
          ) : (
            <><Zap className="w-4 h-4 inline mr-2" /> LAUNCH PROXIMITY BLAST</>
          )}
        </button>
      </div>

      {/* Results */}
      {leads.length > 0 && (
        <div className="space-y-3" data-testid="blast-results">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>
              Leads Found ({totalFound})
            </h3>
            <div className="flex items-center gap-2">
              <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                within {radius}km radius
              </span>
              <button
                onClick={deployEnvoy}
                disabled={envoyDeploying || envoyDeployed}
                data-testid="deploy-envoy-btn"
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[10px] font-bold tracking-wider transition-all hover:scale-[1.02] disabled:opacity-50"
                style={{
                  background: envoyDeployed ? 'rgba(74,222,128,0.15)' : 'linear-gradient(135deg, #FF6B00, #CC5500)',
                  color: envoyDeployed ? '#4ade80' : '#050507',
                  boxShadow: envoyDeployed ? 'none' : '0 4px 16px rgba(255,107,0,0.2)',
                  border: envoyDeployed ? '1px solid rgba(74,222,128,0.3)' : 'none',
                }}
              >
                {envoyDeployed ? (
                  <><Star className="w-3 h-3" /> ENVOY DEPLOYED</>
                ) : envoyDeploying ? (
                  <><RefreshCw className="w-3 h-3 animate-spin" /> DEPLOYING...</>
                ) : (
                  <><Rocket className="w-3 h-3" /> DEPLOY ENVOY OUTREACH</>
                )}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {leads.map((lead) => {
              const statusStyle = STATUS_COLORS[lead.status] || STATUS_COLORS.new;
              return (
                <div
                  key={lead.lead_id}
                  className="aurem-glass-card p-4 transition-all hover:scale-[1.01]"
                  data-testid={`lead-card-${lead.lead_id}`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{
                        background: 'rgba(255,107,0,0.08)',
                        border: '1px solid rgba(255,107,0,0.12)',
                      }}>
                        <Building2 className="w-4 h-4 text-[#FF6B00]" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>
                          {lead.business_name}
                        </h4>
                        <p className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                          {lead.business_type}
                        </p>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded-full text-[8px] font-bold" style={{
                      background: statusStyle.bg,
                      color: statusStyle.text,
                    }}>
                      {statusStyle.label}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mb-2">
                    <div className="flex items-center gap-1.5">
                      <MapPin className="w-3 h-3" style={{ color: 'var(--aurem-body-secondary)' }} />
                      <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                        {lead.distance_km}km away
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Star className="w-3 h-3 text-[#D4B977]" />
                      <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                        {lead.rating} ({lead.review_count} reviews)
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <div className="h-1.5 w-16 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
                        <div className="h-full rounded-full" style={{
                          width: `${lead.match_score}%`,
                          background: lead.match_score > 80 ? '#4ade80' : lead.match_score > 60 ? '#FF6B00' : '#f59e0b',
                        }} />
                      </div>
                      <span className="text-[9px] font-bold" style={{
                        color: lead.match_score > 80 ? '#4ade80' : '#FF6B00',
                      }}>
                        {lead.match_score}% match
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button className="p-1 rounded-md hover:bg-white/5 transition-colors" title={lead.phone}>
                        <Phone className="w-3 h-3" style={{ color: 'var(--aurem-body-secondary)' }} />
                      </button>
                      <button className="p-1 rounded-md hover:bg-white/5 transition-colors" title={lead.email}>
                        <Mail className="w-3 h-3" style={{ color: 'var(--aurem-body-secondary)' }} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Campaign History */}
      {campaigns.length > 0 && (
        <div className="aurem-glass-card p-5" data-testid="campaign-history">
          <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>
            Campaign History
          </h3>
          <div className="space-y-2">
            {campaigns.slice(0, 5).map((c, i) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg" style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid rgba(255,255,255,0.04)',
              }}>
                <div className="flex items-center gap-2">
                  <Activity className="w-3 h-3 text-[#FF6B00]" />
                  <span className="text-[10px] font-medium" style={{ color: 'var(--aurem-heading)' }}>
                    {c.radius_km}km blast
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] font-mono" style={{ color: '#FF6B00' }}>
                    {c.leads_found} leads
                  </span>
                  <span className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                    {c.data_source === 'simulated' ? 'SIM' : 'LIVE'}
                  </span>
                  <span className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                    {new Date(c.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ProximityBlast;
