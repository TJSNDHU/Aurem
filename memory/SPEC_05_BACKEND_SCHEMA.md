# SPEC 05 — Backend Schema (MongoDB collections)

> Read sixth. Updated 2026-05-28, iter D-57.
>
> Data ownership rules:
>   - Customer-owned data → `tenant_id` field MUST be present + indexed.
>   - Founder-owned data → live in `admin_*` collections.
>   - Audit data → append-only, never updated. Lives in `unified_audit_log`.

## Auth + identity

### `users`
- `_id` (ObjectId) — internal
- `email` (str, unique) — primary identity
- `first_name`, `last_name`, `phone`
- `password_hash` (bcrypt, rounds 12)
- `is_admin`, `is_super_admin`, `role` (`"founder" | "admin" | "user"`)
- `tenant_id` (str)
- `email_verified_at` (iso str)
- `must_set_password` (bool)
- `created_at`, `updated_at` (iso str)
- **Indexes**: `email` unique, `tenant_id`

### `platform_users`, `aurem_users`
- Mirror of `users` for legacy compatibility — kept in sync by
  emergency-reset and signup flows.

### `auth_sessions`
- `session_id` (uuid)
- `user_id`, `email`, `tenant_id`
- `issued_at`, `expires_at`
- `revoked` (bool), `revoked_at`, `revoked_reason`
- **Indexes**: `session_id` unique, `email + revoked`

### `developer_accounts`
- `account_id` (uuid)
- `email`, `password_hash`
- `tenant_id`, `byok_provider`, `byok_key_encrypted`
- `created_at`, `last_login_at`
- **Indexes**: `email` unique

### `developer_github_links` (D-42)
- `account_id` → `developer_accounts.account_id`
- `github_user`, `access_token` (encrypted)
- `connected_at`
- **Indexes**: `account_id`, latest by `connected_at` desc

### `customer_security_keys` (D-46)
- `key_id` (uuid), `account_id`, `key_type`
  (`"jwt" | "aes" | "emergency_reset"`)
- `encrypted_value` (AES-256-GCM via AUREM_ENCRYPTION_KEY)
- `rotated_at`, `expires_at`
- **Indexes**: `account_id + key_type`

---

## CRM / lead pipeline

### `leads`
- `lead_id` (str, unique), `source` (`"openfang"/"osm"/"csv"/"public_form"`)
- `business_name`, `email`, `phone`, `website`, `city`, `country`
- `status` (`"new" | "queued" | "emailed" | "responded" | "signed_up" |
  "not_interested" | "unsubscribed"`)
- `noise_flag` (bool), `noise_reason` (str)
- `created_at`, `updated_at`
- **Indexes**: `lead_id` unique, `email`, `phone`, `status`,
  `country`, `created_at`

### `campaign_leads`
- Same shape as `leads` + outreach metadata:
- `last_blast_at`, `last_blast_channel`, `last_blast_result`
- `verification.channel_gating.{email|sms|call|whatsapp}` (bool)
- `verification.source` (`"cto_tool" | "ghost_scout_iproyal" | …`)
- `hot_lead_flag`, `hot_lead_reason`, `hot_lead_signal_at`,
  `last_hot_email_id`, `last_clicked_url` (D-57)
- `flame_score_boost` (int)
- `dnc` (bool), `casl_blocked` (bool)
- **Indexes**:
  - `lead_id` unique
  - `last_blast_at` (sparse) + `status`
  - `hot_lead_flag + hot_lead_signal_at desc` (D-57 list)
  - `verification.channel_gating.email`
  - `country + city`

### `outreach_queue`, `outreach_history`
- `queue` carries pending attempts; `history` carries delivered ones.
- `outreach_history`:
  - `ts`, `lead_id`, `tenant_id`, `type`, `channels_attempted` (list)
  - `result.sent` (list of `{channel, to, ok, id|sid, status, reason}`)
- **Indexes**: `ts desc`, `lead_id + ts`

### `sent_emails`
- `to`, `subject`, `template`, `sent_at`, `resend_message_id`
- **Indexes**: `sent_at desc`, `to`

### `unsub_tokens`
- `token` (uuid), `lead_id`, `email`, `created_at`, `used_at`
- **Indexes**: `token` unique

---

## CTO subsystem (D-49 → D-57)

### `cto_tool_runs` (D-49)
- `tool`, `actor`, `ts`, `input`, `result` (dict, `_id` stripped)
- **Indexes**: `actor + ts desc`

### `cto_verify_runs` (D-52)
- `tool`, `actor`, `ts`, `input`, `result`
- **Indexes**: `actor + ts desc`, `tool`

### `cto_learnings` (D-53)
- `_id` (uuid), `task_type`, `approach`, `result` (`"success" | "failure"`)
- `verified_by` (`"code_green" | "github_green" | "deploy_green" |
  "user_thumbs_up"`)
- `actor`, `ts`, `week_iso`, `metadata` (dict)
- **Indexes**: `task_type + result`, `week_iso`, `ts desc`

### `cto_weekly_reports` (D-53)
- `_id` (`"weekly-<YYYY-W##>"`)
- `week_iso`, `generated_at`, `learnings_added`, `success_rate`
- `top_patterns` (list), `failed_patterns` (list)
- **Indexes**: `_id` unique (per-week upsert)

---

## Billing + token wallets

### `onboarding_token_wallets`
- `tenant_id`, `account_id`, `balance_free`, `balance_paid`
- `updated_at`, `last_topup_amount`, `last_topup_at`
- **Indexes**: `account_id` unique

### `stripe_customers`, `stripe_subscriptions`
- `customer_id`, `email`, `subscription_id`, `plan`, `status`
- `current_period_end`, `cancel_at_period_end`
- **Indexes**: `customer_id` unique, `email`

### `aurem_customers`
- Paid-customer state — populated on first successful Stripe charge.
- `customer_id`, `email`, `plan`, `created_at`, `mrr`, `churned_at`
- **Indexes**: `created_at`, `email`

---

## Enterprise + audit

### `enterprise_leads`
- `email`, `company`, `seats_estimated`, `notes`, `submitted_at`
- **Indexes**: `submitted_at desc`

### `organizations`
- `org_id`, `name`, `domain`, `residency_region`, `branding` (dict),
  `created_at`
- **Indexes**: `org_id` unique, `domain`

### `saml_configs`
- `org_id`, `idp_metadata_xml`, `idp_sso_url`, `idp_cert`,
  `sp_entity_id`, `sp_acs_url`, `sign_authnrequest` (bool)
- **Indexes**: `org_id` unique

### `scim_users`
- IdP-mirrored user state. `org_id`, `external_id`, `email`,
  `active`, `roles`
- **Indexes**: `org_id + external_id`

### `unified_audit_log`
- `ts`, `actor`, `action`, `outcome` (`"ok" | "fail"`),
  `org_id`, `tenant_id`, `meta` (dict)
- Append-only. Never `updateOne`.
- **Indexes**: `ts desc`, `org_id + ts desc`, `actor + ts`

---

## Auto-website builder + previews

### `auto_websites`
- `lead_id`, `slug`, `theme`, `copy_blocks` (dict),
  `built_at`, `last_viewed_at`
- **Indexes**: `slug` unique, `lead_id`

### `cta_clicks`
- `slug`, `ts`, `ip_hash`, `ua_hash`, `cta_id`
- **Indexes**: `slug + ts desc`

---

## Scheduler / health

### `aurem_health_log`
- `ts`, `service`, `status`, `latency_ms`, `error`
- **Indexes**: `ts desc`

### `auto_blast_config`
- `tenant_id` (default `"global"`)
- `last_run_at`, `last_run_processed`, `last_run_sent`,
  `last_run_note`
- **Indexes**: `tenant_id` unique

### `ghost_scout_log`
- `ts`, `query`, `location`, `country`, `fetched`, `with_contact`,
  `inserted`, `skipped_dup`
- **Indexes**: `ts desc`

---

## Data ownership + retention rules

| Collection                  | Tenant scope     | Retention      |
|---|---|---|
| users / developer_accounts  | global / tenant  | until delete   |
| campaign_leads              | global           | 24 months      |
| outreach_history            | global           | 18 months      |
| sent_emails                 | global           | 12 months      |
| cto_tool_runs / verify_runs | global           | 12 months      |
| cto_learnings               | global           | 24 months      |
| cto_weekly_reports          | global           | 24 months      |
| unified_audit_log           | global / org     | 7 years (SOC 2)|
| organizations / saml_configs| org              | until delete   |

## ObjectId rules (anti-foot-gun)

- Every projection that leaves the wire MUST include `{"_id": 0}` or
  use a Pydantic response model.
- Never spread (`{**doc}`) a freshly inserted document into a response
  — Mongo mutates it to include `_id`.
- ObjectId reference fields (`created_by`, `parent_id`, …) MUST be
  serialized to `str` before returning.
