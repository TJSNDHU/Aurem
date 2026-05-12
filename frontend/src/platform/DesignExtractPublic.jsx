import React, { useState, useEffect } from 'react';
import { Sparkles, Loader2, ExternalLink, Mail, Globe } from 'lucide-react';

export default function DesignExtractPublic() {
  const [url, setUrl] = useState('');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [sample, setSample] = useState(null);

  useEffect(() => {
    fetch(`${process.env.REACT_APP_BACKEND_URL}/api/design-extract/public/sample`)
      .then(res => res.json())
      .then(data => setSample(data))
      .catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/design-extract/public/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, email, source: 'public-page' })
      });

      if (res.status === 429) {
        setError('Daily limit reached — try again tomorrow.');
        setLoading(false);
        return;
      }

      if (!res.ok) {
        const errData = await res.json();
        setError(errData.message || 'Something went wrong');
        setLoading(false);
        return;
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  };

  const renderExtractCard = (data, testIdPrefix = '') => {
    if (!data) return null;
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6">
        {data.colors && data.colors.length > 0 && (
          <div>
            <h3 className="text-lg font-semibold mb-3">Colors</h3>
            <div className="flex flex-wrap gap-4">
              {data.colors.map((color, i) => (
                <div key={i} className="flex flex-col items-center gap-1" data-testid={testIdPrefix ? `${testIdPrefix}-color-swatch-${i}` : `color-swatch-${i}`}>
                  <div className="w-12 h-12 rounded-full border-2 border-slate-700" style={{ backgroundColor: color }}></div>
                  <span className="text-xs text-slate-400 font-mono">{color}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.fonts && data.fonts.length > 0 && (
          <div>
            <h3 className="text-lg font-semibold mb-3">Fonts</h3>
            <div className="flex flex-wrap gap-3">
              {data.fonts.map((font, i) => (
                <div
                  key={i}
                  className="bg-slate-800 border border-slate-700 rounded px-4 py-2"
                  style={{ fontFamily: font }}
                  data-testid={testIdPrefix ? `${testIdPrefix}-font-tile-${i}` : `font-tile-${i}`}
                >
                  {font}
                </div>
              ))}
            </div>
          </div>
        )}

        {data.meta && (
          <div>
            <h3 className="text-lg font-semibold mb-3">Meta Description</h3>
            <p className="bg-slate-800 border border-slate-700 rounded p-3 font-mono text-sm text-slate-300">
              {data.meta}
            </p>
          </div>
        )}

        {data.headlineCount !== undefined && (
          <div>
            <h3 className="text-lg font-semibold mb-3">Headline Count</h3>
            <span className="inline-block bg-amber-500 text-slate-950 font-bold px-4 py-2 rounded-full">
              {data.headlineCount}
            </span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="container mx-auto px-4 py-16">
        {/* Hero */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold mb-4">
            Extract any site's design system in 10 seconds. Free.
          </h1>
          <p className="text-xl text-slate-400">
            Colors, fonts, meta, headline count — pasted to a clean report your team can actually use.
          </p>
        </div>

        {/* Form Card */}
        <div className="max-w-3xl mx-auto mb-12">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="relative">
                  <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                  <input
                    type="url"
                    placeholder="https://example.com"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    required
                    disabled={loading}
                    className="w-full bg-slate-800 border border-slate-700 rounded pl-11 pr-4 py-3 focus:outline-none focus:border-amber-500 disabled:opacity-50"
                    data-testid="url-input"
                  />
                </div>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                  <input
                    type="email"
                    placeholder="your@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={loading}
                    className="w-full bg-slate-800 border border-slate-700 rounded pl-11 pr-4 py-3 focus:outline-none focus:border-amber-500 disabled:opacity-50"
                    data-testid="email-input"
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold py-4 rounded-lg flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition"
                data-testid="extract-submit"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Analysing...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Extract design
                  </>
                )}
              </button>
            </form>

            {error && (
              <div className="mt-4 bg-red-900/20 border border-red-800 rounded p-4 text-red-300">
                {error}
              </div>
            )}
          </div>
        </div>

        {/* Result Card */}
        {result && (
          <div className="max-w-3xl mx-auto mb-12" data-testid="extract-result">
            {renderExtractCard(result)}
            <div className="mt-6 text-center">
              <a
                href="/pricing"
                className="inline-flex items-center gap-2 text-amber-500 hover:text-amber-400 font-semibold"
                data-testid="cta-pricing"
              >
                Want competitor analysis + full audit report? See pricing →
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          </div>
        )}

        {/* Sample Preview */}
        {sample && (
          <div className="max-w-3xl mx-auto mb-12" data-testid="sample-preview">
            <h2 className="text-2xl font-bold mb-6 text-center">Live sample</h2>
            {renderExtractCard(sample, 'sample')}
          </div>
        )}

        {/* Footer */}
        <div className="text-center text-slate-400 text-sm">
          No signup. No card. 3 extractions per email per day.
        </div>
      </div>
    </div>
  );
}