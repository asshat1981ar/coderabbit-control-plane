import json
from pathlib import Path

from coderabbit_control.cli import main


def _write_manifest(path: Path, *, local=()):
    local_yaml = "\n".join(f"    - {item}" for item in local) or "    []"
    path.write_text(
        "\n".join(
            [
                "apiVersion: coderabbit.control/v1",
                "kind: RepositoryManifest",
                "repository:",
                "  provider: github",
                "  full_name: example/repo",
                "profiles:",
                "  explicit: []",
                "policy:",
                "  local:",
                local_yaml,
                "generation:",
                "  coderabbit: true",
                "  pull_request_template: true",
                "  markdown_policy: true",
                "  ast_grep: true",
                "discovery:",
                "  allow_auto_detect: true",
                "  minimum_confidence: 0.85",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_fingerprint(path: Path):
    path.write_text(
        "\n".join(
            [
                "apiVersion: coderabbit.control/v1",
                "kind: RepositoryFingerprint",
                "repository: example/repo",
                "revision: abc123",
                "languages: {}",
                "capabilities: []",
                "trust_boundaries: []",
                "verification_commands: []",
                "ci_files: []",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_resolve_emits_machine_readable_json(tmp_path, capsys):
    manifest = tmp_path / "repository.yaml"
    fingerprint = tmp_path / "fingerprint.yaml"
    _write_manifest(manifest)
    _write_fingerprint(fingerprint)

    code = main(
        [
            "resolve",
            "--manifest",
            str(manifest),
            "--fingerprint",
            str(fingerprint),
            "--as-of",
            "2026-08-21",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repository"] == "example/repo"
    assert payload["revision"] == "abc123"
    assert payload["resolution_digest"].startswith("sha256:")
    assert payload["policies"]


def test_invalid_repository_policy_returns_security_exit_code(tmp_path, capsys):
    manifest = tmp_path / "repository.yaml"
    fingerprint = tmp_path / "fingerprint.yaml"
    _write_manifest(manifest, local=("missing.repository-policy",))
    _write_fingerprint(fingerprint)

    code = main(
        [
            "resolve",
            "--manifest",
            str(manifest),
            "--fingerprint",
            str(fingerprint),
            "--as-of",
            "2026-08-21",
            "--json",
        ]
    )

    assert code == 3
    assert "unknown repository-local policy" in capsys.readouterr().err


def test_audit_fleet_dry_run_reports_partial_failure(tmp_path, capsys):
    valid = tmp_path / "valid"
    valid.mkdir()
    (valid / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0.1.0'\n", encoding="utf-8")
    missing = tmp_path / "missing"

    code = main(
        [
            "audit-fleet",
            str(valid),
            str(missing),
            "--revision",
            "abc123",
            "--dry-run",
            "--json",
        ]
    )

    assert code == 5
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "PARTIAL_FAILURE"
    assert len(payload["repositories"]) == 2
    assert {item["status"] for item in payload["repositories"]} == {"PASS", "FAIL"}
