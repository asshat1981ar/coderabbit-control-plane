"""Deterministic fleet dry-run evaluation over revision-bound pilot snapshots."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .compiler.ast_grep import compile_ast_grep
from .compiler.coderabbit import compile_coderabbit
from .compiler.markdown import compile_markdown
from .compiler.pull_request import compile_pull_request_template
from .policy_loader import (
    load_profile_catalog,
    load_yaml_document,
    policy_definition_from_document,
    repository_fingerprint_from_document,
    repository_manifest_from_document,
)
from .resolver import resolve_policy
from .validation import validate_artifacts


def _catalog(root: Path):
    policies = [
        policy_definition_from_document(load_yaml_document(path, "PolicyDefinition"))
        for path in sorted((root / "policies").glob("**/*.yaml"))
    ]
    profiles = load_profile_catalog(root / "profiles" / "catalog.yaml")
    return policies, profiles


def _compile_all(effective):
    artifacts = []
    artifacts.extend(compile_coderabbit(effective))
    artifacts.extend(compile_markdown(effective))
    artifacts.extend(compile_pull_request_template(effective))
    artifacts.extend(compile_ast_grep(effective))
    return tuple(sorted(artifacts, key=lambda item: item.path))


def audit_configured_fleet(root: Path, *, as_of: date) -> dict[str, object]:
    """Compile configured pilot manifests against their immutable evidence snapshots."""
    catalog, profiles = _catalog(root)
    repositories: list[dict[str, object]] = []
    failures = 0

    for manifest_path in sorted((root / "repositories" / "pilots").glob("*.yaml")):
        try:
            manifest = repository_manifest_from_document(
                load_yaml_document(manifest_path, "RepositoryManifest")
            )
            fingerprint_path = root / "repositories" / "fingerprints" / manifest_path.name
            fingerprint = repository_fingerprint_from_document(
                load_yaml_document(fingerprint_path, "RepositoryFingerprint")
            )
            effective = resolve_policy(
                manifest,
                fingerprint,
                catalog,
                profiles,
                [],
                as_of=as_of,
            )
            artifacts = _compile_all(effective)
            evidence = validate_artifacts(effective, artifacts)
            status = "PASS" if evidence.result == "PASS" else "FAIL"
            if status != "PASS":
                failures += 1
            repositories.append(
                {
                    "repository": manifest.full_name,
                    "revision": fingerprint.revision,
                    "profile_selection": list(effective.profiles),
                    "effective_policy_digest": effective.resolution_digest,
                    "artifact_digests": dict(sorted(evidence.artifact_digests.items())),
                    "drift_status": "NOT_CHECKED_REMOTE",
                    "validation": evidence.result,
                    "status": status,
                }
            )
        except Exception as exc:
            failures += 1
            repositories.append(
                {
                    "manifest": str(manifest_path.relative_to(root)),
                    "status": "FAIL",
                    "error": str(exc),
                    "drift_status": "NOT_CHECKED_REMOTE",
                }
            )

    if not repositories:
        return {"result": "PARTIAL_FAILURE", "repositories": [], "error": "no pilot manifests"}
    return {
        "result": "PASS" if failures == 0 else "PARTIAL_FAILURE",
        "repositories": repositories,
    }
