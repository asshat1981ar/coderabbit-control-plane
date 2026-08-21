"""Conservative structural profile classification."""

from __future__ import annotations

from .models import ProfileSelection, RepositoryFingerprint


_DETECTED_CAPABILITIES = {
    "kotlin-multiplatform": "kotlin-multiplatform",
    "android": "android",
    "mcp-server": "mcp-server",
    "python-agent-tools": "python-agent-tools",
    "github-actions": "github-actions",
}


def classify_repository(fingerprint: RepositoryFingerprint) -> ProfileSelection:
    """Classify structural evidence; ambiguous semantic roles remain suggestions."""
    detected: set[str] = set()
    suggested: set[str] = set()
    confidence: dict[str, float] = {}
    evidence: dict[str, tuple[str, ...]] = {}

    for capability in fingerprint.capabilities:
        capability_id = str(capability["id"])
        profile = _DETECTED_CAPABILITIES.get(capability_id)
        if not profile:
            continue
        score = float(capability["confidence"])
        paths = tuple(sorted(str(path) for path in capability["evidence"]))
        if score >= 0.85:
            detected.add(profile)
        else:
            suggested.add(profile)
        confidence[profile] = score
        evidence[profile] = paths

    rust = fingerprint.languages.get("rust")
    if rust is not None and "rust-secure-runtime" not in detected:
        suggested.add("rust-secure-runtime")
        confidence["rust-secure-runtime"] = 0.6
        evidence["rust-secure-runtime"] = tuple(
            sorted(str(path) for path in rust.get("evidence", ()))
        )

    return ProfileSelection(
        detected=tuple(sorted(detected)),
        suggested=tuple(sorted(suggested - detected)),
        confidence={name: confidence[name] for name in sorted(confidence)},
        evidence={name: evidence[name] for name in sorted(evidence)},
    )
