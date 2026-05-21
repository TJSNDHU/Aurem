"""
iter 326c — ORA-CTO Provider Status panel wiring regression.

User asked for a visual watchdog showing per-provider status, latency,
and model count on /admin/ora?tab=cockpit so they can instantly see
when FreeLLMAPI flips from "not configured" to "online" after the
production deploy.

Verifies:
  1. OraCtoCockpit imports `safeFetchJson` (defensive JSON parse so a
     Cloudflare 5xx never crashes the panel).
  2. State hooks for `providers` + `providersAt` exist.
  3. The component polls `/api/admin/ora/providers/health`.
  4. A `ProviderHealthPanel` component is rendered.
  5. PROVIDER_LABELS map covers all 5 providers in the default chain.
  6. Required test ids exist for E2E selectors.
"""

PATH = "/app/frontend/src/platform/admin/OraCtoCockpit.jsx"


def _src():
    return open(PATH, encoding="utf-8").read()


def test_safefetch_wired():
    src = _src()
    assert 'import { safeFetchJson } from "../../lib/safeFetchJson"' in src


def test_state_hooks_present():
    src = _src()
    assert "const [providers, setProviders]" in src
    assert "const [providersAt, setProvidersAt]" in src


def test_polling_url_correct():
    src = _src()
    assert "/api/admin/ora/providers/health" in src


def test_panel_component_rendered():
    src = _src()
    assert "<ProviderHealthPanel" in src
    assert "function ProviderHealthPanel" in src


def test_all_provider_labels_present():
    src = _src()
    for key in ("deepseek", "freellmapi", "claude", "legion_ollama", "groq"):
        assert f'{key}:' in src or f'"{key}"' in src


def test_required_test_ids():
    src = _src()
    assert 'data-testid="provider-health-panel"' in src
    assert 'data-testid={`provider-row-${key}`}' in src
    assert 'data-testid="provider-checked-at"' in src
