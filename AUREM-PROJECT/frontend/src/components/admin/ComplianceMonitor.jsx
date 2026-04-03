import React, { useState, useEffect, useCallback } from 'react';
import { 
  Shield, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  Search,
  RefreshCw,
  FileText,
  Clock,
  Filter,
  ChevronDown,
  ChevronUp,
  Loader2,
  AlertCircle
} from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

export default function ComplianceMonitor() {
  const [scanHistory, setScanHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [testContent, setTestContent] = useState('');
  const [scanResult, setScanResult] = useState(null);
  const [severityFilter, setSeverityFilter] = useState('all');
  const [expandedScan, setExpandedScan] = useState(null);
  const [deepScan, setDeepScan] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      };

      // Fetch history and stats in parallel
      const [historyRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/compliance/history?limit=50${severityFilter !== 'all' ? `&severity=${severityFilter}` : ''}`, { headers }),
        fetch(`${API_URL}/api/compliance/stats`, { headers })
      ]);

      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setScanHistory(historyData.scans || []);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData.stats);
      }
    } catch (error) {
      console.error('Failed to fetch compliance data:', error);
    } finally {
      setLoading(false);
    }
  }, [severityFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleScan = async () => {
    if (!testContent.trim()) return;

    setScanning(true);
    setScanResult(null);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/compliance/scan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` })
        },
        body: JSON.stringify({
          content: testContent,
          content_type: 'manual_test',
          deep_scan: deepScan
        })
      });

      if (response.ok) {
        const result = await response.json();
        setScanResult(result);
        // Refresh history after scan
        fetchData();
      }
    } catch (error) {
      console.error('Scan failed:', error);
      setScanResult({ error: 'Scan failed. Please try again.' });
    } finally {
      setScanning(false);
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'CRITICAL':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'WARNING':
        return 'text-amber-600 bg-amber-50 border-amber-200';
      case 'PASS':
        return 'text-green-600 bg-green-50 border-green-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'CRITICAL':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'WARNING':
        return <AlertTriangle className="w-5 h-5 text-amber-500" />;
      case 'PASS':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      default:
        return <AlertCircle className="w-5 h-5 text-gray-500" />;
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="p-6 space-y-6" data-testid="compliance-monitor">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-8 h-8 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Compliance Monitor</h1>
            <p className="text-sm text-gray-500">Health Canada cosmetic claim scanner</p>
          </div>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-sm text-gray-500 mb-1">Total Scans</div>
            <div className="text-2xl font-bold text-gray-900">{stats.total_scans}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-sm text-gray-500 mb-1">Compliance Rate</div>
            <div className="text-2xl font-bold text-green-600">{stats.compliance_rate}%</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-sm text-gray-500 mb-1">Critical Issues</div>
            <div className="text-2xl font-bold text-red-600">{stats.critical}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-sm text-gray-500 mb-1">Warnings</div>
            <div className="text-2xl font-bold text-amber-600">{stats.warning}</div>
          </div>
        </div>
      )}

      {/* Test Scanner */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Search className="w-5 h-5" />
          Test Content Scanner
        </h2>
        
        <div className="space-y-4">
          <textarea
            value={testContent}
            onChange={(e) => setTestContent(e.target.value)}
            placeholder="Paste your content here to check for Health Canada compliance issues..."
            className="w-full h-32 p-4 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
            data-testid="compliance-test-input"
          />
          
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={deepScan}
                onChange={(e) => setDeepScan(e.target.checked)}
                className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              Deep AI scan (uses Claude for nuanced analysis)
            </label>
            
            <button
              onClick={handleScan}
              disabled={scanning || !testContent.trim()}
              className="flex items-center gap-2 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              data-testid="compliance-scan-button"
            >
              {scanning ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Scanning...
                </>
              ) : (
                <>
                  <Shield className="w-4 h-4" />
                  Scan Content
                </>
              )}
            </button>
          </div>
        </div>

        {/* Scan Result */}
        {scanResult && (
          <div className={`mt-6 p-4 rounded-lg border ${getSeverityColor(scanResult.severity)}`} data-testid="compliance-scan-result">
            <div className="flex items-start gap-3">
              {getSeverityIcon(scanResult.severity)}
              <div className="flex-1">
                <div className="font-semibold flex items-center gap-2">
                  {scanResult.blocked ? (
                    <span className="text-red-700">Content Blocked</span>
                  ) : scanResult.severity === 'WARNING' ? (
                    <span className="text-amber-700">Compliance Warnings</span>
                  ) : (
                    <span className="text-green-700">Content Approved</span>
                  )}
                  <span className="text-sm font-normal">
                    ({scanResult.critical_count} critical, {scanResult.warning_count} warnings)
                  </span>
                </div>
                
                {scanResult.issues && scanResult.issues.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {scanResult.issues.map((issue, idx) => (
                      <div key={idx} className="text-sm bg-white/60 rounded p-3">
                        <div className="flex items-start gap-2">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            issue.severity === 'CRITICAL' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                          }`}>
                            {issue.severity}
                          </span>
                          <span className="font-medium">"{issue.phrase}"</span>
                        </div>
                        <p className="mt-1 text-gray-600">{issue.reason}</p>
                        {issue.suggested && (
                          <p className="mt-1 text-green-700">
                            Suggested: "{issue.suggested}"
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {scanResult.message && (
                  <p className="mt-3 text-sm italic text-gray-600">
                    AI Assessment: {scanResult.message}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Scan History */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Scan History
          </h2>
          
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-indigo-500"
              data-testid="compliance-filter"
            >
              <option value="all">All Severities</option>
              <option value="CRITICAL">Critical Only</option>
              <option value="WARNING">Warnings Only</option>
              <option value="PASS">Passed Only</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto" />
            <p className="mt-2 text-gray-500">Loading scan history...</p>
          </div>
        ) : scanHistory.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <Shield className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No scans found. Use the scanner above to check content.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {scanHistory.map((scan, idx) => (
              <div 
                key={idx}
                className="p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                onClick={() => setExpandedScan(expandedScan === idx ? null : idx)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {getSeverityIcon(scan.severity)}
                    <div>
                      <div className="font-medium text-gray-900">
                        {scan.content_type || 'General'} Content
                      </div>
                      <div className="text-sm text-gray-500 flex items-center gap-2">
                        <Clock className="w-3 h-3" />
                        {formatDate(scan.scanned_at)}
                        <span className="mx-1">·</span>
                        {scan.issue_count || 0} issues
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(scan.severity)}`}>
                      {scan.severity}
                    </span>
                    {expandedScan === idx ? (
                      <ChevronUp className="w-4 h-4 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    )}
                  </div>
                </div>

                {expandedScan === idx && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <div className="text-sm text-gray-600 mb-3">
                      <span className="font-medium">Preview:</span> {scan.content_preview}
                    </div>
                    
                    {scan.issues && scan.issues.length > 0 && (
                      <div className="space-y-2">
                        {scan.issues.map((issue, issueIdx) => (
                          <div key={issueIdx} className="text-sm bg-gray-50 rounded p-3">
                            <div className="flex items-start gap-2">
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                issue.severity === 'CRITICAL' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                              }`}>
                                {issue.severity}
                              </span>
                              <span className="font-medium">"{issue.phrase}"</span>
                            </div>
                            <p className="mt-1 text-gray-600">{issue.reason}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
