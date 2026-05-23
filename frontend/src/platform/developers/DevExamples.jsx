/**
 * /developers/examples — 5 starter projects (Auth-gated)
 */
import React from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase, Calendar, MessageSquare, FileText, Send } from "lucide-react";
import DeveloperShell from "./DeveloperShell";
import { PageHeader } from "./DevDashboard";

const EXAMPLES = [
  {
    id: "lead-tracker", icon: Briefcase,
    title: "Lead tracker for a local business",
    description:
      "Capture leads from a contact form, score them by industry signals, " +
      "queue daily follow-up emails. Tiny dashboard for the owner.",
    stack: ["FastAPI", "React", "Mongo", "Resend"],
    tokens_est: 220,
    prompt:
      "Build a lead tracker. POST /api/leads ingests name+email+phone+industry. " +
      "Score 0-100 by industry. List view sortable by score. Daily follow-up " +
      "cron sends Resend email to leads with score >= 60.",
  },
  {
    id: "appointment-booking", icon: Calendar,
    title: "Appointment booking system",
    description:
      "Customers pick a slot, system sends a confirmation email with .ics " +
      "calendar invite. Owner sees today's bookings on a single page.",
    stack: ["FastAPI", "React", "Mongo", "Resend", "iCal"],
    tokens_est: 280,
    prompt:
      "Build appointment booking. GET /api/slots?date=YYYY-MM-DD returns " +
      "open 30-min slots 9-5 weekdays. POST /api/book stores customer+slot, " +
      "sends Resend email with .ics. Owner page lists today's bookings.",
  },
  {
    id: "feedback-portal", icon: MessageSquare,
    title: "Customer feedback portal",
    description:
      "Customers leave ratings + comments. Admin moderates and replies inline. " +
      "Star average shown publicly per product.",
    stack: ["FastAPI", "React", "Mongo"],
    tokens_est: 200,
    prompt:
      "Build a feedback portal. POST /api/feedback (product_id, rating 1-5, " +
      "comment). GET /api/feedback/:product_id returns average + comments. " +
      "Admin page approves/rejects/replies.",
  },
  {
    id: "invoice-generator", icon: FileText,
    title: "Invoice generator",
    description:
      "Create a numbered invoice from line items, render a clean PDF, " +
      "email it to the client. Track paid/unpaid status.",
    stack: ["FastAPI", "React", "Mongo", "ReportLab", "Resend"],
    tokens_est: 320,
    prompt:
      "Build invoice generator. POST /api/invoices accepts {client, " +
      "items[{desc, qty, unit_price}]} returns numbered invoice + PDF URL. " +
      "GET /api/invoices lists with paid/unpaid badge. Email PDF on create.",
  },
  {
    id: "campaign-manager", icon: Send,
    title: "Email campaign manager",
    description:
      "Upload contacts (CSV), pick a template, schedule a campaign, " +
      "watch open/click rates roll in.",
    stack: ["FastAPI", "React", "Mongo", "Resend webhooks"],
    tokens_est: 380,
    prompt:
      "Build a campaign manager. POST /api/contacts/import accepts CSV. " +
      "POST /api/campaigns creates {name, template_html, scheduled_at}. Cron " +
      "fires due campaigns via Resend. Webhook stamps open/click counts.",
  },
];

export default function DevExamples() {
  const navigate = useNavigate();

  function build(ex) {
    localStorage.setItem("ora_prefill_prompt",  ex.prompt);
    localStorage.setItem("ora_prefill_project", ex.title);
    navigate("/developers/dashboard");
  }

  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="EXAMPLES"
                  title="Five things you can ship today."
                  sub="Click 'Build this' — AUREM CTO opens with the prompt typed in. Estimates use the real cost table." />

      <div className="av2-grid-2">
        {EXAMPLES.map(ex => (
          <article key={ex.id} data-testid="example-project-card"
                    className="av2-card"
                    style={{ display: "flex", flexDirection: "column",
                              gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <ex.icon size={20} style={{ color: "var(--dash-orange)" }} />
              <h3 style={{
                fontFamily: "'Cinzel', serif",
                fontSize: 16, fontWeight: 600,
                color: "var(--dash-text)",
                letterSpacing: "0.01em",
              }}>{ex.title}</h3>
            </div>
            <p style={{ fontSize: 13, lineHeight: 1.7,
                         color: "var(--dash-text-muted)" }}>
              {ex.description}
            </p>
            <div data-testid="example-stack-tags"
                  style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {ex.stack.map(t => (
                <span key={t} style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10, letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: "var(--dash-gold-bright)",
                  border: "1px solid rgba(201,168,76,0.30)",
                  padding: "3px 9px", borderRadius: 4,
                }}>{t}</span>
              ))}
            </div>
            <div style={{ display: "flex", alignItems: "center",
                           justifyContent: "space-between", marginTop: 6 }}>
              <span data-testid="example-token-est"
                     style={{ fontSize: 12,
                               color: "var(--dash-text-muted)" }}>
                ~ <span style={{ color: "var(--dash-text)",
                                  fontWeight: 500 }}>{ex.tokens_est}</span> tokens
              </span>
              <button data-testid="example-build-btn" onClick={() => build(ex)}
                       style={{
                         padding: "8px 16px",
                         background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                         color: "#fff", border: "none", borderRadius: 6,
                         fontSize: 12, fontWeight: 500, cursor: "pointer",
                       }}>
                Build this →
              </button>
            </div>
          </article>
        ))}
      </div>
    </DeveloperShell>
  );
}
