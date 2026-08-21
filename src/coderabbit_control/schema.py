"""Versioned JSON Schema loading and deterministic validation."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .errors import SchemaValidationError


_SCHEMA_FILES = {
    "RepositoryManifest": "repository-manifest.schema.json",
    "RepositoryFingerprint": "repository-fingerprint.schema.json",
    "PolicyDefinition": "policy-definition.schema.json",
    "PolicyException": "policy-exception.schema.json",
    "EffectivePolicySet": "effective-policy-set.schema.json",
    "FindingRecord": "finding-record.schema.json",
    "EvidenceManifest": "evidence-manifest.schema.json",
}


def _schema_root() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas"


def _load_schema(kind: str) -> dict[str, object]:
    try:
        filename = _SCHEMA_FILES[kind]
    except KeyError as exc:
        raise SchemaValidationError(f"unknown document kind: {kind}") from exc
    path = _schema_root() / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaValidationError(f"cannot load schema for {kind}: {exc}") from exc


def _error_path(error: object) -> str:
    absolute_path = getattr(error, "absolute_path", ())
    parts = [str(part) for part in absolute_path]
    return "/" + "/".join(parts) if parts else "/"


def validate_document(kind: str, payload: dict[str, object]) -> None:
    """Validate one control-plane document or raise a deterministic error."""
    validator = Draft202012Validator(_load_schema(kind))
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: (_error_path(error), error.message),
    )
    if not errors:
        return
    details = "; ".join(f"{_error_path(error)}: {error.message}" for error in errors)
    raise SchemaValidationError(f"{kind} validation failed: {details}")
