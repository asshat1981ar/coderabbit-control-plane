# MVP Three-Repository Pilot

## Purpose

This run validates that one central policy catalog can resolve and compile deterministic CodeRabbit artifacts for structurally different repositories without granting the control plane execution or merge authority.

## Pilot set

| Repository | Snapshot revision | Intent/profile basis |
| --- | --- | --- |
| `asshat1981ar/AutoDev` | `50ae85db97d2ba056ba7443dda353e41920df30c` | Mixed agentic runtime with Rust trusted kernel, Kotlin Multiplatform/Android surfaces, MCP/control-plane components, protocol material, and GitHub Actions. |
| `asshat1981ar/aura-cli` | `72eb3e5ed67f64bed229c805221b33e729e20b9e` | Python autonomous software-development platform explicitly described as a multi-agent loop, with GitHub Actions. |
| `asshat1981ar/nextjs-geist-font-starter` | `5b22d640903a008298bcffaf78a09ed016aa9d68` | Deliberately minimal control repository; its current main branch contains only a Markdown guide, so no shared language/domain profile is explicitly enabled. |

The third repository is the permitted runtime-selected structurally distinct repository from the plan. No named repository was replaced: the plan names AutoDev and aura-cli and intentionally leaves the third slot open.

## Evidence model

Pilot intent is stored in `repositories/pilots/*.yaml`. Repository observations are separate `RepositoryFingerprint` snapshots in `repositories/fingerprints/*.yaml`. Each snapshot is bound to an exact Git revision. If a remote default branch moves before synchronization, the stale-head gate must abort and the fingerprint must be regenerated rather than silently retargeted.

The snapshots are evidence, not repository intent and not execution authority.

## Acceptance sequence

1. Validate all pilot manifests and fingerprints against the versioned schemas.
2. Resolve all three from the same policy catalog and profile catalog.
3. Compile CodeRabbit, Markdown, PR-template, and mechanically supported ast-grep artifacts.
4. Validate each artifact set and emit one `EvidenceManifest` per repository.
5. Run fleet dry-run and record revision, selected profiles, effective-policy digest, artifact digests, and drift state for every pilot.
6. Re-read each remote default-branch HEAD immediately before synchronization. Any mismatch with the snapshot is `STALE` and causes zero writes.
7. Synchronize one repository at a time through a dedicated branch and pull request; never mutate the default branch directly.
8. Observe CodeRabbit parsing/review on each pilot PR and normalize any actionable finding before remediation.
9. Close at least one real finding loop through source-policy/compiler change, RED/GREEN verification, recompile, and resynchronization.
10. Run final full Ruff/pytest/fleet verification and adjudicate all twelve MVP acceptance criteria.

## Current execution record

- Pilot selection: complete.
- Revision-bound fingerprints: complete.
- Deterministic acceptance harness: added in `tests/test_mvp_acceptance.py`.
- Fleet dry-run: pending enhanced fleet report implementation and exact-head CI.
- Pilot synchronization PRs: pending pre-sync stale-head verification and passing control-plane CI.
- CodeRabbit compatibility on generated pilot configs: pending pilot PRs.
- Real finding closure loop: pending pilot review.
- Merge authorization: not granted; no pilot or control-plane PR may be merged by this workflow.

## Execution ruling

The Task 12 example `crctl validate repositories/control-plane.yaml` conflicts with the typed CLI implemented in Task 7, which requires a manifest, a generated fingerprint, and an evaluation date. The binding typed workflow is therefore:

```bash
crctl discover . --revision "$GITHUB_SHA" --json > /tmp/control-plane-fingerprint.json
crctl validate \
  --manifest repositories/control-plane.yaml \
  --fingerprint /tmp/control-plane-fingerprint.json \
  --as-of "$(date -u +%F)" \
  --json
```

This preserves the design distinction between owner-authored repository intent and generated revision-bound observations.
