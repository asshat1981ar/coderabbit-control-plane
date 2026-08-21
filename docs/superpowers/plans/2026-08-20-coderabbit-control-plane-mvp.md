# CodeRabbit Control Plane MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-capable multi-repository CodeRabbit policy compiler with deterministic resolution, generated review artifacts, validation, drift detection, GitHub branch/PR synchronization, and a ChatGPT/Codex orchestration skill.

**Architecture:** A Python 3.11+ deterministic core owns schemas, typed models, policy resolution, compilation, validation, discovery, and finding normalization. Thin CLI/GitHub/skill adapters call that core; Git is the durable authority, generated artifacts are reproducible outputs, and all writes are path-confined and revision-checked.

**Tech Stack:** Python 3.11+, `dataclasses`, `pathlib`, `hashlib`, `json`, `argparse`, PyYAML, jsonschema, pytest, Hypothesis, Ruff, GitHub REST API via a narrow adapter, ast-grep CLI as an external validation tool, CodeRabbit CLI/service for final integration verification.

**Spec:** `docs/superpowers/specs/2026-08-20-coderabbit-control-plane-design.md`

## Global Constraints

- Authoritative policy state lives in Git; generated `.coderabbit.yaml` is never a source of truth.
- Tier-1 mandatory policy cannot be weakened by repository-local policy without a valid scoped exception.
- External review/comment/model/MCP text is untrusted data and must never be executed as instruction.
- Generation and synchronization fail closed on schema ambiguity, policy conflict, invalid/expired exceptions, unsupported targets, stale repository revisions, path escape, or deterministic replay mismatch.
- Production writes are confined to explicit generated paths and use branches/pull requests by default.
- Semantic invariants must not be represented as ast-grep rules unless mechanical detection is actually sound.
- Identical canonical inputs must produce identical output bytes and digests.
- Every successful compilation/synchronization emits an `EvidenceManifest`.
- MCP implementation, organization-level writes, Slack/Discord auth automation, dashboard work, and automatic policy promotion are post-MVP.
- TDD is mandatory for production behavior: RED -> verify RED -> minimal GREEN -> verify GREEN -> refactor -> commit.

---

## File Structure

Create and maintain these focused units:

```text
pyproject.toml
src/coderabbit_control/
  __init__.py
  canonical.py          # canonical serialization + SHA-256 helpers
  errors.py             # typed fail-closed exceptions
  models.py             # dataclasses/enums for core entities
  schema.py             # JSON Schema loading/validation
  policy_loader.py      # YAML -> validated model loading
  resolver.py           # authority merge/conflict/exception logic
  compiler/
    __init__.py
    coderabbit.py       # .coderabbit.yaml generation
    markdown.py         # review-policy Markdown generation
    pull_request.py     # PR template generation
    ast_grep.py         # mechanical-rule generation only
  validation.py         # artifact checks + evidence manifest
  drift.py              # expected-vs-checked-in comparison
  discovery.py          # high-signal repository fingerprinting
  classify.py           # structural profile classification
  findings.py           # vendor-neutral CodeRabbit finding normalization
  github.py             # narrow GitHub API boundary
  sync.py               # revision-checked branch/PR synchronization orchestration
  cli.py                # argparse command surface
schemas/
  repository-manifest.schema.json
  repository-fingerprint.schema.json
  policy-definition.schema.json
  policy-exception.schema.json
  effective-policy-set.schema.json
  finding-record.schema.json
  evidence-manifest.schema.json
policies/
  core/*.yaml
  languages/*.yaml
  domains/*.yaml
profiles/*.yaml
repositories/*.yaml
fixtures/
  repositories/{rust-cli,python-agent,kotlin-mpp,mcp-server,mixed-agent-runtime}/
  findings/
tests/
  test_canonical.py
  test_schema.py
  test_policy_loader.py
  test_resolver.py
  test_compiler_coderabbit.py
  test_compiler_markdown.py
  test_compiler_pull_request.py
  test_compiler_ast_grep.py
  test_validation.py
  test_drift.py
  test_discovery.py
  test_classify.py
  test_findings.py
  test_sync.py
  test_cli.py
  test_properties.py
skills/coderabbit-control/SKILL.md
.github/workflows/ci.yml
.coderabbit.yaml
```

---

### Task 1: Python Package, Canonical Serialization, and Error Boundary

**Files:**
- Create: `pyproject.toml`
- Create: `src/coderabbit_control/__init__.py`
- Create: `src/coderabbit_control/canonical.py`
- Create: `src/coderabbit_control/errors.py`
- Create: `tests/test_canonical.py`

**Interfaces:**
- Produces: `canonical_json(value: object) -> str`
- Produces: `sha256_digest(value: object) -> str`
- Produces: `ControlPlaneError`, `SchemaValidationError`, `PolicyResolutionError`, `SecurityBoundaryError`, `StaleRevisionError`

- [ ] **Step 1: Add project metadata and test dependencies**

Create `pyproject.toml` with Python `>=3.11`, package discovery from `src`, runtime dependencies `PyYAML>=6,<7` and `jsonschema>=4.23,<5`, and dev dependencies `pytest>=8,<9`, `hypothesis>=6,<7`, `ruff>=0.12,<1`.

Expose:

```toml
[project.scripts]
crctl = "coderabbit_control.cli:main"
```

- [ ] **Step 2: Write the failing canonicalization tests**

```python
from coderabbit_control.canonical import canonical_json, sha256_digest


def test_canonical_json_is_key_order_independent():
    left = {"b": 2, "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert sha256_digest(left) == sha256_digest(right)


def test_canonical_json_uses_compact_utf8_stable_encoding():
    assert canonical_json({"z": "é", "a": 1}) == '{"a":1,"z":"é"}'
```

- [ ] **Step 3: Verify RED**

Run:

```bash
python -m pytest tests/test_canonical.py -q
```

Expected: FAIL because `coderabbit_control.canonical` does not exist.

- [ ] **Step 4: Implement minimal canonical serialization**

```python
import hashlib
import json


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_digest(value: object) -> str:
    data = canonical_json(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()
```

Create the typed exception hierarchy in `errors.py` with no side effects.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
python -m pytest tests/test_canonical.py -q
python -m ruff check src tests
```

Expected: PASS, 0 test failures, 0 Ruff errors.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/coderabbit_control tests/test_canonical.py
git commit -m "feat(core): add deterministic canonical serialization"
```

---

### Task 2: Versioned Schemas and Typed Core Models

**Files:**
- Create: `src/coderabbit_control/models.py`
- Create: `src/coderabbit_control/schema.py`
- Create: seven `schemas/*.schema.json` files listed above
- Create: `tests/test_schema.py`

**Interfaces:**
- Produces enums: `AuthorityTier`, `Severity`, `PolicyMaturity`, `ProfileStatus`
- Produces dataclasses: `RepositoryManifest`, `RepositoryFingerprint`, `PolicyDefinition`, `PolicyException`, `EffectivePolicySet`, `FindingRecord`, `EvidenceManifest`
- Produces: `validate_document(kind: str, payload: dict[str, object]) -> None`

- [ ] **Step 1: Write failing schema tests**

Test a valid `RepositoryManifest` and prove rejection of missing `repository.full_name`, unknown top-level fields, invalid confidence outside `0..1`, and an exception missing `expires` or compensating controls.

Example assertion:

```python
with pytest.raises(SchemaValidationError):
    validate_document("PolicyException", invalid_exception)
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python -m pytest tests/test_schema.py -q
```

Expected: FAIL because schemas/model loader are absent.

- [ ] **Step 3: Add strict JSON Schemas**

Use Draft 2020-12, set `additionalProperties: false` for control-plane-owned objects, and encode stable `apiVersion: coderabbit.control/v1` plus exact `kind` constants.

- [ ] **Step 4: Implement dataclasses and schema loader**

`schema.py` must load schemas relative to repository/package resources, instantiate `Draft202012Validator`, sort validation failures by JSON path, and raise one deterministic `SchemaValidationError` message.

- [ ] **Step 5: Verify GREEN**

```bash
python -m pytest tests/test_schema.py -q
python -m ruff check src tests
```

- [ ] **Step 6: Commit**

```bash
git add schemas src/coderabbit_control/models.py src/coderabbit_control/schema.py tests/test_schema.py
git commit -m "feat(schema): add versioned control-plane models"
```

---

### Task 3: YAML Policy Loading and Hybrid Authority Resolver

**Files:**
- Create: `src/coderabbit_control/policy_loader.py`
- Create: `src/coderabbit_control/resolver.py`
- Create initial YAML under `policies/core/`, `policies/languages/`, `policies/domains/`, `profiles/`
- Create: `tests/test_policy_loader.py`
- Create: `tests/test_resolver.py`

**Interfaces:**
- Produces: `load_yaml_document(path: Path, kind: str) -> dict[str, object]`
- Produces: `resolve_policy(manifest, fingerprint, catalog, profiles, exceptions, *, as_of: date) -> EffectivePolicySet`

- [ ] **Step 1: Write RED resolver tests for authority semantics**

Required cases:

```python
def test_local_policy_cannot_weaken_mandatory_core(): ...
def test_local_policy_can_strengthen_mandatory_core(): ...
def test_expired_exception_is_rejected(): ...
def test_scoped_valid_exception_affects_only_its_scope(): ...
def test_policy_input_order_does_not_change_resolution_digest(): ...
def test_unknown_mandatory_policy_fails_closed(): ...
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_policy_loader.py tests/test_resolver.py -q
```

Expected: FAIL on missing loader/resolver.

- [ ] **Step 3: Implement strict YAML loading**

Use `yaml.safe_load`; require a mapping root; validate immediately through `validate_document`; never instantiate Python objects from YAML tags.

- [ ] **Step 4: Implement deterministic merge rules**

Define effective severity ordering explicitly:

```python
SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2, "blocking": 3}
```

Reject a local rule if it lowers severity, removes a required target, broadens an exception, or changes a non-weakenable requirement incompatibly. Sort resolved policies by stable policy ID before digesting.

- [ ] **Step 5: Seed the initial ten policies**

Create the ten IDs from the design spec. For semantic-only policies set:

```yaml
mechanical:
  ast_grep:
    supported: false
```

Only `python.no-shell-true`, `kotlin.commonmain-platform-purity`, and clearly mechanical GitHub/Rust checks may advertise mechanical generation in MVP.

- [ ] **Step 6: Verify GREEN**

```bash
python -m pytest tests/test_policy_loader.py tests/test_resolver.py -q
python -m ruff check src tests
```

- [ ] **Step 7: Commit**

```bash
git add policies profiles src/coderabbit_control/policy_loader.py src/coderabbit_control/resolver.py tests/test_policy_loader.py tests/test_resolver.py
git commit -m "feat(policy): enforce hybrid authority resolution"
```

---

### Task 4: Deterministic Artifact Compilers

**Files:**
- Create: `src/coderabbit_control/compiler/__init__.py`
- Create: `src/coderabbit_control/compiler/coderabbit.py`
- Create: `src/coderabbit_control/compiler/markdown.py`
- Create: `src/coderabbit_control/compiler/pull_request.py`
- Create: `src/coderabbit_control/compiler/ast_grep.py`
- Create four compiler test files
- Create expected-output fixture directories

**Interfaces:**
- Produces: `GeneratedArtifact(path: str, content: str, source_policy_ids: tuple[str, ...])`
- Produces: `compile_coderabbit(effective) -> list[GeneratedArtifact]`
- Produces: `compile_markdown(effective) -> list[GeneratedArtifact]`
- Produces: `compile_pull_request_template(effective) -> list[GeneratedArtifact]`
- Produces: `compile_ast_grep(effective) -> list[GeneratedArtifact]`

- [ ] **Step 1: Write golden RED tests**

For a fixed effective-policy fixture, assert exact bytes for `.coderabbit.yaml`, policy Markdown, PR template, and a supported ast-grep rule.

Also assert semantic-only policies generate no ast-grep output.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_compiler_*.py -q
```

- [ ] **Step 3: Implement generated-file headers and stable ordering**

Headers must include compiler version and effective-policy digest but no wall-clock timestamp.

YAML output must use deterministic key ordering configured explicitly; lists must be sorted by stable semantic identity unless order is semantically meaningful.

- [ ] **Step 4: Implement compiler target gating**

If a policy requests ast-grep with `supported: false`, raise `PolicyResolutionError` instead of silently emitting a weak rule.

- [ ] **Step 5: Verify byte-for-byte GOLDEN output**

```bash
python -m pytest tests/test_compiler_*.py -q
```

Expected: PASS and unchanged golden files on a second run.

- [ ] **Step 6: Commit**

```bash
git add src/coderabbit_control/compiler tests/test_compiler_* fixtures
git commit -m "feat(compile): generate deterministic review artifacts"
```

---

### Task 5: Validation, Evidence Manifest, Path Confinement, and Drift

**Files:**
- Create: `src/coderabbit_control/validation.py`
- Create: `src/coderabbit_control/drift.py`
- Create: `tests/test_validation.py`
- Create: `tests/test_drift.py`

**Interfaces:**
- Produces: `validate_output_path(path: str, allowlist: tuple[str, ...]) -> None`
- Produces: `validate_artifacts(effective, artifacts, checked_in=None) -> EvidenceManifest`
- Produces: `detect_drift(expected, actual) -> DriftReport`

- [ ] **Step 1: Write adversarial RED tests**

Required tests:

```python
def test_parent_path_escape_is_rejected(): ...
def test_absolute_output_path_is_rejected(): ...
def test_secret_like_material_in_generated_output_fails_validation(): ...
def test_manual_generated_edit_is_reported_as_drift(): ...
def test_success_manifest_contains_all_artifact_digests(): ...
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_validation.py tests/test_drift.py -q
```

- [ ] **Step 3: Implement normalized path confinement**

Resolve repository-relative POSIX paths, reject absolute paths and `..` after normalization, and match only declared generated prefixes.

- [ ] **Step 4: Implement deterministic evidence output**

Evidence records contain source revision and digests, but generated manifest digest calculations exclude non-deterministic run timestamps. Operational timestamps may live in separate audit logs later.

- [ ] **Step 5: Verify GREEN**

```bash
python -m pytest tests/test_validation.py tests/test_drift.py -q
```

- [ ] **Step 6: Commit**

```bash
git add src/coderabbit_control/validation.py src/coderabbit_control/drift.py tests/test_validation.py tests/test_drift.py
git commit -m "feat(validation): add evidence and drift gates"
```

---

### Task 6: Evidence-Backed Repository Discovery and Profile Classification

**Files:**
- Create: `src/coderabbit_control/discovery.py`
- Create: `src/coderabbit_control/classify.py`
- Create five repository fixtures under `fixtures/repositories/`
- Create: `tests/test_discovery.py`
- Create: `tests/test_classify.py`

**Interfaces:**
- Produces: `discover_repository(root: Path, revision: str) -> RepositoryFingerprint`
- Produces: `classify_repository(fingerprint: RepositoryFingerprint) -> ProfileSelection`

- [ ] **Step 1: Write fixture-driven RED tests**

Prove structural evidence detects Rust from `Cargo.toml`, Kotlin MPP from `commonMain`, Android from Gradle/manifest evidence, MCP from explicit protocol/dependency evidence, and Python agent tooling from source/manifests.

Also prove unsupported semantic guesses are `suggested`, not `detected`.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_discovery.py tests/test_classify.py -q
```

- [ ] **Step 3: Implement high-signal discovery only**

Do not recursively ingest all repository text. Inspect known manifests, CI paths, agent instruction files, architecture/security docs, existing `.coderabbit.yaml`, and ast-grep config.

- [ ] **Step 4: Attach evidence references and confidence**

Any automatically activated profile must include at least one objective evidence path and confidence meeting the manifest threshold.

- [ ] **Step 5: Verify GREEN**

```bash
python -m pytest tests/test_discovery.py tests/test_classify.py -q
```

- [ ] **Step 6: Commit**

```bash
git add src/coderabbit_control/discovery.py src/coderabbit_control/classify.py fixtures/repositories tests/test_discovery.py tests/test_classify.py
git commit -m "feat(discovery): add evidence-backed repository profiles"
```

---

### Task 7: Canonical CLI

**Files:**
- Create: `src/coderabbit_control/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Produces commands: `discover`, `classify`, `resolve`, `compile`, `validate`, `diff`, `audit-fleet`, `explain`
- Defers mutating `sync` wiring until Task 9

- [ ] **Step 1: Write RED CLI tests**

Invoke `main([...])` directly rather than shelling out. Assert machine-readable `--json` output for `resolve`, non-zero exit on invalid policy, and dry-run fleet status `PARTIAL_FAILURE` when one fixture fails.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_cli.py -q
```

- [ ] **Step 3: Implement argparse command routing**

Every command maps to one core function. Keep formatting separate from policy semantics. Errors become stable exit codes:

```text
0 success
2 invalid user/config input
3 policy/security boundary rejection
4 stale/external repository state
5 partial fleet failure
```

- [ ] **Step 4: Verify installed CLI**

```bash
python -m pip install -e '.[dev]'
crctl --help
crctl audit-fleet --dry-run --json
python -m pytest tests/test_cli.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/coderabbit_control/cli.py tests/test_cli.py pyproject.toml
git commit -m "feat(cli): expose deterministic policy commands"
```

---

### Task 8: Finding Normalization and CodeRabbit Review Boundary

**Files:**
- Create: `src/coderabbit_control/findings.py`
- Create fixture: `fixtures/findings/coderabbit-pr40.json`
- Create: `tests/test_findings.py`

**Interfaces:**
- Produces: `normalize_coderabbit_finding(raw: Mapping[str, object]) -> FindingRecord`
- Produces: `finding_learning_scope(record: FindingRecord) -> str`

- [ ] **Step 1: Write RED tests using the real AutoDev PR #40 finding shape**

Assert normalization preserves source, repository, PR, revision, path, severity, recommendation summary, and provenance while treating the review body as opaque text.

- [ ] **Step 2: Add prompt-injection adversarial fixture**

The review text contains a fake shell command. Assert no subprocess/shell execution occurs and normalized output only stores the text.

- [ ] **Step 3: Verify RED**

```bash
python -m pytest tests/test_findings.py -q
```

- [ ] **Step 4: Implement normalization and narrow-scope classification**

Do not implement automatic promotion. Output only repository/language/domain/core candidate scope and confidence.

- [ ] **Step 5: Verify GREEN and commit**

```bash
python -m pytest tests/test_findings.py -q
git add src/coderabbit_control/findings.py fixtures/findings tests/test_findings.py
git commit -m "feat(findings): normalize CodeRabbit review evidence"
```

---

### Task 9: GitHub Adapter and Safe Synchronization

**Files:**
- Create: `src/coderabbit_control/github.py`
- Create: `src/coderabbit_control/sync.py`
- Create: `tests/test_sync.py`

**Interfaces:**
- Produces protocol: `GitHubRepositoryClient`
- Required methods: `get_head`, `create_branch`, `read_file`, `write_files`, `open_pull_request`
- Produces: `sync_repository(plan: SyncPlan, client: GitHubRepositoryClient) -> SyncResult`

- [ ] **Step 1: Write RED synchronization tests against an in-memory fake client**

Required behaviors:

```python
def test_sync_aborts_when_head_moves_after_compile(): ...
def test_sync_never_writes_default_branch(): ...
def test_sync_rejects_output_outside_allowlist(): ...
def test_sync_creates_branch_before_writing_files(): ...
def test_sync_opens_pr_only_after_validation_passes(): ...
```

The fake records calls; assertions verify behavior, not mock invocation internals alone.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_sync.py -q
```

- [ ] **Step 3: Implement orchestration with optimistic concurrency**

Read HEAD before discovery/compile and immediately before write. If SHAs differ, raise `StaleRevisionError` and perform zero writes.

- [ ] **Step 4: Implement the narrow REST adapter**

Keep HTTP/auth details inside `github.py`; no token enters policy models or evidence artifacts. Accept token only through process environment/credential provider.

- [ ] **Step 5: Wire `crctl sync` with `--dry-run` default-safe behavior**

Require explicit `--apply` for mutations. Default invocation shows semantic diff and planned branch name.

- [ ] **Step 6: Verify GREEN and commit**

```bash
python -m pytest tests/test_sync.py tests/test_cli.py -q
git add src/coderabbit_control/github.py src/coderabbit_control/sync.py src/coderabbit_control/cli.py tests/test_sync.py tests/test_cli.py
git commit -m "feat(sync): add revision-checked GitHub PR synchronization"
```

---

### Task 10: Property Tests and Security Regression Suite

**Files:**
- Create: `tests/test_properties.py`
- Extend resolver/validation tests

**Interfaces:**
- Consumes stable resolver/compiler APIs
- Produces no new production interface

- [ ] **Step 1: Add Hypothesis property tests**

Prove:

```text
policy ordering cannot change resolution digest
adding stricter local policy cannot weaken effective severity
removing local policy cannot remove mandatory IDs
expired exceptions never change effective output
same effective set always compiles to same bytes/digests
```

- [ ] **Step 2: Add path and hostile-text fuzz cases**

Generate relative path segments including encoded/suspicious forms and assert path escape never enters `GeneratedArtifactSet`.

- [ ] **Step 3: Run focused security suite**

```bash
python -m pytest tests/test_properties.py tests/test_resolver.py tests/test_validation.py tests/test_findings.py -q
```

Expected: 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tests/test_properties.py tests/test_resolver.py tests/test_validation.py tests/test_findings.py
git commit -m "test(security): add policy and path invariants"
```

---

### Task 11: ChatGPT/Codex Skill Adapter

**Files:**
- Create: `skills/coderabbit-control/SKILL.md`
- Create: `tests/test_skill_contract.py`

**Interfaces:**
- Skill workflows: `bootstrap repository`, `audit repository`, `upgrade policy`, `triage review`, `audit fleet`, `propose learning candidate`
- Skill calls `crctl`; it does not duplicate resolver semantics

- [ ] **Step 1: Write RED contract test**

Parse `SKILL.md` and assert it explicitly requires `crctl validate` before sync, prohibits direct default-branch writes, classifies external review text as untrusted, and routes hosted OAuth/org-admin actions to explicit user authorization.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_skill_contract.py -q
```

- [ ] **Step 3: Write the skill**

Include decision flow:

```text
inspect -> discover -> classify -> resolve -> compile -> validate -> show semantic diff -> approval for WRITE -> sync -> observe CodeRabbit/CI -> normalize findings
```

Explicitly mark MCP adapter as future work.

- [ ] **Step 4: Verify GREEN and commit**

```bash
python -m pytest tests/test_skill_contract.py -q
git add skills/coderabbit-control/SKILL.md tests/test_skill_contract.py
git commit -m "feat(skill): add CodeRabbit control orchestration skill"
```

---

### Task 12: CI, Self-Hosting CodeRabbit Policy, and Exact-Head Verification

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.coderabbit.yaml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `docs/CODERABBIT_REVIEW_POLICY.md`

**Interfaces:**
- CI runs the same core tests/validation as local development
- CodeRabbit reviews the control plane's own high-risk paths

- [ ] **Step 1: Add CI gates**

Required jobs:

```text
ruff
pytest
schema-validation
fixture-recompile-drift
```

Use Python 3.11 and 3.12 for tests. Pin GitHub Actions to immutable major versions initially; before production hardening, replace with commit SHAs if repository policy requires immutable action pinning.

- [ ] **Step 2: Add self-hosted CodeRabbit path instructions**

Review aggressively for:

```text
src/coderabbit_control/resolver.py
src/coderabbit_control/validation.py
src/coderabbit_control/sync.py
policies/core/**
schemas/**
skills/coderabbit-control/**
```

Instructions must reinforce authority non-weakening, path confinement, deterministic output, stale-head protection, and untrusted review text.

- [ ] **Step 3: Run complete local verification**

```bash
python -m ruff check src tests
python -m pytest -q
crctl audit-fleet --dry-run --json
crctl validate repositories/control-plane.yaml
```

Expected: all commands exit 0 except deliberately configured failing fixture commands used only in isolated tests.

- [ ] **Step 4: Commit and push an implementation branch**

```bash
git add .github .coderabbit.yaml docs/CODERABBIT_REVIEW_POLICY.md
git commit -m "ci: enforce control-plane verification gates"
git push -u origin <implementation-branch>
```

- [ ] **Step 5: Run CodeRabbit review**

```bash
coderabbit auth status --agent
coderabbit review --agent --base main -c .coderabbit.yaml
```

If CodeRabbit reports issues, normalize each actionable issue into a `FindingRecord`, fix through RED/GREEN where behavior changes, and rerun the review.

- [ ] **Step 6: Verify exact-head GitHub Actions**

Record final branch HEAD SHA and require all workflow jobs for that exact SHA to pass before claiming MVP slice completion.

---

### Task 13: Three-Repository Pilot and MVP Acceptance Harness

**Files:**
- Create manifests under `repositories/` for three structurally different pilot repositories
- Create: `tests/test_mvp_acceptance.py`
- Create: `docs/operations/pilot.md`

**Interfaces:**
- Produces one `EvidenceManifest` per pilot repository
- Produces fleet-level `PASS` or `PARTIAL_FAILURE`

- [ ] **Step 1: Write RED acceptance test**

Require three repository manifests to resolve and compile from the same catalog with distinct profile sets.

- [ ] **Step 2: Add pilot manifests**

Use:

```text
asshat1981ar/AutoDev
asshat1981ar/aura-cli
one simpler structurally distinct repository available to the authenticated GitHub account
```

If a named repository is unavailable at execution time, select another repository only after recording the substitution in `docs/operations/pilot.md`.

- [ ] **Step 3: Run dry-run fleet audit**

```bash
crctl audit-fleet --dry-run --json
```

Require each repo result to contain revision, profile selection, effective-policy digest, artifact digests, and drift status.

- [ ] **Step 4: Sync pilot PRs one repository at a time**

For each repository:

```bash
crctl sync <owner/repo> --apply
```

Confirm no default-branch direct mutation occurred.

- [ ] **Step 5: Verify CodeRabbit accepts generated config**

Observe the resulting PR's CodeRabbit status/review and confirm `.coderabbit.yaml` is parsed rather than rejected as invalid configuration.

- [ ] **Step 6: Close the real finding loop**

Take at least one actionable CodeRabbit issue from a pilot PR, normalize it into `FindingRecord`, change source policy/compiler logic, prove RED/GREEN, recompile, sync, and verify the issue no longer appears or is explicitly adjudicated.

- [ ] **Step 7: Run final acceptance suite**

```bash
python -m ruff check src tests
python -m pytest -q
crctl audit-fleet --dry-run --json
```

Then verify all twelve acceptance criteria from the design spec line-by-line and record evidence in `docs/operations/pilot.md`.

- [ ] **Step 8: Commit**

```bash
git add repositories tests/test_mvp_acceptance.py docs/operations/pilot.md
git commit -m "test(mvp): verify three-repository policy pilot"
```

---

## Plan Self-Review

### Spec coverage

- Hybrid authority/resolution: Tasks 2-3.
- Deterministic compilation: Tasks 1, 4, 10.
- CodeRabbit/Markdown/PR/ast-grep outputs: Task 4.
- Schema and exception validation: Tasks 2-3.
- Evidence manifests and drift: Task 5.
- Discovery/classification: Task 6.
- CLI: Task 7.
- Untrusted CodeRabbit findings: Task 8.
- GitHub branch/PR synchronization and stale-head protection: Task 9.
- Property/adversarial testing: Task 10.
- ChatGPT/Codex skill: Task 11.
- CI and CodeRabbit self-review: Task 12.
- Three-repository pilot and real review loop: Task 13.
- MCP/org-level writes/automatic promotion remain excluded as required.

### Placeholder scan

No implementation step depends on `TBD`, `TODO`, unspecified function names, or an undefined adjacent interface. Pilot repository substitution is explicitly constrained to runtime repository availability and requires recorded provenance.

### Type/interface consistency

The plan uses the same model names and core function boundaries throughout: `RepositoryManifest`, `RepositoryFingerprint`, `PolicyDefinition`, `PolicyException`, `EffectivePolicySet`, `FindingRecord`, `EvidenceManifest`, `resolve_policy`, `validate_artifacts`, `discover_repository`, and `sync_repository`.

## Execution Handoff

Implementation begins only after this plan is reviewed. The recommended execution mode is **Subagent-Driven Development** with one fresh worker per task and review gates between tasks. Inline execution remains available using the Superpowers executing-plans workflow.