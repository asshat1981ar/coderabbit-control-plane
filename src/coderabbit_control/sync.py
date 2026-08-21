"""Revision-checked synchronization orchestration for generated policy artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from .compiler import GeneratedArtifact
from .errors import SecurityBoundaryError, StaleRevisionError
from .models import EvidenceManifest
from .validation import DEFAULT_GENERATED_ALLOWLIST, validate_output_path


class GitHubRepositoryClient(Protocol):
    def get_head(self, repository: str, branch: str) -> str: ...

    def create_branch(self, repository: str, branch: str, sha: str) -> None: ...

    def read_file(self, repository: str, path: str, ref: str) -> str | None: ...

    def write_files(
        self,
        repository: str,
        branch: str,
        files: Mapping[str, str],
        message: str,
    ) -> str: ...

    def open_pull_request(
        self,
        repository: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class SyncPlan:
    repository: str
    base_branch: str
    expected_head: str
    branch_name: str
    artifacts: Sequence[GeneratedArtifact]
    evidence: EvidenceManifest
    commit_message: str
    pull_request_title: str
    pull_request_body: str


@dataclass(frozen=True, slots=True)
class SyncResult:
    repository: str
    branch_name: str
    commit_sha: str
    pull_request_number: int
    evidence_run_id: str


def _validate_plan(plan: SyncPlan) -> dict[str, str]:
    if plan.branch_name == plan.base_branch:
        raise SecurityBoundaryError("synchronization branch must differ from default/base branch")
    if plan.evidence.result != "PASS":
        raise SecurityBoundaryError("synchronization requires passing validation evidence")
    if plan.evidence.repository != plan.repository:
        raise SecurityBoundaryError("evidence repository does not match synchronization target")
    if plan.evidence.revision != plan.expected_head:
        raise SecurityBoundaryError("evidence revision does not match synchronization target revision")

    files: dict[str, str] = {}
    for artifact in sorted(plan.artifacts, key=lambda item: item.path):
        validate_output_path(artifact.path, DEFAULT_GENERATED_ALLOWLIST)
        if artifact.path in files:
            raise SecurityBoundaryError(f"duplicate synchronization path: {artifact.path}")
        files[artifact.path] = artifact.content
    if not files:
        raise SecurityBoundaryError("synchronization has no generated artifacts")
    return files


def sync_repository(plan: SyncPlan, client: GitHubRepositoryClient) -> SyncResult:
    """Apply a validated artifact set through a dedicated branch and pull request."""
    files = _validate_plan(plan)

    current_head = client.get_head(plan.repository, plan.base_branch)
    if current_head != plan.expected_head:
        raise StaleRevisionError(
            f"target head moved: expected {plan.expected_head}, found {current_head}"
        )

    client.create_branch(plan.repository, plan.branch_name, plan.expected_head)
    commit_sha = client.write_files(
        plan.repository,
        plan.branch_name,
        files,
        plan.commit_message,
    )
    pull_request_number = client.open_pull_request(
        plan.repository,
        plan.branch_name,
        plan.base_branch,
        plan.pull_request_title,
        plan.pull_request_body,
    )
    return SyncResult(
        repository=plan.repository,
        branch_name=plan.branch_name,
        commit_sha=commit_sha,
        pull_request_number=pull_request_number,
        evidence_run_id=plan.evidence.run_id,
    )
