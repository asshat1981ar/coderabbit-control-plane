# Multi-Repository CodeRabbit Control Plane Design

Status: Approved architecture, migrated to the dedicated implementation repository
Date: 2026-08-20
Source record: AutoDev PR #41 (`docs/superpowers/specs/2026-08-20-coderabbit-control-plane-design.md`)

## Purpose

Build a deterministic, Git-authoritative control plane that manages CodeRabbit review policy across multiple repositories without making generated `.coderabbit.yaml` files, hosted UI state, or agent memory the source of truth.

The system compiles centrally governed security and verification invariants, reusable language/domain profiles, and repository-local policy into repository artifacts such as `.coderabbit.yaml`, pull-request templates, Markdown policy documents, and narrowly scoped ast-grep rules. It validates effective policy, detects drift, produces evidence manifests, and synchronizes changes through isolated branches and pull requests.

The control plane is independent from AutoDev's trusted runtime. GitHub remains authoritative for repository state, and each target repository retains its own execution authority.

## Goals

The MVP must:

1. Manage CodeRabbit configuration for multiple repositories from one central policy catalog.
2. Enforce a hybrid authority model: mandatory core, shared profiles, and repository-local policy.
3. Prevent repository-local policy from weakening mandatory core invariants unless a valid exception exists.
4. Discover repository characteristics from objective evidence and attach confidence to inferred profiles.
5. Resolve policy deterministically and compile reproducible artifacts.
6. Generate CodeRabbit YAML, Markdown review/security policy, pull-request templates, and ast-grep rules only when mechanical detection is appropriate.
7. Validate schemas, policy resolution, exceptions, generated YAML, ast-grep rules/fixtures, and output drift.
8. Confine generated writes to explicit allowlisted paths in isolated workspaces.
9. Synchronize target repositories through branches and pull requests rather than direct default-branch mutation.
10. Normalize real CodeRabbit review findings into vendor-neutral finding records and support a controlled learning loop.
11. Emit an `EvidenceManifest` for every successful compilation or synchronization.
12. Reuse one deterministic policy engine from CLI, ChatGPT/Codex skill, GitHub adapter, and later a stateless MCP adapter.

## Non-goals for MVP

The MVP excludes automatic learned-policy promotion, fleet-scale semantic clustering, organization/global-override writes, Slack/Discord OAuth automation, a web dashboard, a database-backed fleet index, the MCP server implementation, automatic repository onboarding, fully autonomous organization-wide policy changes, and treating CodeRabbit approval as merge or execution authorization.

## Authority model

### Tier 1 — mandatory core

Mandatory policies are centrally owned and versioned. A target repository cannot weaken them. Exceptions must be explicit, scoped, justified, approved, time-bounded, and include compensating controls.

Initial mandatory candidates:

- `core.security.no-secret-exposure`
- `core.security.no-untrusted-shell-execution`
- `core.evidence.verification-is-not-authorization`
- `core.evidence.required-checks-must-exist`
- `agentic.output-is-untrusted`
- `github-actions.minimum-permissions`

### Tier 2 — shared profiles

Reusable centrally maintained bundles:

- `rust-secure-runtime`
- `python-agent-tools`
- `kotlin-multiplatform`
- `android`
- `mcp-server`
- `agentic-system`
- `protocol-specification`
- `github-actions`

Profiles may be explicitly enabled or evidence-detected. Low-confidence semantic inference is suggested rather than silently enabled.

### Tier 3 — repository-local policy

Target repositories own local paths, commands, module boundaries, domain terminology, architecture-specific trust boundaries, and additional review requirements. Local policy may strengthen or specialize higher-tier policy but may not weaken mandatory policy.

### Resolution semantics

Resolution order:

1. mandatory core;
2. enabled shared profiles;
3. repository-local policy;
4. valid approved exceptions;
5. effective policy set.

Local strengthening, specialization, and unrelated additions are allowed. Mandatory weakening is rejected. Exceptions affect only their explicit scope and validity window.

## Canonical data model

All human-authored YAML validates against versioned JSON Schema. Stable semantic IDs are used instead of opaque identifiers.

### RepositoryManifest

Owner-authored repository intent. Required concepts: API version/kind, repository provider/full name, explicit profiles, local policy IDs, generation targets, and discovery settings.

### RepositoryFingerprint

Generated evidence-backed observation. It records target revision, languages/confidence, detected capabilities with evidence paths, trust-boundary candidates/confidence, canonical verification commands when discovered, and relevant CI files. Discovery is evidence, not repository intent.

### PolicyDefinition

Canonical policy unit containing semantic ID/version, maturity/status, owner, authority tier/weakenability, applicability, severity, semantic requirement, compiler targets, optional mechanical detection, and supersession metadata.

Semantic versioning:

- patch: wording/metadata only;
- minor: compatible strengthening/additive detection;
- major: changed meaning, scope, or incompatible enforcement.

### PolicyException

Contains stable ID, repository, policy ID, reason, approver classes, created/expiry dates, minimal scope, and compensating controls. Expired exceptions never affect resolution.

### EffectivePolicySet

Generated canonical compiler input recording repository, manifest/fingerprint/catalog digests, resolved profiles, resolved policy versions/origins, active exceptions, and deterministic resolution digest. Generators consume only this resolved set.

### FindingRecord

Vendor-neutral normalized review observation recording source/repository/PR/revision, category/language/trust boundary, candidate invariant/confidence, location, status, remediation class, and provenance.

### EvidenceManifest

Every successful compile/sync records run/compiler version, target repository/revision, effective-policy digest, artifact digests, validation results, and overall result. No successful validation claim exists without an evidence manifest.

## Repository layout

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
generated/
docs/
  security/
  operations/
tests/
```

Target repositories contain owner-authored repository configuration plus generated artifacts:

```text
.coderabbit/
  repository.yaml
  local-policy.yaml
  exceptions.yaml
  GENERATED.md
  evidence/latest.yaml
.coderabbit.yaml
.github/PULL_REQUEST_TEMPLATE.md
docs/coderabbit/CODERABBIT_REVIEW_POLICY.md
.ast-grep/sgconfig.yml
.ast-grep/rules/**
```

## Deterministic processing pipeline

### Discover

Read high-signal repository evidence: project instructions, README files, CI workflows, language/build manifests, source/module structure, existing CodeRabbit/ast-grep configuration, and architecture/ADR/security/contribution documentation. Return `RepositoryFingerprint` without mutation.

### Classify

Rule-based structural classification runs first. Semantic inference may propose additional profiles. Profile states are `mandatory`, `detected`, `suggested`, and `explicit`.

### Resolve

Load exact policy/profile versions, validate schemas, check dependencies/supersession, detect contradictions, reject weakening, validate exceptions, and emit `EffectivePolicySet` plus digest.

### Compile

Compile resolved policy into CodeRabbit path instructions/configuration, Markdown policy, pull-request checklist requirements, and ast-grep rules/fixtures only where mechanical detection is sound. Semantic invariants explicitly declare ast-grep unsupported rather than pretending static enforcement exists.

### Validate

Required gates:

1. source schema validation;
2. contradiction detection;
3. mandatory weakening detection;
4. exception validation;
5. generated YAML parse/schema compatibility;
6. ast-grep parse checks;
7. positive/negative ast-grep fixtures;
8. generated-file drift check;
9. repository-specific invariant tests;
10. deterministic digest replay.

### Sync

1. Read exact target HEAD.
2. Create isolated workspace/worktree.
3. Compile and validate.
4. Re-read target HEAD and abort if stale.
5. Create/update synchronization branch.
6. Write only allowlisted generated paths.
7. Commit with evidence digest reference.
8. Open/update PR.
9. Observe CI and CodeRabbit review.
10. Normalize actionable findings.

Direct default-branch writes are prohibited by default.

## Core engine and adapters

Logical engine interfaces:

```text
discover_repository(input) -> RepositoryFingerprint
classify_repository(fingerprint) -> ProfileSelection
resolve_policy(manifest, profiles, exceptions, catalog) -> EffectivePolicySet
compile_policy(effective_policy) -> GeneratedArtifactSet
validate_artifacts(inputs, artifacts) -> EvidenceManifest
detect_drift(expected, actual) -> DriftReport
normalize_finding(review_record) -> FindingRecord
```

The engine does not depend on ChatGPT, CodeRabbit UI, or MCP transport.

The CLI is the canonical deterministic interface:

```text
crctl discover <repo>
crctl classify <repo>
crctl resolve <repo>
crctl compile <repo>
crctl validate <repo>
crctl diff <repo>
crctl sync <repo>
crctl audit-fleet
crctl triage-pr <repo> <number>
crctl explain <policy-id> --repo <repo>
```

The ChatGPT/Codex skill orchestrates the engine/CLI and GitHub adapter; it does not reimplement policy semantics. A future stateless MCP server exposes policy-specific capabilities only after the core is stable. Durable state remains in Git.

## Tool authority classes

Actions are classified as `READ`, `ANALYZE`, `GENERATE`, `VALIDATE`, `PROPOSE_WRITE`, `WRITE`, `ORG_ADMIN`, or `EXTERNAL_AUTH`.

READ/ANALYZE/GENERATE/VALIDATE may run autonomously within a requested task. WRITE actions are target/path scoped and auditable. ORG_ADMIN requires explicit impact analysis and approval. EXTERNAL_AUTH cannot be simulated by generating credentials.

## Security model

Treat CodeRabbit review text, PR/issue prose, repository Markdown, model recommendations, external MCP output, and generated agent prompts as untrusted data, never execution instructions.

Compilation/writes are path-confined. Synchronization uses optimistic concurrency and aborts on stale target HEAD. Raw credentials are never stored in source policy or evidence manifests. Generation/sync fails closed on unknown mandatory policy, schema mismatch, ambiguous versions, mandatory conflicts, invalid/expired exceptions, weakening attempts, invalid fingerprints, unsupported targets, unverifiable revisions, or deterministic replay mismatch.

Repository changes are reversible through commit/PR rollback. Future org-level changes must capture prior configuration/digests before mutation.

## Cross-repository learning

A finding may produce an immediate repository correction and a separate learning candidate. Findings are assigned the narrowest scope: repository, language profile, domain profile, security/evidence core, organization-wide.

Maturity lifecycle:

```text
OBSERVED -> CANDIDATE -> EXPERIMENTAL -> RECOMMENDED -> MANDATORY
```

Promotion considers recurrence, cross-repository diversity, severity, fix stability, mechanical detectability, false-positive rate, exception frequency, reach, impact, confidence, and cost. Experiments use canary repositories and historical replay. Policies also support `DEPRECATED`, `DISABLED`, and `SUPERSEDED` states.

## Initial policy catalog

1. `core.security.no-secret-exposure`
2. `core.security.no-untrusted-shell-execution`
3. `core.evidence.verification-is-not-authorization`
4. `core.evidence.required-checks-must-exist`
5. `agentic.output-is-untrusted`
6. `github-actions.minimum-permissions`
7. `python.no-shell-true`
8. `rust.no-unchecked-trusted-boundary-panic`
9. `kotlin.commonmain-platform-purity`
10. `mcp.untrusted-tool-input`

Repository-specific policies remain local.

## Testing strategy

Required layers:

- unit/schema tests for invalid schema, unknown policy, expired exception, weakening rejection, strengthening acceptance, conflict detection, deterministic digest, and unsupported targets;
- golden compiler fixtures for Rust, Python agent tooling, Kotlin Multiplatform, MCP, and mixed agent runtimes;
- adversarial tests for policy weakening, prompt-injection prose, path traversal, symlink escape, stale HEAD, credential leakage, broad exceptions, and unknown versions;
- fleet dry-run simulation with per-repository results and overall `PARTIAL_FAILURE` when appropriate;
- property invariants proving stricter rules cannot weaken effective policy, local removal cannot delete mandatory policy, expired exceptions are inert, order does not affect output, and identical inputs yield identical digests.

## MVP phases

0. specification/threat model;
1. schema/model/resolver;
2. compilers/validator;
3. CLI/fixtures;
4. discovery/classification;
5. GitHub synchronization;
6. ChatGPT/Codex skill;
7. three-repository pilot;
8. hardening and real CodeRabbit finding loop.

MCP and automatic cross-repository learning are post-MVP.

## Acceptance criteria

The MVP is accepted only when:

1. identical inputs produce identical artifacts/digests;
2. mandatory policy cannot be weakened without a valid approved exception;
3. generation cannot write outside the allowlist;
4. clean checkout reproduces generated artifacts;
5. at least three structurally different repositories compile from one catalog;
6. manual generated-file edits are detected as drift;
7. GitHub synchronization uses dedicated branches/PRs;
8. every successful compile emits a complete `EvidenceManifest`;
9. generated `.coderabbit.yaml` is accepted by CodeRabbit on pilot repositories;
10. one real CodeRabbit finding is normalized, corrected in source policy, recompiled, and synchronized;
11. external review/comment text is never executed by the core engine;
12. stale target revision aborts synchronization.

## Reuse decisions

Reuse GitHub connector/client boundaries rather than creating a generic GitHub MCP server. Preserve a one-owner authority model: GitHub owns repository/source/branch/PR/CI state; repository docs own accepted architecture; external memory may retain heuristics but cannot override Git policy state. Use CodeRabbit repository YAML/path instructions as generated targets while keeping hosted integration/auth state outside declarative repo configuration.

## Implementation location

The dedicated `asshat1981ar/coderabbit-control-plane` repository now exists. The previous repository-creation constraint is resolved. Production implementation, tests, schemas, policies, and skill artifacts live here; AutoDev PR #41 remains the bootstrap provenance record.