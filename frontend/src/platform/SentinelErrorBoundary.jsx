/**
 * AUREM Sentinel Error Boundary — Self-Repair Loop
 * Catches React errors, shows AI-proactive messaging, and auto-retries.
 * No generic "Something went wrong" — only AI status updates.
 */
import React from 'react';
import { RefreshCw, Shield } from 'lucide-react';

class SentinelErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, retryCount: 0, errorInfo: null };
    this.retryTimer = null;
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('[Sentinel] Component error caught:', error, errorInfo);
    // Auto-retry micro-reset after 3 seconds
    if (this.state.retryCount < 3) {
      this.retryTimer = setTimeout(() => {
        this.setState(prev => ({ hasError: false, retryCount: prev.retryCount + 1 }));
      }, 3000);
    }
  }

  componentWillUnmount() {
    if (this.retryTimer) clearTimeout(this.retryTimer);
  }

  handleManualRetry = () => {
    this.setState({ hasError: false, retryCount: 0 });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-[200px] p-8" data-testid="sentinel-error-boundary">
          <div className="text-center max-w-md">
            <div className="w-14 h-14 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{
              background: 'rgba(255,107,0,0.08)',
              border: '1px solid rgba(255,107,0,0.15)',
              animation: 'pulse 2s ease-in-out infinite',
            }}>
              <Shield className="w-7 h-7 text-[#FF6B00]" />
            </div>
            <h3 className="text-sm font-bold mb-2" style={{ color: 'var(--aurem-heading)', fontFamily: 'Cinzel, Georgia, serif' }}>
              {this.state.retryCount < 3
                ? 'Recalibrating for peak accuracy...'
                : 'Module requires attention'}
            </h3>
            <p className="text-xs mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>
              {this.state.retryCount < 3
                ? `I'm optimizing the data stream, stay with me... (attempt ${this.state.retryCount + 1}/3)`
                : 'The Sentinel detected an anomaly in this module. Click below to reset.'}
            </p>
            {this.state.retryCount < 3 ? (
              <div className="flex items-center justify-center gap-2 text-[#FF6B00]">
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span className="text-xs font-medium">Auto-repairing...</span>
              </div>
            ) : (
              <button
                onClick={this.handleManualRetry}
                data-testid="sentinel-retry-btn"
                className="px-5 py-2.5 rounded-xl text-xs font-bold tracking-wider transition-all hover:scale-[1.02]"
                style={{
                  background: 'linear-gradient(135deg, #FF6B00, #CC5500)',
                  color: '#050507',
                  boxShadow: '0 4px 16px rgba(255,107,0,0.2)',
                }}
              >
                <RefreshCw className="w-3.5 h-3.5 inline mr-2" />
                RESET MODULE
              </button>
            )}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default SentinelErrorBoundary;
