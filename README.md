# CodeRabbit Control Plane

A multi-repository, Git-authoritative policy compiler and orchestration layer for managing CodeRabbit review configuration consistently across repositories.

## Purpose

The project centralizes mandatory security and verification invariants, reusable language/domain profiles, and repository-local policy while keeping generated `.coderabbit.yaml` files as build artifacts rather than sources of truth.

The control plane is designed to:

- discover repository characteristics from objective evidence;
- resolve mandatory, shared, and repository-local policy deterministically;
- compile CodeRabbit YAML, Markdown policy documents, pull-request templates, and ast-grep rules where mechanical enforcement is appropriate;
- validate policy, exceptions, generated artifacts, and drift;
- synchronize changes through isolated branches and pull requests;
- emit reproducible evidence manifests for successful compile and sync operations;
- normalize CodeRabbit review findings into vendor-neutral learning records without automatically promoting them to global policy.

## Authority model

The system uses a hybrid authority model:

1. **Mandatory core** — centrally owned security and verification invariants that repositories cannot weaken without a valid, scoped, expiring exception.
2. **Shared profiles** — reusable policy bundles for ecosystems such as Rust, Python, Kotlin Multiplatform, MCP, Android, agentic systems, and GitHub Actions.
3. **Repository-local policy** — project-specific paths, trust boundaries, terminology, verification commands, and additional review requirements.

Authoritative state lives in Git. Generated CodeRabbit configuration, hosted UI state, agent memory, and review comments are not authoritative policy sources.

## Planned architecture

The deterministic core policy engine will be shared by thin adapters:

```text
CLI ───────────────┐
ChatGPT/Codex skill├──> Policy Engine ──> Validation ──> EvidenceManifest
GitHub adapter ────┘                         │
                                             └──> branch / pull-request sync

Future stateless MCP adapter ────────────────> same Policy Engine
```

The future MCP surface will expose policy-specific tools rather than duplicating a generic GitHub API server.

## Planned repository layout

```text
policies/
  core/
  languages/
  domains/
profiles/
repositories/
schemas/
fixtures/
  repositories/
  findings/
src/
  coderabbit_control/
skills/
  coderabbit-control/
docs/
  security/
  operations/
tests/
```

## MVP scope

The MVP includes versioned schemas, repository manifests, policy definitions and exceptions, deterministic policy resolution, CodeRabbit/Markdown/PR-template/basic ast-grep compilers, validation, CLI operations, GitHub synchronization, dry-run discovery, multi-repository manifests, evidence manifests, drift detection, and an initial ChatGPT/Codex skill.

The MVP intentionally excludes autonomous global policy promotion, organization-level CodeRabbit writes, Slack/Discord OAuth automation, a web dashboard, database-backed fleet indexing, and the MCP adapter implementation.

## Development principles

- Same inputs must produce the same policy resolution and generated artifact digests.
- Mandatory policy fails closed on ambiguity, invalid exceptions, conflicts, stale revisions, or weakening attempts.
- External review text, repository prose, and model output are untrusted data and must never become executable instructions.
- Generated writes are path-confined and synchronized through branches and pull requests by default.
- Semantic invariants must not be misrepresented as AST-enforceable rules.
- Successful validation claims require an `EvidenceManifest`.

## Design source

The approved architecture was developed in the AutoDev project and formalized in:

`docs/superpowers/specs/2026-08-20-coderabbit-control-plane-design.md`

The implementation plan and production source will live in this repository.

## Status

Bootstrap repository. The next milestone is the formal implementation plan followed by schema/resolver development using test-driven development and exact-head verification.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
