import pytest

from coderabbit_control.errors import SchemaValidationError
from coderabbit_control.schema import validate_document


def valid_manifest():
    return {
        "apiVersion": "coderabbit.control/v1",
        "kind": "RepositoryManifest",
        "repository": {"provider": "github", "full_name": "asshat1981ar/AutoDev"},
        "profiles": {"explicit": ["agentic-system"]},
        "policy": {"local": ["autodev.forgecore-boundary"]},
        "generation": {
            "coderabbit": True,
            "pull_request_template": True,
            "markdown_policy": True,
            "ast_grep": True,
        },
        "discovery": {"allow_auto_detect": True, "minimum_confidence": 0.85},
    }


def test_valid_repository_manifest_passes():
    validate_document("RepositoryManifest", valid_manifest())


def test_repository_manifest_requires_full_name():
    payload = valid_manifest()
    del payload["repository"]["full_name"]
    with pytest.raises(SchemaValidationError):
        validate_document("RepositoryManifest", payload)


def test_repository_manifest_rejects_unknown_top_level_fields():
    payload = valid_manifest()
    payload["mystery"] = True
    with pytest.raises(SchemaValidationError):
        validate_document("RepositoryManifest", payload)


def test_repository_fingerprint_rejects_confidence_outside_unit_interval():
    payload = {
        "apiVersion": "coderabbit.control/v1",
        "kind": "RepositoryFingerprint",
        "repository": "asshat1981ar/AutoDev",
        "revision": "abc123",
        "languages": {"python": {"confidence": 1.1, "evidence": ["pyproject.toml"]}},
        "capabilities": [],
        "trust_boundaries": [],
        "verification_commands": [],
        "ci_files": [],
    }
    with pytest.raises(SchemaValidationError):
        validate_document("RepositoryFingerprint", payload)


@pytest.mark.parametrize("missing", ["expires", "compensating_controls"])
def test_policy_exception_requires_expiry_and_compensating_controls(missing):
    payload = {
        "apiVersion": "coderabbit.control/v1",
        "kind": "PolicyException",
        "metadata": {"id": "legacy-shell", "repository": "example/repo"},
        "policy_id": "core.security.no-untrusted-shell-execution",
        "reason": "Legacy migration window",
        "approved_by": ["repository-maintainer", "security-owner"],
        "created": "2026-08-20",
        "expires": "2026-10-01",
        "scope": {"paths": ["tools/legacy_runner.py"]},
        "compensating_controls": ["input allowlist"],
    }
    del payload[missing]
    with pytest.raises(SchemaValidationError):
        validate_document("PolicyException", payload)
