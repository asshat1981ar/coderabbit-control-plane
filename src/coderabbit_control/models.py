"""Typed entities used by the deterministic policy engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Mapping


class AuthorityTier(StrEnum):
    CORE = "core"
    PROFILE = "profile"
    REPOSITORY = "repository"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class PolicyMaturity(StrEnum):
    OBSERVED = "observed"
    CANDIDATE = "candidate"
    EXPERIMENTAL = "experimental"
    RECOMMENDED = "recommended"
    MANDATORY = "mandatory"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    SUPERSEDED = "superseded"


class ProfileStatus(StrEnum):
    MANDATORY = "mandatory"
    DETECTED = "detected"
    SUGGESTED = "suggested"
    EXPLICIT = "explicit"


@dataclass(frozen=True, slots=True)
class ProfileSelection:
    mandatory: tuple[str, ...] = ()
    detected: tuple[str, ...] = ()
    suggested: tuple[str, ...] = ()
    explicit: tuple[str, ...] = ()
    confidence: Mapping[str, float] = field(default_factory=dict)
    evidence: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RepositoryManifest:
    full_name: str
    provider: str = "github"
    explicit_profiles: tuple[str, ...] = ()
    local_policy_ids: tuple[str, ...] = ()
    generation: Mapping[str, bool] = field(default_factory=dict)
    allow_auto_detect: bool = True
    minimum_confidence: float = 0.85


@dataclass(frozen=True, slots=True)
class RepositoryFingerprint:
    repository: str
    revision: str
    languages: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    capabilities: tuple[Mapping[str, object], ...] = ()
    trust_boundaries: tuple[Mapping[str, object], ...] = ()
    verification_commands: tuple[str, ...] = ()
    ci_files: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PolicyDefinition:
    policy_id: str
    version: str
    maturity: PolicyMaturity
    owners: tuple[str, ...]
    authority_tier: AuthorityTier
    weakenable: bool
    severity: Severity
    requirement: str
    targets: Mapping[str, bool] = field(default_factory=dict)
    applicability: Mapping[str, object] = field(default_factory=dict)
    mechanical_ast_grep_supported: bool = False
    raw: Mapping[str, object] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class PolicyException:
    exception_id: str
    repository: str
    policy_id: str
    reason: str
    approved_by: tuple[str, ...]
    created: date
    expires: date
    scope_paths: tuple[str, ...]
    compensating_controls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EffectivePolicySet:
    repository: str
    revision: str
    manifest_digest: str
    fingerprint_digest: str
    catalog_digest: str
    profiles: tuple[str, ...]
    policies: tuple[PolicyDefinition, ...]
    exceptions: tuple[PolicyException, ...]
    resolution_digest: str


@dataclass(frozen=True, slots=True)
class FindingRecord:
    finding_id: str
    source_provider: str
    repository: str
    pull_request: int | None
    revision: str
    category: str
    severity: str
    language: str | None
    trust_boundary: str | None
    invariant_id: str | None
    confidence: float
    path: str
    status: str
    remediation_type: str | None
    recommendation: str
    provenance: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvidenceManifest:
    run_id: str
    compiler_version: str
    repository: str
    revision: str
    effective_policy_digest: str
    artifact_digests: Mapping[str, str]
    checks: Mapping[str, str]
    result: str
