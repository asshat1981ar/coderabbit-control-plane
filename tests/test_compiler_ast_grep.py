from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from coderabbit_control.compiler.ast_grep import compile_ast_grep
from coderabbit_control.errors import PolicyResolutionError
from tests.compiler_helpers import effective_fixture


def test_ast_grep_compiler_matches_supported_policy_golden_bytes():
    root = Path(__file__).resolve().parents[1]
    expected = (root / "fixtures/expected/compiler/kotlin-commonmain-platform-purity.yml").read_text(encoding="utf-8")
    artifacts = compile_ast_grep(effective_fixture())
    assert len(artifacts) == 1
    assert artifacts[0].path == ".ast-grep/rules/kotlin-commonmain-platform-purity.yml"
    assert artifacts[0].content == expected


def test_semantic_only_policy_generates_no_ast_grep_output():
    effective = effective_fixture()
    semantic_only = replace(effective, policies=(effective.policies[0],))
    assert compile_ast_grep(semantic_only) == []


def test_ast_grep_target_fails_closed_when_mechanical_support_is_false():
    effective = effective_fixture()
    bad = replace(
        effective.policies[0],
        targets={**effective.policies[0].targets, "ast_grep": True},
        mechanical_ast_grep_supported=False,
    )
    with pytest.raises(PolicyResolutionError):
        compile_ast_grep(replace(effective, policies=(bad,)))


def test_seeded_kotlin_policy_contains_complete_mechanical_rule():
    from coderabbit_control.policy_loader import (
        load_yaml_document,
        policy_definition_from_document,
    )

    root = Path(__file__).resolve().parents[1]
    payload = load_yaml_document(
        root / "policies/languages/kotlin-commonmain-platform-purity.yaml",
        "PolicyDefinition",
    )
    seeded = policy_definition_from_document(payload)
    effective = replace(effective_fixture(), policies=(seeded,))
    artifacts = compile_ast_grep(effective)
    assert len(artifacts) == 1
    assert "kind: import_header" in artifacts[0].content
    parsed = yaml.safe_load(artifacts[0].content)
    assert parsed["rule"]["regex"] == r"^import\s+(java|javax|android)\."


def test_seeded_python_policy_does_not_claim_incomplete_ast_grep_support():
    from coderabbit_control.policy_loader import (
        load_yaml_document,
        policy_definition_from_document,
    )

    root = Path(__file__).resolve().parents[1]
    payload = load_yaml_document(
        root / "policies/languages/python-no-shell-true.yaml",
        "PolicyDefinition",
    )
    seeded = policy_definition_from_document(payload)
    assert seeded.targets["ast_grep"] is False
    assert seeded.mechanical_ast_grep_supported is False
