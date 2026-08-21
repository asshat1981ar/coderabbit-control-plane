from pathlib import Path

from coderabbit_control.discovery import discover_repository


ROOT = Path(__file__).resolve().parents[1] / "fixtures/repositories"


def test_rust_is_detected_from_cargo_manifest():
    fingerprint = discover_repository(ROOT / "rust-cli", "rust-sha")
    assert fingerprint.languages["rust"]["confidence"] == 1.0
    assert fingerprint.languages["rust"]["evidence"] == ["Cargo.toml"]


def test_kotlin_multiplatform_is_backed_by_commonmain_evidence():
    fingerprint = discover_repository(ROOT / "kotlin-mpp", "kmp-sha")
    capability = next(
        item for item in fingerprint.capabilities if item["id"] == "kotlin-multiplatform"
    )
    assert capability["confidence"] == 1.0
    assert any("commonMain" in path for path in capability["evidence"])


def test_android_is_detected_from_manifest_evidence():
    fingerprint = discover_repository(ROOT / "mixed-agent-runtime", "mixed-sha")
    capability = next(item for item in fingerprint.capabilities if item["id"] == "android")
    assert capability["confidence"] == 1.0
    assert capability["evidence"] == ["kotlin/app/src/main/AndroidManifest.xml"]


def test_mcp_requires_explicit_manifest_or_dependency_evidence():
    fingerprint = discover_repository(ROOT / "mcp-server", "mcp-sha")
    capability = next(item for item in fingerprint.capabilities if item["id"] == "mcp-server")
    assert capability["confidence"] >= 0.95
    assert "pyproject.toml" in capability["evidence"]


def test_discovery_uses_stable_local_identity_when_no_remote_metadata_exists():
    fingerprint = discover_repository(ROOT / "python-agent", "py-sha")
    assert fingerprint.repository == "local/python-agent"
    assert fingerprint.revision == "py-sha"
