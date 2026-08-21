from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_ci_exposes_required_jobs_and_python_versions():
    workflow_text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for job in ("ruff:", "pytest:", "schema-validation:", "fixture-recompile-drift:"):
        assert job in workflow_text
    assert '"3.11"' in workflow_text
    assert '"3.12"' in workflow_text
    assert "permissions:\n  contents: read" in workflow_text


def test_coderabbit_self_reviews_all_high_risk_paths():
    config = yaml.safe_load((ROOT / ".coderabbit.yaml").read_text(encoding="utf-8"))
    paths = {entry["path"] for entry in config["reviews"]["path_instructions"]}
    required = {
        "src/coderabbit_control/resolver.py",
        "src/coderabbit_control/validation.py",
        "src/coderabbit_control/sync.py",
        "policies/core/**",
        "schemas/**",
        "skills/coderabbit-control/**",
    }
    assert required <= paths


def test_coderabbit_instructions_reinforce_control_plane_invariants():
    text = (ROOT / ".coderabbit.yaml").read_text(encoding="utf-8").lower()
    for phrase in (
        "must not weaken mandatory",
        "path confinement",
        "deterministic",
        "stale-head",
        "untrusted review text",
    ):
        assert phrase in text


def test_pr_template_requires_evidence_and_noncontradictory_boundary_declaration():
    text = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8").lower()
    assert "select exactly one" in text
    assert "commands run" in text
    assert "ci run" in text
    assert "evidencemanifest" in text
    assert "coderabbit findings" in text


def test_review_policy_denies_review_as_authorization():
    text = (ROOT / "docs" / "CODERABBIT_REVIEW_POLICY.md").read_text(encoding="utf-8").lower()
    assert "review evidence" in text
    assert "never execution or merge authorization" in text
    assert "generated `.coderabbit.yaml` is not policy authority" in text
