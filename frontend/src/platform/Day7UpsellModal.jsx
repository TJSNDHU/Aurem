import React, { useEffect } from 'react';
import { X, Sparkles, CheckCircle2 } from 'lucide-react';

export default function Day7UpsellModal({ isOpen, onClose, trial, onUpgrade }) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const elapsed_days = Math.floor((Date.now() / 1000 - trial.created_at) / 86400);
  const days_left = Math.max(0, (trial.trial_days_total || 14) - elapsed_days);

  const tiers = [
    {
      key: 'starter',
      name: 'Starter',
      price: 49,
      features: ['100 leads/month', 'Basic CRM', 'Email support'],
      highlighted: false,
    },
    {
      key: 'growth',
      name: 'Growth',
      price: 149,
      features: ['1,000 leads/month', 'Full CRM + Scout', 'Priority support', 'ORA CTO Lite'],
      highlighted: true,
    },
    {
      key: 'enterprise',
      name: 'Enterprise',
      price: 499,
      features: ['Unlimited leads', 'Multi-seat', 'Dedicated success', 'Full ORA CTO + Council', 'Custom integrations'],
      highlighted: false,
    },
  ];

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50"
      data-testid="day7-backdrop"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-slate-900 border border-slate-700 rounded-2xl max-w-4xl w-full mx-4 p-8 relative"
        data-testid="day7-modal"
      >
        <button
          onClick={onClose}
          className="absolute top-6 right-6 text-slate-400 hover:text-slate-200 transition-colors"
          data-testid="day7-close"
        >
          <X className="size-6" />
        </button>

        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <Sparkles className="size-8 text-amber-400" />
            <h2 className="text-3xl font-bold text-white">
              Day 7, half-way through your AUREM trial
            </h2>
          </div>
          <p className="text-slate-300 text-lg ml-11">
            {days_left} days left to lock in your launch pricing.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-6">
          {tiers.map((tier) => (
            <div
              key={tier.key}
              className={`bg-slate-800 border rounded-xl p-6 flex flex-col ${
                tier.highlighted
                  ? 'border-amber-400 scale-105 ring-2 ring-amber-400/30'
                  : 'border-slate-700'
              }`}
              data-testid={`day7-tier-${tier.key}`}
            >
              <h3 className="text-xl font-bold text-white mb-2">{tier.name}</h3>
              <div className="mb-4">
                <span className="text-4xl font-bold text-white">${tier.price}</span>
                <span className="text-slate-400">/mo</span>
              </div>
              <ul className="space-y-3 mb-6 flex-grow">
                {tier.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-slate-300">
                    <CheckCircle2 className="size-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <span className="text-sm">{feature}</span>
                  </li>
                ))}
              </ul>
              <button
                onClick={() => onUpgrade(tier.key)}
                className={`w-full py-3 rounded-lg font-semibold transition-all ${
                  tier.highlighted
                    ? 'bg-amber-500 hover:bg-amber-600 text-black'
                    : 'bg-slate-700 hover:bg-slate-600 text-white'
                }`}
              >
                Upgrade to {tier.name}
              </button>
            </div>
          ))}
        </div>

        <div className="mt-6 text-center">
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-300 text-sm transition-colors"
            data-testid="day7-skip"
          >
            Continue trial — {days_left} days left
          </button>
        </div>
      </div>
    </div>
  );
}