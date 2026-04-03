/**
 * Language Analytics Dashboard Component
 * ═══════════════════════════════════════════════════════════════════
 * Displays customer language breakdown and multilingual AI stats.
 * 
 * Features:
 * - Pie/bar chart of customer languages
 * - RTL language indicators
 * - Language detection confidence stats
 * ═══════════════════════════════════════════════════════════════════
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Globe2, Languages, ArrowLeft, ArrowRight, BarChart3, Loader2 } from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Language flags/icons
const LANG_ICONS = {
  en: '🇬🇧', es: '🇪🇸', fr: '🇫🇷', de: '🇩🇪', it: '🇮🇹',
  pt: '🇵🇹', nl: '🇳🇱', ru: '🇷🇺', zh: '🇨🇳', ja: '🇯🇵',
  ko: '🇰🇷', ar: '🇸🇦', he: '🇮🇱', fa: '🇮🇷', ur: '🇵🇰',
  hi: '🇮🇳', bn: '🇧🇩', ta: '🇮🇳', vi: '🇻🇳', th: '🇹🇭',
  tr: '🇹🇷', pl: '🇵🇱', uk: '🇺🇦', cs: '🇨🇿', ro: '🇷🇴',
};

export default function LanguageAnalytics() {
  const [analytics, setAnalytics] = useState({ total_customers: 0, languages: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch language analytics
  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/chat-widget/language-analytics`, {
        headers: { 'X-Brand-Key': 'reroots' }
      });
      
      const data = await response.json();
      setAnalytics(data);
    } catch (err) {
      setError('Failed to load language analytics');
      console.error('Language analytics error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  // Calculate max for scaling
  const maxCount = Math.max(...analytics.languages.map(l => l.count), 1);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8" data-testid="lang-loading">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
        <span className="ml-2 text-gray-600">Loading language data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700" data-testid="lang-error">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="language-analytics">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Languages className="w-5 h-5 text-blue-500" />
          <h3 className="font-semibold text-gray-900">Customer Languages</h3>
        </div>
        <span className="text-sm text-gray-500">
          {analytics.total_customers} total customers
        </span>
      </div>

      {/* Language Bars */}
      {analytics.languages.length === 0 ? (
        <div className="p-6 text-center bg-gray-50 rounded-lg">
          <Globe2 className="w-8 h-8 mx-auto text-gray-400 mb-2" />
          <p className="text-gray-600">No language data yet</p>
          <p className="text-sm text-gray-500">Language is detected from customer messages</p>
        </div>
      ) : (
        <div className="space-y-3">
          {analytics.languages.slice(0, 10).map((lang) => (
            <div key={lang.code} className="flex items-center gap-3">
              {/* Language icon/flag */}
              <div className="w-8 text-center text-xl">
                {LANG_ICONS[lang.code] || <Globe2 className="w-5 h-5 text-gray-400 mx-auto" />}
              </div>
              
              {/* Language info */}
              <div className="w-24 flex-shrink-0">
                <p className="font-medium text-sm text-gray-900">{lang.name}</p>
                <p className="text-xs text-gray-500">{lang.native_name}</p>
              </div>
              
              {/* Bar */}
              <div className="flex-1 h-8 bg-gray-100 rounded-lg overflow-hidden relative">
                <div
                  className={`h-full rounded-lg transition-all ${
                    lang.is_rtl 
                      ? 'bg-gradient-to-r from-amber-400 to-amber-500' 
                      : 'bg-gradient-to-r from-blue-400 to-blue-500'
                  }`}
                  style={{ width: `${(lang.count / maxCount) * 100}%` }}
                />
                <span className="absolute inset-0 flex items-center px-3 text-sm font-medium text-gray-700">
                  {lang.count} ({lang.percentage}%)
                </span>
              </div>
              
              {/* RTL indicator */}
              {lang.is_rtl && (
                <div className="flex items-center gap-1 px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs">
                  <ArrowLeft className="w-3 h-3" />
                  RTL
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 pt-4 border-t border-gray-200">
        <div className="flex items-center gap-2 text-sm">
          <div className="w-3 h-3 rounded bg-blue-500" />
          <span className="text-gray-600">LTR Languages</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <div className="w-3 h-3 rounded bg-amber-500" />
          <span className="text-gray-600">RTL Languages (Arabic, Hebrew, etc.)</span>
        </div>
      </div>

      {/* Multilingual Status */}
      <div className="p-3 bg-blue-50 rounded-lg flex items-start gap-3">
        <BarChart3 className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm">
          <p className="font-medium text-blue-900">Multilingual AI Active</p>
          <p className="text-blue-700 mt-1">
            The AI automatically detects customer language and responds in their native language.
            RTL languages (Arabic, Hebrew, Urdu, Persian) have special text direction support.
          </p>
        </div>
      </div>
    </div>
  );
}
