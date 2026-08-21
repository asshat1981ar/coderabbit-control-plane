"""Generate repository CodeRabbit YAML from an effective policy set."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable

from coderabbit_control.errors import PolicyResolutionError
from coderabbit_control.models import EffectivePolicySet, PolicyDefinition

from . import GeneratedArtifact, hash_header, one_line


def _paths(policy: PolicyDefinition) -> tuple[str, ...]:
    raw = policy.applicability.get("paths")
    if raw is None:
        return ("**/*",)
    if not isinstance(raw, (list, tuple)) or not raw:
        raise PolicyResolutionError(f"{policy.policy_id} has invalid applicability paths")
    paths = tuple(sorted({str(item) for item in raw if str(item)}))
    if not paths:
        raise PolicyResolutionError(f"{policy.policy_id} has empty applicability paths")
    return paths


def _instruction_lines(policies: Iterable[PolicyDefinition]) -> list[str]:
    return [
        f"{policy.policy_id} [{policy.severity.value}]: {one_line(policy.requirement)}"
        for policy in sorted(policies, key=lambda item: item.policy_id)
    ]


def compile_coderabbit(effective: EffectivePolicySet) -> list[GeneratedArtifact]:
    selected = sorted(
        (policy for policy in effective.policies if policy.targets.get("coderabbit", False)),
        key=lambda item: item.policy_id,
    )
    groups: dict[str, list[PolicyDefinition]] = defaultdict(list)
    for policy in selected:
        for path in _paths(policy):
            groups[path].append(policy)

    lines = [
        hash_header(effective).rstrip("\n"),
        "# yaml-language-server: $schema=https://coderabbit.ai/integrations/schema.v2.json",
        "",
        "reviews:",
    ]
    if not groups:
        lines.append("  path_instructions: []")
    else:
        lines.append("  path_instructions:")
        for path in sorted(groups):
            lines.append(f"    - path: {json.dumps(path, ensure_ascii=False)}")
            lines.append("      instructions: |")
            lines.extend(f"        {line}" for line in _instruction_lines(groups[path]))

    content = "\n".join(lines) + "\n"
    return [
        GeneratedArtifact(
            path=".coderabbit.yaml",
            content=content,
            source_policy_ids=tuple(policy.policy_id for policy in selected),
        )
    ]
