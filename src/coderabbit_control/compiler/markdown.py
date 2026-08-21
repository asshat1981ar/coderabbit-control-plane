"""Generate human-readable review policy documentation."""

from __future__ import annotations

from coderabbit_control.models import EffectivePolicySet

from . import GeneratedArtifact, html_header, one_line


def compile_markdown(effective: EffectivePolicySet) -> list[GeneratedArtifact]:
    selected = sorted(
        (policy for policy in effective.policies if policy.targets.get("markdown", False)),
        key=lambda item: item.policy_id,
    )
    lines = [html_header(effective).rstrip("\n"), "", "# CodeRabbit Review Policy"]
    for policy in selected:
        lines.extend(
            [
                "",
                f"## `{policy.policy_id}`",
                "",
                f"- Severity: **{policy.severity.value}**",
                f"- Authority: **{policy.authority_tier.value}**",
                f"- Requirement: {one_line(policy.requirement)}",
            ]
        )
    content = "\n".join(lines) + "\n"
    return [
        GeneratedArtifact(
            path="docs/coderabbit/CODERABBIT_REVIEW_POLICY.md",
            content=content,
            source_policy_ids=tuple(policy.policy_id for policy in selected),
        )
    ]
