import React, { useState, useEffect } from 'react';
import { AlertTriangle, Phone, Mail, MessageSquare, Globe, Clock } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Language flag emojis
const LANGUAGE_FLAGS = {
  'en': '🇺🇸',
  'fr': '🇫🇷',
  'es': '🇪🇸',
  'de': '🇩🇪',
  'zh': '🇨🇳',
  'ja': '🇯🇵',
  'it': '🇮🇹',
  'pt': '🇵🇹',
  'ru': '🇷🇺',
  'ar': '🇸🇦',
  'hi': '🇮🇳'
};

const PanicAlerts = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showOriginal, setShowOriginal] = useState({});

  useEffect(() => {
    loadAlerts();
    // Refresh every 10 seconds for real-time updates
    const interval = setInterval(loadAlerts, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadAlerts = async () => {
    try {
      const response = await fetch(`${API_URL}/api/panic/events?tenant_id=aurem_platform&status=triggered&limit=20`);
      const data = await response.json();
      if (data.success) {
        setAlerts(data.events);
      }
    } catch (error) {
      console.error('Failed to load panic alerts:', error);
    } finally {
      setLoading(false);
    }
  };

  const takeControl = async (conversationId) => {
    try {
      const response = await fetch(`${API_URL}/api/panic/takeover/${conversationId}?tenant_id=aurem_platform`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        alert('✓ You are now in control. AI responses paused.');
        loadAlerts();
      }
    } catch (error) {
      console.error('Failed to take control:', error);
      alert('Failed to take control');
    }
  };

  const toggleTranslation = (eventId) => {
    setShowOriginal(prev => ({
      ...prev,
      [eventId]: !prev[eventId]
    }));
  };

  const getTimeAgo = (timestamp) => {
    const now = new Date();
    const created = new Date(timestamp);
    const seconds = Math.floor((now - created) / 1000);
    
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pink-600"></div>
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
        <AlertTriangle className="w-12 h-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-600 font-medium">No active panic alerts</p>
        <p className="text-sm text-gray-500 mt-1">All conversations are running smoothly</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-6 h-6 text-red-600" />
          <h2 className="text-2xl font-bold text-gray-900">
            Active Panic Alerts
            <span className="ml-3 text-sm font-normal text-gray-500">
              ({alerts.length} need attention)
            </span>
          </h2>
        </div>
      </div>

      {/* Alert Cards */}
      <div className="space-y-4">
        {alerts.map((alert) => {
          const language = alert.detected_language || 'en';
          const flag = LANGUAGE_FLAGS[language] || '🌐';
          const isOriginal = showOriginal[alert.event_id];
          const displayMessage = isOriginal 
            ? alert.original_message 
            : (alert.english_translation || alert.last_message);

          return (
            <div
              key={alert.event_id}
              className="panic-active bg-white rounded-lg border-2 overflow-hidden"
              style={{
                borderColor: '#E2B19D',
                animation: 'panic-pulse 2.5s ease-in-out infinite'
              }}
            >
              {/* Alert Header */}
              <div className="bg-gradient-to-r from-red-50 to-pink-50 px-6 py-4 border-b border-red-100">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5 text-red-600" />
                      <h3 className="text-lg font-semibold text-gray-900">
                        {alert.customer?.name || 'Unknown Customer'}
                      </h3>
                      <span className="text-2xl">{flag}</span>
                      <span className="text-xs font-medium text-gray-500 uppercase">
                        {language}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600">
                      {getTimeAgo(alert.created_at)}
                    </span>
                  </div>
                </div>

                {/* Contact Info */}
                <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                  {alert.customer?.email && alert.customer.email !== 'N/A' && (
                    <div className="flex items-center gap-1">
                      <Mail className="w-4 h-4" />
                      <span>{alert.customer.email}</span>
                    </div>
                  )}
                  {alert.customer?.phone && alert.customer.phone !== 'N/A' && (
                    <div className="flex items-center gap-1">
                      <Phone className="w-4 h-4" />
                      <span>{alert.customer.phone}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Alert Body */}
              <div className="px-6 py-4">
                {/* Sentiment & Trigger Info */}
                <div className="flex items-center gap-4 mb-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-700">Sentiment:</span>
                    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
                      alert.sentiment_score < -0.8 ? 'bg-red-100 text-red-700' :
                      alert.sentiment_score < -0.5 ? 'bg-orange-100 text-orange-700' :
                      'bg-yellow-100 text-yellow-700'
                    }`}>
                      {alert.sentiment_label?.toUpperCase()} ({alert.sentiment_score?.toFixed(2)})
                    </span>
                  </div>

                  {alert.detected_keywords?.length > 0 && (
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-700">Keywords:</span>
                      <div className="flex gap-2">
                        {alert.detected_keywords.slice(0, 3).map((keyword) => (
                          <span
                            key={keyword}
                            className="px-2 py-1 bg-red-50 text-red-600 rounded text-xs font-medium"
                          >
                            {keyword}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Message */}
                <div className="bg-gray-50 rounded-lg p-4 mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <MessageSquare className="w-4 h-4 text-gray-600" />
                      <span className="text-sm font-medium text-gray-700">
                        {isOriginal ? 'Original Message' : 'English Translation'}
                      </span>
                    </div>
                    
                    {language !== 'en' && alert.english_translation && (
                      <button
                        onClick={() => toggleTranslation(alert.event_id)}
                        className="text-xs text-pink-600 hover:text-pink-700 font-medium flex items-center gap-1"
                      >
                        <Globe className="w-3 h-3" />
                        {isOriginal ? 'Show Translation' : 'Show Original'}
                      </button>
                    )}
                  </div>
                  
                  <p className="text-gray-900 italic">
                    "{displayMessage}"
                  </p>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3">
                  <button
                    onClick={() => takeControl(alert.conversation_id)}
                    className="flex-1 px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 font-semibold flex items-center justify-center gap-2"
                  >
                    <AlertTriangle className="w-5 h-5" />
                    Take Manual Control
                  </button>
                  
                  <button
                    onClick={() => window.location.href = `/conversation/${alert.conversation_id}`}
                    className="px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-lg hover:border-gray-400 font-semibold"
                  >
                    View Conversation
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* CSS for subtle "breathing" animation - Scientific-Luxe aesthetic */}
      <style>{`
        @keyframes panic-pulse {
          0%, 100% {
            box-shadow: 0 0 12px rgba(226, 177, 157, 0.4), 0 0 24px rgba(226, 177, 157, 0.2);
          }
          50% {
            box-shadow: 0 0 24px rgba(226, 177, 157, 0.7), 0 0 40px rgba(226, 177, 157, 0.4);
          }
        }
        
        .panic-active {
          position: relative;
        }
      `}</style>
    </div>
  );
};

export default PanicAlerts;
