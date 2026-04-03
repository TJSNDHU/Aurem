/**
 * AUREM Circuit Breaker Dashboard
 * Visual status of all circuit breakers protecting external services
 */

import React, { useState, useEffect } from 'react';
import { 
  Activity, AlertTriangle, CheckCircle, XCircle, 
  RotateCcw, TrendingUp, Clock, Zap 
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const CircuitBreakerCard = ({ breaker, onReset }) => {
  const isOpen = breaker.state === 'open';
  const isHalfOpen = breaker.state === 'half_open';
  const isClosed = breaker.state === 'closed';
  
  const stateColor = {
    'closed': '#4A4',
    'open': '#F44',
    'half_open': '#FA4'
  }[breaker.state];

  const StateIcon = {
    'closed': CheckCircle,
    'open': XCircle,
    'half_open': AlertTriangle
  }[breaker.state];

  return (
    <div style={{
      background: '#0A0A0A',
      border: `1px solid ${isOpen ? '#3A1A1A' : isHalfOpen ? '#3A2A1A' : '#1A3A1A'}`,
      borderRadius: 12,
      padding: 16,
      position: 'relative'
    }}>
      {/* State Badge */}
      <div style={{
        position: 'absolute',
        top: 12,
        right: 12,
        padding: '4px 10px',
        background: `${stateColor}20`,
        border: `1px solid ${stateColor}40`,
        borderRadius: 6,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 11,
        color: stateColor,
        fontWeight: 600,
        textTransform: 'uppercase'
      }}>
        <StateIcon className="w-3 h-3" />
        {breaker.state.replace('_', ' ')}
      </div>

      {/* Service Name */}
      <div style={{
        fontSize: 16,
        fontWeight: 600,
        color: '#F4F4F4',
        marginBottom: 12,
        textTransform: 'capitalize'
      }}>
        {breaker.name}
      </div>

      {/* Stats Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 12,
        marginBottom: 12
      }}>
        {/* Failures */}
        <div style={{
          background: '#050505',
          padding: 10,
          borderRadius: 8,
          border: '1px solid #1A1A1A'
        }}>
          <div style={{fontSize: 11, color: '#666', marginBottom: 4}}>Failures</div>
          <div style={{fontSize: 18, fontWeight: 700, color: isOpen ? '#F44' : '#F4F4F4'}}>
            {breaker.failures} / {breaker.threshold}
          </div>
        </div>

        {/* Failure Rate */}
        <div style={{
          background: '#050505',
          padding: 10,
          borderRadius: 8,
          border: '1px solid #1A1A1A'
        }}>
          <div style={{fontSize: 11, color: '#666', marginBottom: 4}}>Failure Rate</div>
          <div style={{fontSize: 18, fontWeight: 700, color: '#F4F4F4'}}>
            {breaker.stats?.failure_rate || 0}%
          </div>
        </div>
      </div>

      {/* Total Stats */}
      <div style={{
        display: 'flex',
        gap: 16,
        fontSize: 11,
        color: '#888',
        marginBottom: 12
      }}>
        <div style={{display: 'flex', alignItems: 'center', gap: 4}}>
          <Activity className="w-3 h-3" />
          {breaker.stats?.total_calls || 0} calls
        </div>
        <div style={{display: 'flex', alignItems: 'center', gap: 4}}>
          <XCircle className="w-3 h-3" />
          {breaker.stats?.total_failures || 0} failures
        </div>
        {breaker.stats?.total_blocks > 0 && (
          <div style={{display: 'flex', alignItems: 'center', gap: 4, color: '#F88'}}>
            <AlertTriangle className="w-3 h-3" />
            {breaker.stats?.total_blocks} blocked
          </div>
        )}
      </div>

      {/* Last Activity */}
      {(breaker.last_failure || breaker.last_success) && (
        <div style={{
          padding: 10,
          background: '#050505',
          borderRadius: 8,
          border: '1px solid #1A1A1A',
          fontSize: 11,
          color: '#666',
          marginBottom: 12
        }}>
          {breaker.last_failure && (
            <div style={{marginBottom: 4}}>
              Last failure: {new Date(breaker.last_failure).toLocaleString()}
            </div>
          )}
          {breaker.last_success && (
            <div>
              Last success: {new Date(breaker.last_success).toLocaleString()}
            </div>
          )}
        </div>
      )}

      {/* Reset Button (only if not closed) */}
      {!isClosed && (
        <button
          onClick={() => onReset(breaker.name)}
          style={{
            width: '100%',
            padding: '8px 0',
            background: 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
            border: 'none',
            borderRadius: 8,
            color: '#050505',
            fontWeight: 600,
            fontSize: 12,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6
          }}
        >
          <RotateCcw className="w-3 h-3" />
          Reset Circuit
        </button>
      )}
    </div>
  );
};

const CircuitBreakerDashboard = ({ token }) => {
  const [breakers, setBreakers] = useState(null);
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(null);

  useEffect(() => {
    loadBreakers();
    // Refresh every 30 seconds
    const interval = setInterval(loadBreakers, 30000);
    return () => clearInterval(interval);
  }, [token]);

  const loadBreakers = async () => {
    if (!token) return;
    
    try {
      const response = await fetch(`${API_URL}/api/system/circuit-breakers`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setBreakers(data);
    } catch (err) {
      console.error('Failed to load circuit breakers:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (service) => {
    setResetting(service);
    
    try {
      await fetch(`${API_URL}/api/system/circuit-breakers/reset?service=${service}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      // Reload breakers
      await loadBreakers();
    } catch (err) {
      console.error('Failed to reset circuit breaker:', err);
    } finally {
      setResetting(null);
    }
  };

  const handleResetAll = async () => {
    setResetting('all');
    
    try {
      await fetch(`${API_URL}/api/system/circuit-breakers/reset`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      await loadBreakers();
    } catch (err) {
      console.error('Failed to reset all circuit breakers:', err);
    } finally {
      setResetting(null);
    }
  };

  if (loading) {
    return (
      <div style={{padding: 24, textAlign: 'center', color: '#666'}}>
        <Activity className="w-8 h-8 mx-auto mb-4 animate-pulse" />
        Loading circuit breakers...
      </div>
    );
  }

  if (!breakers) {
    return (
      <div style={{padding: 24, textAlign: 'center', color: '#666'}}>
        Failed to load circuit breakers
      </div>
    );
  }

  const breakerList = Object.values(breakers.breakers || {});
  const openCount = breakerList.filter(b => b.state === 'open').length;

  return (
    <div style={{padding: 24}}>
      {/* Header */}
      <div style={{marginBottom: 24}}>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8}}>
          <div>
            <h2 style={{fontSize: 24, fontWeight: 600, color: '#F4F4F4', marginBottom: 4}}>
              Circuit Breakers
            </h2>
            <p style={{fontSize: 14, color: '#666'}}>
              Protecting {breakers.total_breakers} external services
            </p>
          </div>
          
          {openCount > 0 && (
            <button
              onClick={handleResetAll}
              disabled={resetting === 'all'}
              style={{
                padding: '10px 20px',
                background: 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
                border: 'none',
                borderRadius: 8,
                color: '#050505',
                fontWeight: 600,
                fontSize: 14,
                cursor: resetting === 'all' ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                opacity: resetting === 'all' ? 0.6 : 1
              }}
            >
              <RotateCcw className={`w-4 h-4 ${resetting === 'all' ? 'animate-spin' : ''}`} />
              Reset All
            </button>
          )}
        </div>

        {/* Summary Stats */}
        <div style={{display: 'flex', gap: 16}}>
          <div style={{
            padding: '12px 20px',
            background: openCount > 0 ? '#1A0A0A' : '#0A1A0A',
            border: `1px solid ${openCount > 0 ? '#3A1A1A' : '#1A3A1A'}`,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 10
          }}>
            {openCount > 0 ? (
              <AlertTriangle className="w-5 h-5 text-[#F44]" />
            ) : (
              <CheckCircle className="w-5 h-5 text-[#4A4]" />
            )}
            <div>
              <div style={{fontSize: 20, fontWeight: 700, color: openCount > 0 ? '#F44' : '#4A4'}}>
                {openCount}
              </div>
              <div style={{fontSize: 11, color: '#888', textTransform: 'uppercase'}}>
                Open Circuits
              </div>
            </div>
          </div>

          <div style={{
            padding: '12px 20px',
            background: '#0A0A0A',
            border: '1px solid #1A1A1A',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 10
          }}>
            <Zap className="w-5 h-5 text-[#D4AF37]" />
            <div>
              <div style={{fontSize: 20, fontWeight: 700, color: '#F4F4F4'}}>
                {breakers.total_breakers}
              </div>
              <div style={{fontSize: 11, color: '#888', textTransform: 'uppercase'}}>
                Total Breakers
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Breakers Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: 16
      }}>
        {breakerList.map((breaker) => (
          <CircuitBreakerCard
            key={breaker.name}
            breaker={breaker}
            onReset={handleReset}
          />
        ))}
      </div>
    </div>
  );
};

export default CircuitBreakerDashboard;
