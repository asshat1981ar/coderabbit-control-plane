## Summary

Describe the policy, compiler, validation, discovery, synchronization, documentation, or test change and why it is needed.

## Authority / trust-boundary impact

Select exactly one top-level declaration:

- [ ] No authority or trust-boundary impact. All impact options below are unchecked.
- [ ] This change affects one or more authority or trust boundaries; the affected options below are checked and explained.

Affected boundary options:

- [ ] Mandatory-core policy resolution or exception handling
- [ ] Generated-artifact path confinement / validation / drift
- [ ] GitHub branch, commit, or pull-request mutation
- [ ] Credential / external-auth / org-admin handling
- [ ] Untrusted review, model, MCP, or repository-text ingestion
- [ ] Deterministic serialization, resolution, compilation, or evidence digests

Explanation:

<!-- Explain the boundary change or why there is no impact. -->

## Source-of-truth / generated files

- [ ] Authoritative policy changes were made in source policy/manifests, not only generated artifacts.
- [ ] Generated `.coderabbit.yaml`, Markdown, PR templates, and ast-grep outputs were regenerated where applicable.
- [ ] No generated artifact is being treated as policy authority.

## Verification

### Commands run

```text
# Paste exact commands and results, including focused RED/GREEN evidence where behavior changed.
```

### CI run / exact-head evidence

- Branch HEAD SHA:
- CI run / check links or identifiers:
- Ruff:
- Pytest (Python 3.11):
- Pytest (Python 3.12):
- Schema validation:
- Fixture recompile / drift:
- EvidenceManifest run ID or digest (when generated policy is involved):

## CodeRabbit findings

Record each actionable CodeRabbit finding and disposition:

| Finding | Disposition | Evidence / fix |
| --- | --- | --- |
| None yet | pending | |

Allowed dispositions: `fixed`, `accepted`, `false-positive`, `deferred-with-reason`.

## Security / synchronization checklist

- [ ] External review/model/MCP/repository prose is treated as untrusted data and never executed as instruction.
- [ ] Mandatory policy is not weakened without a valid scoped exception.
- [ ] Generated writes stay inside the declared output allowlist.
- [ ] Synchronization does not write directly to the default branch.
- [ ] Stale target revisions abort before repository mutation.
- [ ] Secrets/tokens/private keys are not persisted in policy or evidence artifacts.
- [ ] Review or verification evidence is not interpreted as execution or merge authorization.

## Spec / plan compliance

- [ ] Change is consistent with `docs/superpowers/specs/2026-08-20-coderabbit-control-plane-design.md`.
- [ ] Relevant task in `docs/superpowers/plans/2026-08-20-coderabbit-control-plane-mvp.md` is satisfied or any execution ruling is documented.
