from pathlib import Path

import pytest

from coderabbit_control.errors import SchemaValidationError
from coderabbit_control.policy_loader import load_yaml_document


def test_load_yaml_document_validates_and_returns_mapping(tmp_path: Path):
    path = tmp_path / "policy.yaml"
    path.write_text(
        """apiVersion: coderabbit.control/v1
kind: PolicyDefinition
metadata:
  id: python.no-shell-true
  version: 1.0.0
  status: recommended
  owners: [security]
authority:
  tier: profile
  weakenable: false
applicability:
  profiles: [python-agent-tools]
severity: blocking
requirement:
  statement: Do not use shell=True.
targets:
  coderabbit: {enabled: true}
  markdown: {enabled: true}
  pull_request_template: {enabled: true}
  ast_grep: {enabled: true}
mechanical:
  ast_grep:
    supported: true
    rule: {language: python}
""",
        encoding="utf-8",
    )
    payload = load_yaml_document(path, "PolicyDefinition")
    assert payload["metadata"]["id"] == "python.no-shell-true"


def test_load_yaml_document_rejects_python_object_tags(tmp_path: Path):
    path = tmp_path / "unsafe.yaml"
    path.write_text("!!python/object/apply:os.system ['echo unsafe']\n", encoding="utf-8")
    with pytest.raises(SchemaValidationError):
        load_yaml_document(path, "PolicyDefinition")


def test_seed_policy_catalog_validates():
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "policies").rglob("*.yaml"))
    assert len(files) == 10
    ids = {load_yaml_document(path, "PolicyDefinition")["metadata"]["id"] for path in files}
    assert len(ids) == 10


def test_profile_catalog_loads_deterministically():
    from coderabbit_control.policy_loader import load_profile_catalog

    root = Path(__file__).resolve().parents[1]
    profiles = load_profile_catalog(root / "profiles" / "catalog.yaml")
    assert profiles["python-agent-tools"] == ("python.no-shell-true",)
    assert profiles["android"] == ()
