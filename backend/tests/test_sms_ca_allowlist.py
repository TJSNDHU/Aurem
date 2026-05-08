"""
iter 282al-33 — CA allowlist + kill-switch policy tests.
"""
from __future__ import annotations

import os

import pytest


# ─────────────── CA NPA detection ───────────────
def test_is_canadian_number_e164_plus1():
    from services.ca_numbers import is_canadian_number, is_us_number
    assert is_canadian_number("+14314500004") is True   # Manitoba
    assert is_canadian_number("+14165551234") is True   # Toronto
    assert is_canadian_number("+16045551234") is True   # Vancouver
    assert is_canadian_number("+19025551234") is True   # Halifax
    assert is_us_number("+12025550123") is True         # DC
    assert is_us_number("+16175550123") is True         # Boston
    assert is_us_number("+14314500004") is False


def test_is_canadian_number_no_plus():
    from services.ca_numbers import is_canadian_number
    assert is_canadian_number("14165551234") is True
    assert is_canadian_number("4165551234")  is True
    assert is_canadian_number("4315551234")  is True


def test_is_canadian_number_garbage_returns_false():
    from services.ca_numbers import is_canadian_number
    assert is_canadian_number("") is False
    assert is_canadian_number("not a phone") is False
    assert is_canadian_number("+441234567890") is False   # UK
    assert is_canadian_number("+91999999999") is False    # India
    assert is_canadian_number(None) is False  # type: ignore[arg-type]


# ─────────────── Kill-switch policy ───────────────
def _reset_env(monkeypatch, **kw):
    for k in ("SMS_DISABLED", "SMS_ALLOW_CA"):
        monkeypatch.delenv(k, raising=False)
    for k, v in kw.items():
        monkeypatch.setenv(k, v)


def test_kill_switch_default_is_true_blocks_us(monkeypatch):
    _reset_env(monkeypatch)  # both unset → defaults
    from services.sms_killswitch import is_sms_disabled, is_ca_allowed
    assert is_sms_disabled() is True
    assert is_ca_allowed() is True


def test_blocks_us_when_disabled(monkeypatch):
    _reset_env(monkeypatch)
    from services.sms_killswitch import is_blocked_destination
    assert is_blocked_destination("+12025550123") is True
    assert is_blocked_destination("+16175550123") is True


def test_allows_ca_when_disabled_but_ca_allowed(monkeypatch):
    _reset_env(monkeypatch, SMS_DISABLED="true", SMS_ALLOW_CA="true")
    from services.sms_killswitch import is_blocked_destination
    assert is_blocked_destination("+14314500004") is False
    assert is_blocked_destination("+14165551234") is False


def test_blocks_ca_when_ca_disallowed(monkeypatch):
    _reset_env(monkeypatch, SMS_DISABLED="true", SMS_ALLOW_CA="false")
    from services.sms_killswitch import is_blocked_destination
    assert is_blocked_destination("+14314500004") is True


def test_allows_everything_when_sms_enabled(monkeypatch):
    _reset_env(monkeypatch, SMS_DISABLED="false")
    from services.sms_killswitch import is_blocked_destination
    assert is_blocked_destination("+12025550123") is False
    assert is_blocked_destination("+14165551234") is False


def test_whatsapp_always_passes(monkeypatch):
    _reset_env(monkeypatch, SMS_DISABLED="true", SMS_ALLOW_CA="false")
    from services.sms_killswitch import is_blocked_destination
    assert is_blocked_destination("whatsapp:+12025550123") is False
    assert is_blocked_destination("whatsapp:+14165551234") is False
