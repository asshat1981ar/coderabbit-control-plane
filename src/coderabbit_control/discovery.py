"""Evidence-backed, high-signal repository discovery."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .models import RepositoryFingerprint


_MAX_TEXT_BYTES = 256_000
_MCP_PATTERN = re.compile(r"(?im)(?:^|[\"'\s])(?:mcp|modelcontextprotocol)(?:[<>=~!\s\"']|$)")


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _read_small(path: Path) -> str:
    try:
        if path.stat().st_size > _MAX_TEXT_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _sorted_paths(root: Path, paths: Iterable[Path]) -> list[str]:
    return sorted({_relative(root, path) for path in paths if path.exists()})


def _repository_identity(root: Path) -> str:
    git_config = root / ".git" / "config"
    text = _read_small(git_config)
    if text:
        match = re.search(
            r"(?m)^\s*url\s*=\s*(?:https://github\.com/|git@github\.com:)([^/\s]+/[^/\s]+?)(?:\.git)?\s*$",
            text,
        )
        if match:
            return match.group(1)
    return f"local/{root.name}"


def discover_repository(root: Path, revision: str) -> RepositoryFingerprint:
    """Fingerprint only high-signal manifests, source layout, and CI metadata."""
    root = root.resolve()
    languages: dict[str, dict[str, object]] = {}
    capabilities: list[dict[str, object]] = []

    cargo = root / "Cargo.toml"
    pyproject = root / "pyproject.toml"
    package_json = root / "package.json"
    gradle_files = sorted(
        set(root.rglob("build.gradle.kts")) | set(root.rglob("build.gradle")),
        key=lambda path: _relative(root, path),
    )
    commonmain_dirs = sorted(
        root.glob("**/src/commonMain"), key=lambda path: _relative(root, path)
    )
    android_manifests = sorted(
        root.rglob("AndroidManifest.xml"), key=lambda path: _relative(root, path)
    )
    workflows = sorted(
        list((root / ".github" / "workflows").glob("*.yml"))
        + list((root / ".github" / "workflows").glob("*.yaml")),
        key=lambda path: _relative(root, path),
    )

    if cargo.exists():
        languages["rust"] = {"confidence": 1.0, "evidence": ["Cargo.toml"]}
    if pyproject.exists():
        languages["python"] = {"confidence": 1.0, "evidence": ["pyproject.toml"]}
    if package_json.exists():
        languages["javascript"] = {"confidence": 0.95, "evidence": ["package.json"]}
    if gradle_files or commonmain_dirs:
        evidence = _sorted_paths(root, [*gradle_files, *commonmain_dirs])
        languages["kotlin"] = {"confidence": 0.98, "evidence": evidence}

    if commonmain_dirs:
        capabilities.append(
            {
                "id": "kotlin-multiplatform",
                "confidence": 1.0,
                "evidence": _sorted_paths(root, commonmain_dirs),
            }
        )
    if android_manifests:
        capabilities.append(
            {
                "id": "android",
                "confidence": 1.0,
                "evidence": _sorted_paths(root, android_manifests),
            }
        )

    manifest_evidence: list[Path] = []
    for manifest in (pyproject, package_json, cargo):
        if manifest.exists() and _MCP_PATTERN.search(_read_small(manifest)):
            manifest_evidence.append(manifest)
    if manifest_evidence:
        capabilities.append(
            {
                "id": "mcp-server",
                "confidence": 0.97,
                "evidence": _sorted_paths(root, manifest_evidence),
            }
        )

    agents_file = root / "AGENTS.md"
    if pyproject.exists() and agents_file.exists():
        capabilities.append(
            {
                "id": "python-agent-tools",
                "confidence": 0.9,
                "evidence": ["AGENTS.md", "pyproject.toml"],
            }
        )
    if workflows:
        capabilities.append(
            {
                "id": "github-actions",
                "confidence": 1.0,
                "evidence": _sorted_paths(root, workflows),
            }
        )

    return RepositoryFingerprint(
        repository=_repository_identity(root),
        revision=revision,
        languages={name: languages[name] for name in sorted(languages)},
        capabilities=tuple(sorted(capabilities, key=lambda item: str(item["id"]))),
        trust_boundaries=(),
        verification_commands=(),
        ci_files=tuple(_sorted_paths(root, workflows)),
    )
