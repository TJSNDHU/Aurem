import React from 'react';
import { AlertTriangle, RefreshCw, WifiOff } from 'lucide-react';

/**
 * ServiceGuard — wraps dashboard views to catch API / render failures.
 * If the child component throws during render, this shows a recoverable
 * "Service Unavailable" pane instead of a white-screen crash.
 *
 * Usage:
 *   <ServiceGuard name="Voice Analytics">
 *     <VoiceAnalytics token={token} />
 *   </ServiceGuard>
 */
class ServiceGuard extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error(`[ServiceGuard] ${this.props.name || 'Unknown'} crashed:`, error, info);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="flex-1 flex items-center justify-center"
          style={{ background: 'transparent' }}
          data-testid="service-unavailable"
        >
          <div
            className="text-center p-10 rounded-2xl max-w-md"
            style={{
              background: 'rgba(255,255,255,0.6)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(45,122,74,0.15)',
            }}
          >
            <div
              className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-5"
              style={{ background: 'rgba(212,175,55,0.08)' }}
            >
              <WifiOff className="w-7 h-7" style={{ color: '#D4AF37' }} />
            </div>

            <h2 className="text-lg font-semibold mb-1" style={{ color: '#1A1A2E' }}>
              Service Unavailable
            </h2>

            <p className="text-sm mb-1" style={{ color: '#555' }}>
              <span className="font-medium" style={{ color: '#2D7A4A' }}>
                {this.props.name || 'This module'}
              </span>{' '}
              could not be loaded.
            </p>

            <p className="text-xs mb-6" style={{ color: '#888' }}>
              The backend service may be offline or undergoing maintenance.
            </p>

            <button
              onClick={this.handleRetry}
              className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-xs font-medium transition-all hover:scale-105"
              style={{
                background: 'linear-gradient(135deg, #2D7A4A, #3a9960)',
                color: '#fff',
              }}
              data-testid="service-retry-btn"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Retry
            </button>

            {this.state.error && (
              <details className="mt-4 text-left">
                <summary className="text-[10px] cursor-pointer" style={{ color: '#999' }}>
                  <AlertTriangle className="w-3 h-3 inline mr-1" />
                  Error details
                </summary>
                <pre
                  className="mt-2 p-2 rounded text-[10px] overflow-auto max-h-24"
                  style={{ background: 'rgba(0,0,0,0.03)', color: '#666' }}
                >
                  {this.state.error.message}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ServiceGuard;
