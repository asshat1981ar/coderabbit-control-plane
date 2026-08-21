"""Generate a policy-derived pull-request checklist."""

from __future__ import annotations

from coderabbit_control.models import EffectivePolicySet

from . import GeneratedArtifact, html_header, one_line


def compile_pull_request_template(effective: EffectivePolicySet) -> list[GeneratedArtifact]:
    selected = sorted(
        (
            policy
            for policy in effective.policies
            if policy.targets.get("pull_request_template", False)
        ),
        key=lambda item: item.policy_id,
    )
    lines = [html_header(effective).rstrip("\n"), "", "# Policy checklist", ""]
    lines.extend(
        f"- [ ] `{policy.policy_id}` — {one_line(policy.requirement)}" for policy in selected
    )
    content = "\n".join(lines) + "\n"
    return [
        GeneratedArtifact(
            path=".github/PULL_REQUEST_TEMPLATE.md",
            content=content,
            source_policy_ids=tuple(policy.policy_id for policy in selected),
        )
    ]
