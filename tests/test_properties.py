from datetime import date

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st

from coderabbit_control.models import (
    AuthorityTier,
    PolicyDefinition,
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


def _manifest():
    return RepositoryManifest(full_name="example/repo")


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
    manifest = RepositoryManifest(full_name="example/repo", local_policy_ids=("core.test",))

    effective = resolve_policy(manifest, _fingerprint(), [base, local], {}, [], as_of=date(2026, 8, 21))

    assert SEVERITIES.index(effective.policies[0].severity) >= SEVERITIES.index(base_severity)


@given(
    st.lists(
        st.sampled_from(["safe/file.py", ".coderabbit/policy.yaml", "../escape", "/absolute", "a/../../b"]),
        min_size=1,
        max_size=8,
    )
)
def test_path_escape_inputs_never_pass_generated_allowlist(paths):
    for path in paths:
        if path in {".coderabbit/policy.yaml"}:
            validate_output_path(path, DEFAULT_GENERATED_ALLOWLIST)
        else:
            with pytest.raises(Exception):
                validate_output_path(path, DEFAULT_GENERATED_ALLOWLIST)
