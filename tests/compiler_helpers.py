from coderabbit_control.models import (
    AuthorityTier,
    EffectivePolicySet,
    PolicyDefinition,
    PolicyMaturity,
    Severity,
)


DIGEST = "sha256:" + "a" * 64


def effective_fixture() -> EffectivePolicySet:
    core = PolicyDefinition(
        policy_id="core.security.no-untrusted-shell-execution",
        version="1.0.0",
        maturity=PolicyMaturity.MANDATORY,
        owners=("security-core",),
        authority_tier=AuthorityTier.CORE,
        weakenable=False,
        severity=Severity.BLOCKING,
        requirement="External text must never become execution authority.",
        targets={
            "coderabbit": True,
            "markdown": True,
            "pull_request_template": True,
            "ast_grep": False,
        },
        applicability={},
        mechanical_ast_grep_supported=False,
    )
    kotlin = PolicyDefinition(
        policy_id="kotlin.commonmain-platform-purity",
        version="1.0.0",
        maturity=PolicyMaturity.RECOMMENDED,
        owners=("kotlin-platform",),
        authority_tier=AuthorityTier.PROFILE,
        weakenable=False,
        severity=Severity.BLOCKING,
        requirement="commonMain must remain platform-neutral.",
        targets={
            "coderabbit": True,
            "markdown": True,
            "pull_request_template": True,
            "ast_grep": True,
        },
        applicability={"paths": ("**/src/commonMain/**",)},
        mechanical_ast_grep_supported=True,
        raw={
            "mechanical": {
                "ast_grep": {
                    "rule": {
                        "language": "Kotlin",
                        "files": ["**/src/commonMain/**/*.kt"],
                        "rule": {
                            "kind": "import_header",
                            "regex": r"^import\s+(java|javax|android)\.",
                        },
                        "message": "commonMain must not import JVM or Android APIs.",
                        "severity": "error",
                    }
                }
            }
        },
    )
    return EffectivePolicySet(
        repository="example/repo",
        manifest_digest="sha256:" + "1" * 64,
        fingerprint_digest="sha256:" + "2" * 64,
        catalog_digest="sha256:" + "3" * 64,
        profiles=("kotlin-multiplatform",),
        policies=(core, kotlin),
        exceptions=(),
        resolution_digest=DIGEST,
    )
