"""
aurem_cto.services.db — single Mongo handle for the module.
The host application registers the db once at startup via aurem_cto.set_db.
"""
from __future__ import annotations
from typing import Optional

_db = None


def set_db(db) -> None:
    global _db
    _db = db


def get_db():
    return _db


def require_db():
    if _db is None:
        raise RuntimeError("aurem_cto db not initialized — host must call aurem_cto.set_db(db)")
    return _db
