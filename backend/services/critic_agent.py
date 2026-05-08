"""
Critic Agent — The 6th Agent (Zero-Trust Validation Layer)
==========================================================

Every agent output passes through the Critic before reaching the user
or being committed to MongoDB/workspace. Based on CriticGPT research:
- AI critic catches 85% of issues missed by primary agent
- Most common AI error: "Misinterpretation" (20.77%)
- Multi-LLM review improves quality 89% of the time

Three modes:
1. VALIDATE: Standard review — checks logic, data, SOUL.md compliance
2. ADVERSARIAL: Aggressive review — challenges assumptions, finds corner cases
3. RESCUE: Fallback when primary agent confidence < 0.7

Source: CriticGPT (OpenAI), ICLR 2025 Multi-LLM Study
"""

import logging
import json
import os
import re
import asyncio
from typing import Dict, Optional
from datetime import datetime, timezone

from services.ultraplinian_scorer import score_response as ultraplinian_score

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY")

_db = None


def set_db(database):
    global _db
    _db = database


def get_db():
    return _db


# ═══════════════════════════════════════════════════
# CRITIC SYSTEM PROMPTS
# ═══════════════════════════════════════════════════

CRITIC_VALIDATE_PROMPT = """CRITIC — AUREM zero-trust validator.
Find flaws in other agents' output.

5-Point QA:
1. FUNCTIONALITY: Actions executable? IDs valid? Links work?
2. HIERARCHY: Visual focus correct? Scientific-Luxe? No clutter?
3. DATA INTEGRITY: Numbers consistent? Totals add up? Percentages valid?
4. LOGIC: Conclusion follows data? Edge cases? False positives?
5. CONTENT: CEO-grade copy? No hedging/filler?

JSON only:
{"verdict":"APPROVED|FLAGGED","confidence":<0-1>,"issues":[{"type":"<FUNCTIONALITY|HIERARCHY|DATA_ERROR|LOGIC_GAP|CONTENT_QUALITY>","description":"<finding>","severity":"<critical|major|minor>"}],"qa_checklist":{"functionality":true,"hierarchy":true,"data_integrity":true,"logic":true,"content_quality":true},"recommendation":"<fix or 'Output validated'>"}"""

CRITIC_ADVERSARIAL_PROMPT = """You are the ADVERSARIAL CRITIC — your job is to BREAK other agents' conclusions.

Assume every output is wrong until proven right. Specifically challenge:
1. OVERCONFIDENCE: Is the confidence score justified by the data?
2. SURVIVORSHIP BIAS: Are we only looking at positive signals?
3. MISSING VARIABLES: What external factors could invalidate this forecast?
4. FALSE POSITIVES: Could these "high-quality leads" actually be noise?
5. PIPELINE INFLATION: Are deal values realistic? Are stages accurate?

You are not hostile — you are protecting a $302K pipeline from bad decisions.

Respond ONLY with valid JSON:
{
  "verdict": "VALIDATED" | "CHALLENGED",
  "confidence": <float 0-1>,
  "challenges": [{"aspect": "<specific claim being challenged>", "counter_argument": "<why it might be wrong>", "risk_level": "<high|medium|low>"}],
  "adjusted_confidence": <float 0-1, your estimate of the true confidence>,
  "recommendation": "<what the human should verify manually>"
}"""


# ═══════════════════════════════════════════════════
# CORE CRITIC ENGINE
# ═══════════════════════════════════════════════════

_critic_sessions = {}


def _get_critic_session(mode: str):
    """Get or create a critic LLM session."""
    if mode not in _critic_sessions:
        try:
            from emergentintegrations.llm.chat import LlmChat
            prompt = CRITIC_VALIDATE_PROMPT if mode == "validate" else CRITIC_ADVERSARIAL_PROMPT
            _critic_sessions[mode] = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"critic_{mode}",
                system_message=prompt,
            ).with_model("openai", "gpt-4o")
        except Exception as e:
            logger.error(f"[Critic] Session init error: {e}")
            return None
    return _critic_sessions[mode]


async def _call_critic(mode: str, review_input: str, model_hint: str = "critic") -> Dict:
    """
    Send data to the Critic via OpenRouter free model.
    Falls back to Emergent LLM Key, then heuristic.

    model_hint: "critic" (GPT-OSS-120B) or "heartbeat" (Step Flash)
    """
    prompt = CRITIC_VALIDATE_PROMPT if mode == "validate" else CRITIC_ADVERSARIAL_PROMPT

    try:
        from services.openrouter_client import call_model, AGENT_MODELS
        model = AGENT_MODELS.get(model_hint, AGENT_MODELS["critic"])

        # Hard cap — if LLM path (OpenRouter + failover) takes >12s, bail to
        # heuristic. This prevents the critic from starving the event loop
        # when OpenRouter is rate-limited AND Emergent failover 502s.
        result = await asyncio.wait_for(
            call_model(model, prompt, review_input, temperature=0.2, max_tokens=1500),
            timeout=12.0,
        )

        content = result.get("content", "")
        if not content:
            return _heuristic_review(review_input, mode)

        response_clean = content.strip()
        if response_clean.startswith("```"):
            match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response_clean, re.DOTALL)
            if match:
                response_clean = match.group(1)

        parsed = json.loads(response_clean)
        parsed["_model"] = result.get("model", "unknown")
        parsed["_provider"] = result.get("provider", "unknown")
        return parsed
    except json.JSONDecodeError:
        logger.warning("[Critic] Non-JSON response, falling back to heuristic")
        return _heuristic_review(review_input, mode)
    except asyncio.TimeoutError:
        logger.warning("[Critic] LLM path exceeded 12s timeout — using heuristic fallback")
        return _heuristic_review(review_input, mode)
    except Exception as e:
        logger.error(f"[Critic] OpenRouter error: {e}")
        return _heuristic_review(review_input, mode)


def _heuristic_review(data_str: str, mode: str) -> Dict:
    """
    Heuristic critic when LLM is unavailable.
    Checks for common patterns without AI.
    """
    issues = []

    # Check for suspiciously round numbers
    numbers = re.findall(r"\$[\d,]+", data_str)
    for n in numbers:
        val = int(n.replace("$", "").replace(",", ""))
        if val > 0 and val % 10000 == 0:
            issues.append({
                "type": "DATA_ERROR",
                "description": f"Suspiciously round number: {n}. Real data rarely lands on exact multiples.",
                "severity": "minor",
            })

    # Check for empty results
    if '"results": []' in data_str or '"plans": []' in data_str:
        issues.append({
            "type": "CORNER_CASE",
            "description": "Agent returned empty results. Was the query too restrictive?",
            "severity": "major",
        })

    # Check for missing summary
    if '"summary"' not in data_str:
        issues.append({
            "type": "LOGIC_GAP",
            "description": "Agent output missing summary field.",
            "severity": "minor",
        })

    if mode == "adversarial":
        return {
            "verdict": "CHALLENGED" if issues else "VALIDATED",
            "confidence": 0.6,
            "challenges": [{"aspect": i["description"], "counter_argument": "Heuristic check", "risk_level": "medium"} for i in issues],
            "adjusted_confidence": 0.5 if issues else 0.7,
            "recommendation": "LLM unavailable — heuristic review only. Manual verification recommended.",
        }

    return {
        "verdict": "FLAGGED" if issues else "APPROVED",
        "confidence": 0.6,
        "issues": issues,
        "recommendation": "Manual review recommended" if issues else "Heuristic pass — LLM unavailable",
    }


# ═══════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════

async def validate_agent_output(
    agent_id: str,
    intent: str,
    result: Dict,
) -> Dict:
    """
    Standard validation review of an agent's output.

    Returns:
        {
            "passed": bool,
            "verdict": "APPROVED" | "FLAGGED",
            "review": { ... full critic response ... },
            "agent": str,
        }
    """
    review_input = f"""Agent: {agent_id.upper()}
Intent: {intent}
Output:
{json.dumps(result, indent=2, default=str)[:2000]}

Review this output for Misinterpretations, Missing Corner Cases, Data Errors, Logic Gaps, and Brand Voice violations."""

    review = await _call_critic("validate", review_input)

    passed = review.get("verdict") == "APPROVED"
    confidence = review.get("confidence", 0.5)

    # ULTRAPLINIAN 5-axis scoring
    content_str = json.dumps(result, default=str)[:3000]
    ultra_score = ultraplinian_score(content_str, query=intent)

    # Merge ULTRAPLINIAN into verdict: if binary says APPROVED but score < 60, override to FLAGGED
    if passed and ultra_score["total"] < 60:
        passed = False
        review["verdict"] = "FLAGGED"
        review.setdefault("issues", []).append({
            "type": "ULTRAPLINIAN_GATE",
            "description": f"ULTRAPLINIAN score {ultra_score['total']}/100 below 60-point threshold",
            "severity": "major",
        })

    # Audit the critic review
    db = get_db()
    if db is not None:
        try:
            from routers.agent_execution_router import create_audit_entry
            await create_audit_entry(
                db,
                action=f"critic_validate_{agent_id}",
                agent_id="critic",
                data={
                    "reviewed_agent": agent_id,
                    "verdict": review.get("verdict", "UNKNOWN"),
                    "issues_count": len(review.get("issues", [])),
                    "ultraplinian_total": ultra_score["total"],
                    "ultraplinian_grade": ultra_score["grade"],
                },
            )
        except Exception:
            pass

    logger.info(f"[Critic] {agent_id} → {review.get('verdict', 'UNKNOWN')} (conf: {confidence}, ultra: {ultra_score['total']}/{ultra_score['grade']})")

    return {
        "passed": passed,
        "verdict": review.get("verdict", "UNKNOWN"),
        "confidence": confidence,
        "review": review,
        "agent": agent_id,
        "ultraplinian": ultra_score,
    }


async def adversarial_review(
    data: Dict,
    context: str = "pipeline",
    model_hint: str = "critic",
) -> Dict:
    """
    Adversarial review — actively tries to break the data.

    Used by ClawChief heartbeat for pipeline integrity checks.
    model_hint: "critic" (GPT-OSS) or "heartbeat" (Step Flash for speed)
    """
    review_input = f"""Context: {context}
Data to Challenge:
{json.dumps(data, indent=2, default=str)[:2000]}

Challenge every assumption. Look for overconfidence, survivorship bias, missing variables, and false positives."""

    review = await _call_critic("adversarial", review_input, model_hint=model_hint)

    db = get_db()
    if db is not None:
        try:
            from routers.agent_execution_router import create_audit_entry
            await create_audit_entry(
                db,
                action=f"critic_adversarial_{context}",
                agent_id="critic",
                data={
                    "context": context,
                    "verdict": review.get("verdict", "UNKNOWN"),
                    "challenges_count": len(review.get("challenges", [])),
                },
            )
        except Exception:
            pass

    return review


async def rescue_fallback(
    agent_id: str,
    original_result: Dict,
    original_confidence: float,
) -> Dict:
    """
    Rescue pattern — triggered when agent confidence < 0.7.
    Gets a second opinion from the Critic's LLM session.
    """
    review_input = f"""RESCUE MODE: The {agent_id.upper()} agent returned a LOW CONFIDENCE result ({original_confidence:.2f}).

Original Output:
{json.dumps(original_result, indent=2, default=str)[:2000]}

Provide your own assessment. Is the output salvageable? Should it be:
1. ACCEPTED (low confidence but correct)
2. CORRECTED (partially right, needs adjustment)
3. REJECTED (fundamentally flawed, retry)

Respond with JSON:
{{
  "rescue_verdict": "ACCEPTED" | "CORRECTED" | "REJECTED",
  "adjusted_confidence": <float 0-1>,
  "corrections": [<list of specific corrections if any>],
  "recommendation": "<what to do next>"
}}"""

    session = _get_critic_session("validate")
    if not session:
        return {
            "rescue_verdict": "ACCEPTED",
            "adjusted_confidence": original_confidence,
            "corrections": [],
            "recommendation": "LLM unavailable for rescue. Accepting original output with caution.",
        }

    try:
        from emergentintegrations.llm.chat import UserMessage
        response = await session.send_message(UserMessage(text=review_input))

        response_clean = response.strip()
        if response_clean.startswith("```"):
            match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response_clean, re.DOTALL)
            if match:
                response_clean = match.group(1)

        result = json.loads(response_clean)

        db = get_db()
        if db is not None:
            try:
                from routers.agent_execution_router import create_audit_entry
                await create_audit_entry(
                    db,
                    action=f"critic_rescue_{agent_id}",
                    agent_id="critic",
                    data={
                        "rescued_agent": agent_id,
                        "original_confidence": original_confidence,
                        "rescue_verdict": result.get("rescue_verdict", "UNKNOWN"),
                    },
                )
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[Critic] Rescue error: {e}")
        return {
            "rescue_verdict": "ACCEPTED",
            "adjusted_confidence": original_confidence,
            "corrections": [],
            "recommendation": f"Rescue failed: {str(e)}. Accepting original.",
        }


# ═══════════════════════════════════════════════════
# CONSENSUS VALIDATION (Dual-Model Review via OpenRouter)
# ═══════════════════════════════════════════════════

async def consensus_validate_agent_output(
    agent_id: str,
    intent: str,
    result: Dict,
) -> Dict:
    """
    Consensus validation — dual-model Critic review.

    Both GPT-OSS-120B and Qwen 3.6 Plus review the same output.
    Both must agree for APPROVED. Disagreement defaults to FLAGGED.
    Cost: $0 (both models are free tier).
    """
    review_input = f"""Agent: {agent_id.upper()}
Intent: {intent}
Output:
{json.dumps(result, indent=2, default=str)[:2000]}

Review this output for Misinterpretations, Missing Corner Cases, Data Errors, Logic Gaps, and Brand Voice violations."""

    try:
        from services.openrouter_client import consensus_validate

        consensus = await consensus_validate(CRITIC_VALIDATE_PROMPT, review_input)

        passed = consensus.get("consensus_verdict") == "APPROVED"
        confidence = consensus.get("consensus_confidence", 0.5)

        # ULTRAPLINIAN 5-axis scoring on consensus
        content_str = json.dumps(result, default=str)[:3000]
        ultra_score = ultraplinian_score(content_str, query=intent)

        if passed and ultra_score["total"] < 60:
            passed = False
            consensus["consensus_verdict"] = "FLAGGED"

        # Audit
        db = get_db()
        if db is not None:
            try:
                from routers.agent_execution_router import create_audit_entry
                await create_audit_entry(
                    db,
                    action=f"critic_consensus_{agent_id}",
                    agent_id="critic",
                    data={
                        "reviewed_agent": agent_id,
                        "consensus_verdict": consensus.get("consensus_verdict"),
                        "agreement": consensus.get("agreement"),
                        "models": consensus.get("models_used", []),
                        "ultraplinian_total": ultra_score["total"],
                    },
                )
            except Exception:
                pass

        logger.info(
            f"[Critic] CONSENSUS {agent_id} → {consensus.get('consensus_verdict')} "
            f"(conf: {confidence}, agree: {consensus.get('agreement')}, ultra: {ultra_score['total']})"
        )

        return {
            "passed": passed,
            "verdict": consensus.get("consensus_verdict", "UNKNOWN"),
            "confidence": confidence,
            "review": consensus,
            "agent": agent_id,
            "mode": "consensus",
            "ultraplinian": ultra_score,
        }
    except Exception as e:
        logger.warning(f"[Critic] Consensus failed, falling back to single-model: {e}")
        return await validate_agent_output(agent_id, intent, result)
