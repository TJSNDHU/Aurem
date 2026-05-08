/**
 * GitHub Lead Miner Dashboard
 * Intelligence & Growth - ORA-Powered Lead Discovery
 */

import React, { useState, useEffect } from 'react';
import { Users, Mail, Phone, Github, TrendingUp, Zap, ExternalLink, Loader } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const GitHubLeadMiner = ({ token }) => {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchLeads();
    fetchStats();
  }, []);

  const fetchLeads = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/growth/leads?limit=50`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      setLeads(data.leads || []);
    } catch (error) {
      console.error('Failed to fetch leads:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/growth/stats`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const triggerSync = async () => {
    setSyncing(true);
    try {
      const response = await fetch(`${API_URL}/api/growth/github/sync`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          repo_url: 'example/repo',
          scan_depth: 'full'
        })
      });
      
      if (response.ok) {
        await fetchLeads();
        await fetchStats();
      }
    } catch (error) {
      console.error('Sync failed:', error);
    } finally {
      setSyncing(false);
    }
  };

  const triggerOutreach = async (lead) => {
    try {
      await fetch(`${API_URL}/api/growth/outreach/trigger`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          lead_id: lead.lead_id,
          channels: ['email', 'whatsapp'],
          priority: 'high'
        })
      });
      
      alert(`ORA Outbound triggered for ${lead.name || lead.email}`);
    } catch (error) {
      console.error('Outreach failed:', error);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-[#4A4]';
    if (score >= 60) return 'text-[#FA4]';
    return 'text-[#888]';
  };

  const getScoreBg = (score) => {
    if (score >= 80) return 'bg-[#0A2A0A] border-[#2A5A2A]';
    if (score >= 60) return 'bg-[#2A1A0A] border-[#5A3A1A]';
    return 'bg-[#1A1A1A] border-[#2A2A2A]';
  };

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 400
      }}>
        <Loader className="w-8 h-8 animate-spin text-[#D4AF37]" />
      </div>
    );
  }

  return (
    <div style={{padding: 24, color: '#F4F4F4'}}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 24
      }}>
        <div>
          <h1 style={{fontSize: 24, fontWeight: 600, marginBottom: 4}}>
            Intelligence & Growth
          </h1>
          <p style={{fontSize: 13, color: '#888'}}>
            ORA-Powered Lead Discovery from GitHub
          </p>
        </div>
        
        <button
          onClick={triggerSync}
          disabled={syncing}
          style={{
            padding: '10px 20px',
            background: syncing ? '#333' : 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
            border: 'none',
            borderRadius: 8,
            color: '#050505',
            fontSize: 13,
            fontWeight: 600,
            cursor: syncing ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}
        >
          {syncing ? (
            <>
              <Loader className="w-4 h-4 animate-spin" />
              Syncing...
            </>
          ) : (
            <>
              <Github className="w-4 h-4" />
              Sync GitHub
            </>
          )}
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 16,
          marginBottom: 24
        }}>
          <div style={{
            padding: 16,
            background: '#0A0A0A',
            border: '1px solid #1A1A1A',
            borderRadius: 12
          }}>
            <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8}}>
              <Users className="w-4 h-4 text-[#D4AF37]" />
              <span style={{fontSize: 11, color: '#888', textTransform: 'uppercase'}}>
                Total Leads
              </span>
            </div>
            <div style={{fontSize: 24, fontWeight: 600}}>
              {stats.total_leads || 0}
            </div>
          </div>

          <div style={{
            padding: 16,
            background: '#0A0A0A',
            border: '1px solid #1A1A1A',
            borderRadius: 12
          }}>
            <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8}}>
              <TrendingUp className="w-4 h-4 text-[#4A4]" />
              <span style={{fontSize: 11, color: '#888', textTransform: 'uppercase'}}>
                High Value
              </span>
            </div>
            <div style={{fontSize: 24, fontWeight: 600}}>
              {stats.high_value_leads || 0}
            </div>
          </div>

          <div style={{
            padding: 16,
            background: '#0A0A0A',
            border: '1px solid #1A1A1A',
            borderRadius: 12
          }}>
            <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8}}>
              <Zap className="w-4 h-4 text-[#FA4]" />
              <span style={{fontSize: 11, color: '#888', textTransform: 'uppercase'}}>
                Avg ORA Score
              </span>
            </div>
            <div style={{fontSize: 24, fontWeight: 600}}>
              {stats.average_score ? Math.round(stats.average_score) : 0}
            </div>
          </div>
        </div>
      )}

      {/* Leads Table */}
      <div style={{
        background: '#0A0A0A',
        border: '1px solid #1A1A1A',
        borderRadius: 12,
        overflow: 'hidden'
      }}>
        <div style={{
          padding: '12px 16px',
          borderBottom: '1px solid #1A1A1A',
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}>
          <Github className="w-4 h-4 text-[#D4AF37]" />
          <span style={{fontSize: 13, fontWeight: 600}}>
            Discovered Leads ({leads.length})
          </span>
        </div>

        {leads.length === 0 ? (
          <div style={{
            padding: 40,
            textAlign: 'center',
            color: '#666'
          }}>
            <Github className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p style={{fontSize: 14}}>
              No leads discovered yet
            </p>
            <p style={{fontSize: 12, marginTop: 4}}>
              Click "Sync GitHub" to mine repositories for potential leads
            </p>
          </div>
        ) : (
          <div style={{maxHeight: 600, overflowY: 'auto'}}>
            {leads.map((lead, index) => (
              <div
                key={lead.lead_id || index}
                style={{
                  padding: 16,
                  borderBottom: index < leads.length - 1 ? '1px solid #1A1A1A' : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 16,
                  transition: 'background 0.2s'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#0F0F0F'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                {/* ORA Score Badge */}
                <div style={{
                  width: 60,
                  height: 60,
                  borderRadius: 12,
                  border: '1px solid',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
                className={getScoreBg(lead.ora_score || 0)}
                >
                  <div style={{
                    fontSize: 20,
                    fontWeight: 700
                  }}
                  className={getScoreColor(lead.ora_score || 0)}
                  >
                    {lead.ora_score || 0}
                  </div>
                  <div style={{fontSize: 9, color: '#666', textTransform: 'uppercase'}}>
                    Score
                  </div>
                </div>

                {/* Lead Info */}
                <div style={{flex: 1}}>
                  <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4}}>
                    <span style={{fontSize: 14, fontWeight: 600}}>
                      {lead.name || 'Unknown'}
                    </span>
                    {lead.github_profile && (
                      <a
                        href={lead.github_profile}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{color: '#888'}}
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                  
                  <div style={{display: 'flex', alignItems: 'center', gap: 16, fontSize: 12, color: '#888'}}>
                    {lead.email && (
                      <div style={{display: 'flex', alignItems: 'center', gap: 6}}>
                        <Mail className="w-3 h-3" />
                        {lead.email}
                      </div>
                    )}
                    {lead.phone && (
                      <div style={{display: 'flex', alignItems: 'center', gap: 6}}>
                        <Phone className="w-3 h-3" />
                        {lead.phone}
                      </div>
                    )}
                  </div>

                  {lead.source && (
                    <div style={{fontSize: 11, color: '#666', marginTop: 4}}>
                      Source: {lead.source}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <button
                  onClick={() => triggerOutreach(lead)}
                  style={{
                    padding: '8px 16px',
                    background: 'linear-gradient(135deg, #4A4 0%, #2A2 100%)',
                    border: 'none',
                    borderRadius: 8,
                    color: '#FFF',
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6
                  }}
                >
                  <Zap className="w-3 h-3" />
                  ORA Outbound
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default GitHubLeadMiner;
