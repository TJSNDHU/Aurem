"""
AUREM Multi-Agent Pipeline (OODA Loop)
========================================
Staged pipeline replacing keyword-matching in ORA Action Router.

  SCOUT     → Reads logs, site state, user input (Observation)
  ARCHITECT → Maps observations to system capabilities (Orientation)
  ENVOY     → Selects the specific tool/function to execute (Decision)
  CLOSER    → Executes the final system mutation or API call (Action)
  VERIFIER  → Checks system health post-action (Recursive validation)

Persistence: Pipeline state stored in MongoDB for crash recovery.
Escalation: WhatsApp alert on 4th failure, Safe Mode for tenant.
"""
import os
import time
import uuid
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MAX_VERIFY_RETRIES = 3
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

_db = None


def set_db(database):
    global _db
    _db = database


def get_db():
    return _db


# ═══════════════════════════════════════════════════════════════
# PIPELINE STATE MODEL
# ═══════════════════════════════════════════════════════════════

class PipelineState(BaseModel):
    pipeline_id: str
    tenant_id: str
    stage: str = "scout"  # scout, architect, envoy, closer, verifier, done, failed, safe_mode
    input_text: str = ""
    scout_output: Optional[Dict] = None
    architect_output: Optional[Dict] = None
    envoy_output: Optional[Dict] = None
    closer_output: Optional[Dict] = None
    verify_attempts: int = 0
    error_log: List[str] = []
    created_at: str = ""
    updated_at: str = ""


async def _save_state(state: PipelineState):
    """Persist pipeline state to MongoDB for crash recovery."""
    db = get_db()
    if db is None:
        return
    doc = state.model_dump()
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db["pipeline_states"].update_one(
        {"pipeline_id": state.pipeline_id},
        {"$set": doc},
        upsert=True,
    )


async def _load_state(pipeline_id: str) -> Optional[PipelineState]:
    """Load pipeline state from MongoDB."""
    db = get_db()
    if db is None:
        return None
    doc = await db["pipeline_states"].find_one({"pipeline_id": pipeline_id}, {"_id": 0})
    if doc:
        return PipelineState(**doc)
    return None


# ═══════════════════════════════════════════════════════════════
# ACTION REGISTRY (same actions, now structured for agents)
# ═══════════════════════════════════════════════════════════════

ACTION_REGISTRY = {
    "fix_seo": {"name": "Fix SEO Issues", "engine": "ai_repair", "params": ["url"],
                "voice_response": "I'm scanning your site for SEO issues now. I'll fix what I find.",
                "triggers": ["fix seo", "repair seo", "seo issues", "fix my seo", "check seo"]},
    "scan_accessibility": {"name": "Accessibility Audit", "engine": "ai_repair", "params": ["url"],
                           "voice_response": "Running an accessibility audit now.",
                           "triggers": ["fix accessibility", "accessibility audit", "wcag check", "ada compliance"]},
    "send_invoice": {"name": "Send Invoice", "engine": "revenue", "params": ["customer_name", "amount", "description"],
                     "voice_response": "Creating the invoice now.",
                     "triggers": ["send invoice", "create invoice", "bill customer", "send a bill"]},
    "send_reminder": {"name": "Payment Reminder", "engine": "revenue", "params": ["invoice_id"],
                      "voice_response": "Sending the payment reminder now.",
                      "triggers": ["send reminder", "payment reminder", "chase payment", "remind customer"]},
    "scan_customers": {"name": "Customer Scan", "engine": "scanner", "params": [],
                       "voice_response": "Analyzing your customer database.",
                       "triggers": ["scan customers", "customer analysis", "analyze customers"]},
    "check_revenue": {"name": "Revenue Report", "engine": "revenue", "params": [],
                      "voice_response": "Pulling your revenue numbers now.",
                      "triggers": ["revenue report", "how much revenue", "sales report", "check revenue"]},
    "import_products": {"name": "Import Products", "engine": "universal", "params": ["file_url"],
                        "voice_response": "Ready to import your product catalog.",
                        "triggers": ["import products", "upload products", "add inventory", "bulk import"]},
    "ghost_mode_toggle": {"name": "Ghost Mode", "engine": "settings", "params": ["enabled"],
                          "voice_response": "Toggling Ghost Mode.",
                          "triggers": ["ghost mode", "autopilot", "autonomous mode", "auto mode"]},
    "voice_debug": {"name": "Voice Debug", "engine": "ai_repair", "params": ["url", "issue_description"],
                    "voice_response": "I see the issue. Let me analyze and fix it.",
                    "triggers": ["debug this", "fix this page", "something is broken"]},
}


# ═══════════════════════════════════════════════════════════════
# AGENT 1: SCOUT (Observation)
# ═══════════════════════════════════════════════════════════════

class ScoutAgent:
    """Reads logs, site state, user input. Produces structured observation."""

    async def observe(self, text: str, tenant_id: str, context: Optional[Dict] = None) -> Dict:
        start = time.time()
        db = get_db()

        # Hermes Memory: recall prior successes before observing
        scout_memory_recall = {}
        try:
            from services.hermes_memory_agent import recall as hermes_recall
            scout_memory_recall = await hermes_recall(tenant_id, text, "scout")
        except Exception as mem_err:
            logger.debug(f"[Pipeline] SCOUT memory recall: {mem_err}")

        # Gather environment signals
        recent_errors = []
        active_ghost = False
        if db is not None:
            try:
                errors = await db["ora_action_logs"].find(
                    {"tenant_id": tenant_id, "result_status": "error"},
                    {"_id": 0, "action_id": 1, "created_at": 1}
                ).sort("created_at", -1).limit(3).to_list(3)
                recent_errors = [e.get("action_id", "") for e in errors]
            except Exception as e:
                logger.debug(f"[Pipeline] SCOUT recent_errors lookup: {e}")
            try:
                settings = await db["tenant_settings"].find_one({"tenant_id": tenant_id}, {"_id": 0, "ghost_mode": 1})
                active_ghost = settings.get("ghost_mode", False) if settings else False
            except Exception as e:
                logger.debug(f"[Pipeline] SCOUT ghost_mode lookup: {e}")

        observation = {
            "input_text": text,
            "input_length": len(text),
            "tenant_id": tenant_id,
            "context": context or {},
            "recent_errors": recent_errors,
            "ghost_mode_active": active_ghost,
            "scout_memory_recall": scout_memory_recall,
            "observation_time_ms": round((time.time() - start) * 1000, 1),
        }
        return observation


# ═══════════════════════════════════════════════════════════════
# AGENT 2: ARCHITECT (Orientation)
# ═══════════════════════════════════════════════════════════════

class ArchitectAgent:
    """Maps observations to system capabilities. Picks candidate actions."""

    async def orient(self, observation: Dict) -> Dict:
        start = time.time()
        text_lower = observation["input_text"].lower().strip()

        # Score all actions against input
        candidates = []
        for action_id, action in ACTION_REGISTRY.items():
            max_score = 0
            matched_trigger = ""
            for trigger in action["triggers"]:
                if trigger in text_lower:
                    score = len(trigger) / max(len(text_lower), 1)
                    if score > max_score:
                        max_score = score
                        matched_trigger = trigger
            if max_score > 0:
                candidates.append({
                    "action_id": action_id,
                    "score": round(max_score, 3),
                    "trigger": matched_trigger,
                    "engine": action["engine"],
                })

        # LLM fallback for ambiguous inputs (no trigger match)
        if not candidates and EMERGENT_LLM_KEY and len(text_lower) > 5:
            try:
                candidates = await self._llm_classify(text_lower)
            except Exception as e:
                logger.warning(f"[Architect] LLM classify failed: {e}")

        candidates.sort(key=lambda c: c["score"], reverse=True)

        # Check if the top candidate's engine had recent errors
        avoid_engines = set()
        for err_action in observation.get("recent_errors", []):
            info = ACTION_REGISTRY.get(err_action, {})
            if info:
                avoid_engines.add(info.get("engine", ""))

        return {
            "candidates": candidates[:3],
            "top_match": candidates[0] if candidates else None,
            "avoid_engines": list(avoid_engines),
            "orientation_time_ms": round((time.time() - start) * 1000, 1),
        }

    async def _llm_classify(self, text: str) -> List[Dict]:
        """Use LLM to classify intent when keyword matching fails."""
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        action_list = ", ".join([f'"{k}"' for k in ACTION_REGISTRY.keys()])
        prompt = f'Given this user request: "{text[:300]}", which of these actions best matches? Actions: [{action_list}]. Return JSON: {{"action_id": "...", "confidence": 0.0-1.0}} or {{"action_id": null}} if none match.'

        llm = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"arch_{int(time.time())}",
            system_message="You classify user intents into system actions. Return only valid JSON.",
        ).with_model("openai", "gpt-4o")

        resp = await llm.send_message(UserMessage(text=prompt))
        resp_text = resp if isinstance(resp, str) else str(resp)

        import re
        match = re.search(r'\{[^{}]*"action_id"[^{}]*\}', resp_text)
        if match:
            data = json.loads(match.group())
            if data.get("action_id") and data["action_id"] in ACTION_REGISTRY:
                return [{"action_id": data["action_id"], "score": float(data.get("confidence", 0.7)), "trigger": "llm_classified", "engine": ACTION_REGISTRY[data["action_id"]]["engine"]}]
        return []


# ═══════════════════════════════════════════════════════════════
# AGENT 3: ENVOY (Decision)
# ═══════════════════════════════════════════════════════════════

class EnvoyAgent:
    """Selects the specific tool/function call to execute."""

    async def decide(self, orientation: Dict, observation: Dict) -> Dict:
        start = time.time()
        top = orientation.get("top_match")

        if not top:
            return {
                "decision": "no_action",
                "action_id": None,
                "voice_response": "I can help with SEO repairs, invoicing, revenue reports, customer analysis, and more. What would you like me to do?",
                "decision_time_ms": round((time.time() - start) * 1000, 1),
            }

        action_id = top["action_id"]
        action = ACTION_REGISTRY[action_id]

        # If engine was recently erroring, pick alternative
        avoid = set(orientation.get("avoid_engines", []))
        if action["engine"] in avoid and len(orientation["candidates"]) > 1:
            alt = orientation["candidates"][1]
            action_id = alt["action_id"]
            action = ACTION_REGISTRY[action_id]
            logger.info(f"[Envoy] Avoiding {top['engine']}, using {action_id}")

        return {
            "decision": "execute",
            "action_id": action_id,
            "action_name": action["name"],
            "engine": action["engine"],
            "required_params": action["params"],
            "voice_response": action["voice_response"],
            "confidence": top["score"],
            "decision_time_ms": round((time.time() - start) * 1000, 1),
        }


# ═══════════════════════════════════════════════════════════════
# AGENT 4: CLOSER (Action)
# ═══════════════════════════════════════════════════════════════

class CloserAgent:
    """Executes the final system mutation or API call."""

    async def execute(self, decision: Dict, tenant_id: str, params: Optional[Dict] = None) -> Dict:
        start = time.time()
        db = get_db()
        if db is None:
            return {"status": "error", "voice_summary": "System unavailable.", "data": {}}

        # SOC 2 RBAC: Scope Closer to specific tenant, verify write permission
        from services.agent_rbac import check_permission, Permission, scope_agent_to_tenant, clear_agent_scope
        agent_id = f"closer_{tenant_id}"
        scope_agent_to_tenant(agent_id, tenant_id)

        if not check_permission("closer", Permission.DB_WRITE, tenant_id):
            clear_agent_scope(agent_id)
            return {"status": "error", "voice_summary": "Permission denied.", "data": {}}

        action_id = decision["action_id"]
        params = params or {}
        result = {"status": "completed", "data": {}, "voice_summary": ""}
        now = datetime.now(timezone.utc).isoformat()

        try:
            if action_id == "check_revenue":
                pipeline = [
                    {"$match": {"tenant_id": tenant_id, "status": "paid"}},
                    {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}}
                ]
                agg = await db.invoices.aggregate(pipeline).to_list(1)
                stats = agg[0] if agg else {"total": 0, "count": 0}
                pending = await db.invoices.count_documents({"tenant_id": tenant_id, "status": {"$in": ["sent", "awaiting_payment"]}})
                overdue = await db.invoices.count_documents({"tenant_id": tenant_id, "status": "overdue"})
                result["data"] = {"paid_total": stats.get("total", 0), "paid_count": stats.get("count", 0), "pending": pending, "overdue": overdue}
                result["voice_summary"] = f"You have ${stats.get('total', 0):,.2f} collected from {stats.get('count', 0)} paid invoices. {pending} pending, {overdue} overdue."

            elif action_id == "scan_customers":
                total = await db.tenant_customers.count_documents({"tenant_id": tenant_id})
                result["data"] = {"total_customers": total}
                result["voice_summary"] = f"You have {total} customers in your database."

            elif action_id == "send_reminder":
                inv_id = params.get("invoice_id")
                if inv_id:
                    await db.payment_reminders.insert_one({
                        "id": str(uuid.uuid4()), "tenant_id": tenant_id,
                        "invoice_id": inv_id, "sent_at": now,
                        "method": "pipeline_triggered", "status": "sent",
                    })
                    result["voice_summary"] = "Payment reminder sent successfully."
                else:
                    result["voice_summary"] = "Which invoice should I send a reminder for?"
                    result["status"] = "needs_params"

            elif action_id == "ghost_mode_toggle":
                enabled = params.get("enabled", True)
                await db.tenant_settings.update_one(
                    {"tenant_id": tenant_id},
                    {"$set": {"ghost_mode": enabled, "updated_at": now}},
                    upsert=True,
                )
                result["voice_summary"] = f"Ghost Mode is now {'ON' if enabled else 'OFF'}."

            else:
                engine = decision.get("engine", "unknown")
                result["voice_summary"] = f"Action '{action_id}' routed to {engine} engine."

        except Exception as e:
            logger.error(f"[Closer] Execution error: {e}")
            result["status"] = "error"
            result["voice_summary"] = "I encountered an error. Let me try a different approach."

        result["execution_time_ms"] = round((time.time() - start) * 1000, 1)

        # SOC 2 Audit Trail: log every Closer write action
        if db is not None:
            try:
                await db["aurem_audit_logs"].insert_one({
                    "action": "agent_action",
                    "business_id": tenant_id,
                    "actor_id": agent_id,
                    "actor_type": "ai",
                    "resource_type": "pipeline_action",
                    "resource_id": action_id,
                    "details": {
                        "decision": decision.get("action_id"),
                        "engine": decision.get("engine", "unknown"),
                        "execution_time_ms": result["execution_time_ms"],
                    },
                    "success": result["status"] == "completed",
                    "timestamp": datetime.now(timezone.utc),
                    "_immutable": True,
                })
            except Exception as audit_err:
                logger.debug(f"[Closer] Audit log error: {audit_err}")

        # Clear RBAC scope
        clear_agent_scope(agent_id)

        return result


# ═══════════════════════════════════════════════════════════════
# AGENT 5: VERIFIER (Post-Action Health Check)
# ═══════════════════════════════════════════════════════════════

class VerifierAgent:
    """Checks system health post-action. Loops back to ENVOY on failure."""

    async def verify(self, closer_output: Dict, tenant_id: str) -> Dict:
        start = time.time()
        checks = {"db_ok": False, "status_ok": False, "latency_ok": False}

        # Check 1: Closer status
        checks["status_ok"] = closer_output.get("status") in ("completed", "needs_params")

        # Check 2: DB connectivity
        db = get_db()
        if db is not None:
            try:
                await db.command("ping")
                checks["db_ok"] = True
            except Exception as e:
                logger.warning(f"[Pipeline] VERIFIER db ping failed: {e}")

        # Check 3: Execution latency < 500ms
        exec_ms = closer_output.get("execution_time_ms", 0)
        checks["latency_ok"] = exec_ms < 500

        passed = all(checks.values())
        return {
            "passed": passed,
            "checks": checks,
            "verify_time_ms": round((time.time() - start) * 1000, 1),
        }


# ═══════════════════════════════════════════════════════════════
# PIPELINE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

# Singleton agent instances
_scout = ScoutAgent()
_architect = ArchitectAgent()
_envoy = EnvoyAgent()
_closer = CloserAgent()
_verifier = VerifierAgent()


async def run_pipeline(
    text: str,
    tenant_id: str,
    context: Optional[Dict] = None,
    params: Optional[Dict] = None,
    pipeline_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the full OODA pipeline: SCOUT → ARCHITECT → ENVOY → CLOSER → VERIFIER.
    Recursive retry on verify failure (max 3). Escalation on 4th.
    """
    pipeline_id = pipeline_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    state = PipelineState(
        pipeline_id=pipeline_id,
        tenant_id=tenant_id,
        input_text=text,
        created_at=now,
        updated_at=now,
    )

    total_start = time.time()

    try:
        # ── STAGE 1: SCOUT ──
        state.stage = "scout"
        await _save_state(state)
        observation = await _scout.observe(text, tenant_id, context)
        state.scout_output = observation

        # ── STAGE 2: ARCHITECT ──
        state.stage = "architect"
        await _save_state(state)
        orientation = await _architect.orient(observation)
        state.architect_output = orientation

        # ── STAGE 3: ENVOY ──
        state.stage = "envoy"
        await _save_state(state)
        decision = await _envoy.decide(orientation, observation)
        state.envoy_output = decision

        if decision["decision"] == "no_action":
            state.stage = "done"
            await _save_state(state)
            return _build_result(state, decision, total_start)

        # ── RECURSIVE CLOSER + VERIFIER LOOP ──
        for attempt in range(MAX_VERIFY_RETRIES + 1):
            state.verify_attempts = attempt

            # ── STAGE 4: CLOSER ──
            state.stage = "closer"
            await _save_state(state)
            closer_result = await _closer.execute(decision, tenant_id, params)
            state.closer_output = closer_result

            # ── STAGE 5: VERIFIER ──
            state.stage = "verifier"
            await _save_state(state)
            verify = await _verifier.verify(closer_result, tenant_id)

            if verify["passed"]:
                state.stage = "done"
                await _save_state(state)
                # Hermes Memory: auto-store pipeline result
                try:
                    from services.hermes_memory_agent import fire_and_forget_store
                    fire_and_forget_store(
                        tenant_id=tenant_id,
                        session_id=pipeline_id,
                        agent_id=f"pipeline_{decision.get('action_id', 'unknown')}",
                        input_text=text[:300],
                        output_text=closer_result.get("voice_summary", "")[:300],
                        outcome="success" if closer_result.get("status") == "completed" else "partial",
                        action_type=decision.get("action_id", "pipeline_action"),
                        execution_time_s=(time.time() - total_start),
                        metadata={"engine": decision.get("engine", ""), "verify_attempts": attempt},
                    )
                except Exception:
                    pass
                return _build_result(state, closer_result, total_start, verify)

            # Verify failed — log and retry
            err_msg = f"Attempt {attempt + 1}: verify failed — {verify['checks']}"
            state.error_log.append(err_msg)
            logger.warning(f"[Pipeline] {tenant_id}: {err_msg}")

            if attempt < MAX_VERIFY_RETRIES:
                # Loop back to ENVOY with updated orientation (avoid failed engine)
                if closer_result.get("status") == "error":
                    engine = decision.get("engine", "")
                    orientation.setdefault("avoid_engines", [])
                    if engine not in orientation["avoid_engines"]:
                        orientation["avoid_engines"].append(engine)
                decision = await _envoy.decide(orientation, observation)
                state.envoy_output = decision
                if decision["decision"] == "no_action":
                    break

        # ── 4th FAILURE: ESCALATION ──
        state.stage = "safe_mode"
        await _save_state(state)
        # Hermes Memory: store escalation failure
        try:
            from services.hermes_memory_agent import fire_and_forget_store
            fire_and_forget_store(
                tenant_id=tenant_id,
                session_id=pipeline_id,
                agent_id="pipeline_escalation",
                input_text=text[:300],
                output_text="Escalated after max retries",
                outcome="failure",
                action_type=decision.get("action_id", "pipeline_escalation") if decision else "pipeline_escalation",
                execution_time_s=(time.time() - total_start),
                metadata={"error_log": state.error_log[-3:]},
            )
        except Exception:
            pass
        await _escalate(tenant_id, state)

        closer_result = state.closer_output or {}
        closer_result["voice_summary"] = "I'm having trouble completing that. I've flagged this for the team."
        closer_result["status"] = "escalated"
        return _build_result(state, closer_result, total_start)

    except Exception as e:
        state.stage = "failed"
        state.error_log.append(str(e))
        await _save_state(state)
        logger.error(f"[Pipeline] Fatal error for {tenant_id}: {e}")
        return {
            "resolved": False,
            "pipeline_id": pipeline_id,
            "status": "error",
            "voice_summary": "I encountered an issue. Please try again.",
            "error": str(e),
        }


def _build_result(state: PipelineState, action_result: Dict, start_time: float, verify: Dict = None) -> Dict:
    """Build the final pipeline response."""
    decision = state.envoy_output or {}
    return {
        "resolved": decision.get("decision") != "no_action",
        "pipeline_id": state.pipeline_id,
        "action_id": decision.get("action_id"),
        "action_name": decision.get("action_name"),
        "voice_response": action_result.get("voice_summary") or decision.get("voice_response", ""),
        "status": action_result.get("status", "completed"),
        "data": action_result.get("data", {}),
        "confidence": decision.get("confidence", 0),
        "stages": {
            "scout_ms": state.scout_output.get("observation_time_ms", 0) if state.scout_output else 0,
            "architect_ms": state.architect_output.get("orientation_time_ms", 0) if state.architect_output else 0,
            "envoy_ms": decision.get("decision_time_ms", 0),
            "closer_ms": action_result.get("execution_time_ms", 0),
            "verify_ms": verify.get("verify_time_ms", 0) if verify else 0,
        },
        "verify_attempts": state.verify_attempts,
        "total_pipeline_ms": round((time.time() - start_time) * 1000, 1),
    }


async def _escalate(tenant_id: str, state: PipelineState):
    """4th failure escalation: WhatsApp alert + Safe Mode."""
    logger.critical(f"[Pipeline] ESCALATION for {tenant_id}: {state.error_log}")

    db = get_db()
    if db is not None:
        # Enter Safe Mode: pause Ghost Mode for this tenant
        await db["tenant_settings"].update_one(
            {"tenant_id": tenant_id},
            {"$set": {"ghost_mode": False, "safe_mode": True, "safe_mode_since": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        # Log escalation
        await db["security_events"].insert_one({
            "event_type": "pipeline_escalation",
            "severity": "critical",
            "tenant_id": tenant_id,
            "pipeline_id": state.pipeline_id,
            "error_log": state.error_log,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # WhatsApp alert
    try:
        from routers.whatsapp_alerts import send_whatsapp
        admin_phone = os.environ.get("ADMIN_WHATSAPP", "12265017777")
        errors = "; ".join(state.error_log[-3:])
        msg = f"AUREM PIPELINE ESCALATION: Tenant {tenant_id} entered Safe Mode after {state.verify_attempts + 1} failed attempts. Last errors: {errors}"
        await send_whatsapp(admin_phone, msg)
    except Exception as e:
        logger.error(f"[Pipeline] WhatsApp escalation failed: {e}")


# ═══════════════════════════════════════════════════════════════
# CLAWCHIEF DEADLOCK MONITOR HOOK
# ═══════════════════════════════════════════════════════════════

async def check_pipeline_deadlocks() -> List[Dict]:
    """
    Called by ClawChief to detect stuck pipelines.
    Returns list of deadlocked pipelines (stuck > 60 seconds).
    """
    db = get_db()
    if db is None:
        return []
    try:
        from datetime import timedelta
        threshold = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        stuck = await db["pipeline_states"].find({
            "stage": {"$nin": ["done", "failed", "safe_mode"]},
            "updated_at": {"$lt": threshold},
        }, {"_id": 0}).to_list(50)
        return stuck
    except Exception as e:
        logger.warning(f"[Pipeline] detect_stuck_pipelines error: {e}")
        return []


print("[STARTUP] Multi-Agent Pipeline loaded — SCOUT/ARCHITECT/ENVOY/CLOSER/VERIFIER active", flush=True)
