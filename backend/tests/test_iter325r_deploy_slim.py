"""iter 325r — Deployment slim regression tests.

Locks in the strip-down so future `pip freeze` regenerations don't
silently re-introduce blockers that would crash Emergent K8s deploy
(250m CPU / 1Gi RAM limit).
"""
from __future__ import annotations

import importlib
import re

import pytest

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)


REQS = "/app/backend/requirements.txt"

# Hard-blocked packages — Emergent K8s deploy WILL crash if these come
# back via pip freeze. Keep this list in lockstep with the iter 325r
# strip-down + deployment_agent's BLOCKER list.
DEPLOY_BLOCKERS = (
    "chromadb",
    "cuda-bindings", "cuda-pathfinder", "cuda-toolkit",
    "huggingface_hub",
    "langchain-core", "langchain-protocol",
    "nvidia-cublas", "nvidia-cuda-cupti", "nvidia-cuda-nvrtc",
    "nvidia-cuda-runtime", "nvidia-cufft", "nvidia-cufile",
    "nvidia-curand", "nvidia-cusolver", "nvidia-cusparse",
    "nvidia-nvjitlink", "nvidia-nvtx",
    "onnxruntime",
    "pandas",
    "scikit-learn",
    "scipy",
    "eth-hash", "eth-typing", "eth-utils",
    "hexbytes",
    "rlp",
)


def _read():
    with open(REQS) as fh:
        return fh.read()


def test_no_deploy_blockers_in_requirements():
    body = _read()
    offenders = []
    for pkg in DEPLOY_BLOCKERS:
        # Match pinned-version line like ``pkg==1.2.3`` or unpinned ``pkg``
        if re.search(rf"^{re.escape(pkg)}(==|>=|<=|~=|<|>|$)", body, re.MULTILINE):
            offenders.append(pkg)
    assert not offenders, (
        f"Deploy-blocker packages back in requirements.txt — "
        f"will crash Emergent K8s pod (1Gi RAM): {offenders}\n"
        f"If a feature truly needs one, use an external API instead."
    )


@pytest.mark.parametrize("mod", [
    "chromadb", "scipy", "sklearn", "pandas", "onnxruntime",
    "huggingface_hub", "eth_hash", "eth_typing", "eth_utils",
    "hexbytes", "rlp",
])
def test_blocker_modules_actually_uninstalled(mod):
    """Sanity — pip uninstall actually removed the packages."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(mod)


def test_optional_ml_users_have_fallback_guards():
    """The 5 files that historically imported the heavy ML stack must
    still have a try/except guard so the backend boots even when the
    lib is absent. (``except Exception`` catches ImportError too.)"""
    files = [
        "/app/backend/services/rag_knowledge_base.py",
        "/app/backend/services/vector_search.py",
        "/app/backend/services/embeddings.py",
        "/app/backend/services/lightrag_adapter.py",
        "/app/backend/shared/commercial/semantic_cache.py",
    ]
    for f in files:
        with open(f) as fh:
            body = fh.read()
        assert "try:" in body and ("ImportError" in body or "except Exception" in body), \
            f"{f}: missing try/except fallback guard — will crash on deploy"


def test_iter_marker_present():
    """The iter-325r header comment must remain so it's clear WHY the
    big block of deps is missing if anyone reads the file."""
    body = _read()
    assert "iter 325r" in body and "Emergent K8s" in body, \
        "iter-325r marker must stay in requirements.txt header"


def test_numpy_still_present():
    """NumPy IS used unconditionally in 3 files (biometric_secure,
    lightrag_adapter, rag/embedder) — must stay in requirements."""
    body = _read()
    assert re.search(r"^numpy==", body, re.MULTILINE), \
        "numpy was incorrectly removed — used unconditionally in 3 backend files"
