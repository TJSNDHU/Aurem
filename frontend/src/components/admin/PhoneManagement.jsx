/**
 * Phone Management Dashboard Component
 * ═══════════════════════════════════════════════════════════════════
 * Admin interface for managing global phone numbers via Telnyx.
 * 
 * Features:
 * - View provisioned phone numbers by country
 * - Provision new numbers in 13+ countries
 * - Release/delete numbers
 * - Cost breakdown and billing summary
 * 
 * Mock Mode: Works without TELNYX_API_KEY for testing
 * ═══════════════════════════════════════════════════════════════════
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Phone, Globe, Plus, Trash2, DollarSign, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Country flags (emoji)
const FLAGS = {
  CA: '🇨🇦', US: '🇺🇸', GB: '🇬🇧', FR: '🇫🇷', DE: '🇩🇪',
  AU: '🇦🇺', IN: '🇮🇳', AE: '🇦🇪', SA: '🇸🇦', SG: '🇸🇬',
  JP: '🇯🇵', BR: '🇧🇷', MX: '🇲🇽'
};

export default function PhoneManagement({ tenantId = 'reroots' }) {
  const [numbers, setNumbers] = useState([]);
  const [countries, setCountries] = useState([]);
  const [totalCost, setTotalCost] = useState(0);
  const [isTelnyxConfigured, setIsTelnyxConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [provisioning, setProvisioning] = useState(false);
  const [selectedCountry, setSelectedCountry] = useState('');
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Fetch phone numbers and countries
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch countries
      const countriesRes = await fetch(`${API_URL}/api/admin/phone/countries`);
      const countriesData = await countriesRes.json();
      
      if (countriesData.success) {
        setCountries(countriesData.countries || []);
        setIsTelnyxConfigured(countriesData.telnyx_configured || false);
      }

      // Fetch numbers
      const numbersRes = await fetch(`${API_URL}/api/admin/phone/numbers?tenant_id=${tenantId}`);
      const numbersData = await numbersRes.json();
      
      if (numbersData.success) {
        setNumbers(numbersData.numbers || []);
        setTotalCost(numbersData.total_monthly_cost_usd || 0);
      }
    } catch (err) {
      setError('Failed to load phone data');
      console.error('Phone fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Provision a new number
  const provisionNumber = async () => {
    if (!selectedCountry) {
      setError('Please select a country');
      return;
    }

    setProvisioning(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const response = await fetch(`${API_URL}/api/admin/phone/provision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          country_code: selectedCountry,
          tenant_id: tenantId
        })
      });

      const data = await response.json();

      if (data.success) {
        setSuccessMessage(`Provisioned ${data.phone_number} in ${data.country}`);
        setSelectedCountry('');
        fetchData(); // Refresh list
      } else {
        setError(data.detail || data.error || 'Provisioning failed');
      }
    } catch (err) {
      setError('Provisioning failed - check network');
      console.error('Provision error:', err);
    } finally {
      setProvisioning(false);
    }
  };

  // Release a number
  const releaseNumber = async (phoneNumber) => {
    if (!window.confirm(`Release ${phoneNumber}? This cannot be undone.`)) {
      return;
    }

    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/admin/phone/release`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone_number: phoneNumber,
          tenant_id: tenantId
        })
      });

      const data = await response.json();

      if (data.success) {
        setSuccessMessage(`Released ${phoneNumber}`);
        fetchData(); // Refresh list
      } else {
        setError(data.detail || data.error || 'Release failed');
      }
    } catch (err) {
      setError('Release failed - check network');
      console.error('Release error:', err);
    }
  };

  // Group numbers by country
  const numbersByCountry = numbers.reduce((acc, num) => {
    const country = num.country || 'UNKNOWN';
    if (!acc[country]) acc[country] = [];
    acc[country].push(num);
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12" data-testid="phone-loading">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <span className="ml-3 text-gray-600">Loading phone numbers...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="phone-management">
      {/* Header with Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Globe className="w-8 h-8 text-blue-500" />
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Global Phone Numbers</h2>
            <p className="text-sm text-gray-500">
              {isTelnyxConfigured ? (
                <span className="flex items-center gap-1 text-green-600">
                  <CheckCircle className="w-4 h-4" /> Telnyx Connected
                </span>
              ) : (
                <span className="flex items-center gap-1 text-amber-600">
                  <AlertCircle className="w-4 h-4" /> Mock Mode (add TELNYX_API_KEY for real numbers)
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Monthly Cost */}
        <div className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg">
          <DollarSign className="w-5 h-5 text-gray-600" />
          <span className="font-medium">${totalCost.toFixed(2)}</span>
          <span className="text-gray-500">/month</span>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700" data-testid="phone-error">
          {error}
        </div>
      )}
      {successMessage && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700" data-testid="phone-success">
          {successMessage}
        </div>
      )}

      {/* Provision New Number */}
      <div className="p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
        <h3 className="text-lg font-medium mb-4 flex items-center gap-2">
          <Plus className="w-5 h-5" />
          Provision New Number
        </h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={selectedCountry}
            onChange={(e) => setSelectedCountry(e.target.value)}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            data-testid="country-select"
          >
            <option value="">Select a country...</option>
            {countries.map((country) => (
              <option key={country.code} value={country.code}>
                {FLAGS[country.code] || '🌍'} {country.name} - ${country.monthly_cost_usd}/mo
              </option>
            ))}
          </select>
          <button
            onClick={provisionNumber}
            disabled={!selectedCountry || provisioning}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            data-testid="provision-btn"
          >
            {provisioning ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Provisioning...
              </>
            ) : (
              <>
                <Phone className="w-4 h-4" />
                Provision Number
              </>
            )}
          </button>
        </div>
      </div>

      {/* Numbers List */}
      <div className="space-y-4">
        {numbers.length === 0 ? (
          <div className="p-8 text-center bg-gray-50 rounded-xl border border-gray-200">
            <Phone className="w-12 h-12 mx-auto text-gray-400 mb-3" />
            <p className="text-gray-600">No phone numbers provisioned yet</p>
            <p className="text-sm text-gray-500 mt-1">Select a country above to get started</p>
          </div>
        ) : (
          Object.entries(numbersByCountry).map(([country, countryNumbers]) => (
            <div
              key={country}
              className="bg-white border border-gray-200 rounded-xl overflow-hidden"
              data-testid={`country-section-${country}`}
            >
              <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{FLAGS[country] || '🌍'}</span>
                  <span className="font-medium">
                    {countries.find((c) => c.code === country)?.name || country}
                  </span>
                  <span className="text-sm text-gray-500">
                    ({countryNumbers.length} number{countryNumbers.length !== 1 ? 's' : ''})
                  </span>
                </div>
                <span className="text-sm text-gray-600">
                  ${countryNumbers.reduce((sum, n) => sum + (n.monthly_cost_usd || 0), 0).toFixed(2)}/mo
                </span>
              </div>
              <div className="divide-y divide-gray-100">
                {countryNumbers.map((num, idx) => (
                  <div
                    key={num.phone_number || idx}
                    className="px-4 py-3 flex items-center justify-between hover:bg-gray-50"
                  >
                    <div>
                      <p className="font-mono text-lg">{num.phone_number}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {num.is_mock && (
                          <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs rounded">
                            MOCK
                          </span>
                        )}
                        <span className="text-sm text-gray-500">
                          ${num.monthly_cost_usd}/mo
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => releaseNumber(num.phone_number)}
                      className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                      title="Release number"
                      data-testid={`release-${num.phone_number}`}
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Supported Countries Overview */}
      <div className="p-4 bg-gray-50 rounded-xl border border-gray-200">
        <h3 className="text-sm font-medium text-gray-600 mb-3">Supported Countries</h3>
        <div className="flex flex-wrap gap-2">
          {countries.map((country) => (
            <div
              key={country.code}
              className="px-3 py-1 bg-white rounded-full border border-gray-200 text-sm flex items-center gap-1"
            >
              <span>{FLAGS[country.code] || '🌍'}</span>
              <span>{country.code}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
