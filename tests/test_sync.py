from coderabbit_control.compiler import GeneratedArtifact
from coderabbit_control.errors import SecurityBoundaryError, StaleRevisionError
from coderabbit_control.models import EvidenceManifest
from coderabbit_control.sync import SyncPlan, sync_repository


class FakeGitHubClient:
    def __init__(self, *, head="abc123"):
        self.head = head
        self.calls = []

    def get_head(self, repository, branch):
        self.calls.append(("get_head", repository, branch))
        return self.head

    def create_branch(self, repository, branch, sha):
        self.calls.append(("create_branch", repository, branch, sha))

    def read_file(self, repository, path, ref):
        self.calls.append(("read_file", repository, path, ref))
        return None

    def write_files(self, repository, branch, files, message):
        self.calls.append(("write_files", repository, branch, tuple(sorted(files)), message))
        return "def456"

    def open_pull_request(self, repository, head, base, title, body):
        self.calls.append(("open_pull_request", repository, head, base, title))
        return 7


def evidence(*, result="PASS"):
    return EvidenceManifest(
        run_id="sha256:" + "1" * 64,
        compiler_version="0.1.0",
        repository="example/repo",
        revision="abc123",
        effective_policy_digest="sha256:" + "2" * 64,
        artifact_digests={".coderabbit.yaml": "sha256:" + "3" * 64},
        checks={"output_paths": "PASS", "secret_scan": "PASS", "drift": "SKIP"},
        result=result,
    )


def plan(*, branch="chore/coderabbit-sync", artifact_path=".coderabbit.yaml", validation="PASS"):
    return SyncPlan(
        repository="example/repo",
        base_branch="main",
        expected_head="abc123",
        branch_name=branch,
        artifacts=(GeneratedArtifact(artifact_path, "reviews: {}\n", ("core.test",)),),
        evidence=evidence(result=validation),
        commit_message="chore: sync CodeRabbit policy",
        pull_request_title="chore: sync CodeRabbit policy",
        pull_request_body="Generated from validated policy.",
    )


def test_sync_aborts_when_head_moves_after_compile():
    client = FakeGitHubClient(head="moved456")

    try:
        sync_repository(plan(), client)
    except StaleRevisionError:
        pass
    else:
        raise AssertionError("expected stale revision rejection")

    assert not any(call[0] in {"create_branch", "write_files", "open_pull_request"} for call in client.calls)


def test_sync_never_writes_default_branch():
    client = FakeGitHubClient()

    try:
        sync_repository(plan(branch="main"), client)
    except SecurityBoundaryError:
        pass
    else:
        raise AssertionError("expected default-branch rejection")

    assert not any(call[0] == "write_files" for call in client.calls)


def test_sync_rejects_output_outside_allowlist():
    client = FakeGitHubClient()

    try:
        sync_repository(plan(artifact_path="../escape.txt"), client)
    except SecurityBoundaryError:
        pass
    else:
        raise AssertionError("expected path confinement rejection")

    assert not any(call[0] == "write_files" for call in client.calls)


def test_sync_creates_branch_before_writing_files():
    client = FakeGitHubClient()
    result = sync_repository(plan(), client)

    names = [call[0] for call in client.calls]
    assert names.index("create_branch") < names.index("write_files")
    assert result.commit_sha == "def456"
    assert result.pull_request_number == 7


def test_sync_opens_pr_only_after_validation_passes():
    client = FakeGitHubClient()

    try:
        sync_repository(plan(validation="FAIL"), client)
    except SecurityBoundaryError:
        pass
    else:
        raise AssertionError("expected failed validation rejection")

    assert not any(call[0] == "open_pull_request" for call in client.calls)
