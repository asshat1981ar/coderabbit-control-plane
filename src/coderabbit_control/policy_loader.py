"""Safe YAML loading and conversion into typed control-plane models."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Mapping

import yaml

from .errors import SchemaValidationError
from .models import (
    AuthorityTier,
    PolicyDefinition,
    PolicyException,
    PolicyMaturity,
    RepositoryFingerprint,
    RepositoryManifest,
    Severity,
)
from .schema import validate_document


def _normalize_yaml(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize_yaml(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_yaml(item) for item in value]
    return value


def load_yaml_document(path: Path, kind: str) -> dict[str, object]:
    """Safely load and immediately schema-validate one YAML document."""
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SchemaValidationError(f"cannot load {path}: {exc}") from exc
    loaded = _normalize_yaml(loaded)
    if not isinstance(loaded, dict):
        raise SchemaValidationError(f"{path} must contain a mapping root")
    payload = dict(loaded)
    validate_document(kind, payload)
    return payload


def repository_manifest_from_document(payload: Mapping[str, object]) -> RepositoryManifest:
    repository = payload["repository"]
    profiles = payload["profiles"]
    policy = payload["policy"]
    generation = payload["generation"]
    discovery = payload["discovery"]
    assert isinstance(repository, Mapping)
    assert isinstance(profiles, Mapping)
    assert isinstance(policy, Mapping)
    assert isinstance(generation, Mapping)
    assert isinstance(discovery, Mapping)
    return RepositoryManifest(
        full_name=str(repository["full_name"]),
        provider=str(repository["provider"]),
        explicit_profiles=tuple(str(item) for item in profiles["explicit"]),
        local_policy_ids=tuple(str(item) for item in policy["local"]),
        generation={str(key): bool(value) for key, value in generation.items()},
        allow_auto_detect=bool(discovery["allow_auto_detect"]),
        minimum_confidence=float(discovery["minimum_confidence"]),
    )


def repository_fingerprint_from_document(payload: Mapping[str, object]) -> RepositoryFingerprint:
    return RepositoryFingerprint(
        repository=str(payload["repository"]),
        revision=str(payload["revision"]),
        languages=dict(payload["languages"]),
        capabilities=tuple(payload["capabilities"]),
        trust_boundaries=tuple(payload["trust_boundaries"]),
        verification_commands=tuple(str(item) for item in payload["verification_commands"]),
        ci_files=tuple(str(item) for item in payload["ci_files"]),
    )


def policy_definition_from_document(payload: Mapping[str, object]) -> PolicyDefinition:
    metadata = payload["metadata"]
    authority = payload["authority"]
    requirement = payload["requirement"]
    targets = payload["targets"]
    mechanical = payload["mechanical"]
    applicability = payload["applicability"]
    assert isinstance(metadata, Mapping)
    assert isinstance(authority, Mapping)
    assert isinstance(requirement, Mapping)
    assert isinstance(targets, Mapping)
    assert isinstance(mechanical, Mapping)
    assert isinstance(applicability, Mapping)
    ast_grep = mechanical["ast_grep"]
    assert isinstance(ast_grep, Mapping)
    enabled_targets: dict[str, bool] = {}
    for name, config in targets.items():
        assert isinstance(config, Mapping)
        enabled_targets[str(name)] = bool(config["enabled"])
    return PolicyDefinition(
        policy_id=str(metadata["id"]),
        version=str(metadata["version"]),
        maturity=PolicyMaturity(str(metadata["status"])),
        owners=tuple(str(item) for item in metadata["owners"]),
        authority_tier=AuthorityTier(str(authority["tier"])),
        weakenable=bool(authority["weakenable"]),
        severity=Severity(str(payload["severity"])),
        requirement=str(requirement["statement"]),
        targets=enabled_targets,
        applicability=dict(applicability),
        mechanical_ast_grep_supported=bool(ast_grep["supported"]),
        raw=dict(payload),
    )


def policy_exception_from_document(payload: Mapping[str, object]) -> PolicyException:
    metadata = payload["metadata"]
    scope = payload["scope"]
    assert isinstance(metadata, Mapping)
    assert isinstance(scope, Mapping)
    return PolicyException(
        exception_id=str(metadata["id"]),
        repository=str(metadata["repository"]),
        policy_id=str(payload["policy_id"]),
        reason=str(payload["reason"]),
        approved_by=tuple(str(item) for item in payload["approved_by"]),
        created=date.fromisoformat(str(payload["created"])),
        expires=date.fromisoformat(str(payload["expires"])),
        scope_paths=tuple(str(item) for item in scope["paths"]),
        compensating_controls=tuple(str(item) for item in payload["compensating_controls"]),
    )


def load_profile_catalog(path: Path) -> dict[str, tuple[str, ...]]:
    """Load the small versioned profile-to-policy mapping used by the resolver."""
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SchemaValidationError(f"cannot load {path}: {exc}") from exc
    loaded = _normalize_yaml(loaded)
    if not isinstance(loaded, dict) or set(loaded) != {"version", "profiles"}:
        raise SchemaValidationError(f"{path} must contain only version and profiles")
    if loaded["version"] != 1 or not isinstance(loaded["profiles"], dict):
        raise SchemaValidationError(f"{path} has unsupported profile catalog shape")
    result: dict[str, tuple[str, ...]] = {}
    for name, config in sorted(loaded["profiles"].items()):
        if not isinstance(config, dict) or set(config) != {"policies"}:
            raise SchemaValidationError(f"profile {name} must contain only policies")
        policies = config["policies"]
        if not isinstance(policies, list) or not all(isinstance(item, str) for item in policies):
            raise SchemaValidationError(f"profile {name} policies must be a string list")
        if len(set(policies)) != len(policies):
            raise SchemaValidationError(f"profile {name} contains duplicate policy IDs")
        result[str(name)] = tuple(sorted(policies))
    return result
