"""Generate ast-grep rules only for explicitly mechanical policies."""

from __future__ import annotations

from collections.abc import Mapping

import yaml

from coderabbit_control.errors import PolicyResolutionError
from coderabbit_control.models import EffectivePolicySet, PolicyDefinition

from . import GeneratedArtifact, hash_header


def _stable(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _stable(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    if isinstance(value, tuple):
        return [_stable(item) for item in value]
    return value


def _mechanical_rule(policy: PolicyDefinition) -> Mapping[str, object]:
    mechanical = policy.raw.get("mechanical") if isinstance(policy.raw, Mapping) else None
    ast_grep = mechanical.get("ast_grep") if isinstance(mechanical, Mapping) else None
    rule = ast_grep.get("rule") if isinstance(ast_grep, Mapping) else None
    if not isinstance(rule, Mapping):
        raise PolicyResolutionError(
            f"{policy.policy_id} declares ast-grep support without a mechanical rule"
        )
    return rule


def _config(policy: PolicyDefinition) -> dict[str, object]:
    source = _mechanical_rule(policy)
    for key in ("language", "rule", "message", "severity"):
        if key not in source:
            raise PolicyResolutionError(
                f"{policy.policy_id} ast-grep rule is missing required key: {key}"
            )
    config: dict[str, object] = {
        "id": policy.policy_id.replace(".", "-"),
        "language": source["language"],
    }
    if "files" in source:
        config["files"] = _stable(source["files"])
    config["rule"] = _stable(source["rule"])
    config["message"] = source["message"]
    config["severity"] = source["severity"]
    for key in sorted(set(source) - {"id", "language", "files", "rule", "message", "severity"}):
        config[str(key)] = _stable(source[key])
    return config


def compile_ast_grep(effective: EffectivePolicySet) -> list[GeneratedArtifact]:
    artifacts: list[GeneratedArtifact] = []
    for policy in sorted(effective.policies, key=lambda item: item.policy_id):
        requested = policy.targets.get("ast_grep", False)
        if not requested:
            continue
        if not policy.mechanical_ast_grep_supported:
            raise PolicyResolutionError(
                f"{policy.policy_id} requests ast-grep but mechanical detection is unsupported"
            )
        content = hash_header(effective) + yaml.safe_dump(
            _config(policy),
            sort_keys=False,
            allow_unicode=True,
            width=1000,
        )
        artifacts.append(
            GeneratedArtifact(
                path=f".ast-grep/rules/{policy.policy_id.replace('.', '-')}.yml",
                content=content,
                source_policy_ids=(policy.policy_id,),
            )
        )
    return artifacts
