import React, { useState, useEffect } from 'react';
import { TrendingUp, Globe, Briefcase, MessageSquare, BarChart3, Users } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const ADMIN_KEY = 'aurem_admin_2024_secure';

const AnalyticsDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [insights, setInsights] = useState(null);
  const [dateRange, setDateRange] = useState(30);

  useEffect(() => {
    loadInsights();
  }, [dateRange]);

  const loadInsights = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `${API_URL}/api/admin/analytics/insights?date_range_days=${dateRange}`,
        {
          headers: {
            'X-Admin-Key': ADMIN_KEY
          }
        }
      );
      const data = await response.json();
      if (data.success) {
        setInsights(data.insights);
      }
    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pink-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (!insights) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">No analytics data available</p>
      </div>
    );
  }

  const topIndustries = Object.entries(insights.by_industry || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  const topCountries = Object.entries(insights.by_geography || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">AUREM Intelligence Dashboard</h1>
              <p className="text-gray-600">
                Anonymized insights across all tenants • Privacy-first analytics
              </p>
            </div>
            
            <select
              value={dateRange}
              onChange={(e) => setDateRange(parseInt(e.target.value))}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-600">Total Leads</h3>
              <Users className="w-5 h-5 text-pink-600" />
            </div>
            <p className="text-3xl font-bold text-gray-900">{insights.total_leads.toLocaleString()}</p>
            <p className="text-sm text-gray-500 mt-2">
              {insights.previous_period_total > 0 && (
                <span className={insights.growth_rate >= 0 ? 'text-green-600' : 'text-red-600'}>
                  {insights.growth_rate >= 0 ? '↑' : '↓'} {Math.abs(insights.growth_rate)}%
                </span>
              )}
              {' '}vs previous period
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-600">Industries</h3>
              <Briefcase className="w-5 h-5 text-pink-600" />
            </div>
            <p className="text-3xl font-bold text-gray-900">
              {Object.keys(insights.by_industry || {}).length}
            </p>
            <p className="text-sm text-gray-500 mt-2">Active verticals</p>
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-600">Countries</h3>
              <Globe className="w-5 h-5 text-pink-600" />
            </div>
            <p className="text-3xl font-bold text-gray-900">
              {Object.keys(insights.by_geography || {}).length}
            </p>
            <p className="text-sm text-gray-500 mt-2">Geographic reach</p>
          </div>
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Industry Breakdown */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Briefcase className="w-5 h-5 text-pink-600" />
              <h3 className="text-lg font-semibold text-gray-900">Top Industries</h3>
            </div>
            
            <div className="space-y-4">
              {topIndustries.map(([industry, count]) => {
                const percentage = (count / insights.total_leads * 100).toFixed(1);
                return (
                  <div key={industry}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium text-gray-700">{industry}</span>
                      <span className="text-gray-600">{count} ({percentage}%)</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-pink-600 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${percentage}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Geographic Distribution */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Globe className="w-5 h-5 text-pink-600" />
              <h3 className="text-lg font-semibold text-gray-900">Top Countries</h3>
            </div>
            
            <div className="space-y-4">
              {topCountries.map(([country, count]) => {
                const percentage = (count / insights.total_leads * 100).toFixed(1);
                return (
                  <div key={country}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium text-gray-700">{country}</span>
                      <span className="text-gray-600">{count} ({percentage}%)</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${percentage}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Trending Topics */}
        {insights.trending_topics && insights.trending_topics.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
            <div className="flex items-center gap-2 mb-4">
              <MessageSquare className="w-5 h-5 text-pink-600" />
              <h3 className="text-lg font-semibold text-gray-900">Trending Topics</h3>
            </div>
            
            <div className="flex flex-wrap gap-3">
              {insights.trending_topics.map(({ topic, count }) => (
                <div
                  key={topic}
                  className="px-4 py-2 bg-pink-50 text-pink-700 rounded-full text-sm font-medium"
                >
                  {topic} ({count})
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Privacy Notice */}
        <div className="bg-gray-100 border border-gray-300 rounded-lg p-4">
          <div className="flex gap-3">
            <BarChart3 className="w-5 h-5 text-gray-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-gray-700">
              <p className="font-semibold mb-1">Privacy-First Analytics</p>
              <p className="text-gray-600">
                This dashboard shows anonymized aggregate data only. No customer PII (names, emails, phone numbers) 
                is stored or displayed. Customer data belongs exclusively to tenants.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
