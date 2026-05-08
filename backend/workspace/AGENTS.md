# AGENTS.md — Agent Fleet Capabilities & Rules

> ClawChief OS | AUREM Automation Intelligence
> Last Updated: 2026-04-06
> Status: ACTIVE

---

## Agent Registry

### Scout Agent
- **Role**: Intelligence Gathering
- **Capabilities**: Lead discovery, data enrichment, lead scoring (0-100, A/B/C/D grades)
- **Trigger**: Daily sweep (08:00 EST), manual dispatch, heartbeat alert
- **Output**: Updated contact scores in MongoDB, summary in `tasks/current.md`
- **Token Budget**: Low (uses heuristic scoring first, LLM only for ambiguous leads)

### Envoy Agent
- **Role**: External Communications
- **Capabilities**: Outreach planning, follow-up scheduling, email drafting
- **Trigger**: Scout identifies high-priority leads, ORA detects follow-up intent
- **Output**: Outreach plans with contact/company/channel/priority
- **Brand Rule**: All communications must pass SOUL.md voice check

### Closer Agent
- **Role**: Deal Progression
- **Capabilities**: Win probability analysis, closing strategies, at-risk detection
- **Trigger**: Pipeline audit (every 4 hours), manual dispatch
- **Output**: Deal strategies with health scores (healthy/at_risk/cold)
- **Alert Rule**: At-risk deals trigger Rose-Gold pulse in HEARTBEAT.md

### Oracle Agent
- **Role**: Predictive Intelligence
- **Capabilities**: Revenue forecasting, churn prediction, trend analysis
- **Trigger**: Daily sweep, manual dispatch
- **Output**: N-month forecast with confidence scores, weighted pipeline value
- **Data Rule**: Uses historical MongoDB data + AI-enhanced projections

### Architect Agent
- **Role**: System Optimization
- **Capabilities**: Database audit, workflow design, collection health checks
- **Trigger**: Weekly sweep, manual dispatch, system anomaly
- **Output**: Active collection stats, optimization recommendations
- **Safety Rule**: Read-only access. Never modifies data autonomously.

### Critic Agent (6th Agent — Zero-Trust Validation)
- **Role**: Output Validation & Adversarial Review
- **Capabilities**: Validates all agent outputs before they reach the user. Catches Misinterpretations (20.77% of AI errors), Missing Corner Cases, Logic Gaps, Data Errors, and SOUL.md Voice violations.
- **Modes**: VALIDATE (standard review), ADVERSARIAL (challenges assumptions), RESCUE (second opinion on low-confidence outputs)
- **Trigger**: Automatic (every agent dispatch), Heartbeat (adversarial pipeline check), Manual
- **Output**: Verdict (APPROVED/FLAGGED/CHALLENGED), confidence score, list of issues/challenges
- **Authority**: Can escalate alert level if adversarial review challenges pipeline data
- **Source**: CriticGPT research (85% bug detection rate vs 25% human baseline)

---

## Delegation Rules

| Intent | Primary Agent | Backup Agent |
|--------|--------------|--------------|
| FOLLOW_UP | Envoy | Closer |
| OUTREACH | Envoy | Scout |
| PIPELINE_CHECK | Closer | Oracle |
| DEAL_ANALYSIS | Closer | Oracle |
| LEAD_SCORE | Scout | — |
| LEAD_DISCOVERY | Scout | Envoy |
| FORECAST | Oracle | Architect |
| SYSTEM_AUDIT | Architect | — |

---

## Execution Protocol

1. ORA classifies intent
2. Primary agent is dispatched
3. Agent executes and returns result
4. Result is written to `tasks/current.md`
5. Blockchain audit hash is generated
6. If result contains alerts, HEARTBEAT.md is updated
7. ORA summarizes result for the user (or logs silently if autonomous)
