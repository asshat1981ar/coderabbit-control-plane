from datetime import date
from pathlib import Path

from coderabbit_control.compiler.ast_grep import compile_ast_grep
from coderabbit_control.compiler.coderabbit import compile_coderabbit
from coderabbit_control.compiler.markdown import compile_markdown
from coderabbit_control.compiler.pull_request import compile_pull_request_template
from coderabbit_control.policy_loader import (
    load_profile_catalog,
    load_yaml_document,
    policy_definition_from_document,
    repository_fingerprint_from_document,
    repository_manifest_from_document,
)
from coderabbit_control.resolver import resolve_policy
from coderabbit_control.validation import validate_artifacts


ROOT = Path(__file__).resolve().parents[1]
PILOTS = {
    "autodev": "autodev.yaml",
    "aura-cli": "aura-cli.yaml",
    "markdown-control": "markdown-control.yaml",
}


def _catalog():
    policies = [
        policy_definition_from_document(load_yaml_document(path, "PolicyDefinition"))
        for path in sorted((ROOT / "policies").glob("**/*.yaml"))
    ]
    profiles = load_profile_catalog(ROOT / "profiles" / "catalog.yaml")
    return policies, profiles


def _compile(effective):
    artifacts = []
    artifacts.extend(compile_coderabbit(effective))
    artifacts.extend(compile_markdown(effective))
    artifacts.extend(compile_pull_request_template(effective))
    artifacts.extend(compile_ast_grep(effective))
    return tuple(sorted(artifacts, key=lambda item: item.path))


def test_three_structurally_distinct_pilots_resolve_compile_and_validate():
    catalog, profiles = _catalog()
    results = {}

    for name, filename in PILOTS.items():
        manifest = repository_manifest_from_document(
            load_yaml_document(ROOT / "repositories" / "pilots" / filename, "RepositoryManifest")
        )
        fingerprint = repository_fingerprint_from_document(
            load_yaml_document(
                ROOT / "repositories" / "fingerprints" / filename,
                "RepositoryFingerprint",
            )
        )
        effective = resolve_policy(
            manifest,
            fingerprint,
            catalog,
            profiles,
            [],
            as_of=date(2026, 8, 21),
        )
        artifacts = _compile(effective)
        evidence = validate_artifacts(effective, artifacts)
        results[name] = (manifest, effective, artifacts, evidence)

        assert evidence.result == "PASS"
        assert evidence.repository == manifest.full_name
        assert evidence.revision == fingerprint.revision
        assert artifacts
        assert any(item.path == ".coderabbit.yaml" for item in artifacts)
        assert evidence.artifact_digests

    profile_sets = {tuple(result[1].profiles) for result in results.values()}
    assert len(profile_sets) == 3
    assert len({result[1].catalog_digest for result in results.values()}) == 1


def test_pilot_evidence_snapshots_are_bound_to_specific_revisions():
    expected = {
        "autodev.yaml": "50ae85db97d2ba056ba7443dda353e41920df30c",
        "aura-cli.yaml": "72eb3e5ed67f64bed229c805221b33e729e20b9e",
        "markdown-control.yaml": "5b22d640903a008298bcffaf78a09ed016aa9d68",
    }
    for filename, revision in expected.items():
        fingerprint = repository_fingerprint_from_document(
            load_yaml_document(
                ROOT / "repositories" / "fingerprints" / filename,
                "RepositoryFingerprint",
            )
        )
        assert fingerprint.revision == revision
