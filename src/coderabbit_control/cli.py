"""Canonical deterministic command-line interface for the control plane."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Sequence

from .classify import classify_repository
from .compiler.ast_grep import compile_ast_grep
from .compiler.coderabbit import compile_coderabbit
from .compiler.markdown import compile_markdown
from .compiler.pull_request import compile_pull_request_template
from .discovery import discover_repository
from .drift import detect_drift
from .errors import (
    ExternalRepositoryError,
    PolicyResolutionError,
    SchemaValidationError,
    SecurityBoundaryError,
    StaleRevisionError,
)
from .github import GitHubRestClient
from .policy_loader import (
    load_profile_catalog,
    load_yaml_document,
    policy_definition_from_document,
    policy_exception_from_document,
    repository_fingerprint_from_document,
    repository_manifest_from_document,
)
from .resolver import resolve_policy
from .sync import SyncPlan, sync_repository
from .validation import validate_artifacts


EXIT_SUCCESS = 0
EXIT_INVALID_INPUT = 2
EXIT_POLICY_REJECTED = 3
EXIT_STALE_STATE = 4
EXIT_PARTIAL_FAILURE = 5


def _control_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _jsonable(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _emit(payload: object, *, json_output: bool) -> None:
    normalized = _jsonable(payload)
    if json_output:
        print(json.dumps(normalized, ensure_ascii=False, sort_keys=True))
    elif isinstance(normalized, str):
        print(normalized)
    else:
        print(json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True))


def _load_catalog(root: Path | None = None):
    root = root or _control_root()
    policies = []
    for path in sorted((root / "policies").glob("**/*.yaml")):
        payload = load_yaml_document(path, "PolicyDefinition")
        policies.append(policy_definition_from_document(payload))
    if not policies:
        raise SchemaValidationError(f"no policy definitions found under {root / 'policies'}")
    profiles = load_profile_catalog(root / "profiles" / "catalog.yaml")
    return policies, profiles


def _load_effective(args: argparse.Namespace):
    manifest = repository_manifest_from_document(
        load_yaml_document(Path(args.manifest), "RepositoryManifest")
    )
    fingerprint = repository_fingerprint_from_document(
        load_yaml_document(Path(args.fingerprint), "RepositoryFingerprint")
    )
    catalog, profiles = _load_catalog()
    exceptions = [
        policy_exception_from_document(load_yaml_document(Path(path), "PolicyException"))
        for path in getattr(args, "exception", ())
    ]
    return resolve_policy(
        manifest,
        fingerprint,
        catalog,
        profiles,
        exceptions,
        as_of=date.fromisoformat(args.as_of),
    )


def _compile_all(effective):
    artifacts = []
    artifacts.extend(compile_coderabbit(effective))
    artifacts.extend(compile_markdown(effective))
    artifacts.extend(compile_pull_request_template(effective))
    artifacts.extend(compile_ast_grep(effective))
    return sorted(artifacts, key=lambda item: item.path)


def _fingerprint_document(fingerprint) -> dict[str, object]:
    """Serialize discovery output as a schema-valid RepositoryFingerprint document."""
    return {
        "apiVersion": "coderabbit.control/v1",
        "kind": "RepositoryFingerprint",
        "repository": fingerprint.repository,
        "revision": fingerprint.revision,
        "languages": {
            name: dict(value) for name, value in sorted(fingerprint.languages.items())
        },
        "capabilities": [dict(item) for item in fingerprint.capabilities],
        "trust_boundaries": [dict(item) for item in fingerprint.trust_boundaries],
        "verification_commands": list(fingerprint.verification_commands),
        "ci_files": list(fingerprint.ci_files),
    }


def _effective_payload(effective) -> dict[str, object]:
    return {
        "repository": effective.repository,
        "revision": effective.revision,
        "manifest_digest": effective.manifest_digest,
        "fingerprint_digest": effective.fingerprint_digest,
        "catalog_digest": effective.catalog_digest,
        "profiles": list(effective.profiles),
        "policies": [
            {
                "id": policy.policy_id,
                "version": policy.version,
                "severity": policy.severity.value,
                "authority": policy.authority_tier.value,
            }
            for policy in effective.policies
        ],
        "exceptions": [exception.exception_id for exception in effective.exceptions],
        "resolution_digest": effective.resolution_digest,
    }


def _add_resolution_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--fingerprint", required=True)
    parser.add_argument("--exception", action="append", default=[])
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--json", action="store_true")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crctl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover")
    discover.add_argument("root")
    discover.add_argument("--revision", required=True)
    discover.add_argument("--json", action="store_true")

    classify = subparsers.add_parser("classify")
    classify.add_argument("root")
    classify.add_argument("--revision", required=True)
    classify.add_argument("--json", action="store_true")

    resolve = subparsers.add_parser("resolve")
    _add_resolution_arguments(resolve)

    compile_parser = subparsers.add_parser("compile")
    _add_resolution_arguments(compile_parser)

    validate = subparsers.add_parser("validate")
    _add_resolution_arguments(validate)

    diff = subparsers.add_parser("diff")
    _add_resolution_arguments(diff)
    diff.add_argument("--checked-in-root", required=True)

    explain = subparsers.add_parser("explain")
    explain.add_argument("policy_id")
    _add_resolution_arguments(explain)

    audit = subparsers.add_parser("audit-fleet")
    audit.add_argument("roots", nargs="+")
    audit.add_argument("--revision", required=True)
    audit.add_argument("--dry-run", action="store_true", required=True)
    audit.add_argument("--json", action="store_true")

    sync = subparsers.add_parser("sync")
    _add_resolution_arguments(sync)
    sync.add_argument("--base-branch", default="main")
    sync.add_argument("--branch-name")
    sync.add_argument("--apply", action="store_true")

    return parser


def _run_discover(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if not root.is_dir():
        raise ValueError(f"repository root does not exist: {root}")
    fingerprint = discover_repository(root, args.revision)
    _emit(_fingerprint_document(fingerprint), json_output=args.json)
    return EXIT_SUCCESS


def _run_classify(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if not root.is_dir():
        raise ValueError(f"repository root does not exist: {root}")
    fingerprint = discover_repository(root, args.revision)
    _emit(classify_repository(fingerprint), json_output=args.json)
    return EXIT_SUCCESS


def _run_resolve(args: argparse.Namespace) -> int:
    _emit(_effective_payload(_load_effective(args)), json_output=args.json)
    return EXIT_SUCCESS


def _run_compile(args: argparse.Namespace) -> int:
    effective = _load_effective(args)
    artifacts = _compile_all(effective)
    payload = [
        {
            "path": artifact.path,
            "content": artifact.content,
            "source_policy_ids": list(artifact.source_policy_ids),
        }
        for artifact in artifacts
    ]
    _emit(payload, json_output=args.json)
    return EXIT_SUCCESS


def _run_validate(args: argparse.Namespace) -> int:
    effective = _load_effective(args)
    evidence = validate_artifacts(effective, _compile_all(effective))
    _emit(evidence, json_output=args.json)
    return EXIT_SUCCESS if evidence.result == "PASS" else EXIT_POLICY_REJECTED


def _run_diff(args: argparse.Namespace) -> int:
    effective = _load_effective(args)
    artifacts = _compile_all(effective)
    expected = {artifact.path: artifact.content for artifact in artifacts}
    checked_root = Path(args.checked_in_root)
    actual = {}
    for path in sorted(expected):
        candidate = checked_root / path
        if candidate.is_file():
            actual[path] = candidate.read_text(encoding="utf-8")
    report = detect_drift(expected, actual)
    _emit(report, json_output=args.json)
    return EXIT_POLICY_REJECTED if report.has_drift else EXIT_SUCCESS


def _run_explain(args: argparse.Namespace) -> int:
    effective = _load_effective(args)
    for policy in effective.policies:
        if policy.policy_id == args.policy_id:
            _emit(
                {
                    "id": policy.policy_id,
                    "version": policy.version,
                    "authority": policy.authority_tier.value,
                    "severity": policy.severity.value,
                    "requirement": policy.requirement,
                    "targets": dict(sorted(policy.targets.items())),
                    "resolution_digest": effective.resolution_digest,
                },
                json_output=args.json,
            )
            return EXIT_SUCCESS
    raise PolicyResolutionError(f"policy is not effective for repository: {args.policy_id}")


def _run_audit_fleet(args: argparse.Namespace) -> int:
    repositories = []
    failures = 0
    for raw_root in args.roots:
        root = Path(raw_root)
        if not root.is_dir():
            failures += 1
            repositories.append(
                {"root": str(root), "status": "FAIL", "error": "repository root does not exist"}
            )
            continue
        try:
            fingerprint = discover_repository(root, args.revision)
            selection = classify_repository(fingerprint)
            repositories.append(
                {
                    "root": str(root),
                    "repository": fingerprint.repository,
                    "revision": fingerprint.revision,
                    "status": "PASS",
                    "detected_profiles": list(selection.detected),
                    "suggested_profiles": list(selection.suggested),
                }
            )
        except (OSError, ValueError, SchemaValidationError) as exc:
            failures += 1
            repositories.append({"root": str(root), "status": "FAIL", "error": str(exc)})
    result = "PASS" if failures == 0 else "PARTIAL_FAILURE"
    _emit({"result": result, "repositories": repositories}, json_output=args.json)
    return EXIT_SUCCESS if failures == 0 else EXIT_PARTIAL_FAILURE


def _run_sync(args: argparse.Namespace) -> int:
    effective = _load_effective(args)
    artifacts = _compile_all(effective)
    evidence = validate_artifacts(effective, artifacts)
    branch_name = args.branch_name or f"chore/coderabbit-sync-{effective.resolution_digest[7:15]}"
    plan = SyncPlan(
        repository=effective.repository,
        base_branch=args.base_branch,
        expected_head=effective.revision,
        branch_name=branch_name,
        artifacts=tuple(artifacts),
        evidence=evidence,
        commit_message="chore: sync generated CodeRabbit policy",
        pull_request_title="chore: sync generated CodeRabbit policy",
        pull_request_body=(
            "Generated from validated CodeRabbit control-plane policy.\n\n"
            f"Evidence: `{evidence.run_id}`\n"
            f"Effective policy: `{effective.resolution_digest}`"
        ),
    )
    if not args.apply:
        _emit(
            {
                "mode": "dry-run",
                "repository": plan.repository,
                "base_branch": plan.base_branch,
                "expected_head": plan.expected_head,
                "branch_name": plan.branch_name,
                "files": [artifact.path for artifact in plan.artifacts],
                "evidence_run_id": plan.evidence.run_id,
            },
            json_output=args.json,
        )
        return EXIT_SUCCESS

    result = sync_repository(plan, GitHubRestClient.from_environment())
    _emit(result, json_output=args.json)
    return EXIT_SUCCESS


_HANDLERS = {
    "discover": _run_discover,
    "classify": _run_classify,
    "resolve": _run_resolve,
    "compile": _run_compile,
    "validate": _run_validate,
    "diff": _run_diff,
    "audit-fleet": _run_audit_fleet,
    "explain": _run_explain,
    "sync": _run_sync,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Run one deterministic CLI operation and return a stable process exit code."""
    parser = _build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        return _HANDLERS[args.command](args)
    except (SchemaValidationError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID_INPUT
    except (PolicyResolutionError, SecurityBoundaryError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_POLICY_REJECTED
    except (StaleRevisionError, ExternalRepositoryError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_STALE_STATE


if __name__ == "__main__":
    raise SystemExit(main())
