"""Fail-closed validation for generated control-plane artifacts."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from coderabbit_control import __version__
from coderabbit_control.canonical import sha256_digest
from coderabbit_control.compiler import GeneratedArtifact
from coderabbit_control.drift import detect_drift
from coderabbit_control.errors import SecurityBoundaryError
from coderabbit_control.models import EffectivePolicySet, EvidenceManifest


DEFAULT_GENERATED_ALLOWLIST = (
    ".coderabbit.yaml",
    ".coderabbit/**",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "docs/coderabbit/**",
    ".ast-grep/**",
)

_SECRET_PATTERNS = (
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
)


def _matches_allowlist(path: str, allowlist: Sequence[str]) -> bool:
    for allowed in allowlist:
        if allowed.endswith("/**"):
            prefix = allowed[:-3].rstrip("/")
            if path == prefix or path.startswith(prefix + "/"):
                return True
        elif path == allowed:
            return True
    return False


def validate_output_path(path: str, allowlist: tuple[str, ...]) -> None:
    """Ensure a generated path is unambiguously repository-relative and allowed."""
    if not path or "\\" in path:
        raise SecurityBoundaryError(f"invalid generated output path: {path!r}")
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part in {".", ".."} for part in pure.parts):
        raise SecurityBoundaryError(f"generated output escapes repository scope: {path}")
    normalized = pure.as_posix()
    if normalized != path or not _matches_allowlist(normalized, allowlist):
        raise SecurityBoundaryError(f"generated output is outside allowlist: {path}")


def _content_digest(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def _reject_secret_like_material(artifact: GeneratedArtifact) -> None:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(artifact.content):
            raise SecurityBoundaryError(
                f"generated artifact contains credential-like material: {artifact.path}"
            )


def validate_artifacts(
    effective: EffectivePolicySet,
    artifacts: Sequence[GeneratedArtifact],
    checked_in: Mapping[str, str] | None = None,
) -> EvidenceManifest:
    """Validate generated artifacts and emit deterministic evidence."""
    seen: set[str] = set()
    expected: dict[str, str] = {}
    for artifact in sorted(artifacts, key=lambda item: item.path):
        if artifact.path in seen:
            raise SecurityBoundaryError(f"duplicate generated output path: {artifact.path}")
        seen.add(artifact.path)
        validate_output_path(artifact.path, DEFAULT_GENERATED_ALLOWLIST)
        _reject_secret_like_material(artifact)
        expected[artifact.path] = artifact.content

    artifact_digests = {
        path: _content_digest(content) for path, content in sorted(expected.items())
    }
    checks = {
        "output_paths": "PASS",
        "secret_scan": "PASS",
        "drift": "SKIP",
    }
    result = "PASS"
    if checked_in is not None:
        report = detect_drift(expected, checked_in)
        checks["drift"] = "FAIL" if report.has_drift else "PASS"
        if report.has_drift:
            result = "FAIL"

    run_id = sha256_digest(
        {
            "effective_policy_digest": effective.resolution_digest,
            "revision": effective.revision,
            "artifacts": artifact_digests,
            "checks": checks,
            "result": result,
        }
    )
    return EvidenceManifest(
        run_id=run_id,
        compiler_version=__version__,
        repository=effective.repository,
        revision=effective.revision,
        effective_policy_digest=effective.resolution_digest,
        artifact_digests=artifact_digests,
        checks=checks,
        result=result,
    )
