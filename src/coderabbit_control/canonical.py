"""Deterministic serialization and digest helpers."""

from __future__ import annotations

import hashlib
import json


def canonical_json(value: object) -> str:
    """Serialize JSON-compatible data with stable ordering and encoding."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_digest(value: object) -> str:
    """Return a prefixed SHA-256 digest of canonical JSON bytes."""
    data = canonical_json(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()
