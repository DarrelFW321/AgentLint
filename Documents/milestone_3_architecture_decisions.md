# Milestone 3 Architecture Decisions

Decision date: 2026-07-01

Status: finalized for Milestone 3 implementation.

This document records the resolved D3 decisions for Milestone 3. It supersedes brainstorming notes and should be treated as the implementation baseline for the YAML Policy DSL V1 build.

## Current State Evaluation

Milestone 2 completed the native trace model, trace loading, diagnostics model, and structural validation pass. The current policy package is still a placeholder:

```text
src/agentlint/policy/__init__.py
```

The current CLI validates native traces and structural diagnostics:

```text
agentlint validate TRACE.json
```

There are no policy models, loaders, examples, validation commands, policy diagnostics, or policy checks yet.

The important architectural constraint is that Milestone 3 must create the policy configuration surface without pulling in Milestone 4 enforcement or Milestone 5 reports.

## Research Basis

Local sources reviewed:

1. `Documents/requirements_specification.md`
2. `Documents/milestones.md`
3. `Documents/architecture.md`
4. `Documents/research_note.md`
5. `Documents/milestone_2_architecture_decisions.md`
6. `Documents/milestone_2_build_report.md`
7. `Documents/milestone_3_implementation_plan.md`
8. `src/agentlint/cli.py`
9. `src/agentlint/diagnostics/models.py`
10. `src/agentlint/ir/v1/models.py`
11. `src/agentlint/policy/__init__.py`

Primary implementation references reviewed:

1. PyYAML documentation: https://pyyaml.org/wiki/PyYAMLDocumentation
2. YAML 1.2.2 specification: https://yaml.org/spec/1.2.2/
3. Pydantic models documentation: https://docs.pydantic.dev/latest/concepts/models/
4. Typer subcommands documentation: https://typer.tiangolo.com/tutorial/subcommands/add-typer/
5. Python `StrEnum` documentation: https://docs.python.org/3/library/enum.html#enum.StrEnum

## Final Decision Summary

1. Milestone 3 implements policy definition and validation only.
2. Policy checks over traces begin in Milestone 4.
3. Policies use a versioned YAML DSL, loaded with a safe YAML loader.
4. Duplicate YAML mapping keys are rejected in Milestone 3.
5. Policy schema validation uses strict Pydantic models.
6. Policy severities and rule IDs are separate from diagnostic severities and diagnostic codes.
7. Policy load/schema errors are CLI input errors, not trace diagnostics.
8. The CLI gains `agentlint policy validate POLICY.yaml`.
9. `agentlint validate TRACE.json --policy POLICY.yaml` pre-validates the policy but does not run policy checks.

## ADR-001: Milestone 3 Scope Boundary

Decision:

Milestone 3 defines, loads, and validates YAML policies. It does not evaluate policies against traces.

Milestone 3 owns:

1. Policy models.
2. Policy YAML parsing.
3. Policy schema validation.
4. Policy-internal validation.
5. Policy examples.
6. Policy CLI validation.
7. Optional policy pre-validation in trace validation.

Milestone 3 does not own:

1. Unknown tool checks.
2. Unauthorized tool checks.
3. Approval checks.
4. Data-flow checks.
5. Provenance checks.
6. Report output.
7. CI threshold behavior.

Reasoning:

The current codebase has structural trace validation but no policy object. Enforcement before a stable policy schema would mix two different risks: language design and analysis semantics. Milestone 3 should stabilize the policy input contract first so Milestone 4 can focus on checks and diagnostics.

Consequences:

1. Tests in Milestone 3 should assert policy loading and validation behavior, not policy violation detection.
2. CLI help and output should avoid implying that policy checks run in Milestone 3.
3. Milestone 4 will map valid policy objects to trace diagnostics.

## ADR-002: Policy Package Ownership

Decision:

Policy models and loading live under `agentlint.policy`.

Expected package shape:

```text
src/agentlint/policy/
  __init__.py
  models.py
  loaders.py
```

Reasoning:

The architecture already reserves `policy/` for policy loading and evaluation. Milestone 3 should keep policy schema and loader code out of the CLI, IR, diagnostics, and passes packages.

Consequences:

1. The CLI orchestrates policy loading but does not own policy parsing.
2. Milestone 4 can add policy evaluation without moving model or loader code.
3. Future report emitters can consume the same policy model.

## ADR-003: YAML Loading And Duplicate Keys

Decision:

Use PyYAML with a safe loader base and reject duplicate YAML mapping keys.

Implementation direction:

1. Use PyYAML rather than adding a new YAML dependency.
2. Base loading on `yaml.SafeLoader` or `yaml.safe_load` semantics.
3. Add a local `UniqueKeySafeLoader` in `agentlint.policy.loaders`.
4. Reject duplicate mapping keys with a policy YAML error before Pydantic validation.

Reasoning:

PyYAML is already in project dependencies and is sufficient for the plain mapping/list/scalar shape needed by Milestone 3. PyYAML documentation warns that unrestricted `yaml.load` can construct arbitrary Python objects, while safe loading limits construction to simple Python objects. Policy files should use that safe loading behavior.

Duplicate mapping keys need stricter handling than the initial implementation plan proposed. Silent overwrites are dangerous in policy files because duplicated keys can change the apparent severity of a rule or replace a tool definition. Policy authors should not rely on duplicate-key behavior.

Consequences:

1. `PolicyYamlError` should cover malformed YAML and duplicate YAML keys.
2. Tests should include a duplicate-key fixture.
3. No new dependency such as `ruamel.yaml` is required in Milestone 3.
4. The loader should still reject empty YAML and top-level non-mapping YAML separately from malformed YAML.

## ADR-004: Versioned Strict Policy Schema

Decision:

Policy V1 uses a strict Pydantic model with:

```python
POLICY_VERSION = 1

class Policy(StrictPolicyModel):
    version: Literal[1]
    policy_id: PolicyName
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    tools: dict[PolicyName, ToolPolicy] = Field(default_factory=dict)
    sources: dict[PolicyName, SourcePolicy] = Field(default_factory=dict)
    sinks: dict[PolicyName, SinkPolicy] = Field(default_factory=dict)
    rules: dict[RuleId, PolicySeverity] = Field(default_factory=dict)
    exceptions: list[PolicyException] = Field(default_factory=list)
```

All policy models use `ConfigDict(extra="forbid")`.

Reasoning:

The project already uses Pydantic for IR and diagnostics. Pydantic model validation gives deterministic schema errors, stable enum serialization, and a path to generated JSON Schema later. Strict extra-field rejection is important because misspelled policy keys should not be silently ignored.

Consequences:

1. Unknown top-level or nested policy fields are schema errors.
2. Intentional extension fields go under `metadata`.
3. Policy tests should assert `model_dump(mode="json")` for stable enum string output.

## ADR-005: Policy Names And Keys

Decision:

Policy object identifiers and mapping keys should be non-empty strings after trimming whitespace, but Milestone 3 should not impose a narrow regex.

Affected values:

1. `policy_id`
2. Tool names.
3. Source names.
4. Sink names.
5. Argument names.
6. Exception IDs.
7. Exception match values.

Reasoning:

Trace adapters and tool ecosystems may use dotted names, slash-like names, provider-qualified names, or names that are inconvenient to predict now. A strict regex would likely create churn before the external-adapter milestone. Empty or whitespace-only names, however, are never meaningful.

Consequences:

1. Use a reusable constrained string type such as `PolicyName`.
2. Reject empty and whitespace-only names.
3. Do not parse dotted policy keys such as `web_search.query` in Milestone 3.

## ADR-006: Policy Enums

Decision:

Use policy-specific `StrEnum` classes.

Required enums:

```python
class ToolPermission(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"

class ApprovalRequirement(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"

class ToolRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"
    SECRET = "secret"

class TrustLevel(StrEnum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"

class SinkVisibility(StrEnum):
    MODEL = "model"
    INTERNAL = "internal"
    PRIVATE = "private"
    PUBLIC = "public"

class PolicySeverity(StrEnum):
    OFF = "off"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
```

Reasoning:

Python `StrEnum` gives named constants with string values. That matches the existing Milestone 2 diagnostic style and keeps YAML values readable.

Policy severity must remain separate from diagnostic severity because policy configuration needs `off`, while emitted diagnostics should continue to use `error`, `warning`, or `info`.

Consequences:

1. Do not reuse `agentlint.diagnostics.Severity` for policy configuration.
2. Invalid enum values are policy schema errors.
3. Policy severity is mapped to diagnostic severity only when Milestone 4 emits policy diagnostics.

## ADR-007: Rule IDs

Decision:

Milestone 3 defines the Milestone 4 rule catalog as policy rule IDs, but it does not add new diagnostic codes yet.

Rule IDs:

1. `unknown_tool`
2. `unauthorized_tool_call`
3. `disallowed_tool_argument`
4. `missing_approval`
5. `approval_after_action`
6. `action_after_denial`
7. `approval_mismatch`
8. `private_to_public_sink`
9. `secret_exposure`
10. `untrusted_to_privileged_action`
11. `sensitive_final_answer`
12. `unsupported_claim`
13. `invalid_provenance_reference`
14. `evidence_after_claim`

Reasoning:

Policies need stable names for rule severity configuration before checks exist. Diagnostic codes should wait until the checks emit concrete diagnostics; otherwise the diagnostics enum will imply behavior that is not implemented.

Consequences:

1. Add `RuleId(StrEnum)` under policy models.
2. Keep `DiagnosticCode` unchanged in Milestone 3.
3. Milestone 4 maps `RuleId` values to emitted diagnostic codes.

## ADR-008: Tool Policy Model

Decision:

Tool policy V1 should be shallow and practical:

```python
class ArgumentType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"

class ArgumentPolicy(StrictPolicyModel):
    required: bool = False
    allowed_types: list[ArgumentType] | None = None
    allowed_values: list[JsonValue] | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

class ToolPolicy(StrictPolicyModel):
    permission: ToolPermission = ToolPermission.ALLOWED
    approval: ApprovalRequirement = ApprovalRequirement.NOT_REQUIRED
    risk: ToolRisk = ToolRisk.LOW
    arguments: dict[PolicyName, ArgumentPolicy] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
```

Reasoning:

Milestone 4 needs enough configuration to check unknown tools, denied tools, approval requirements, and simple argument constraints. A full JSON Schema or expression language is too broad for V1. `allowed_types` and `allowed_values` cover useful early checks without committing to a full schema engine.

Consequences:

1. Unknown argument behavior remains deferred until Milestone 4.
2. Regex, numeric ranges, nested object schemas, conditional requirements, and custom expressions are out of scope.
3. Empty `allowed_types` or `allowed_values` lists should be rejected if the field is provided; use `None` to mean unconstrained.

## ADR-009: Source And Sink Policy Model

Decision:

Sources and sinks are named policy entries, not parsed expressions.

Model direction:

```python
class SourcePolicy(StrictPolicyModel):
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    trust: TrustLevel = TrustLevel.UNKNOWN
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

class SinkPolicy(StrictPolicyModel):
    visibility: SinkVisibility = SinkVisibility.INTERNAL
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
```

Reasoning:

The requirements call for source sensitivity, trust labels, sink visibility, and later data-flow checks. The full value graph remains deferred, so Milestone 3 should avoid pretending to bind source/sink names to trace values. Named entries give Milestone 4 enough vocabulary for explicit metadata and event-level checks.

Consequences:

1. Policy keys such as `gmail.read` and `web_search.query` remain opaque names.
2. No value nodes, labels, or propagation rules are added in Milestone 3.
3. Source/sink binding is a Milestone 4 analysis decision.

## ADR-010: Exceptions

Decision:

Milestone 3 models exceptions but does not evaluate them.

Model direction:

```python
class ExceptionMatch(StrictPolicyModel):
    tool: PolicyName | None = None
    source: PolicyName | None = None
    sink: PolicyName | None = None
    event: PolicyName | None = None

class PolicyException(StrictPolicyModel):
    id: PolicyName
    rules: list[RuleId] = Field(min_length=1)
    reason: str = Field(min_length=1)
    expires: str | None = None
    match: ExceptionMatch = Field(default_factory=ExceptionMatch)
```

Reasoning:

Project-specific exceptions are part of the requirements and are important for adoption. Their matching semantics depend on policy checks that do not exist yet. Milestone 3 should validate exception shape and uniqueness without applying exceptions to diagnostics.

Consequences:

1. Exception IDs must be unique within a policy.
2. `rules` must contain at least one rule.
3. `reason` is required and non-empty.
4. `expires` is a string in Milestone 3, documented as ISO 8601 but not date-parsed.
5. References inside `match` are not required to point to existing tools, sources, or sinks until Milestone 4.

## ADR-011: Policy-Internal Validation

Decision:

Milestone 3 should add lightweight model validators for policy-internal consistency.

Required checks:

1. Unique exception IDs.
2. Non-empty tool, source, sink, and argument keys.
3. Non-empty `allowed_types` if provided.
4. Non-empty `allowed_values` if provided.

Deferred checks:

1. Every exception match references an existing policy entry.
2. Every policy contains every rule ID.
3. Risk and approval consistency.
4. Rule coverage analysis.
5. Source/sink binding to trace metadata.

Reasoning:

Internal validation should catch authoring mistakes that can be judged from the policy alone. Binding and coverage checks require policy semantics that belong in Milestone 4 or later.

Consequences:

1. Use Pydantic field/model validators where they produce clear errors.
2. Keep validator messages policy-oriented and deterministic.
3. Tests should cover every policy-internal validation rule.

## ADR-012: Policy Errors Are Not Diagnostics

Decision:

Policy load, YAML, and schema errors are exceptions and CLI input errors, not `Diagnostic` objects.

Reasoning:

Milestone 2 diagnostics describe findings over parsed traces. A malformed policy is more like malformed JSON or trace schema failure: the input cannot proceed to analysis. Treating policy-load failures as diagnostics would blur the boundary before the report layer exists.

Consequences:

1. Add policy error classes under `agentlint.policy.loaders`.
2. Format policy validation errors with a policy-specific helper.
3. Do not add policy parse/load error codes to `DiagnosticCode`.

## ADR-013: CLI Policy Surface

Decision:

Add a `policy` command group and add optional policy pre-validation to trace validation.

Commands:

```text
agentlint policy validate POLICY.yaml
agentlint validate TRACE.json --policy POLICY.yaml
```

Behavior:

1. `agentlint policy validate` validates only the policy file.
2. `agentlint validate --policy` validates the policy before loading the trace.
3. Successful policy validation in `validate --policy` should print `valid policy: POLICY_ID`.
4. `validate --policy` should not run policy checks in Milestone 3.
5. Policy errors print to stderr and exit `1`.

Reasoning:

Typer supports nested command groups through sub-Typer applications. A `policy validate` command keeps policy validation discoverable without introducing the later `check` command prematurely.

Consequences:

1. Add a `policy_app = typer.Typer(...)`.
2. Register it with `app.add_typer(policy_app, name="policy")`.
3. Keep `agentlint validate` as the trace validation command.
4. Do not add `agentlint check`, `--format`, or `--fail-on` in Milestone 3.

## ADR-014: Example Policy Strategy

Decision:

Keep Milestone 3 policy examples flat under `examples/policies/`.

Required examples:

1. `customer_support.yaml`
2. `research.yaml`
3. `coding.yaml`
4. `invalid_schema.yaml`
5. `malformed.yaml`
6. `duplicate_key.yaml`

Reasoning:

The repo already has flat example directories for traces. A flat policy examples directory is enough for Milestone 3. Broader fixture corpus discipline and golden snapshots belong to Milestone 6.

Consequences:

1. Example policies should be synthetic but realistic.
2. Examples should provide vocabulary for Milestone 4 failure fixtures.
3. Invalid examples should target loader/schema behavior, not policy enforcement.

## ADR-015: Generated Policy Schema

Decision:

Do not commit generated JSON Schema for the policy DSL in Milestone 3.

Reasoning:

Generated schema will be useful for editor tooling and external consumers, but committing it now creates churn before policy semantics settle. Pydantic can generate schema when needed, and tests can assert selected schema properties without a checked-in artifact.

Consequences:

1. No `schemas/policy_v1.json` in Milestone 3.
2. Add schema export later when a concrete consumer exists.
3. Keep tests focused on model validation and selected schema properties.

## ADR-016: Deferred Policy Work

Decision:

Defer these items:

1. Policy enforcement over traces.
2. Full JSON Schema for tool arguments.
3. Rule condition language.
4. Policy preset packaging.
5. Policy coverage analysis.
6. Duplicate exception rule de-duplication beyond validating valid `RuleId` entries.
7. Expiration date parsing and enforcement.
8. Generated policy schema artifacts.
9. OPA/Rego integration.
10. Reports and CI thresholds.

Reasoning:

Milestone 3 is the policy input contract. These deferred items depend on enforcement, reports, adapter bindings, or maturing user-facing workflows.

## Implementation Checklist Impact

The Milestone 3 implementation plan should align to these decisions:

1. Add duplicate YAML key rejection to the loader.
2. Add a `duplicate_key.yaml` invalid fixture.
3. Include `ArgumentType` and `allowed_types` in argument policies.
4. Keep policy errors separate from trace diagnostics.
5. Keep `DiagnosticCode` unchanged until Milestone 4.
6. Keep `agentlint validate --policy` as pre-validation only.
