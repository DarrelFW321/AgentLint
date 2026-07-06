# Milestone 3 Implementation Plan

Status: implemented.

Milestone 3 defines the first AgentLint policy format. It should make policies loadable, validated, versioned, documented by examples, and usable from the CLI. It should not yet evaluate policies against traces; that belongs to Milestone 4.

## Objective

Implement YAML Policy DSL V1.

Milestone 3 is complete when:

1. AgentLint has a versioned YAML policy schema.
2. AgentLint can safely load and validate policy YAML files.
3. Policy load, parse, and schema errors are distinct from trace schema errors and trace diagnostics.
4. The CLI can validate example policies.
5. The CLI can optionally validate a policy before trace structural validation.
6. Example policies exist for customer-support, research, and coding agents.
7. Unit, loader, fixture, and CLI tests cover the policy surface.

## Current Baseline

Milestone 2 implemented:

1. Native AgentLint IR v1 models and loader.
2. Structural validation diagnostics.
3. Diagnostic model and lightweight terminal formatting.
4. `agentlint validate TRACE.json` for schema and structural validation.

The policy package exists only as a placeholder:

```text
src/agentlint/policy/__init__.py
```

The examples policy directory exists but has no real policy fixtures:

```text
examples/policies/.gitkeep
```

## Finalized Scope

Milestone 3 should implement:

1. Policy models.
2. Policy YAML loading.
3. Policy schema validation.
4. Policy error formatting.
5. CLI policy validation.
6. Optional policy pre-validation in trace validation.
7. Example policies.
8. Focused tests.
9. Documentation updates.

Milestone 3 should not implement:

1. Tool authorization checks.
2. Approval checks.
3. Data-flow checks.
4. Provenance checks.
5. Report output.
6. JSON report schema.
7. CI `--fail-on` behavior.
8. Multiple trace validation.
9. Policy presets as installed package data.
10. OPA/Rego integration.
11. Runtime gating.
12. Full value graph modeling.

## Reevaluated Decisions

### D3.1 Policy YAML Loader

Decision:

Use PyYAML with `yaml.safe_load`.

Reasoning:

PyYAML is already a project dependency, and Milestone 3 only needs ordinary YAML mappings, sequences, strings, numbers, and booleans. `safe_load` avoids arbitrary Python object construction and is sufficient for policy configuration.

Implementation consequence:

Create:

```text
src/agentlint/policy/loaders.py
```

With:

```python
class PolicyLoadError(Exception): ...
class PolicyFileError(PolicyLoadError): ...
class PolicyYamlError(PolicyLoadError): ...
class PolicySchemaError(PolicyLoadError): ...

def load_policy(path: str | Path) -> Policy: ...
def format_policy_validation_error(error: ValidationError) -> list[str]: ...
```

Policy loading should reject:

1. Missing files.
2. Directories.
3. Malformed YAML.
4. Duplicate YAML mapping keys.
5. Empty YAML documents.
6. Top-level YAML values that are not mappings.
7. Schema-invalid policy objects.

### D3.2 Versioned Policy Model

Decision:

Use a strict Pydantic model with `version: Literal[1]`.

Reasoning:

The IR and diagnostics are already Pydantic-backed. Using Pydantic for policies gives consistent schema validation, predictable errors, and a natural path to future JSON schema export.

Implementation consequence:

Create:

```text
src/agentlint/policy/models.py
```

With:

```python
POLICY_VERSION = 1

class Policy(BaseModel):
    version: Literal[1]
    policy_id: str
    metadata: dict[str, JsonValue]
    tools: dict[str, ToolPolicy]
    sources: dict[str, SourcePolicy]
    sinks: dict[str, SinkPolicy]
    rules: dict[RuleId, PolicySeverity]
    exceptions: list[PolicyException]
```

All policy models should use `extra="forbid"` by default. Explicit extension points should be represented through `metadata`, not arbitrary unknown top-level keys.

### D3.3 Policy Enums

Decision:

Define policy-specific `StrEnum` classes instead of overloading existing diagnostic enums.

Reasoning:

Diagnostic severity currently has `error`, `warning`, and `info`. Policy rule configuration also needs `off` so teams can define gradual adoption policies. Keeping policy severity separate avoids weakening diagnostic severity semantics.

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

### D3.4 Rule IDs

Decision:

Milestone 3 should define rule IDs needed by Milestone 4, but it should not implement the checks.

Reasoning:

Policies need to validate before policy checks exist. Defining rule IDs now lets example policies and CLI validation stabilize before Milestone 4 uses them.

Initial rule IDs:

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

Implementation consequence:

Use:

```python
class RuleId(StrEnum):
    UNKNOWN_TOOL = "unknown_tool"
    ...
```

Policy YAML should use lower snake-case string values.

### D3.5 Minimal Tool Argument Policy

Decision:

Include a small argument-policy model in Milestone 3, but keep it intentionally simple.

Reasoning:

Milestone 4 includes `DISALLOWED_TOOL_ARGUMENT`, so policies need somewhere to express argument constraints. A full schema language is too much for Milestone 3.

Implementation consequence:

Add:

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
```

And:

```python
class ToolPolicy(StrictPolicyModel):
    permission: ToolPermission = ToolPermission.ALLOWED
    approval: ApprovalRequirement = ApprovalRequirement.NOT_REQUIRED
    risk: ToolRisk = ToolRisk.LOW
    arguments: dict[str, ArgumentPolicy] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
```

Do not add regex matching, numeric ranges, nested JSON schemas, or custom expression logic yet.

### D3.6 Source And Sink Policies

Decision:

Represent sources and sinks by stable names that can later match tool endpoints, event metadata, adapter metadata, or value labels.

Reasoning:

The full value graph is deferred, but Milestone 4 needs enough policy vocabulary to start simple source/sink checks over explicit metadata and event-level relationships.

Implementation consequence:

Add:

```python
class SourcePolicy(StrictPolicyModel):
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    trust: TrustLevel = TrustLevel.UNKNOWN
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

class SinkPolicy(StrictPolicyModel):
    visibility: SinkVisibility = SinkVisibility.INTERNAL
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
```

Policy keys such as `gmail.read` or `web_search.query` are names, not parsed expressions in Milestone 3.

### D3.7 Exceptions

Decision:

Model exceptions as structured policy entries, but do not evaluate them until Milestone 4.

Reasoning:

Exceptions are a requirement for policy adoption, but exception matching depends on checks that do not exist yet. The schema can validate exception shape now without implementing behavior.

Implementation consequence:

Add:

```python
class ExceptionMatch(StrictPolicyModel):
    tool: str | None = None
    source: str | None = None
    sink: str | None = None
    event: str | None = None

class PolicyException(StrictPolicyModel):
    id: str
    rules: list[RuleId]
    reason: str
    expires: str | None = None
    match: ExceptionMatch = Field(default_factory=ExceptionMatch)
```

Validation rules:

1. `id` and `reason` must be non-empty.
2. `rules` must contain at least one rule.
3. `expires` remains a string in Milestone 3. Document it as ISO 8601, but do not enforce date semantics yet.

### D3.8 Duplicate Key Handling

Decision:

Reject duplicate YAML mapping keys in the Milestone 3 policy loader.

Reasoning:

PyYAML normally overwrites duplicate mapping keys. That behavior is too risky for policy files because duplicate keys can silently replace tool definitions or rule severities. A small SafeLoader subclass can reject duplicates without adding a new YAML dependency.

Implementation consequence:

Create a policy YAML loader that preserves safe-loading behavior and raises `PolicyYamlError` for duplicate mapping keys. Add a `duplicate_key.yaml` fixture and loader test.

### D3.9 Policy Semantic Checks

Decision:

Add only lightweight policy-internal validation in Milestone 3.

Required semantic checks:

1. Exception IDs are unique.
2. Tool, source, and sink keys are non-empty.
3. Argument names are non-empty.
4. `allowed_types` is non-empty if provided.
5. `allowed_values` is non-empty if provided.

Deferred semantic checks:

1. Every exception match refers to an existing tool/source/sink.
2. Every rule required by a tool policy is configured.
3. Approval requirements are consistent with risk.
4. Source/sink names match trace metadata.
5. Rule coverage analysis.

Reasoning:

Milestone 3 should validate policy shape without pretending to know how policy will bind to traces. Binding semantics belong with Milestone 4 checks.

### D3.10 CLI Surface

Decision:

Add a policy command group and optional policy pre-validation in trace validation.

CLI additions:

```text
agentlint policy validate POLICY.yaml
agentlint validate TRACE.json --policy POLICY.yaml
```

Behavior:

1. `agentlint policy validate` validates only the policy file.
2. `agentlint validate --policy` validates the policy first, then runs existing trace schema and structural validation.
3. `--policy` does not run policy checks in Milestone 3.
4. Policy errors print to stderr and exit `1`.
5. Successful policy validation prints a small summary to stdout.

Example success:

```text
valid policy: customer_support_v1
version: 1
tools: 4
sources: 3
sinks: 3
rules: 14
exceptions: 1
```

Example trace validation with policy:

```text
valid policy: customer_support_v1
valid trace: trace_structural_valid_tool_flow
events: 5
edges: 5
diagnostics: 0
```

### D3.11 Policy Errors Are Not Diagnostics Yet

Decision:

Policy file/load/schema errors should remain exceptions and CLI errors, not `Diagnostic` objects.

Reasoning:

Diagnostics currently describe trace or policy violations over a parsed trace. A malformed policy is an input error, like malformed JSON or invalid trace schema. It should be reported separately until the report layer exists.

Implementation consequence:

Do not add policy-load errors to `DiagnosticCode`. Milestone 4 may add policy violation diagnostic codes such as `UNKNOWN_TOOL` and `MISSING_APPROVAL`.

## Proposed Policy YAML Shape

```yaml
version: 1
policy_id: customer_support_v1

metadata:
  owner: support-platform

tools:
  lookup_account:
    permission: allowed
    approval: not_required
    risk: low
    arguments:
      account_id:
        required: true
  send_email:
    permission: allowed
    approval: required
    risk: high
  web_search:
    permission: allowed
    approval: not_required
    risk: medium
  delete_account:
    permission: denied
    approval: required
    risk: critical

sources:
  customer_profile:
    sensitivity: private
    trust: trusted
  public_web:
    sensitivity: public
    trust: untrusted

sinks:
  web_search.query:
    visibility: public
  final_answer:
    visibility: model
  email.body:
    visibility: private

rules:
  unknown_tool: error
  unauthorized_tool_call: error
  disallowed_tool_argument: error
  missing_approval: error
  approval_after_action: error
  action_after_denial: error
  approval_mismatch: error
  private_to_public_sink: error
  secret_exposure: error
  untrusted_to_privileged_action: error
  sensitive_final_answer: warning
  unsupported_claim: warning
  invalid_provenance_reference: error
  evidence_after_claim: warning

exceptions:
  - id: allow_public_status_search
    rules:
      - private_to_public_sink
    reason: Synthetic fixture allows public lookup of non-sensitive status text.
    expires: "2026-12-31"
    match:
      tool: web_search
      sink: web_search.query
```

## Build Track

### B3.1 Add Policy Models

Files:

```text
src/agentlint/policy/models.py
src/agentlint/policy/__init__.py
tests/test_policy_models.py
```

Implement:

1. `POLICY_VERSION`
2. `Policy`
3. `ToolPolicy`
4. `ArgumentPolicy`
5. `SourcePolicy`
6. `SinkPolicy`
7. `PolicyException`
8. `ExceptionMatch`
9. `ArgumentType`
10. Policy enums and rule IDs

Tests:

1. Minimal valid policy parses.
2. Defaults apply predictably.
3. Extra fields are rejected.
4. Unsupported `version` is rejected.
5. Invalid enum values are rejected.
6. Empty names are rejected where possible.
7. Duplicate exception IDs are rejected.
8. Empty `allowed_types` and `allowed_values` are rejected when provided.
9. `model_dump(mode="json")` produces stable strings for enums.

### B3.2 Add Policy Loader

Files:

```text
src/agentlint/policy/loaders.py
tests/test_policy_loader.py
```

Implement:

1. File reading errors.
2. YAML parse errors.
3. Empty YAML error.
4. Top-level non-mapping error.
5. Pydantic schema error wrapping.
6. Validation error formatting.

Tests:

1. Valid example policy loads.
2. Missing file fails with `PolicyFileError`.
3. Directory path fails with `PolicyFileError`.
4. Malformed YAML fails with `PolicyYamlError`.
5. Empty policy fails with `PolicySchemaError` or a dedicated policy load error.
6. Invalid schema fails with `PolicySchemaError`.
7. Duplicate YAML keys fail with `PolicyYamlError`.

### B3.3 Add Example Policies

Files:

```text
examples/policies/customer_support.yaml
examples/policies/research.yaml
examples/policies/coding.yaml
examples/policies/invalid_schema.yaml
examples/policies/malformed.yaml
examples/policies/duplicate_key.yaml
```

Examples should be synthetic but realistic enough to support Milestone 4 fixtures.

Policy themes:

1. Customer support: account lookup, email, refund, public web search.
2. Research: web search, paper lookup, citation/provenance expectations.
3. Coding: repository read, shell command, network access, secret exposure rules.

### B3.4 Add CLI Policy Validation

Files:

```text
src/agentlint/cli.py
tests/test_cli.py
```

Implement:

1. `policy_app = typer.Typer(...)`.
2. `agentlint policy validate POLICY.yaml`.
3. Shared policy summary formatting helper, likely private in `cli.py` until reports exist.
4. Optional `--policy POLICY.yaml` on `agentlint validate`.
5. Policy validation before trace loading when `--policy` is supplied.

Tests:

1. Help output lists `policy`.
2. `agentlint policy validate examples/policies/customer_support.yaml` exits `0`.
3. Invalid policy schema exits `1` and prints policy schema error to stderr.
4. Missing policy file exits `1`.
5. `agentlint validate TRACE --policy POLICY` validates policy and trace.
6. Invalid policy with missing trace path still reports policy error first.

### B3.5 Documentation Updates

Files:

```text
README.md
Documents/architecture.md
Documents/research_note.md
Documents/milestone_3_build_report.md
```

Update:

1. Status to Milestone 3 after build completion.
2. CLI examples with `agentlint policy validate`.
3. Architecture note with policy package responsibilities.
4. Research note with final Milestone 3 build decision.
5. Build report after implementation and verification.

### B3.6 Optional Generated Schema

Decision:

Do not commit generated JSON Schema in Milestone 3 unless a concrete consumer appears.

Reasoning:

Generated schema can be useful for editor tooling, but committing it adds churn before the DSL settles. Tests can assert selected schema properties without writing generated artifacts.

## Verification Plan

Required commands:

```text
py -3.12 -m agentlint --help
py -3.12 -m agentlint policy validate examples\policies\customer_support.yaml
py -3.12 -m agentlint policy validate examples\policies\research.yaml
py -3.12 -m agentlint policy validate examples\policies\coding.yaml
py -3.12 -m agentlint policy validate examples\policies\invalid_schema.yaml
py -3.12 -m agentlint validate examples\traces\structural_valid_tool_flow.json --policy examples\policies\customer_support.yaml
py -3.12 -m pytest
py -3.12 -m ruff check .
py -3.12 -m ruff format --check .
git diff --check
```

Expected behavior:

1. Valid policies exit `0`.
2. Invalid policy exits `1` with a policy-specific error.
3. Trace validation with a valid policy still exits `0` on the valid structural trace.
4. Tests pass.
5. Ruff lint and format checks pass.
6. Whitespace check passes.

## Risks And Mitigations

### Risk: Policy DSL Becomes Too Expressive Too Early

Mitigation:

Keep Milestone 3 declarative and shallow. Avoid custom expressions, regex constraints, nested schemas, and rule condition language.

### Risk: Policy Validation Is Confused With Policy Enforcement

Mitigation:

CLI output and docs must state that Milestone 3 validates policy files but does not run policy checks. Milestone 4 owns enforcement.

### Risk: Policy Names Cannot Bind To Traces Yet

Mitigation:

Treat tool/source/sink keys as stable names only. Do not enforce trace binding semantics until Milestone 4 has concrete checks and fixtures.

### Risk: Duplicate YAML Keys Are Silently Overwritten

Mitigation:

Reject duplicate mapping keys with a SafeLoader subclass and add an invalid duplicate-key fixture.

### Risk: Policy Error Formatting Diverges From Trace Error Formatting

Mitigation:

Mirror the existing trace loader error style, but keep policy helpers local to `agentlint.policy` until a shared error-formatting package is justified.

## Completion Checklist

- [x] Policy models exist.
- [x] Policy enums and rule IDs exist.
- [x] Policy loader exists.
- [x] Policy loading uses safe YAML loading.
- [x] Policy file errors are represented.
- [x] Policy YAML parse errors are represented.
- [x] Duplicate YAML keys are rejected.
- [x] Policy schema errors are represented.
- [x] Policy validation errors format cleanly.
- [x] Example customer-support policy exists.
- [x] Example research policy exists.
- [x] Example coding policy exists.
- [x] Invalid policy fixtures exist.
- [x] CLI policy validation command exists.
- [x] `agentlint validate --policy` pre-validates policy.
- [x] Tests cover policy models.
- [x] Tests cover policy loading.
- [x] Tests cover policy CLI behavior.
- [x] README is updated.
- [x] Architecture note is updated.
- [x] Research note records Milestone 3 decisions.
- [x] Verification commands pass on Python 3.12.
- [x] Milestone 3 build report is written.
