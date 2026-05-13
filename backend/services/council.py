"""
AUREM Council — Pre-Action Deliberation Layer (iter 296)
========================================================
Every major action runs through here BEFORE execution.

Voters:
  Heuristic agents (always run — free):
    - sentinel : budget + system health gate
    - architect: template-ready check (for site builds)
    - closer   : historical conversion probability
    - scout    : lead-data confidence
  LLM voters (cost-gated):
    - groq    : llama-3.3-70b — fast, cheap quality vote
    - claude  : Claude Sonnet via Emergent LLM Key — quality + CASL/legal
    - gemini  : Gemini Flash via Emergent LLM Key — content drafting if needed
  Chair:
    - ora_brain: weighted aggregation, final decision

Decision matrix:
  approved if avg_confidence >= 0.7 AND no veto AND cost <= threshold
  vetoed if any voter casts confidence <= 0.2 with reason="block"
  escalated if cost > escalate_above_usd OR avg_confidence in [0.5, 0.7)

Public API:
  decision = await council.deliberate(
      action_kind, payload, cost_usd=0.0,
      llm_voters=False,  # or True for high-stakes
      escalate_above_usd=5.0,
      confidence_threshold=0.7,
  )
  # → {decision_id, decision: approve|veto|escalate, confidence, votes, reason}
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


HIGH_STAKES_ACTIONS = {
    "site_deploy", "domain_purchase", "blast_to_50plus_leads",
    "stripe_charge", "founder_alert", "bulk_email", "voice_blast",
}


class Council:
    def __init__(self):
        self._db = None

    def set_db(self, db):
        self._db = db

    # ─── Heuristic voters ────────────────────────────────────────────────────
    async def _vote_sentinel(self, action_kind: str, payload: Dict, cost_usd: float) -> Dict:
        if cost_usd > 50:
            return {"agent": "sentinel", "confidence": 0.1, "verdict": "block",
                    "reason": f"cost ${cost_usd:.2f} exceeds 50 hard cap"}
        if cost_usd > 5:
            return {"agent": "sentinel", "confidence": 0.55, "verdict": "warn",
                    "reason": f"cost ${cost_usd:.2f} above $5 — escalate"}
        return {"agent": "sentinel", "confidence": 0.9, "verdict": "ok",
                "reason": f"cost ${cost_usd:.4f} within budget"}

    async def _vote_architect(self, action_kind: str, payload: Dict) -> Optional[Dict]:
        if action_kind != "site_deploy":
            return None
        niche = (payload.get("niche") or "").lower()
        if not niche:
            return {"agent": "architect", "confidence": 0.5, "verdict": "warn",
                    "reason": "no niche provided — using default template"}
        return {"agent": "architect", "confidence": 0.85, "verdict": "ok",
                "reason": f"template ready for niche={niche}"}

    async def _vote_closer(self, action_kind: str, payload: Dict) -> Optional[Dict]:
        if self._db is None:
            return None
        if action_kind not in ("outreach_blast", "site_deploy", "voice_blast"):
            return None
        try:
            similar = await self._db.agent_outcomes.count_documents({
                "action": action_kind, "outcome": "converted",
            })
            total = await self._db.agent_outcomes.count_documents({"action": action_kind})
            if total == 0:
                return {"agent": "closer", "confidence": 0.55, "verdict": "warn",
                        "reason": "no historical data yet"}
            rate = similar / total
            return {"agent": "closer", "confidence": min(0.5 + rate, 0.95), "verdict": "ok",
                    "reason": f"historical conv rate {rate:.1%} ({similar}/{total})"}
        except Exception as e:
            return {"agent": "closer", "confidence": 0.6, "verdict": "warn", "reason": str(e)[:80]}

    async def _vote_scout(self, action_kind: str, payload: Dict) -> Optional[Dict]:
        if action_kind != "outreach_blast":
            return None
        # Only vote on per-lead deliberation (when verification + channel_gating is supplied).
        # Founders-Console-style instructions ("send blast to 3 leads") have no lead context;
        # the actual per-lead gating happens later inside auto_blast_engine.
        ver = payload.get("verification")
        if not ver:
            return None
        # iter 282aa — if verification exists but channel_gating wasn't populated
        # (verifier timed out or hit a slow site), DON'T veto. The lead has phone
        # data already validated by `_eligible_leads`. Defer to closer/sentinel.
        # Only block when gating EXPLICITLY says all 4 channels closed.
        gates = ver.get("channel_gating")
        if not gates:
            return {"agent": "scout", "confidence": 0.65, "verdict": "ok",
                    "reason": "no gating hint — defer to other voters"}
        open_count = sum(1 for v in gates.values() if v)
        if open_count == 0:
            return {"agent": "scout", "confidence": 0.2, "verdict": "block",
                    "reason": "no open channels for this lead"}
        return {"agent": "scout", "confidence": 0.6 + (open_count * 0.1), "verdict": "ok",
                "reason": f"{open_count} channel(s) open"}

    # ─── LLM voters (cost-gated) ─────────────────────────────────────────────
    async def _vote_llm(self, model: str, action_kind: str, payload: Dict) -> Optional[Dict]:
        """Single LLM vote via Emergent LLM Key; never throws."""
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            return None
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
        except Exception:
            return None
        try:
            session_id = f"council-{uuid.uuid4().hex[:8]}"
            provider, model_name = ("anthropic", "claude-sonnet-4.5") if model == "claude" \
                else ("gemini", "gemini-2.5-flash") if model == "gemini" \
                else ("openai", "gpt-4o-mini")
            chat = LlmChat(
                api_key=api_key, session_id=session_id,
                system_message=(
                    "You are an AUREM council voter. You will see an action_kind and payload. "
                    "Reply STRICTLY with JSON: "
                    '{"confidence": <float 0-1>, "verdict": "ok|warn|block", "reason": "<<= 80 chars>"}. '
                    "Vote 'block' only if action violates CASL/PIPEDA, contains PII you'd flag, "
                    "or is logically broken. Vote 'warn' if quality is poor. Otherwise 'ok'."
                ),
            ).with_model(provider, model_name).with_max_tokens(150)
            prompt = f"action_kind={action_kind}\npayload={str(payload)[:1200]}"
            resp = await asyncio.wait_for(chat.send_message(UserMessage(text=prompt)), timeout=8.0)
            import json as _json
            import re
            m = re.search(r"\{.*\}", resp or "", re.S)
            data = _json.loads(m.group(0)) if m else {}
            return {"agent": model, "confidence": float(data.get("confidence", 0.6)),
                    "verdict": data.get("verdict", "ok"), "reason": (data.get("reason") or "")[:120]}
        except Exception as e:
            logger.debug(f"[council] LLM vote {model} failed: {e}")
            return None

    # ─── Public deliberate ───────────────────────────────────────────────────
    async def deliberate(
        self,
        action_kind: str,
        payload: Dict[str, Any],
        cost_usd: float = 0.0,
        llm_voters: Optional[bool] = None,
        escalate_above_usd: float = 5.0,
        confidence_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        if llm_voters is None:
            llm_voters = (action_kind in HIGH_STAKES_ACTIONS) or (cost_usd >= 0.10)

        votes: List[Dict[str, Any]] = []

        # Heuristic voters
        for fn in (
            self._vote_sentinel(action_kind, payload, cost_usd),
            self._vote_architect(action_kind, payload),
            self._vote_closer(action_kind, payload),
            self._vote_scout(action_kind, payload),
        ):
            v = await fn
            if v:
                votes.append(v)

        # LLM voters (parallel, time-boxed)
        if llm_voters:
            llm_results = await asyncio.gather(
                self._vote_llm("claude", action_kind, payload),
                self._vote_llm("gemini", action_kind, payload),
                return_exceptions=True,
            )
            for r in llm_results:
                if isinstance(r, dict):
                    votes.append(r)

        # Aggregate
        confidences = [v["confidence"] for v in votes] or [0.6]
        avg_conf = sum(confidences) / len(confidences)
        veto_votes = [v for v in votes if v.get("verdict") == "block"]

        if veto_votes:
            decision = "veto"
            reason = "; ".join(f"{v['agent']}:{v['reason']}" for v in veto_votes)[:300]
        elif cost_usd > escalate_above_usd:
            decision = "escalate"
            reason = f"avg_conf={avg_conf:.2f}, cost=${cost_usd:.2f} — TJ approval needed (over ${escalate_above_usd})"
        elif avg_conf >= confidence_threshold:
            decision = "approve"
            reason = f"avg_conf={avg_conf:.2f}, {len(votes)} voters"
        elif 0.5 <= avg_conf < confidence_threshold:
            # iter 322g — for low-cost actions (<$0.10) avoid escalation:
            # auto-approve if confidence is at least 0.5. Saves the
            # founder from manual approval clicks on cheap outreach.
            if cost_usd < 0.10:
                decision = "approve"
                reason = (
                    f"avg_conf={avg_conf:.2f} (auto-approved: cost ${cost_usd:.3f}<$0.10, "
                    f"{len(votes)} voters)"
                )
            else:
                decision = "escalate"
                reason = f"avg_conf={avg_conf:.2f}, cost=${cost_usd:.2f} — TJ approval needed"
        else:
            decision = "veto"
            reason = f"avg_conf={avg_conf:.2f} below 0.5 — too risky"

        decision_id = uuid.uuid4().hex[:14]
        record = {
            "decision_id": decision_id,
            "action_kind": action_kind,
            "payload_summary": {k: payload.get(k) for k in ("lead_id", "domain", "niche", "to") if k in payload},
            "cost_usd": float(cost_usd),
            "votes": votes,
            "avg_confidence": round(avg_conf, 3),
            "decision": decision,
            "reason": reason,
            "llm_voters_used": llm_voters,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        # iter 282ah — schema-drift guard: ensure lead_id / created_at /
        # agent / action / status are always top-level and non-null.
        try:
            from services.schema_migrations import guard_council_record
            record = guard_council_record(record)
        except Exception:
            pass
        if self._db is not None:
            try:
                await self._db.council_decisions.insert_one(record)
                if decision == "escalate":
                    await self._db.pending_escalations.insert_one({
                        "decision_id": decision_id,
                        "action_kind": action_kind,
                        "reason": reason,
                        "cost_usd": cost_usd,
                        "ts": record["ts"],
                        "status": "pending",
                    })
            except Exception as e:
                logger.warning(f"[council] persist failed: {e}")

        logger.info(f"[council] {action_kind} → {decision} (avg_conf={avg_conf:.2f}, voters={len(votes)})")
        record.pop("_id", None)
        return record

    async def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        return await self._db.council_decisions.find({}, {"_id": 0}).sort("ts", -1).limit(int(limit)).to_list(int(limit))

    async def pending_escalations(self) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        return await self._db.pending_escalations.find({"status": "pending"}, {"_id": 0}).sort("ts", -1).to_list(50)


council = Council()


def set_db(db):
    council.set_db(db)
    try:
        import asyncio as _a
        async def _ix():
            try:
                await db.council_decisions.create_index([("ts", -1)], background=True)
                await db.council_decisions.create_index([("action_kind", 1), ("ts", -1)], background=True)
                await db.pending_escalations.create_index([("status", 1), ("ts", -1)], background=True)
            except Exception:
                pass
        _a.create_task(_ix())
    except Exception:
        pass
