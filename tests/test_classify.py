from pathlib import Path

from coderabbit_control.classify import classify_repository
from coderabbit_control.discovery import discover_repository


ROOT = Path(__file__).resolve().parents[1] / "fixtures/repositories"


def test_structural_capabilities_activate_detected_profiles():
    kotlin = classify_repository(discover_repository(ROOT / "kotlin-mpp", "sha"))
    mcp = classify_repository(discover_repository(ROOT / "mcp-server", "sha"))
    python = classify_repository(discover_repository(ROOT / "python-agent", "sha"))
    mixed = classify_repository(discover_repository(ROOT / "mixed-agent-runtime", "sha"))

    assert "kotlin-multiplatform" in kotlin.detected
    assert "mcp-server" in mcp.detected
    assert "python-agent-tools" in python.detected
    assert "android" in mixed.detected
    assert "github-actions" in mixed.detected


def test_rust_manifest_alone_does_not_claim_secure_runtime_semantics():
    selection = classify_repository(discover_repository(ROOT / "rust-cli", "sha"))
    assert "rust-secure-runtime" not in selection.detected
    assert "rust-secure-runtime" in selection.suggested
    assert selection.confidence["rust-secure-runtime"] < 0.85


def test_automatically_detected_profile_retains_evidence():
    selection = classify_repository(discover_repository(ROOT / "mcp-server", "sha"))
    assert selection.evidence["mcp-server"]
    assert selection.confidence["mcp-server"] >= 0.85
