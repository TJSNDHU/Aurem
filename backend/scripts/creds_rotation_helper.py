"""
scripts/creds_rotation_helper.py — iter D-75 #4

Target: <3 minutes human time per credential rotation event.

Flow:
  1. Probe all 16 providers via `services.creds_health.probe_all()`.
  2. List only the RED ones with:
       • current key tail (last 4 chars)
       • direct rotation-page URL
  3. Prompt for new value per provider (Enter = skip).
  4. Update /app/backend/.env in place (atomic write, preserves
     comments + ordering of unchanged lines).
  5. `sudo supervisorctl restart backend` + 25-second wait.
  6. Re-probe and show before/after.

No mocks. Real HTTP probes against real providers. Real .env writes.

Run:
    python3 /app/backend/scripts/creds_rotation_helper.py
    python3 /app/backend/scripts/creds_rotation_helper.py --dry-run
    python3 /app/backend/scripts/creds_rotation_helper.py --only twilio
"""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/app/backend")

ENV_FILE = "/app/backend/.env"

# Per-provider rotation URLs + .env var names
PROVIDER_META = {
    "twilio":           {"vars": ["TWILIO_AUTH_TOKEN"],
                          "rotate_url": "https://console.twilio.com/us1/account/keys-credentials/api-keys"},
    "resend":           {"vars": ["RESEND_API_KEY"],
                          "rotate_url": "https://resend.com/api-keys"},
    "openrouter":       {"vars": ["OPENROUTER_API_KEY"],
                          "rotate_url": "https://openrouter.ai/keys"},
    "stripe":           {"vars": ["STRIPE_SECRET_KEY", "STRIPE_API_KEY"],
                          "rotate_url": "https://dashboard.stripe.com/apikeys"},
    "apollo":           {"vars": ["APOLLO_API_KEY"],
                          "rotate_url": "https://app.apollo.io/#/settings/integrations/api"},
    "tavily":           {"vars": ["TAVILY_API_KEY"],
                          "rotate_url": "https://app.tavily.com/home"},
    "github":           {"vars": ["GITHUB_TOKEN"],
                          "rotate_url": "https://github.com/settings/tokens"},
    "emergent_llm":     {"vars": ["EMERGENT_LLM_KEY"],
                          "rotate_url": "Profile → Universal Key (Emergent platform)"},
    "firecrawl":        {"vars": ["FIRECRAWL_API_KEY"],
                          "rotate_url": "https://www.firecrawl.dev/app/api-keys"},
    "sentry":           {"vars": ["SENTRY_DSN"],
                          "rotate_url": "https://sentry.io/settings/account/api/auth-tokens/"},
    "e2b":              {"vars": ["E2B_API_KEY"],
                          "rotate_url": "https://e2b.dev/dashboard?tab=keys"},
    "vercel":           {"vars": ["VERCEL_TOKEN"],
                          "rotate_url": "https://vercel.com/account/tokens"},
    "elevenlabs":       {"vars": ["ELEVENLABS_API_KEY"],
                          "rotate_url": "https://elevenlabs.io/app/settings/api-keys"},
    "google_pagespeed": {"vars": ["GOOGLE_PAGESPEED_API_KEY", "GOOGLE_API_KEY"],
                          "rotate_url": "https://console.cloud.google.com/apis/credentials"},
    "deepgram":         {"vars": ["DEEPGRAM_API_KEY"],
                          "rotate_url": "https://console.deepgram.com/project/_/keys"},
}


def read_env() -> list[str]:
    return Path(ENV_FILE).read_text().splitlines()


def write_env(lines: list[str]) -> None:
    """Atomic write — temp + rename so a crash mid-write can't blank
    the .env file."""
    tmp = ENV_FILE + ".tmp"
    Path(tmp).write_text("\n".join(lines) + "\n")
    os.replace(tmp, ENV_FILE)


def backup_env() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup = f"{ENV_FILE}.bak.{ts}"
    shutil.copy2(ENV_FILE, backup)
    return backup


def update_env_var(lines: list[str], key: str, new_value: str) -> tuple[list[str], bool]:
    """Replace the value of `KEY=` while preserving the rest of the
    file. If the key isn't present, append it. Returns (new_lines,
    was_replaced)."""
    out = []
    replaced = False
    for line in lines:
        if line.startswith(f"{key}=") and not line.lstrip().startswith("#"):
            out.append(f"{key}={new_value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={new_value}")
    return out, replaced


async def probe_all_results():
    from services import creds_health as ch
    return await ch.probe_all(timeout=6.0)


def print_red_table(results) -> list:
    reds = [r for r in results if r.status == "red"]
    if not reds:
        print("\n  All providers green. Nothing to rotate.")
        return reds
    print(f"\n  {len(reds)} provider(s) RED — rotate these:\n")
    print(f"  {'#':<3} {'provider':<18} {'http':>5}  {'tail':<8}  {'rotation URL'}")
    print("  " + "-" * 96)
    for i, r in enumerate(reds, 1):
        meta = PROVIDER_META.get(r.provider, {})
        url = meta.get("rotate_url", "(no rotation URL — manual lookup)")
        print(f"  {i:<3} {r.provider:<18} {str(r.http or '-'):>5}  …{r.key_tail or '----':<6}  {url}")
    return reds


def prompt_new_values(reds, only: str | None) -> dict[str, str]:
    """Prompt the user for new values. Empty input = skip. Returns
    {env_var_name: new_value}."""
    updates: dict[str, str] = {}
    for r in reds:
        if only and r.provider != only:
            continue
        meta = PROVIDER_META.get(r.provider, {})
        env_vars = meta.get("vars", [])
        if not env_vars:
            print(f"  ⚠ {r.provider}: no env var mapping — skipping")
            continue
        print(f"\n  ─ {r.provider} (rotate at: {meta.get('rotate_url', '?')})")
        for var in env_vars:
            current = os.environ.get(var, "")
            tail = current[-4:] if len(current) >= 4 else "(empty)"
            new = input(f"    {var} (current tail …{tail}) → new value [Enter to skip]: ").strip()
            if new:
                updates[var] = new
    return updates


def restart_backend(wait_s: int = 25) -> None:
    print(f"\n  Restarting backend (waiting {wait_s}s for ready)…")
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=False)
    time.sleep(wait_s)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Probe + prompt + show what would change; don't write")
    p.add_argument("--only", type=str, default=None,
                   help="Limit rotation to one provider (e.g. --only twilio)")
    args = p.parse_args()

    started = time.time()
    print(f"\n=== AUREM creds rotation helper ({datetime.utcnow().isoformat()}Z) ===")
    print("\n[1/6] Probing all providers…")
    pre_results = asyncio.run(probe_all_results())
    summary = {"green": 0, "yellow": 0, "red": 0, "not_configured": 0}
    for r in pre_results:
        summary[r.status] = summary.get(r.status, 0) + 1
    print(f"  Summary: {summary}")

    print("\n[2/6] Listing RED providers…")
    reds = print_red_table(pre_results)
    if not reds:
        print(f"\n  ✓ Done in {time.time()-started:.1f}s — no rotation needed.")
        return 0

    print("\n[3/6] Prompting for new values…")
    updates = prompt_new_values(reds, args.only)
    if not updates:
        print("\n  No values entered — nothing to do.")
        return 0

    print(f"\n[4/6] Updating .env ({len(updates)} variable(s))…")
    if args.dry_run:
        print("  DRY RUN — would update:")
        for var, val in updates.items():
            tail = val[-4:] if len(val) >= 4 else "(short)"
            print(f"    {var} → new tail …{tail}")
        print(f"\n  ✓ Dry-run done in {time.time()-started:.1f}s")
        return 0

    backup = backup_env()
    print(f"  Backed up current .env → {backup}")
    lines = read_env()
    for var, val in updates.items():
        lines, _ = update_env_var(lines, var, val)
    write_env(lines)
    print(f"  Wrote {len(updates)} key(s)")

    print("\n[5/6] Restarting backend…")
    restart_backend(wait_s=25)

    print("\n[6/6] Re-probing…")
    post_results = asyncio.run(probe_all_results())
    pre_by_p = {r.provider: r.status for r in pre_results}
    post_by_p = {r.provider: r.status for r in post_results}
    print(f"\n  {'provider':<18} {'before':<10} → {'after':<10}")
    print("  " + "-" * 48)
    for r in reds:
        before = pre_by_p.get(r.provider, "?")
        after = post_by_p.get(r.provider, "?")
        icon = "✓" if after == "green" else ("✗" if after == "red" else "?")
        print(f"  {r.provider:<18} {before:<10} → {after:<10}  {icon}")

    elapsed = time.time() - started
    print(f"\n=== Done in {elapsed:.1f}s ===")
    if elapsed > 180:
        print("  (Over 3-min target — usually because human input was slow.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
