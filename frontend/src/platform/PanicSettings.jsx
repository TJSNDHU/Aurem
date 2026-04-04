import React, { useState, useEffect } from 'react';
import { Shield, AlertTriangle, Phone, Mail, Globe, Sliders } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const PanicSettings = () => {
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState({
    enabled: true,
    alert_email: '',
    alert_phone: '',
    sensitivity_threshold: -0.7,
    custom_keywords: [],
    auto_pause_ai: true,
    alert_channels: ['email']
  });
  const [newKeyword, setNewKeyword] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await fetch(`${API_URL}/api/panic/settings?tenant_id=aurem_platform`);
      const data = await response.json();
      if (data.success) {
        setConfig(data.config);
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  };

  const saveSettings = async () => {
    try {
      setLoading(true);
      setSaved(false);
      
      const response = await fetch(`${API_URL}/api/panic/settings?tenant_id=aurem_platform`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      const data = await response.json();
      if (data.success) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      }
    } catch (error) {
      console.error('Failed to save settings:', error);
      alert('Failed to save settings');
    } finally {
      setLoading(false);
    }
  };

  const addKeyword = () => {
    if (newKeyword.trim() && !config.custom_keywords.includes(newKeyword.trim())) {
      setConfig({
        ...config,
        custom_keywords: [...config.custom_keywords, newKeyword.trim()]
      });
      setNewKeyword('');
    }
  };

  const removeKeyword = (keyword) => {
    setConfig({
      ...config,
      custom_keywords: config.custom_keywords.filter(k => k !== keyword)
    });
  };

  const toggleChannel = (channel) => {
    const channels = config.alert_channels.includes(channel)
      ? config.alert_channels.filter(c => c !== channel)
      : [...config.alert_channels, channel];
    
    setConfig({ ...config, alert_channels: channels });
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Shield className="w-8 h-8 text-pink-600" />
            <h1 className="text-3xl font-bold text-gray-900">Panic Button Configuration</h1>
          </div>
          <p className="text-gray-600">
            Configure your AI safety net. Get instant alerts when customers need human attention.
          </p>
        </div>

        {/* Main Settings Card */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          {/* Enable/Disable */}
          <div className="mb-6">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={config.enabled}
                onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
                className="w-5 h-5 text-pink-600 rounded focus:ring-pink-500"
              />
              <span className="text-lg font-semibold text-gray-900">
                Enable Panic Button
              </span>
            </label>
            <p className="text-sm text-gray-500 ml-8 mt-1">
              Automatically detect frustration and alert you for human intervention
            </p>
          </div>

          {config.enabled && (
            <>
              {/* Alert Contacts */}
              <div className="mb-6 pb-6 border-b">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Alert Contacts</h3>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      <Mail className="w-4 h-4 inline mr-2" />
                      Alert Email
                    </label>
                    <input
                      type="email"
                      value={config.alert_email || ''}
                      onChange={(e) => setConfig({ ...config, alert_email: e.target.value })}
                      placeholder="owner@business.com"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      <Phone className="w-4 h-4 inline mr-2" />
                      Alert Phone (SMS)
                    </label>
                    <input
                      type="tel"
                      value={config.alert_phone || ''}
                      onChange={(e) => setConfig({ ...config, alert_phone: e.target.value })}
                      placeholder="+1 234 567 8900"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Requires Twilio configuration
                    </p>
                  </div>
                </div>
              </div>

              {/* Sensitivity */}
              <div className="mb-6 pb-6 border-b">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  <Sliders className="w-5 h-5 inline mr-2" />
                  Sensitivity
                </h3>
                
                <div>
                  <div className="flex justify-between text-sm text-gray-600 mb-2">
                    <span>Less Sensitive</span>
                    <span className="font-semibold">{config.sensitivity_threshold.toFixed(2)}</span>
                    <span>More Sensitive</span>
                  </div>
                  <input
                    type="range"
                    min="-1.0"
                    max="-0.3"
                    step="0.1"
                    value={config.sensitivity_threshold}
                    onChange={(e) => setConfig({ ...config, sensitivity_threshold: parseFloat(e.target.value) })}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-pink-600"
                  />
                  <p className="text-xs text-gray-500 mt-2">
                    Lower values trigger alerts more frequently. Default: -0.7
                  </p>
                </div>
              </div>

              {/* Custom Keywords */}
              <div className="mb-6 pb-6 border-b">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Custom Panic Keywords</h3>
                
                <div className="flex gap-2 mb-3">
                  <input
                    type="text"
                    value={newKeyword}
                    onChange={(e) => setNewKeyword(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && addKeyword()}
                    placeholder="e.g., allergy, defect, broken"
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                  />
                  <button
                    onClick={addKeyword}
                    className="px-6 py-2 bg-pink-600 text-white rounded-lg hover:bg-pink-700 font-medium"
                  >
                    Add
                  </button>
                </div>

                <div className="flex flex-wrap gap-2">
                  {config.custom_keywords.map((keyword) => (
                    <span
                      key={keyword}
                      className="inline-flex items-center gap-2 px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
                    >
                      {keyword}
                      <button
                        onClick={() => removeKeyword(keyword)}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  {config.custom_keywords.length === 0 && (
                    <p className="text-sm text-gray-500">No custom keywords added</p>
                  )}
                </div>
              </div>

              {/* Alert Channels */}
              <div className="mb-6 pb-6 border-b">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Alert Channels</h3>
                
                <div className="space-y-3">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.alert_channels.includes('email')}
                      onChange={() => toggleChannel('email')}
                      className="w-5 h-5 text-pink-600 rounded focus:ring-pink-500"
                    />
                    <Mail className="w-5 h-5 text-gray-400" />
                    <span className="text-gray-700">Email Alerts</span>
                  </label>

                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.alert_channels.includes('sms')}
                      onChange={() => toggleChannel('sms')}
                      className="w-5 h-5 text-pink-600 rounded focus:ring-pink-500"
                    />
                    <Phone className="w-5 h-5 text-gray-400" />
                    <span className="text-gray-700">SMS Alerts</span>
                    <span className="text-xs text-gray-500">(Requires Twilio)</span>
                  </label>

                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.alert_channels.includes('webhook')}
                      onChange={() => toggleChannel('webhook')}
                      className="w-5 h-5 text-pink-600 rounded focus:ring-pink-500"
                    />
                    <Globe className="w-5 h-5 text-gray-400" />
                    <span className="text-gray-700">Webhook (Slack/Discord)</span>
                  </label>
                </div>
              </div>

              {/* Auto-Pause */}
              <div className="mb-6">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.auto_pause_ai}
                    onChange={(e) => setConfig({ ...config, auto_pause_ai: e.target.checked })}
                    className="w-5 h-5 text-pink-600 rounded focus:ring-pink-500"
                  />
                  <span className="text-gray-700 font-medium">
                    Auto-pause AI when panic triggered
                  </span>
                </label>
                <p className="text-sm text-gray-500 ml-8 mt-1">
                  AI will stop responding until you manually resume or resolve the issue
                </p>
              </div>
            </>
          )}

          {/* Save Button */}
          <div className="flex items-center gap-4 pt-4">
            <button
              onClick={saveSettings}
              disabled={loading}
              className="px-8 py-3 bg-pink-600 text-white rounded-lg hover:bg-pink-700 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Saving...' : 'Save Configuration'}
            </button>
            
            {saved && (
              <span className="text-green-600 font-medium">
                ✓ Settings saved successfully
              </span>
            )}
          </div>
        </div>

        {/* Info Box */}
        <div className="bg-pink-50 border border-pink-200 rounded-lg p-4">
          <div className="flex gap-3">
            <AlertTriangle className="w-5 h-5 text-pink-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-pink-900">
              <p className="font-semibold mb-1">How the Panic Button works:</p>
              <ul className="list-disc list-inside space-y-1 text-pink-800">
                <li>AI monitors every conversation for negative sentiment and keywords</li>
                <li>When triggered, you receive instant alerts via your chosen channels</li>
                <li>AI can auto-pause to prevent further automated responses</li>
                <li>You can take manual control and respond directly to the customer</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PanicSettings;
