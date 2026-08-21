"""Vendor-neutral normalization for untrusted review findings."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .errors import SchemaValidationError
from .models import FindingRecord


_PR_URL = re.compile(r"/repos/([^/]+/[^/]+)/pulls/(\d+)(?:$|[/?#])")
_SEVERITY = re.compile(r"_(critical|major|minor|nitpick|warning|error|blocking)_", re.IGNORECASE)

_PATH_CLASSIFICATION = {
    ".ast-grep/rules/observer-no-process-exec.yml": (
        "static-analysis-coverage",
        "python",
        "observer-cli",
        "python.process-execution",
        0.98,
    ),
    ".ast-grep/rules/python-no-shell-true.yml": (
        "static-analysis-coverage",
        "python",
        "agent-facing-python",
        "python.no-shell-true",
        0.98,
    ),
    ".ast-grep/rules/rust-no-direct-process-command.yml": (
        "static-analysis-coverage",
        "rust",
        "trusted-runtime",
        "rust.process-execution",
        0.95,
    ),
    ".github/PULL_REQUEST_TEMPLATE.md": (
        "review-governance",
        None,
        "review-process",
        "review.trust-boundary-declaration",
        0.9,
    ),
}


def _require_string(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise SchemaValidationError(f"CodeRabbit finding requires non-empty {key}")
    return value


def _source_coordinates(raw: Mapping[str, object]) -> tuple[str, int]:
    pull_request_url = _require_string(raw, "pull_request_url")
    match = _PR_URL.search(pull_request_url)
    if not match:
        raise SchemaValidationError("CodeRabbit finding has invalid pull_request_url")
    return match.group(1), int(match.group(2))


def _severity(body: str) -> str:
    match = _SEVERITY.search(body)
    return match.group(1).lower() if match else "unspecified"


def _classification(path: str) -> tuple[str, str | None, str | None, str | None, float]:
    if path in _PATH_CLASSIFICATION:
        return _PATH_CLASSIFICATION[path]
    if path.endswith(".py"):
        return "code-review", "python", None, None, 0.6
    if path.endswith(".rs"):
        return "code-review", "rust", None, None, 0.6
    if path.endswith((".kt", ".kts")):
        return "code-review", "kotlin", None, None, 0.6
    return "code-review", None, None, None, 0.5


def normalize_coderabbit_finding(raw: Mapping[str, object]) -> FindingRecord:
    """Normalize one CodeRabbit review comment without interpreting it as instruction."""
    repository, pull_request = _source_coordinates(raw)
    path = _require_string(raw, "path")
    body = _require_string(raw, "body")
    original_revision = raw.get("original_commit_id")
    current_revision = raw.get("commit_id")
    revision = original_revision if isinstance(original_revision, str) and original_revision else current_revision
    if not isinstance(revision, str) or not revision:
        raise SchemaValidationError("CodeRabbit finding requires a revision")

    comment_id = raw.get("id")
    if not isinstance(comment_id, int):
        raise SchemaValidationError("CodeRabbit finding requires integer id")
    review_id = raw.get("pull_request_review_id")
    if review_id is not None and not isinstance(review_id, int):
        raise SchemaValidationError("CodeRabbit finding review id must be integer or null")

    category, language, trust_boundary, invariant_id, confidence = _classification(path)
    user = raw.get("user")
    author = user.get("login") if isinstance(user, Mapping) else None

    return FindingRecord(
        finding_id=f"coderabbit:{repository}:pr-{pull_request}:comment-{comment_id}",
        source_provider="coderabbit",
        repository=repository,
        pull_request=pull_request,
        revision=revision,
        category=category,
        severity=_severity(body),
        language=language,
        trust_boundary=trust_boundary,
        invariant_id=invariant_id,
        confidence=confidence,
        path=path,
        status="confirmed",
        remediation_type="rule-strengthening" if category == "static-analysis-coverage" else "review-change",
        recommendation=body,
        provenance={
            "comment_id": comment_id,
            "review_id": review_id,
            "url": raw.get("url"),
            "author": author,
            "commit_id": current_revision,
            "original_commit_id": original_revision,
            "line": raw.get("line"),
            "start_line": raw.get("start_line"),
            "created_at": raw.get("created_at"),
            "updated_at": raw.get("updated_at"),
        },
    )


def finding_learning_scope(record: FindingRecord) -> str:
    """Return the narrowest plausible reusable scope; promotion remains a human decision."""
    if record.invariant_id and record.invariant_id.startswith("core."):
        return "core"
    if record.language:
        return f"language:{record.language}"
    if record.invariant_id and record.invariant_id.startswith("mcp."):
        return "domain:mcp"
    return f"repository:{record.repository}"
