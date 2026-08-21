from datetime import date

import pytest
from hypothesis import given, strategies as st

from coderabbit_control.compiler.coderabbit import compile_coderabbit
from coderabbit_control.errors import PolicyResolutionError, SecurityBoundaryError
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
from coderabbit_control.validation import DEFAULT_GENERATED_ALLOWLIST, validate_output_path


SEVERITIES = [Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.BLOCKING]


def _policy(policy_id, severity, *, tier=AuthorityTier.CORE, maturity=PolicyMaturity.MANDATORY):
    return PolicyDefinition(
        policy_id=policy_id,
        version="1.0.0",
        maturity=maturity,
        owners=("security",),
        authority_tier=tier,
        weakenable=False,
        severity=severity,
        requirement="preserve invariant",
        targets={"coderabbit": True, "markdown": True},
        applicability={},
    )


def _manifest(*, local=()):
    return RepositoryManifest(full_name="example/repo", local_policy_ids=tuple(local))


def _fingerprint():
    return RepositoryFingerprint(repository="example/repo", revision="abc123")


@given(st.permutations(["core.a", "core.b", "core.c"]))
def test_policy_ordering_never_changes_resolution_digest(order):
    catalog_by_id = {
        "core.a": _policy("core.a", Severity.ERROR),
        "core.b": _policy("core.b", Severity.BLOCKING),
        "core.c": _policy("core.c", Severity.WARNING),
    }
    catalog = [catalog_by_id[item] for item in order]
    baseline = [catalog_by_id[item] for item in ("core.a", "core.b", "core.c")]

    left = resolve_policy(_manifest(), _fingerprint(), catalog, {}, [], as_of=date(2026, 8, 21))
    right = resolve_policy(_manifest(), _fingerprint(), baseline, {}, [], as_of=date(2026, 8, 21))

    assert left.resolution_digest == right.resolution_digest


@given(st.sampled_from(SEVERITIES), st.sampled_from(SEVERITIES))
def test_stronger_repository_overlay_never_weakens_effective_severity(base_severity, local_severity):
    if SEVERITIES.index(local_severity) < SEVERITIES.index(base_severity):
        return
    base = _policy("core.test", base_severity)
    local = _policy(
        "core.test",
        local_severity,
        tier=AuthorityTier.REPOSITORY,
        maturity=PolicyMaturity.RECOMMENDED,
    )

    effective = resolve_policy(
        _manifest(local=("core.test",)),
        _fingerprint(),
        [base, local],
        {},
        [],
        as_of=date(2026, 8, 21),
    )

    assert SEVERITIES.index(effective.policies[0].severity) >= SEVERITIES.index(base_severity)


def test_removing_repository_local_policy_cannot_remove_mandatory_policy():
    mandatory = _policy("core.required", Severity.BLOCKING)
    local = _policy(
        "repo.extra",
        Severity.ERROR,
        tier=AuthorityTier.REPOSITORY,
        maturity=PolicyMaturity.RECOMMENDED,
    )
    with_local = resolve_policy(
        _manifest(local=("repo.extra",)),
        _fingerprint(),
        [mandatory, local],
        {},
        [],
        as_of=date(2026, 8, 21),
    )
    without_local = resolve_policy(
        _manifest(),
        _fingerprint(),
        [mandatory, local],
        {},
        [],
        as_of=date(2026, 8, 21),
    )

    assert "core.required" in {item.policy_id for item in with_local.policies}
    assert "core.required" in {item.policy_id for item in without_local.policies}


def test_expired_exception_never_changes_effective_output():
    mandatory = _policy("core.required", Severity.BLOCKING)
    expired = PolicyException(
        exception_id="expired",
        repository="example/repo",
        policy_id="core.required",
        reason="legacy migration",
        approved_by=("security-owner",),
        created=date(2026, 7, 1),
        expires=date(2026, 8, 1),
        scope_paths=("legacy/tool.py",),
        compensating_controls=("allowlist",),
    )

    with pytest.raises(PolicyResolutionError):
        resolve_policy(
            _manifest(),
            _fingerprint(),
            [mandatory],
            {},
            [expired],
            as_of=date(2026, 8, 21),
        )


def test_same_effective_policy_compiles_to_identical_bytes():
    mandatory = _policy("core.required", Severity.BLOCKING)
    first = resolve_policy(
        _manifest(), _fingerprint(), [mandatory], {}, [], as_of=date(2026, 8, 20)
    )
    second = resolve_policy(
        _manifest(), _fingerprint(), [mandatory], {}, [], as_of=date(2026, 8, 21)
    )

    assert first.resolution_digest == second.resolution_digest
    assert compile_coderabbit(first) == compile_coderabbit(second)


@given(
    st.lists(
        st.sampled_from(
            [
                "safe/file.py",
                ".coderabbit/policy.yaml",
                "../escape",
                "/absolute",
                "a/../../b",
                "..\\escape",
            ]
        ),
        min_size=1,
        max_size=8,
    )
)
def test_path_escape_inputs_never_pass_generated_allowlist(paths):
    for path in paths:
        if path == ".coderabbit/policy.yaml":
            validate_output_path(path, DEFAULT_GENERATED_ALLOWLIST)
        else:
            with pytest.raises(SecurityBoundaryError):
                validate_output_path(path, DEFAULT_GENERATED_ALLOWLIST)
