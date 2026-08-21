"""Deterministic policy artifact compiler primitives."""

from __future__ import annotations

from dataclasses import dataclass

from coderabbit_control import __version__
from coderabbit_control.models import EffectivePolicySet


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    path: str
    content: str
    source_policy_ids: tuple[str, ...]


def hash_header(effective: EffectivePolicySet) -> str:
    return (
        "# GENERATED FILE - DO NOT EDIT DIRECTLY\n"
        f"# Compiler: crctl {__version__}\n"
        f"# Effective policy: {effective.resolution_digest}\n"
    )


def html_header(effective: EffectivePolicySet) -> str:
    return (
        "<!-- GENERATED FILE - DO NOT EDIT DIRECTLY -->\n"
        f"<!-- Compiler: crctl {__version__} -->\n"
        f"<!-- Effective policy: {effective.resolution_digest} -->\n"
    )


def one_line(text: str) -> str:
    return " ".join(text.split())
