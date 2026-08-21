"""Deterministic hybrid-authority policy resolution."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Iterable, Mapping, Sequence

from .canonical import sha256_digest
from .errors import PolicyResolutionError
from .models import (
    AuthorityTier,
    EffectivePolicySet,
    PolicyDefinition,
    PolicyException,
    PolicyMaturity,
    RepositoryFingerprint,
    RepositoryManifest,
    Severity,
)


SEVERITY_RANK = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.ERROR: 2,
    Severity.BLOCKING: 3,
}
_AUTHORITY_RANK = {
    AuthorityTier.CORE: 0,
    AuthorityTier.PROFILE: 1,
    AuthorityTier.REPOSITORY: 2,
}


def _manifest_payload(manifest: RepositoryManifest) -> dict[str, object]:
    return {
        "repository": {"provider": manifest.provider, "full_name": manifest.full_name},
        "profiles": sorted(manifest.explicit_profiles),
        "local_policy_ids": sorted(manifest.local_policy_ids),
        "generation": dict(sorted(manifest.generation.items())),
        "allow_auto_detect": manifest.allow_auto_detect,
        "minimum_confidence": manifest.minimum_confidence,
    }


def _fingerprint_payload(fingerprint: RepositoryFingerprint) -> dict[str, object]:
    return {
        "repository": fingerprint.repository,
        "revision": fingerprint.revision,
        "languages": dict(fingerprint.languages),
        "capabilities": list(fingerprint.capabilities),
        "trust_boundaries": list(fingerprint.trust_boundaries),
        "verification_commands": sorted(fingerprint.verification_commands),
        "ci_files": sorted(fingerprint.ci_files),
    }


def _mechanical_rule(policy: PolicyDefinition) -> object | None:
    mechanical = policy.raw.get("mechanical") if isinstance(policy.raw, Mapping) else None
    if not isinstance(mechanical, Mapping):
        return None
    ast_grep = mechanical.get("ast_grep")
    if not isinstance(ast_grep, Mapping):
        return None
    return ast_grep.get("rule")


def _policy_payload(policy: PolicyDefinition) -> dict[str, object]:
    return {
        "id": policy.policy_id,
        "version": policy.version,
        "maturity": policy.maturity.value,
        "owners": sorted(policy.owners),
        "authority_tier": policy.authority_tier.value,
        "weakenable": policy.weakenable,
        "severity": policy.severity.value,
        "requirement": policy.requirement,
        "targets": dict(sorted(policy.targets.items())),
        "applicability": dict(policy.applicability),
        "mechanical": {
            "ast_grep": {
                "supported": policy.mechanical_ast_grep_supported,
                "rule": _mechanical_rule(policy),
            }
        },
    }


def _exception_payload(exception: PolicyException) -> dict[str, object]:
    return {
        "id": exception.exception_id,
        "repository": exception.repository,
        "policy_id": exception.policy_id,
        "reason": exception.reason,
        "approved_by": sorted(exception.approved_by),
        "created": exception.created.isoformat(),
        "expires": exception.expires.isoformat(),
        "scope_paths": sorted(exception.scope_paths),
        "compensating_controls": sorted(exception.compensating_controls),
    }


def _merge_policy(base: PolicyDefinition, overlay: PolicyDefinition) -> PolicyDefinition:
    if SEVERITY_RANK[overlay.severity] < SEVERITY_RANK[base.severity]:
        raise PolicyResolutionError(
            f"{overlay.policy_id} weakens severity {base.severity.value} -> {overlay.severity.value}"
        )
    missing_targets = sorted(
        name for name, enabled in base.targets.items() if enabled and not overlay.targets.get(name)
    )
    if missing_targets:
        raise PolicyResolutionError(
            f"{overlay.policy_id} removes required targets: {', '.join(missing_targets)}"
        )
    if overlay.requirement != base.requirement:
        raise PolicyResolutionError(f"{overlay.policy_id} changes an established requirement")

    severity = max((base.severity, overlay.severity), key=SEVERITY_RANK.__getitem__)
    target_names = set(base.targets) | set(overlay.targets)
    targets = {
        name: bool(base.targets.get(name, False) or overlay.targets.get(name, False))
        for name in sorted(target_names)
    }
    mechanical_supported = (
        base.mechanical_ast_grep_supported or overlay.mechanical_ast_grep_supported
    )
    mechanical_rule = (
        _mechanical_rule(overlay)
        if overlay.mechanical_ast_grep_supported
        else _mechanical_rule(base)
    )
    return replace(
        base,
        owners=tuple(sorted(set(base.owners) | set(overlay.owners))),
        severity=severity,
        targets=targets,
        mechanical_ast_grep_supported=mechanical_supported,
        raw={
            "mechanical": {"ast_grep": {"rule": mechanical_rule}},
            "sources": [_policy_payload(base), _policy_payload(overlay)],
        },
    )


def _deduplicate_selected(policies: Iterable[PolicyDefinition]) -> list[PolicyDefinition]:
    deduped: dict[tuple[str, str, str, str, str], PolicyDefinition] = {}
    for policy in policies:
        key = (
            policy.policy_id,
            policy.authority_tier.value,
            policy.version,
            policy.severity.value,
            policy.requirement,
        )
        deduped[key] = policy
    return list(deduped.values())


def _select_policies(
    manifest: RepositoryManifest,
    catalog: Sequence[PolicyDefinition],
    profiles: Mapping[str, Sequence[str]],
) -> tuple[list[PolicyDefinition], tuple[str, ...]]:
    selected: list[PolicyDefinition] = [
        policy
        for policy in catalog
        if policy.authority_tier is AuthorityTier.CORE
        and policy.maturity is PolicyMaturity.MANDATORY
    ]
    enabled_profiles = tuple(sorted(set(manifest.explicit_profiles)))
    by_id: dict[str, list[PolicyDefinition]] = {}
    for policy in catalog:
        by_id.setdefault(policy.policy_id, []).append(policy)

    for profile in enabled_profiles:
        if profile not in profiles:
            raise PolicyResolutionError(f"unknown profile: {profile}")
        for policy_id in profiles[profile]:
            candidates = [
                policy
                for policy in by_id.get(policy_id, ())
                if policy.authority_tier is not AuthorityTier.REPOSITORY
            ]
            if not candidates:
                raise PolicyResolutionError(
                    f"profile {profile} references unknown policy: {policy_id}"
                )
            selected.extend(candidates)

    for policy_id in sorted(set(manifest.local_policy_ids)):
        candidates = [
            policy
            for policy in by_id.get(policy_id, ())
            if policy.authority_tier is AuthorityTier.REPOSITORY
        ]
        if not candidates:
            raise PolicyResolutionError(f"unknown repository-local policy: {policy_id}")
        selected.extend(candidates)

    return _deduplicate_selected(selected), enabled_profiles


def _resolve_groups(selected: Sequence[PolicyDefinition]) -> tuple[PolicyDefinition, ...]:
    groups: dict[str, list[PolicyDefinition]] = {}
    for policy in selected:
        groups.setdefault(policy.policy_id, []).append(policy)

    resolved: list[PolicyDefinition] = []
    for policy_id in sorted(groups):
        candidates = sorted(
            groups[policy_id],
            key=lambda policy: (_AUTHORITY_RANK[policy.authority_tier], policy.version),
        )
        authority_counts: dict[AuthorityTier, int] = {}
        for candidate in candidates:
            authority_counts[candidate.authority_tier] = (
                authority_counts.get(candidate.authority_tier, 0) + 1
            )
        ambiguous = [tier.value for tier, count in authority_counts.items() if count > 1]
        if ambiguous:
            raise PolicyResolutionError(
                f"ambiguous definitions for {policy_id} at authority tier(s): {', '.join(sorted(ambiguous))}"
            )
        current = candidates[0]
        for candidate in candidates[1:]:
            current = _merge_policy(current, candidate)
        resolved.append(current)
    return tuple(resolved)


def _validate_exceptions(
    manifest: RepositoryManifest,
    policies: Sequence[PolicyDefinition],
    exceptions: Sequence[PolicyException],
    *,
    as_of: date,
) -> tuple[PolicyException, ...]:
    policy_ids = {policy.policy_id for policy in policies}
    seen: set[str] = set()
    valid: list[PolicyException] = []
    for exception in sorted(exceptions, key=lambda item: item.exception_id):
        if exception.exception_id in seen:
            raise PolicyResolutionError(f"duplicate exception id: {exception.exception_id}")
        seen.add(exception.exception_id)
        if exception.repository != manifest.full_name:
            raise PolicyResolutionError(
                f"exception {exception.exception_id} targets {exception.repository}, not {manifest.full_name}"
            )
        if exception.policy_id not in policy_ids:
            raise PolicyResolutionError(
                f"exception {exception.exception_id} references unknown effective policy: {exception.policy_id}"
            )
        if exception.created > as_of:
            raise PolicyResolutionError(f"exception {exception.exception_id} is not active yet")
        if exception.expires < as_of:
            raise PolicyResolutionError(f"exception {exception.exception_id} is expired")
        if not exception.approved_by:
            raise PolicyResolutionError(f"exception {exception.exception_id} has no approver")
        if not exception.compensating_controls:
            raise PolicyResolutionError(
                f"exception {exception.exception_id} has no compensating controls"
            )
        if not exception.scope_paths:
            raise PolicyResolutionError(f"exception {exception.exception_id} has empty scope")
        if any(path in {"*", "**", "/"} for path in exception.scope_paths):
            raise PolicyResolutionError(f"exception {exception.exception_id} scope is too broad")
        valid.append(exception)
    return tuple(valid)


def resolve_policy(
    manifest: RepositoryManifest,
    fingerprint: RepositoryFingerprint,
    catalog: Sequence[PolicyDefinition],
    profiles: Mapping[str, Sequence[str]],
    exceptions: Sequence[PolicyException],
    *,
    as_of: date,
) -> EffectivePolicySet:
    """Resolve mandatory, profile, local, and exception policy deterministically."""
    if manifest.full_name != fingerprint.repository:
        raise PolicyResolutionError(
            f"manifest repository {manifest.full_name} does not match fingerprint {fingerprint.repository}"
        )

    selected, enabled_profiles = _select_policies(manifest, catalog, profiles)
    policies = _resolve_groups(selected)
    valid_exceptions = _validate_exceptions(manifest, policies, exceptions, as_of=as_of)

    manifest_digest = sha256_digest(_manifest_payload(manifest))
    fingerprint_digest = sha256_digest(_fingerprint_payload(fingerprint))
    catalog_digest = sha256_digest(
        [
            _policy_payload(policy)
            for policy in sorted(
                catalog,
                key=lambda item: (
                    item.policy_id,
                    _AUTHORITY_RANK[item.authority_tier],
                    item.version,
                ),
            )
        ]
    )
    resolution_digest = sha256_digest(
        {
            "repository": manifest.full_name,
            "inputs": {
                "manifest": manifest_digest,
                "fingerprint": fingerprint_digest,
                "catalog": catalog_digest,
            },
            "profiles": enabled_profiles,
            "policies": [_policy_payload(policy) for policy in policies],
            "exceptions": [_exception_payload(item) for item in valid_exceptions],
        }
    )

    return EffectivePolicySet(
        repository=manifest.full_name,
        revision=fingerprint.revision,
        manifest_digest=manifest_digest,
        fingerprint_digest=fingerprint_digest,
        catalog_digest=catalog_digest,
        profiles=enabled_profiles,
        policies=policies,
        exceptions=valid_exceptions,
        resolution_digest=resolution_digest,
    )
