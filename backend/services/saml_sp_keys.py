"""
services/saml_sp_keys.py — iter 332b D-2
==========================================

Self-signed Service Provider (SP) x509 cert + private key for signing
SAML AuthnRequests.

The cert lives in `db.saml_sp_keys` as a single global row (key_id='aurem-sp').
It is auto-generated on first use (10-year RSA 2048) and persisted so all
backend replicas use the same key.

Why we sign AuthnRequests:
  Strict IdPs (Azure AD with strict mode, Okta with Verify Signature: Required)
  refuse to accept an unsigned AuthnRequest. Without this, those IdPs return
  a generic "request rejected" with no SAML response.

The PUBLIC cert is included in the SP metadata XML so IdPs can verify our
signature. The private key NEVER leaves the backend.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None
_cache: dict = {}   # {"cert": "...", "key": "...", "fetched_at": ...}


def set_db(database) -> None:
    global _db
    _db = database


SP_KEY_ID = "aurem-sp"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_keypair() -> tuple[str, str]:
    """Self-signed RSA 2048 + x509 cert valid for 10 years.
    Returns (cert_pem, key_pem)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography import x509
    from cryptography.x509.oid import NameOID

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048,
    )
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "aurem.live SAML SP"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Polaris Built Inc."),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CA"),
    ])
    cert = (
        x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365 * 10))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return cert_pem, key_pem


async def get_sp_keypair(force_regen: bool = False) -> dict:
    """Return {cert, key} — generating + persisting on first use.
    Cached in-process for the lifetime of the worker."""
    global _cache
    if not force_regen and _cache.get("cert") and _cache.get("key"):
        return _cache
    if _db is None:
        # Last-ditch: in-memory only. Tests can still exercise the code.
        cert, key = _generate_keypair()
        _cache = {"cert": cert, "key": key, "fetched_at": _now_iso(),
                   "ephemeral": True}
        return _cache

    row = await _db.saml_sp_keys.find_one({"key_id": SP_KEY_ID}, {"_id": 0})
    if row and row.get("cert") and row.get("key") and not force_regen:
        _cache = {"cert": row["cert"], "key": row["key"],
                   "fetched_at": _now_iso(), "ephemeral": False}
        return _cache

    cert, key = _generate_keypair()
    doc = {
        "key_id":     SP_KEY_ID,
        "cert":       cert,
        "key":        key,
        "created_at": _now_iso(),
        "rotated_at": _now_iso() if force_regen else None,
    }
    await _db.saml_sp_keys.update_one(
        {"key_id": SP_KEY_ID}, {"$set": doc}, upsert=True,
    )
    _cache = {"cert": cert, "key": key, "fetched_at": _now_iso(),
               "ephemeral": False}
    return _cache


def cert_for_metadata_xml(pem: str) -> str:
    """Strip the BEGIN/END lines + newlines so the cert can be embedded
    inside an <X509Certificate> XML element."""
    lines = (pem or "").strip().splitlines()
    body = [ln for ln in lines if "BEGIN CERTIFICATE" not in ln
             and "END CERTIFICATE" not in ln]
    return "".join(body).strip()
