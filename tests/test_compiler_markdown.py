from pathlib import Path

from coderabbit_control.compiler.markdown import compile_markdown
from tests.compiler_helpers import effective_fixture


def test_markdown_compiler_matches_golden_bytes():
    root = Path(__file__).resolve().parents[1]
    expected = (root / "fixtures/expected/compiler/review-policy.md").read_text(encoding="utf-8")
    artifacts = compile_markdown(effective_fixture())
    assert len(artifacts) == 1
    assert artifacts[0].path == "docs/coderabbit/CODERABBIT_REVIEW_POLICY.md"
    assert artifacts[0].content == expected
