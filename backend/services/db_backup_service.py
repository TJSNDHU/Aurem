"""
db_backup_service.py — Disaster Recovery: Primary → Secondary MongoDB mirror.

Strategy:
  1. Connect to PRIMARY (MONGO_URL) — local pod / production Atlas
  2. Connect to SECONDARY (SECONDARY_MONGO_URL) — independent Atlas account ("Backupmy" cluster)
  3. Stream every collection from primary, replace_one() / insert_many() into secondary
  4. Use replace-mode: secondary always reflects the latest primary state (size-bounded)
  5. Track each run in `db_backup_runs` collection on PRIMARY for ops visibility
  6. On failure: log + email founder via Resend (best-effort, non-blocking)

Triggered:
  - APScheduler cron: daily at 03:00 UTC (registered in routers/registry.py)
  - Manual: POST /api/admin/backup/trigger (super_admin only)

Author: Aurem ops · 2026-02-08
"""
import os
import time
import logging
import socket
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# iter 326m-stab.D — Production DNS-storm shield (deploy bug fix)
# ─────────────────────────────────────────────────────────────────────
# Production logs showed:
#   pymongo.errors.AutoReconnect: customer-apps-shard-00-XX.djq3ym.
#   mongodb.net:27017: [Errno -3] Temporary failure in name resolution
#   APScheduler: maximum number of running instances reached
#
# Root cause: SECONDARY_MONGO_URL pointed to a STALE Atlas cluster.
# Constructing `MongoClient(stale_url)` spawns a topology monitor
# THREAD that retries forever, even after `client.close()` — close
# only sets a flag; the thread has to finish its in-flight DNS
# attempt (5–30s) before observing it. Daily DR run + repeated T3
# escalation calls saturated the worker pool with these zombie
# threads → APScheduler "max instances reached" cascade.
#
# Defense (this module + admin_dr_backup_router):
#   1. PRE-FLIGHT DNS RESOLUTION before constructing MongoClient.
#      `socket.getaddrinfo(host, 27017, ...)` with a short budget.
#      If it fails, we NEVER call MongoClient(...) — no zombie thread.
#   2. CIRCUIT BREAKER: 30-minute cooldown after any DNS failure.
#      Subsequent calls return early with `status=skipped` until the
#      cooldown elapses. Stops the per-cycle re-poll storm.
# ─────────────────────────────────────────────────────────────────────
_SECONDARY_DNS_FAIL_UNTIL: float = 0.0   # epoch-seconds; 0 = circuit closed
_SECONDARY_DNS_FAIL_REASON: str = ""
SECONDARY_DNS_COOLDOWN_S: int = 30 * 60  # 30 minutes
SECONDARY_DNS_BUDGET_S: float = 3.0      # per host


def _hosts_from_mongo_url(mongo_url: str) -> list[str]:
    """Extract hostnames from a mongo URL. Handles both
    `mongodb://h1,h2,h3:27017/...` (replica-set form) and the
    `mongodb+srv://host/...` (SRV form) — for SRV we return the bare
    SRV hostname; pymongo will do its own DNS but we still pre-check it
    so an unreachable SRV record fails fast here too."""
    try:
        parsed = urlparse(mongo_url.replace("mongodb+srv://", "https://")
                                    .replace("mongodb://", "https://"))
        netloc = parsed.netloc or ""
        # strip user:pass@
        if "@" in netloc:
            netloc = netloc.rsplit("@", 1)[1]
        # split comma-separated hosts (replica-set form)
        hosts = []
        for piece in netloc.split(","):
            piece = piece.strip()
            if not piece:
                continue
            host = piece.split(":", 1)[0]
            if host:
                hosts.append(host)
        return hosts
    except Exception:
        return []


def _preflight_dns(mongo_url: str) -> tuple[bool, str]:
    """Pre-resolve every host in the URL AND attempt a tight TCP connect.
    Returns (ok, reason). Cheap, synchronous. NO MongoClient spawned
    regardless of result.

    Two-stage probe is critical: Atlas keeps DNS records alive even
    when the cluster is paused/decommissioned, so a `getaddrinfo` pass
    alone would happily return success for a dead cluster. The TCP
    connect is what catches the actually-unreachable case."""
    hosts = _hosts_from_mongo_url(mongo_url)
    if not hosts:
        return False, "no parseable hosts in URL"
    for h in hosts:
        # Stage 1 — name resolution.
        try:
            socket.setdefaulttimeout(SECONDARY_DNS_BUDGET_S)
            addrinfo = socket.getaddrinfo(h, 27017, type=socket.SOCK_STREAM)
        except socket.gaierror as e:
            return False, f"DNS fail for {h}: {e}"
        except socket.timeout:
            return False, f"DNS timeout (> {SECONDARY_DNS_BUDGET_S}s) for {h}"
        except Exception as e:
            return False, f"DNS probe error for {h}: {type(e).__name__}: {e}"
        finally:
            socket.setdefaulttimeout(None)

        # Stage 2 — TCP connect to first resolved address. Atlas DNS
        # outliving the cluster is the EXACT shape of the production
        # bug: name resolves, port 27017 doesn't accept. Without this
        # stage, pymongo gets to spawn its zombie topology thread and
        # the whole guard becomes a no-op.
        if not addrinfo:
            return False, f"DNS empty addrinfo for {h}"
        family, socktype, proto, _canon, sockaddr = addrinfo[0]
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(SECONDARY_DNS_BUDGET_S)
        try:
            sock.connect(sockaddr)
        except (socket.timeout, OSError) as e:
            return False, f"TCP connect fail for {h}:27017 — {type(e).__name__}: {e}"
        except Exception as e:
            return False, f"TCP probe error for {h}: {type(e).__name__}: {e}"
        finally:
            try:
                sock.close()
            except Exception:
                pass
    return True, "ok"


def _secondary_circuit_open() -> tuple[bool, str]:
    """True if the cooldown is still active. Caller should skip MongoClient
    construction entirely to avoid zombie topology threads."""
    if _SECONDARY_DNS_FAIL_UNTIL > time.time():
        remaining = int(_SECONDARY_DNS_FAIL_UNTIL - time.time())
        return True, (
            f"circuit OPEN ({remaining}s left) — last fail: "
            f"{_SECONDARY_DNS_FAIL_REASON}"
        )
    return False, ""


def _trip_secondary_circuit(reason: str) -> None:
    """Trip the breaker for SECONDARY_DNS_COOLDOWN_S seconds."""
    global _SECONDARY_DNS_FAIL_UNTIL, _SECONDARY_DNS_FAIL_REASON
    _SECONDARY_DNS_FAIL_UNTIL = time.time() + SECONDARY_DNS_COOLDOWN_S
    _SECONDARY_DNS_FAIL_REASON = reason[:200]
    logger.warning(
        f"[DR-BACKUP] secondary circuit TRIPPED for "
        f"{SECONDARY_DNS_COOLDOWN_S}s — {reason}"
    )

# ─────────────────────────────────────────────────────────────────────
# WHITELIST mode (iter 322au, May 2026)
# ─────────────────────────────────────────────────────────────────────
# Backup-Atlas is on a 500-collection-per-cluster tier (Atlas free/M0/M2/M5
# all share this cap). Mirroring every collection from primary blew past
# the cap and flooded the logs with `cannot create a new collection` errors
# during every deployment. From iter 322au onward we mirror ONLY the
# business-critical collections that we'd actually need to recover from
# disaster. Operational logs / heartbeats / audit chunks are intentionally
# NOT mirrored — they regenerate naturally post-failover.
DR_WHITELIST = {
    # auth + identity
    "users", "platform_users", "user_api_keys", "tenant_api_keys",
    "customer_api_keys", "api_keys",
    # commercial / billing
    "subscriptions", "subscription_plans", "payments",
    "payment_transactions", "invoices",
    # tenant business data
    "bins", "businesses", "business_intelligence", "bin_intelligence",
    "tenant_health", "tenant_branding", "tenant_booking_services",
    "tenant_settings",
    # customer-facing artifacts
    "bookings", "leads", "lead_intelligence", "appointments",
    "unified_inbox", "messages", "conversations", "campaigns",
    "websites", "sites", "site_pages",
    # founder / admin
    "admin_audit_log", "admin_actions",
    "founder_provision_attempts", "founder_state",
    # learning + intelligence (small, valuable)
    "ora_brain_thoughts", "fix_patterns", "agent_dependency_map",
}

# Anything matching these prefixes/suffixes is treated as transient log noise
# and skipped from DR backup unconditionally — these are the ones the deploy
# logs flagged as repeatedly hitting the 500-collection cap.
TRANSIENT_PATTERNS = (
    "_log", "_logs", "_audit", "_heartbeats", "heartbeats",
    "_archive", "client_errors", "auto_heal", "pillar_heartbeats",
    "temp_buffer", "_quarantine", "hunter_live_tests",
    "voice_interactions", "search_quota", "webauthn_challenges",
    "live_patches", "autotune_usage_log", "morning_briefs",
    "monday_briefs", "case_study_reports", "sent_emails", "email_logs",
    "ora_learning_digests", "founder_notifications", "do_not_contact",
    "site_content", "orders", "_backup_metadata",
)

# Collections we never want to mirror (transient / huge / sensitive).
# High-volume operational/audit logs are intentionally skipped — they're
# write-only noise that bloats the secondary without aiding recovery.
EXCLUDE_COLLECTIONS = {
    "fs.files", "fs.chunks",          # GridFS files (size)
    "system.indexes", "system.users", # mongo internal
    "session_logs",                    # transient
    "api_audit_log", "site_monitor_logs", "qa_bot_endpoint_log",
    "agent_feed", "a2a_events",
    "sentinel_diagnoses_archive", "cost_savings_log_archive",
    "auto_heal_log_archive", "council_decisions_archive",
    "db_backup_runs",                  # self-referential
}


def _is_transient(name: str) -> bool:
    """True if collection name looks like a high-volume log we should skip."""
    low = name.lower()
    for pat in TRANSIENT_PATTERNS:
        if pat in low:
            return True
    return False


# Hard ceiling — never let the secondary exceed this. 480 leaves headroom
# under Atlas's 500-collection cluster cap.
SECONDARY_COLLECTION_CEILING = 480

# Page size when streaming docs (memory bound)
PAGE_SIZE = 500


def _send_failure_email(error_msg: str, run_id: str) -> None:
    """Best-effort Resend email to founder on backup failure. Never raises."""
    try:
        api_key = os.environ.get("RESEND_API_KEY")
        if not api_key:
            return
        import resend
        resend.api_key = api_key
        founder_email = os.environ.get(
            "FOUNDER_ALERT_EMAIL", "teji.ss1986@gmail.com"
        )
        resend.Emails.send({
            "from": "AUREM Ops <ops@aurem.live>",
            "to": [founder_email],
            "subject": f"⚠️ AUREM DR backup FAILED — {run_id}",
            "html": (
                f"<h2>DR Backup failure</h2>"
                f"<p><b>Run ID:</b> {run_id}</p>"
                f"<p><b>Time:</b> {datetime.now(timezone.utc).isoformat()}</p>"
                f"<p><b>Error:</b></p>"
                f"<pre style='background:#111;color:#f5d76e;padding:14px;"
                f"border-radius:6px;overflow:auto'>{error_msg}</pre>"
                f"<p>Check <code>db_backup_runs</code> collection for details.</p>"
            ),
        })
    except Exception as _e:
        logger.warning(f"[DR-BACKUP] failure-email send failed: {_e}")


def _mirror_collection(
    primary_db, secondary_db, coll_name: str
) -> Dict[str, Any]:
    """
    Mirror a single collection from primary to secondary.
    Strategy: drop secondary collection then bulk insert (cheapest for full mirror).
    Returns dict with stats.
    """
    src = primary_db[coll_name]
    dst = secondary_db[coll_name]
    started = time.time()

    # Drop the secondary collection so we get a clean mirror (no stale docs).
    try:
        dst.drop()
    except PyMongoError as e:
        logger.warning(f"[DR-BACKUP] drop {coll_name} failed: {e}")

    inserted = 0
    skipped = 0
    batch = []
    cursor = src.find({}, no_cursor_timeout=False).batch_size(PAGE_SIZE)
    cap_hit = False
    try:
        for doc in cursor:
            if cap_hit:
                # secondary at 500-collection cap → stop trying further
                skipped += 1
                continue
            batch.append(doc)
            if len(batch) >= PAGE_SIZE:
                try:
                    dst.insert_many(batch, ordered=False)
                    inserted += len(batch)
                except PyMongoError as e:
                    skipped += len(batch)
                    msg = str(e)
                    if "already using 500 collections" in msg:
                        cap_hit = True
                        logger.warning(
                            f"[DR-BACKUP] secondary at collection cap — "
                            f"abandoning further inserts for {coll_name}"
                        )
                    else:
                        logger.warning(
                            f"[DR-BACKUP] insert_many {coll_name} chunk failed: {e}"
                        )
                batch = []
        if batch and not cap_hit:
            try:
                dst.insert_many(batch, ordered=False)
                inserted += len(batch)
            except PyMongoError as e:
                skipped += len(batch)
                msg = str(e)
                if "already using 500 collections" in msg:
                    cap_hit = True
                    logger.warning(
                        f"[DR-BACKUP] secondary at collection cap — "
                        f"tail skipped for {coll_name}"
                    )
                else:
                    logger.warning(
                        f"[DR-BACKUP] insert_many {coll_name} tail failed: {e}"
                    )
    finally:
        cursor.close()

    return {
        "collection": coll_name,
        "inserted": inserted,
        "skipped": skipped,
        "cap_hit": cap_hit,
        "elapsed_ms": int((time.time() - started) * 1000),
    }


def run_backup(triggered_by: str = "scheduler") -> Dict[str, Any]:
    """
    Run a full primary → secondary mirror. Returns a dict with full run report.
    Logs progress + persists final report to PRIMARY db_backup_runs collection.
    """
    started_at = datetime.now(timezone.utc)
    run_id = f"dr-{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    primary_url = os.environ.get("MONGO_URL")
    secondary_url = os.environ.get("SECONDARY_MONGO_URL")
    db_name = os.environ.get("DB_NAME", "aurem_db")

    report: Dict[str, Any] = {
        "run_id": run_id,
        "triggered_by": triggered_by,
        "started_at": started_at.isoformat(),
        "status": "running",
        "collections": [],
        "totals": {"inserted": 0, "skipped": 0, "collections": 0},
    }

    if not primary_url:
        report["status"] = "fail"
        report["error"] = "MONGO_URL not configured"
        return report
    if not secondary_url:
        report["status"] = "fail"
        report["error"] = (
            "SECONDARY_MONGO_URL not configured — DR backup disabled"
        )
        logger.warning(f"[DR-BACKUP] {run_id} skipped: SECONDARY_MONGO_URL missing")
        return report

    # iter 326m-stab.D — circuit breaker. If we recently determined the
    # secondary is unreachable, skip CLEANLY. No MongoClient(...) call,
    # no zombie topology thread, no log storm.
    open_, reason = _secondary_circuit_open()
    if open_:
        report["status"] = "skipped"
        report["error"] = f"secondary unreachable — {reason}"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[DR-BACKUP] {run_id} skipped — {reason}")
        return report

    # iter 326m-stab.D — DNS pre-flight on the SECONDARY URL. If hostname
    # doesn't resolve, fail fast and trip the circuit. We skip pymongo
    # entirely so its topology monitor never spawns.
    sec_ok, sec_reason = _preflight_dns(secondary_url)
    if not sec_ok:
        _trip_secondary_circuit(sec_reason)
        report["status"] = "skipped"
        report["error"] = f"secondary DNS pre-flight failed: {sec_reason}"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.warning(
            f"[DR-BACKUP] {run_id} skipped — {sec_reason}. "
            f"Update SECONDARY_MONGO_URL in deployment env vars."
        )
        return report

    primary_client: Optional[MongoClient] = None
    secondary_client: Optional[MongoClient] = None

    try:
        primary_client = MongoClient(primary_url, serverSelectionTimeoutMS=10000)
        secondary_client = MongoClient(
            secondary_url, serverSelectionTimeoutMS=15000
        )
        # Sanity ping both ends
        primary_client.admin.command("ping")
        secondary_client.admin.command("ping")

        primary_db = primary_client[db_name]
        # Use the SAME db_name on the secondary so app failover is a 1-line URL swap.
        secondary_db = secondary_client[db_name]

        # ── iter 322au: pre-flight collection-cap guard ─────────────
        # Atlas free/M0/M2/M5 tiers have a hard 500-collection-per-cluster
        # cap. If the secondary is already near the ceiling, abort the run
        # gracefully instead of flooding logs with `cannot create new
        # collection` errors during deployment.
        try:
            secondary_coll_count = len(secondary_db.list_collection_names())
        except Exception as e:
            secondary_coll_count = 0
            logger.warning(f"[DR-BACKUP] could not count secondary collections: {e}")

        if secondary_coll_count >= SECONDARY_COLLECTION_CEILING:
            report["status"] = "skipped"
            report["error"] = (
                f"Secondary cluster has {secondary_coll_count} collections "
                f"(>= {SECONDARY_COLLECTION_CEILING} ceiling). DR mirror "
                f"skipped to avoid Atlas 500-collection cap. Upgrade tier "
                f"or prune unused collections to resume mirroring."
            )
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            logger.warning(f"[DR-BACKUP] {run_id} skipped — {report['error']}")
            return report

        # ── iter 322au: whitelist-only mirror ─────────────────────────
        # Mirror only business-critical collections (see DR_WHITELIST).
        # Skip anything in EXCLUDE_COLLECTIONS, anything matching the
        # transient log patterns, and anything starting with `system.`.
        all_names = primary_db.list_collection_names()
        coll_names = [
            c for c in all_names
            if c in DR_WHITELIST
            and c not in EXCLUDE_COLLECTIONS
            and not c.startswith("system.")
            and not _is_transient(c)
        ]
        logger.info(
            f"[DR-BACKUP] {run_id} started — "
            f"{len(coll_names)}/{len(all_names)} collections to mirror "
            f"(whitelist mode; secondary has {secondary_coll_count} cols)"
        )

        for name in coll_names:
            stats = _mirror_collection(primary_db, secondary_db, name)
            report["collections"].append(stats)
            report["totals"]["inserted"] += stats["inserted"]
            report["totals"]["skipped"] += stats["skipped"]
            report["totals"]["collections"] += 1
            if stats.get("cap_hit"):
                logger.warning(
                    f"[DR-BACKUP] {run_id} aborting remaining collections — "
                    f"secondary Atlas cluster at 500-collection cap"
                )
                report["aborted_due_to_cap"] = True
                break

        report["status"] = "ok"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_seconds"] = int(
            (datetime.now(timezone.utc) - started_at).total_seconds()
        )
        logger.info(
            f"[DR-BACKUP] {run_id} done — "
            f"{report['totals']['collections']} cols, "
            f"{report['totals']['inserted']} docs, "
            f"{report['elapsed_seconds']}s"
        )
    except Exception as e:
        report["status"] = "fail"
        report["error"] = f"{type(e).__name__}: {e}"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.exception(f"[DR-BACKUP] {run_id} failed: {e}")
        _send_failure_email(str(e), run_id)
    finally:
        # Persist run report to PRIMARY (for ops dashboard); never throw.
        try:
            if primary_client is not None:
                primary_client[db_name]["db_backup_runs"].insert_one(dict(report))
        except Exception as _e:
            logger.warning(f"[DR-BACKUP] could not persist run report: {_e}")
        try:
            if primary_client is not None:
                primary_client.close()
            if secondary_client is not None:
                secondary_client.close()
        except Exception:
            pass

    return report


async def run_backup_async(triggered_by: str = "scheduler") -> Dict[str, Any]:
    """Async wrapper — runs the sync backup in a worker thread so the event
    loop is not blocked by long-running pymongo IO."""
    import asyncio
    return await asyncio.to_thread(run_backup, triggered_by)
