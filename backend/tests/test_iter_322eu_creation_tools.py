"""
Regression test — iter 322eu (Creation + infra tools)
Locks in the 8 new tools so ORA CTO can self-build:
  create_file · create_dir · append_to_file · pytest_run
  cloudflare_dns_list · cloudflare_dns_write
  docker_compose · pip_propose

NOTE: cloudflare_dns_write is not exercised at write because that would
mutate live DNS — only the read path is tested. The write path is
covered by argument-validation tests.
"""
import os
from pathlib import Path
import pytest


def test_new_tools_in_registry():
    from services.ora_tools import TOOL_REGISTRY
    for t in (
        "create_file", "create_dir", "append_to_file", "pytest_run",
        "cloudflare_dns_list", "cloudflare_dns_write",
        "docker_compose", "pip_propose",
    ):
        assert t in TOOL_REGISTRY, f"missing tool: {t}"


def test_aurem_cto_in_write_allowed_roots():
    from services.ora_tools import _WRITE_ALLOWED_ROOTS
    assert "/app/aurem-cto" in _WRITE_ALLOWED_ROOTS


@pytest.mark.asyncio
async def test_create_dir_then_create_file_roundtrip(tmp_path_factory):
    from services.ora_tools import create_dir, create_file
    target_dir = "/app/aurem-cto/test_322eu"
    r = await create_dir(target_dir)
    assert r["ok"] and Path(target_dir).is_dir()
    r2 = await create_file(f"{target_dir}/marker.txt", content="hello",
                            overwrite=True)
    assert r2["ok"]
    assert Path(f"{target_dir}/marker.txt").read_text() == "hello"


@pytest.mark.asyncio
async def test_create_file_refuses_existing_without_overwrite():
    from services.ora_tools import create_file
    p = "/app/aurem-cto/test_322eu/marker.txt"
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text("existing")
    r = await create_file(p, content="X")
    assert r["ok"] is False
    assert "already exists" in r["error"]


@pytest.mark.asyncio
async def test_create_file_blocks_forbidden_root():
    from services.ora_tools import create_file
    r = await create_file("/etc/forbidden_iter_322eu.txt", content="nope")
    assert r["ok"] is False
    assert "not allowed" in r["error"]


@pytest.mark.asyncio
async def test_append_to_file_grows_file():
    from services.ora_tools import create_file, append_to_file
    p = "/app/aurem-cto/test_322eu/append.txt"
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    await create_file(p, content="line1\n", overwrite=True)
    r = await append_to_file(p, content="line2\n")
    assert r["ok"]
    assert r["bytes_appended"] == len("line2\n")
    assert Path(p).read_text() == "line1\nline2\n"


@pytest.mark.asyncio
async def test_docker_compose_rejects_bad_subcommand():
    from services.ora_tools import docker_compose
    r = await docker_compose("rm -rf /")
    assert r["ok"] is False
    assert "not allowed" in r["error"]


@pytest.mark.asyncio
async def test_pip_propose_rejects_non_allowlisted():
    from services.ora_tools import pip_propose
    r = await pip_propose("definitely-not-real-pkg-iter322eu")
    assert r["ok"] is False
    assert "not in allowlist" in r["error"]


@pytest.mark.asyncio
async def test_pytest_run_scope_restricted():
    from services.ora_tools import pytest_run
    r = await pytest_run("/etc")
    assert r["ok"] is False
    assert "limited" in r["error"]


@pytest.mark.asyncio
async def test_cloudflare_dns_write_validates_record_type():
    from services.ora_tools import cloudflare_dns_write
    # Bypasses live API because of bad record_type
    r = await cloudflare_dns_write("INVALID", "test.example.com", "1.1.1.1")
    assert r["ok"] is False
    assert "unsupported record type" in r["error"]


@pytest.mark.asyncio
async def test_cloudflare_dns_write_scopes_to_root_domain():
    """Refuses to touch unrelated zones — security guard."""
    from services.ora_tools import cloudflare_dns_write
    r = await cloudflare_dns_write("A", "evil.different-domain.com", "1.1.1.1")
    assert r["ok"] is False
    assert "CLOUDFLARE_ROOT_DOMAIN" in r["error"]
