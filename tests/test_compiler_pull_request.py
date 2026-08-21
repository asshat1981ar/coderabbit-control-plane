from pathlib import Path

from coderabbit_control.compiler.pull_request import compile_pull_request_template
from tests.compiler_helpers import effective_fixture


def test_pull_request_compiler_matches_golden_bytes():
    root = Path(__file__).resolve().parents[1]
    expected = (root / "fixtures/expected/compiler/pull-request-template.md").read_text(encoding="utf-8")
    artifacts = compile_pull_request_template(effective_fixture())
    assert len(artifacts) == 1
    assert artifacts[0].path == ".github/PULL_REQUEST_TEMPLATE.md"
    assert artifacts[0].content == expected
