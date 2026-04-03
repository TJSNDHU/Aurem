/**
 * ProductSyncStatus Component
 * ═══════════════════════════════════════════════════════════════════
 * Real-time dashboard showing product status across both brands.
 * Displays: stock level, last updated, CNF filing status, live status.
 * ═══════════════════════════════════════════════════════════════════
 */

import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Brand owner mapping
const BRAND_OWNERS = {
  'AURA-GEN': 'Reroots Aesthetics Inc.',
  'La Vela Bianca': 'Reroots Aesthetics Inc.',
  'OROÉ': 'Polaris Built Inc.',
  'reroots': 'Reroots Aesthetics Inc.',
  'lavela': 'Reroots Aesthetics Inc.',
  'oroe': 'Polaris Built Inc.',
};

const getBrandOwner = (brand) => {
  if (!brand) return 'Unknown';
  const normalized = brand.toLowerCase();
  for (const [key, owner] of Object.entries(BRAND_OWNERS)) {
    if (normalized.includes(key.toLowerCase())) {
      return owner;
    }
  }
  return 'Reroots Aesthetics Inc.'; // Default
};

const getRowStatus = (product) => {
  const isLive = product.is_live ?? product.isActive ?? true;
  const cnfFiled = product.cnf_filed ?? false;
  
  if (isLive && cnfFiled) return 'green';
  if (cnfFiled && !isLive) return 'yellow';
  return 'red';
};

const StatusBadge = ({ status }) => {
  const styles = {
    green: { background: '#14532d', color: '#4ade80', border: '1px solid #22c55e' },
    yellow: { background: '#422006', color: '#fbbf24', border: '1px solid #eab308' },
    red: { background: '#450a0a', color: '#f87171', border: '1px solid #ef4444' },
  };
  
  const labels = {
    green: 'Ready',
    yellow: 'CNF Only',
    red: 'Not Ready',
  };
  
  return (
    <span style={{
      ...styles[status],
      padding: '4px 10px',
      borderRadius: '12px',
      fontSize: '0.75rem',
      fontWeight: 500,
      textTransform: 'uppercase',
      letterSpacing: '0.5px',
    }}>
      {labels[status]}
    </span>
  );
};

const ProductSyncStatus = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastFetched, setLastFetched] = useState(null);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const token = localStorage.getItem('adminToken') || localStorage.getItem('token');
      const response = await fetch(`${API_BASE}/api/admin/products/sync-status`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setProducts(Array.isArray(data) ? data : data.products || []);
      setLastFetched(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Failed to fetch product sync status:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Never';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-CA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div style={{
      background: '#141414',
      borderRadius: '12px',
      border: '1px solid #262626',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '16px 20px',
        borderBottom: '1px solid #262626',
        background: '#1a1a1a',
      }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: '#fff' }}>
            Product Sync Status
          </h3>
          {lastFetched && (
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#888' }}>
              Last updated: {lastFetched}
            </p>
          )}
        </div>
        <button
          onClick={fetchProducts}
          disabled={loading}
          style={{
            background: '#262626',
            border: '1px solid #404040',
            borderRadius: '6px',
            padding: '8px 16px',
            color: '#e5e5e5',
            fontSize: '0.85rem',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          {loading ? '⏳' : '🔄'} Refresh
        </button>
      </div>

      {/* Error State */}
      {error && (
        <div style={{
          padding: '16px 20px',
          background: '#450a0a',
          borderBottom: '1px solid #dc2626',
          color: '#fca5a5',
          fontSize: '0.9rem',
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '0.9rem',
        }}>
          <thead>
            <tr style={{ background: '#1a1a1a' }}>
              {['Product Name', 'Brand Owner', 'Stock', 'CNF Filed', 'Live', 'Last Updated', 'Status'].map((header) => (
                <th key={header} style={{
                  padding: '12px 16px',
                  textAlign: 'left',
                  fontWeight: 500,
                  color: '#888',
                  fontSize: '0.8rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  borderBottom: '1px solid #262626',
                }}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && products.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#888' }}>
                  Loading products...
                </td>
              </tr>
            ) : products.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#888' }}>
                  No products found
                </td>
              </tr>
            ) : (
              products.map((product, idx) => {
                const status = getRowStatus(product);
                const brandOwner = product.brand_owner || getBrandOwner(product.brand);
                const isLive = product.is_live ?? product.isActive ?? true;
                const cnfFiled = product.cnf_filed ?? false;
                
                return (
                  <tr key={product.id || idx} style={{
                    borderBottom: '1px solid #262626',
                    background: idx % 2 === 0 ? 'transparent' : '#1a1a1a',
                  }}>
                    <td style={{ padding: '12px 16px', color: '#fff', fontWeight: 500 }}>
                      {product.name || 'Unnamed'}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#888' }}>
                      {brandOwner}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{
                        color: (product.stock ?? 0) > 10 ? '#4ade80' : (product.stock ?? 0) > 0 ? '#fbbf24' : '#f87171',
                        fontWeight: 500,
                      }}>
                        {product.stock ?? 0}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      {cnfFiled ? (
                        <span style={{ color: '#4ade80' }}>✓ Filed</span>
                      ) : (
                        <span style={{ color: '#888' }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      {isLive ? (
                        <span style={{ color: '#4ade80' }}>✓ Live</span>
                      ) : (
                        <span style={{ color: '#888' }}>Draft</span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#888', fontSize: '0.85rem' }}>
                      {formatDate(product.last_updated || product.updated_at)}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <StatusBadge status={status} />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Footer Summary */}
      {products.length > 0 && (
        <div style={{
          padding: '12px 20px',
          borderTop: '1px solid #262626',
          background: '#1a1a1a',
          display: 'flex',
          gap: '24px',
          fontSize: '0.8rem',
          color: '#888',
        }}>
          <span>Total: {products.length}</span>
          <span style={{ color: '#4ade80' }}>
            Ready: {products.filter(p => getRowStatus(p) === 'green').length}
          </span>
          <span style={{ color: '#fbbf24' }}>
            CNF Only: {products.filter(p => getRowStatus(p) === 'yellow').length}
          </span>
          <span style={{ color: '#f87171' }}>
            Not Ready: {products.filter(p => getRowStatus(p) === 'red').length}
          </span>
        </div>
      )}
    </div>
  );
};

export default ProductSyncStatus;
