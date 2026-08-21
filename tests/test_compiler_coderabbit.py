from pathlib import Path

from coderabbit_control.compiler.coderabbit import compile_coderabbit
from tests.compiler_helpers import effective_fixture


def test_coderabbit_compiler_matches_golden_bytes():
    root = Path(__file__).resolve().parents[1]
    expected = (root / "fixtures/expected/compiler/coderabbit.yaml").read_text(encoding="utf-8")
    artifacts = compile_coderabbit(effective_fixture())
    assert len(artifacts) == 1
    assert artifacts[0].path == ".coderabbit.yaml"
    assert artifacts[0].content == expected
