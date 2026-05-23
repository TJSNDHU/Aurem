import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Switch } from "../../components/ui/switch";
import { Badge } from "../../components/ui/badge";

// iter 331c/331d — Consent toggle card for the developer settings page.
// PATCHes /api/me/consent (Sprint 6.1 endpoint).
// Shows discount status + monthly contribution count when consent is on.

const API = process.env.REACT_APP_BACKEND_URL;

export default function ConsentToggleCard() {
  const [state, setState]   = useState(null);
  const [busy, setBusy]     = useState(false);
  const [error, setError]   = useState(null);

  async function load() {
    try {
      const r = await fetch(`${API}/api/me/consent`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("dev_jwt") || ""}` },
      });
      if (!r.ok) throw new Error(`load failed: HTTP ${r.status}`);
      setState(await r.json());
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => { load(); }, []);

  async function toggle(next) {
    setBusy(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/me/consent`, {
        method:  "PATCH",
        headers: {
          "Content-Type":  "application/json",
          "Authorization": `Bearer ${localStorage.getItem("dev_jwt") || ""}`,
        },
        body: JSON.stringify({ consent: !!next }),
      });
      if (!r.ok) throw new Error(`update failed: HTTP ${r.status}`);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const on = !!state?.data_sharing_consent;

  return (
    <Card data-testid="consent-toggle-card" className="border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <span>Data Sharing & 20% Discount</span>
          {on && (
            <Badge data-testid="consent-discount-badge"
                   className="bg-emerald-500/15 text-emerald-300">
              -20% active
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-slate-300">
            {on
              ? "You're sharing anonymized campaign metadata."
              : "Share anonymized campaign metadata to get 20% off tokens."}
          </span>
          <Switch
            data-testid="consent-toggle-switch"
            checked={on}
            disabled={busy}
            onCheckedChange={toggle}
          />
        </div>
        {on && (
          <div className="text-xs text-slate-400" data-testid="consent-stats">
            Leads contributed this month:&nbsp;
            <span className="text-slate-200">
              {state?.contributed_this_month ?? 0}
            </span>
          </div>
        )}
        {!on && state?.network_purge_due_at && (
          <div className="text-xs text-amber-300" data-testid="consent-purge-notice">
            Your historical data will be deleted on&nbsp;
            {new Date(state.network_purge_due_at).toLocaleDateString()}.
          </div>
        )}
        {error && (
          <div data-testid="consent-error" className="text-xs text-rose-400">
            {error}
          </div>
        )}
        <p className="text-xs text-slate-500">
          We only share strictly non-PII fields (industry, city, channel,
          outcome). Personal names, emails, phone numbers, and addresses
          are never shared. Toggle off any time — your historical data is
          purged within 30 days.
        </p>
      </CardContent>
    </Card>
  );
}
