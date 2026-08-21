from dataclasses import replace
from datetime import date

import pytest

from coderabbit_control.errors import PolicyResolutionError
from coderabbit_control.models import (
    AuthorityTier,
    PolicyDefinition,
    PolicyException,
    PolicyMaturity,
    RepositoryFingerprint,
    RepositoryManifest,
    Severity,
)
from coderabbit_control.resolver import resolve_policy


def policy(
    policy_id: str,
    *,
    tier: AuthorityTier,
    severity: Severity,
    requirement: str = "preserve invariant",
    targets: dict[str, bool] | None = None,
    profiles: tuple[str, ...] = (),
    maturity: PolicyMaturity = PolicyMaturity.RECOMMENDED,
    weakenable: bool = False,
) -> PolicyDefinition:
    return PolicyDefinition(
        policy_id=policy_id,
        version="1.0.0",
        maturity=maturity,
        owners=("security",),
        authority_tier=tier,
        weakenable=weakenable,
        severity=severity,
        requirement=requirement,
        targets=targets or {"coderabbit": True, "markdown": True},
        applicability={"profiles": profiles},
    )


def manifest(*, profiles=(), local=()) -> RepositoryManifest:
    return RepositoryManifest(
        full_name="example/repo",
        explicit_profiles=tuple(profiles),
        local_policy_ids=tuple(local),
    )


def fingerprint() -> RepositoryFingerprint:
    return RepositoryFingerprint(repository="example/repo", revision="abc123")


def test_local_policy_cannot_weaken_mandatory_core():
    base = policy(
        "core.test",
        tier=AuthorityTier.CORE,
        severity=Severity.BLOCKING,
        maturity=PolicyMaturity.MANDATORY,
    )
    local = policy("core.test", tier=AuthorityTier.REPOSITORY, severity=Severity.ERROR)
    with pytest.raises(PolicyResolutionError):
        resolve_policy(manifest(local=("core.test",)), fingerprint(), [base, local], {}, [], as_of=date(2026, 8, 20))


def test_local_policy_can_strengthen_mandatory_core():
    base = policy(
        "core.test",
        tier=AuthorityTier.CORE,
        severity=Severity.ERROR,
        maturity=PolicyMaturity.MANDATORY,
    )
    local = policy("core.test", tier=AuthorityTier.REPOSITORY, severity=Severity.BLOCKING)
    effective = resolve_policy(manifest(local=("core.test",)), fingerprint(), [base, local], {}, [], as_of=date(2026, 8, 20))
    assert effective.policies[0].severity is Severity.BLOCKING
    assert effective.policies[0].authority_tier is AuthorityTier.CORE


def test_expired_exception_is_rejected():
    base = policy(
        "core.test",
        tier=AuthorityTier.CORE,
        severity=Severity.BLOCKING,
        maturity=PolicyMaturity.MANDATORY,
    )
    exc = PolicyException(
        exception_id="legacy",
        repository="example/repo",
        policy_id="core.test",
        reason="migration",
        approved_by=("security-owner",),
        created=date(2026, 8, 1),
        expires=date(2026, 8, 10),
        scope_paths=("legacy/tool.py",),
        compensating_controls=("allowlist",),
    )
    with pytest.raises(PolicyResolutionError):
        resolve_policy(manifest(), fingerprint(), [base], {}, [exc], as_of=date(2026, 8, 20))


def test_scoped_valid_exception_affects_only_its_scope():
    first = policy(
        "core.first",
        tier=AuthorityTier.CORE,
        severity=Severity.BLOCKING,
        maturity=PolicyMaturity.MANDATORY,
    )
    second = policy(
        "core.second",
        tier=AuthorityTier.CORE,
        severity=Severity.ERROR,
        maturity=PolicyMaturity.MANDATORY,
    )
    exc = PolicyException(
        exception_id="legacy",
        repository="example/repo",
        policy_id="core.first",
        reason="migration",
        approved_by=("security-owner",),
        created=date(2026, 8, 1),
        expires=date(2026, 9, 1),
        scope_paths=("legacy/tool.py",),
        compensating_controls=("allowlist",),
    )
    effective = resolve_policy(manifest(), fingerprint(), [first, second], {}, [exc], as_of=date(2026, 8, 20))
    assert effective.exceptions == (exc,)
    assert {p.policy_id for p in effective.policies} == {"core.first", "core.second"}


def test_policy_input_order_does_not_change_resolution_digest():
    first = policy(
        "core.first",
        tier=AuthorityTier.CORE,
        severity=Severity.BLOCKING,
        maturity=PolicyMaturity.MANDATORY,
    )
    second = policy(
        "core.second",
        tier=AuthorityTier.CORE,
        severity=Severity.ERROR,
        maturity=PolicyMaturity.MANDATORY,
    )
    left = resolve_policy(manifest(), fingerprint(), [first, second], {}, [], as_of=date(2026, 8, 20))
    right = resolve_policy(manifest(), fingerprint(), [second, first], {}, [], as_of=date(2026, 8, 20))
    assert left.resolution_digest == right.resolution_digest


def test_resolution_digest_is_stable_across_evaluation_dates_when_effective_policy_is_same():
    base = policy(
        "core.test",
        tier=AuthorityTier.CORE,
        severity=Severity.BLOCKING,
        maturity=PolicyMaturity.MANDATORY,
    )
    left = resolve_policy(manifest(), fingerprint(), [base], {}, [], as_of=date(2026, 8, 20))
    right = resolve_policy(manifest(), fingerprint(), [base], {}, [], as_of=date(2026, 8, 21))
    assert left.resolution_digest == right.resolution_digest


def test_unknown_mandatory_policy_fails_closed():
    with pytest.raises(PolicyResolutionError):
        resolve_policy(
            manifest(profiles=("core-security",)),
            fingerprint(),
            [],
            {"core-security": ("missing.policy",)},
            [],
            as_of=date(2026, 8, 20),
        )


def test_mechanical_rule_changes_resolution_digest():
    base = policy(
        "profile.mechanical",
        tier=AuthorityTier.PROFILE,
        severity=Severity.ERROR,
        profiles=("mechanical",),
    )
    left_policy = replace(
        base,
        mechanical_ast_grep_supported=True,
        raw={"mechanical": {"ast_grep": {"rule": {"language": "Python", "rule": {"pattern": "left($A)"}}}}},
    )
    right_policy = replace(
        base,
        mechanical_ast_grep_supported=True,
        raw={"mechanical": {"ast_grep": {"rule": {"language": "Python", "rule": {"pattern": "right($A)"}}}}},
    )
    left = resolve_policy(
        manifest(profiles=("mechanical",)),
        fingerprint(),
        [left_policy],
        {"mechanical": ("profile.mechanical",)},
        [],
        as_of=date(2026, 8, 20),
    )
    right = resolve_policy(
        manifest(profiles=("mechanical",)),
        fingerprint(),
        [right_policy],
        {"mechanical": ("profile.mechanical",)},
        [],
        as_of=date(2026, 8, 20),
    )
    assert left.resolution_digest != right.resolution_digest
