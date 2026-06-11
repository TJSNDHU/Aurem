/**
 * AUREM iter D-81b — Customer Activation Onboarding
 * Route: /onboarding
 *
 * Brand-new subscribers land here right after Stripe checkout. We
 * capture business_url + industry + target_city + target_country,
 * write them to customer_business_profile (BIN-scoped), fire a
 * welcome email, and bounce them to /dashboard.
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Building2, Globe, MapPin, Briefcase, Loader2, CheckCircle2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;
const GOLD = "#C9A227";

const INDUSTRIES = [
  ["hvac", "HVAC / Heating & Cooling"],
  ["plumbing", "Plumbing"],
  ["electrical", "Electrical"],
  ["roofing", "Roofing"],
  ["landscaping", "Landscaping"],
  ["cleaning", "Cleaning"],
  ["auto_repair", "Auto Repair"],
  ["salon", "Salon"],
  ["spa", "Spa"],
  ["fitness", "Fitness / Gym"],
  ["restaurant", "Restaurant"],
  ["retail", "Retail"],
  ["real_estate", "Real Estate"],
  ["legal", "Legal"],
  ["accounting", "Accounting"],
  ["medical_clinic", "Medical Clinic"],
  ["dental", "Dental"],
  ["construction", "Construction"],
  ["moving", "Moving"],
  ["pest_control", "Pest Control"],
  ["other", "Other"],
];

const COUNTRIES = [
  ["CA", "Canada"],
  ["US", "United States"],
  ["GB", "United Kingdom"],
  ["AU", "Australia"],
  ["IN", "India"],
  ["OTHER", "Other"],
];

const Field = ({ icon: Icon, label, children, testid }) => (
  <label className="block" data-testid={`onb-field-${testid}`}>
    <span className="flex items-center gap-2 text-sm font-medium mb-2" style={{ color: "#d4d4d8" }}>
      <Icon className="size-4" style={{ color: GOLD }} />
      {label}
    </span>
    {children}
  </label>
);

const inputStyle = {
  width: "100%",
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(201,162,39,0.22)",
  borderRadius: 8,
  padding: "12px 14px",
  color: "#f4f4f5",
  fontSize: 15,
  outline: "none",
};

export default function OnboardingBusinessProfile() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    business_name: "",
    business_url: "",
    industry: "",
    target_city: "",
    target_country: "CA",
  });

  const token =
    localStorage.getItem("aurem_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("aurem_admin_token") ||
    "";

  // On mount: if profile already exists for this BIN, skip form → /dashboard
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!token) {
        navigate("/my", { replace: true });
        return;
      }
      try {
        const r = await fetch(`${API}/api/onboarding/business-profile`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (cancelled) return;
        if (r.ok) {
          const data = await r.json();
          if (data?.exists) {
            navigate("/dashboard", { replace: true });
            return;
          }
        } else if (r.status === 401 || r.status === 403) {
          navigate("/my", { replace: true });
          return;
        }
      } catch {
        /* network blip — let the user proceed with the form */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, navigate]);

  const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const r = await fetch(`${API}/api/onboarding/business-profile`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(form),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(data?.detail || `Save failed (${r.status})`);
        setSaving(false);
        return;
      }
      navigate(data?.redirect_to || "/dashboard", { replace: true });
    } catch (err) {
      setError(err?.message || "Network error");
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#0A0A0A" }}>
        <Loader2 className="size-8 animate-spin" style={{ color: GOLD }} />
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-12" style={{ background: "#0A0A0A", color: "#f4f4f5" }} data-testid="onboarding-business-profile">
      <div className="max-w-xl mx-auto">
        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full mb-4"
               style={{ background: "rgba(201,162,39,0.12)", border: "1px solid rgba(201,162,39,0.3)" }}>
            <CheckCircle2 className="size-3.5" style={{ color: GOLD }} />
            <span className="text-xs font-medium" style={{ color: GOLD }}>Subscription active</span>
          </div>
          <h1 className="text-3xl font-semibold mb-2" style={{ color: GOLD }}>Activate your AUREM workspace</h1>
          <p className="text-sm" style={{ color: "#a1a1aa" }}>
            Two minutes. ORA needs your business context to start scouting your market.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-5">
          <Field icon={Building2} label="Business name" testid="business-name">
            <input
              required
              type="text"
              value={form.business_name}
              onChange={update("business_name")}
              placeholder="e.g. Royal Premier Homes"
              data-testid="onb-input-business-name"
              style={inputStyle}
            />
          </Field>

          <Field icon={Globe} label="Business website" testid="business-url">
            <input
              required
              type="url"
              value={form.business_url}
              onChange={update("business_url")}
              placeholder="https://example.com"
              data-testid="onb-input-business-url"
              style={inputStyle}
            />
          </Field>

          <Field icon={Briefcase} label="Industry" testid="industry">
            <select
              required
              value={form.industry}
              onChange={update("industry")}
              data-testid="onb-select-industry"
              style={inputStyle}
            >
              <option value="" disabled>Select your industry…</option>
              {INDUSTRIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field icon={MapPin} label="Target city" testid="target-city">
              <input
                required
                type="text"
                value={form.target_city}
                onChange={update("target_city")}
                placeholder="Toronto"
                data-testid="onb-input-target-city"
                style={inputStyle}
              />
            </Field>

            <Field icon={MapPin} label="Country" testid="target-country">
              <select
                required
                value={form.target_country}
                onChange={update("target_country")}
                data-testid="onb-select-target-country"
                style={inputStyle}
              >
                {COUNTRIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
          </div>

          {error && (
            <div data-testid="onb-error"
                 className="px-4 py-3 rounded-lg text-sm"
                 style={{ background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.35)", color: "#fca5a5" }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={saving}
            data-testid="onb-submit-btn"
            className="w-full flex items-center justify-center gap-2 font-semibold rounded-lg transition-all"
            style={{
              padding: "14px 20px",
              background: saving ? "rgba(201,162,39,0.5)" : GOLD,
              color: "#0A0A0A",
              fontSize: 15,
              cursor: saving ? "not-allowed" : "pointer",
            }}
          >
            {saving ? <><Loader2 className="size-4 animate-spin" /> Activating…</> : <>Activate & open dashboard <ArrowRight className="size-4" /></>}
          </button>
        </form>

        <p className="text-xs text-center mt-6" style={{ color: "#71717a" }}>
          Your data stays in Canada · PIPEDA / Law 25 compliant
        </p>
      </div>
    </div>
  );
}
