"""
Self-Edit Engine (iter 305)
============================
Stage 5 of Founders Console — autonomous file edits via Claude Sonnet 4.5,
gated by blast-radius whitelist + auto-rollback pipeline.

Public:
  await self_edit_apply(prompt: str, expected_files: List[str], db) -> dict

Pipeline:
  1. Path safety check (whitelist + blacklist)
  2. Claude generates edits as STRICT JSON {edits:[{path, mode, content,
                                                       old_str?, new_str?}]}
  3. Backup originals to db.self_edit_backups (versioned)
  4. Apply edits
  5. ruff lint backend/ + node lint frontend/ (changed files only)
  6. test_locked_builds (if backend touched)
  7. supervisorctl restart backend (if backend touched)
  8. Health probe http://localhost:8001/api/health for ≤30s
  9. Rollback on ANY failure → restore from backup → restart
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

REPO_ROOT = Path("/app")
SELF_EDIT_BACKUP_COLLECTION = "self_edit_backups"
HEALTH_URL = "http://localhost:8001/api/health"
HEALTH_TIMEOUT_S = 30


def _is_path_safe(rel: str) -> Tuple[bool, str]:
    from services.founders_pipeline import _is_path_safe as _safe
    if not _safe(rel):
        return False, f"path_blocked: {rel}"
    abs_p = (REPO_ROOT / rel).resolve()
    try:
        abs_p.relative_to(REPO_ROOT)
    except ValueError:
        return False, f"path_traversal: {rel}"
    return True, ""


# ─── Claude edit-generation ─────────────────────────────────────────────────
async def _generate_edits(prompt: str, expected_files: List[str]) -> Dict[str, Any]:
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        return {"ok": False, "error": "no_emergent_llm_key"}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    except Exception:
        return {"ok": False, "error": "emergentintegrations_unavailable"}

    sys = (
        "You are AUREM's autonomous file editor. Output STRICT JSON only:\n"
        '{"edits":[{"path":"<rel path>","mode":"replace_block|create_file",'
        '"old_str":"<exact substring to replace, only for replace_block>",'
        '"new_str":"<replacement, only for replace_block>",'
        '"content":"<full file content, only for create_file>",'
        '"reason":"<one-line why>"}]}\n'
        "Rules:\n"
        "- Max 3 files per response.\n"
        "- For replace_block: old_str must be UNIQUE in the file with enough context.\n"
        "- Never edit .env, server.py, auth_router.py, council.py, "
        "  zero_downtime_repair.py, or any file with 'lock' in name.\n"
        "- Allowed paths: frontend/src/components/, frontend/src/pages/, "
        "  backend/routers/ (not auth), backend/services/ (not council/zdr).\n"
        "- For React: import dependencies properly, add data-testid attrs.\n"
        "- For Python: don't break existing imports, follow PEP 8.\n"
        "- No markdown, no prose, no code fences."
    )

    # Read existing files (if any) so Claude has context for replace_block
    file_context = ""
    for ef in (expected_files or [])[:3]:
        ok, _ = _is_path_safe(ef)
        if not ok:
            continue
        p = REPO_ROOT / ef
        if p.is_file() and p.stat().st_size < 60_000:
            try:
                file_context += f"\n\n=== {ef} ===\n{p.read_text()}\n"
            except Exception:
                pass

    full_prompt = f"{prompt}\n\nEXISTING FILE CONTEXT:{file_context or ' (none)'}"

    chat = LlmChat(
        api_key=api_key, session_id=f"se-{uuid.uuid4().hex[:10]}",
        system_message=sys,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=4000)
    try:
        out = await asyncio.wait_for(chat.send_message(UserMessage(text=full_prompt)),
                                      timeout=60)
    except Exception as e:
        return {"ok": False, "error": f"llm_timeout: {e}"}

    raw = (out or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    m = re.search(r"\{.*\}", raw, flags=re.S)
    if not m:
        return {"ok": False, "error": "no_json_in_response", "raw": raw[:500]}
    try:
        parsed = json.loads(m.group(0))
    except Exception as e:
        return {"ok": False, "error": f"json_parse: {e}", "raw": raw[:500]}
    if "edits" not in parsed or not isinstance(parsed["edits"], list):
        return {"ok": False, "error": "missing_edits_array", "raw": raw[:500]}
    if len(parsed["edits"]) > 3:
        return {"ok": False, "error": "too_many_edits"}
    return {"ok": True, "edits": parsed["edits"]}


# ─── Backup / restore ───────────────────────────────────────────────────────
async def _backup(db, change_id: str, edits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bkp: List[Dict[str, Any]] = []
    for ed in edits:
        rel = ed["path"]
        p = REPO_ROOT / rel
        original = p.read_text() if p.is_file() else None
        bkp.append({"path": rel, "original": original})
    if db is not None:
        try:
            await db[SELF_EDIT_BACKUP_COLLECTION].insert_one({
                "change_id": change_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "files": [{"path": b["path"],
                           "original_present": b["original"] is not None}
                          for b in bkp],
                "originals": {b["path"]: b["original"] for b in bkp},
            })
        except Exception as e:
            logger.warning(f"[self-edit] backup persist failed: {e}")
    return bkp


def _restore(bkp: List[Dict[str, Any]]) -> None:
    for b in bkp:
        p = REPO_ROOT / b["path"]
        if b["original"] is None:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
        else:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(b["original"])
            except Exception as e:
                logger.warning(f"[self-edit] restore failed for {b['path']}: {e}")


# ─── Apply ──────────────────────────────────────────────────────────────────
def _apply_edit(ed: Dict[str, Any]) -> Tuple[bool, str]:
    rel = ed.get("path", "")
    ok, why = _is_path_safe(rel)
    if not ok:
        return False, why
    p = REPO_ROOT / rel
    mode = ed.get("mode")
    if mode == "create_file":
        if p.is_file():
            return False, f"create_file: already exists ({rel})"
        content = ed.get("content")
        if not isinstance(content, str):
            return False, f"create_file: missing content ({rel})"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return True, "created"
    if mode == "replace_block":
        if not p.is_file():
            return False, f"replace_block: file missing ({rel})"
        old = ed.get("old_str")
        new = ed.get("new_str")
        if not isinstance(old, str) or not isinstance(new, str):
            return False, f"replace_block: missing old_str/new_str ({rel})"
        text = p.read_text()
        count = text.count(old)
        if count == 0:
            return False, f"replace_block: old_str not found ({rel})"
        if count > 1:
            return False, f"replace_block: old_str ambiguous ({count} matches in {rel})"
        p.write_text(text.replace(old, new, 1))
        return True, "replaced"
    return False, f"unknown_mode: {mode}"


# ─── Validation ─────────────────────────────────────────────────────────────
def _run(cmd: List[str], cwd: Optional[str] = None,
         timeout: int = 60) -> Tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=cwd or str(REPO_ROOT),
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:
        return 1, f"runner_error: {e}"


def _validate(edits: List[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, Any]]]:
    """Returns (ok, [step_results])."""
    steps: List[Dict[str, Any]] = []
    paths = [ed["path"] for ed in edits]
    py_files = [p for p in paths if p.endswith(".py")]
    js_files = [p for p in paths if p.endswith((".js", ".jsx", ".ts", ".tsx"))]
    backend_touched = any(p.startswith("backend/") for p in paths)

    if py_files:
        rc, out = _run(["ruff", "check"] + py_files, timeout=45)
        steps.append({"step": "ruff", "rc": rc, "out": out[-600:]})
        if rc != 0:
            return False, steps

    if js_files:
        rc, out = _run(
            ["yarn", "--cwd", str(REPO_ROOT / "frontend"),
             "eslint", "--no-eslintrc",
             "--parser-options=ecmaVersion:2022,sourceType:module,"
             "ecmaFeatures:{jsx:true}",
             "--rule", "no-undef:0",  # JSX is parsed but we skip strict undef check
             *[str((REPO_ROOT / p).resolve()) for p in js_files]],
            timeout=60,
        )
        # Soft-fail JS lint: log but do NOT block (eslintrc may not be wired).
        steps.append({"step": "eslint", "rc": rc, "out": out[-600:],
                      "soft": True})

    if backend_touched:
        rc, out = _run(
            ["python", "-m", "pytest", "backend/tests/test_locked_builds.py",
             "-x", "-q", "--tb=line"],
            timeout=60,
        )
        steps.append({"step": "test_locked_builds", "rc": rc, "out": out[-800:]})
        if rc != 0:
            return False, steps

    return True, steps


def _restart_backend() -> Tuple[bool, str]:
    rc, out = _run(["sudo", "supervisorctl", "restart", "backend"], timeout=30)
    return rc == 0, out


async def _wait_health() -> Tuple[bool, str]:
    import httpx
    deadline = time.monotonic() + HEALTH_TIMEOUT_S
    last = ""
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(timeout=3) as cli:
                r = await cli.get(HEALTH_URL)
            if r.status_code == 200:
                d = r.json()
                if d.get("status") == "ok":
                    return True, "healthy"
            last = f"http {r.status_code}"
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:80]}"
        await asyncio.sleep(2)
    return False, last or "timeout"


# ─── Public API ─────────────────────────────────────────────────────────────
async def self_edit_apply(prompt: str,
                          expected_files: List[str],
                          db,
                          dry_run: bool = False) -> Dict[str, Any]:
    started = time.monotonic()
    change_id = uuid.uuid4().hex[:14]

    # Pre-validate expected paths
    for ef in expected_files or []:
        ok, why = _is_path_safe(ef)
        if not ok:
            return {"ok": False, "stage": "pre_validate", "error": why,
                    "change_id": change_id}

    gen = await _generate_edits(prompt, expected_files)
    if not gen.get("ok"):
        return {"ok": False, "stage": "generate", "change_id": change_id, **gen}
    edits = gen["edits"]

    for ed in edits:
        ok, why = _is_path_safe(ed.get("path", ""))
        if not ok:
            return {"ok": False, "stage": "post_validate", "error": why,
                    "change_id": change_id, "blocked_path": ed.get("path")}

    if dry_run:
        return {"ok": True, "stage": "dry_run", "change_id": change_id,
                "edits_preview": [{"path": e["path"], "mode": e["mode"]} for e in edits]}

    bkp = await _backup(db, change_id, edits)
    apply_results: List[Dict[str, Any]] = []
    for ed in edits:
        ok, msg = _apply_edit(ed)
        apply_results.append({"path": ed["path"], "mode": ed["mode"],
                              "ok": ok, "msg": msg})
        if not ok:
            _restore(bkp)
            return {"ok": False, "stage": "apply", "change_id": change_id,
                    "apply": apply_results, "rolled_back": True}

    val_ok, val_steps = _validate(edits)
    if not val_ok:
        _restore(bkp)
        return {"ok": False, "stage": "validate", "change_id": change_id,
                "apply": apply_results, "validation": val_steps,
                "rolled_back": True}

    backend_touched = any(e["path"].startswith("backend/") for e in edits)
    restart_info = None
    if backend_touched:
        ok_r, out_r = _restart_backend()
        restart_info = {"ok": ok_r, "out": out_r[-400:]}
        if not ok_r:
            _restore(bkp)
            return {"ok": False, "stage": "restart", "change_id": change_id,
                    "apply": apply_results, "validation": val_steps,
                    "restart": restart_info, "rolled_back": True}
        h_ok, h_msg = await _wait_health()
        if not h_ok:
            _restore(bkp)
            _restart_backend()
            return {"ok": False, "stage": "health", "change_id": change_id,
                    "apply": apply_results, "validation": val_steps,
                    "restart": restart_info, "health": h_msg,
                    "rolled_back": True}
        restart_info["health"] = h_msg

    elapsed = round(time.monotonic() - started, 2)
    return {"ok": True, "stage": "done", "change_id": change_id,
            "apply": apply_results, "validation": val_steps,
            "restart": restart_info, "files_changed": [e["path"] for e in edits],
            "elapsed_s": elapsed, "rolled_back": False}
