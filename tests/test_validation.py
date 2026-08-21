import pytest

from coderabbit_control.compiler import GeneratedArtifact
from coderabbit_control.errors import SecurityBoundaryError
from coderabbit_control.validation import validate_artifacts, validate_output_path
from tests.compiler_helpers import effective_fixture


ALLOWLIST = (
    ".coderabbit.yaml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "docs/coderabbit/**",
    ".ast-grep/**",
)


def artifact(path: str, content: str = "safe generated content\n") -> GeneratedArtifact:
    return GeneratedArtifact(path=path, content=content, source_policy_ids=("core.test",))


def test_parent_path_escape_is_rejected():
    with pytest.raises(SecurityBoundaryError):
        validate_output_path("docs/coderabbit/../../secrets.txt", ALLOWLIST)


def test_absolute_output_path_is_rejected():
    with pytest.raises(SecurityBoundaryError):
        validate_output_path("/tmp/output.txt", ALLOWLIST)


def test_backslash_path_is_rejected_to_keep_posix_confinement_unambiguous():
    with pytest.raises(SecurityBoundaryError):
        validate_output_path(r"docs\coderabbit\policy.md", ALLOWLIST)


def test_secret_like_material_in_generated_output_fails_validation():
    effective = effective_fixture()
    leaked = artifact(".coderabbit.yaml", "token = ghp_1234567890abcdefghijklmnopqrst\n")
    with pytest.raises(SecurityBoundaryError):
        validate_artifacts(effective, [leaked])


def test_success_manifest_contains_revision_and_all_artifact_digests():
    effective = effective_fixture()
    artifacts = [
        artifact(".coderabbit.yaml", "one\n"),
        artifact("docs/coderabbit/CODERABBIT_REVIEW_POLICY.md", "two\n"),
    ]
    manifest = validate_artifacts(effective, artifacts)
    assert manifest.result == "PASS"
    assert manifest.revision == "abc123"
    assert set(manifest.artifact_digests) == {item.path for item in artifacts}
    assert all(value.startswith("sha256:") for value in manifest.artifact_digests.values())


def test_validation_marks_checked_in_drift_as_failure_without_mutating_expected():
    effective = effective_fixture()
    expected = artifact(".coderabbit.yaml", "expected\n")
    manifest = validate_artifacts(
        effective,
        [expected],
        checked_in={".coderabbit.yaml": "manually edited\n"},
    )
    assert manifest.result == "FAIL"
    assert manifest.checks["drift"] == "FAIL"
    assert expected.content == "expected\n"


def test_evidence_run_id_is_deterministic_for_identical_inputs():
    effective = effective_fixture()
    artifacts = [artifact(".coderabbit.yaml", "same\n")]
    left = validate_artifacts(effective, artifacts)
    right = validate_artifacts(effective, artifacts)
    assert left.run_id == right.run_id
    assert left.artifact_digests == right.artifact_digests
