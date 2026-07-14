# AgentLint 0.1 Pre-release and OpenAI Agents Evaluation Plan

Status: Phase 1 in progress

## Objective

Ship an installable alpha release, evaluate AgentLint against representative OpenAI
Agents SDK projects, measure accuracy and integration cost, and use the results to
decide whether the current OpenAI integration is ready before starting another
framework adapter.

This plan covers four outcomes:

1. Publish an installable `0.1.0a1` package.
2. Run AgentLint against several real OpenAI Agents projects.
3. Measure false positives, false negatives, `not_verifiable` outcomes, capture
   fidelity, and required annotations.
4. Resolve findings before approving another framework integration.

## Distribution-name decision

The PyPI distribution is `agentlint-trace`. The product, command, and Python import
package remain `AgentLint` and `agentlint`.

The `agentlint` distribution name is owned by a different active project, so this
project is installed with:

```bash
pip install agentlint-trace[openai-agents]
```

The name must be checked again immediately before its first publication because an
unused PyPI name is not reserved until a project is created.

## Version decision

Use `0.1.0a1` for the first public pre-release. On PyPI, `0.1.0` is a final release;
`0.1.0a1` clearly identifies an alpha.

The evaluation may produce additional alpha releases:

```text
0.1.0a1 -> first installable evaluation release
0.1.0a2 -> fixes from the first project cohort
0.1.0rc1 -> release candidate after the evidence gate
0.1.0    -> first stable release
```

## Phase 1: Package and publish `0.1.0a1`

### 1.1 Package metadata

Update `pyproject.toml`:

1. Replace the occupied distribution name.
2. Set the alpha version to `0.1.0a1`.
3. Use one version source for both package metadata and
   `agentlint.version.__version__`.
4. Change the development classifier from `Pre-Alpha` to `Alpha`.
5. Add project URLs for source, issues, and documentation.
6. Preserve the `agentlint` console command.
7. Preserve the `openai-agents` optional dependency group.
8. Confirm the wheel contains the pytest entry point.
9. Confirm license metadata and the `LICENSE` file agree.

Recommended single version source:

```toml
[project]
dynamic = ["version"]

[tool.hatch.version]
path = "src/agentlint/version.py"
```

### 1.2 Release files

Add:

```text
CHANGELOG.md
.github/workflows/release.yml
```

The changelog should document:

1. Supported Python and OpenAI Agents SDK versions.
2. Supported capture formats.
3. Current policy checks.
4. Known evidence limitations.
5. The difference between pytest capture, `instrument()`, `check-capture`, and
   split import/check commands.
6. The distribution name, CLI name, and import name.

### 1.3 Build validation

Add a release verification script or CI job that performs:

```bash
python -m build
python -m twine check dist/*
```

Then test both artifacts in clean environments:

```bash
pip install dist/<wheel>
pip install "agentlint-trace[openai-agents] @ file://..."
agentlint version
agentlint doctor
agentlint --help
pytest --help
```

The clean-environment smoke test must verify:

1. `import agentlint` resolves to this project.
2. `agentlint` invokes this project's CLI.
3. `pytest --help` lists the AgentLint options.
4. `instrument()` imports when the extra is installed.
5. `check-capture` runs against a packaged example copied outside the repository.
6. The wheel does not depend on repository-relative imports.
7. No live API call is required.

Run the full test suite from the built wheel, not only from the source checkout.

### 1.4 Supported runtime matrix

The project declares Python `>=3.12`. Before publishing, run build and smoke tests on:

```text
Python 3.12
Python 3.13
```

Either support both or narrow the package metadata to versions actually tested.

Test the OpenAI integration against the complete supported constraint:

```text
openai-agents >=0.18,<0.19
```

At minimum, test the oldest allowed `0.18.x` release and the latest available
`0.18.x` release.

### 1.5 Publishing workflow

Use PyPI Trusted Publishing from GitHub Actions:

1. Build artifacts in a dedicated build job.
2. Upload the wheel and source distribution as workflow artifacts.
3. Run installation smoke tests against those exact artifacts.
4. Publish only from a protected GitHub environment.
5. Grant `id-token: write` only to the publish job.
6. Trigger publication from a signed or protected `v*` tag or GitHub Release.
7. Do not store a long-lived PyPI token in repository secrets.
8. Generate PyPI attestations through the official publishing action.

Recommended sequence:

```text
push version commit
-> CI passes
-> create v0.1.0a1 tag
-> build once
-> test artifacts
-> publish artifacts
-> verify PyPI install
-> publish GitHub pre-release notes
```

### 1.6 Publication acceptance criteria

Phase 1 is complete when:

1. The distribution-name decision is recorded.
2. `0.1.0a1` installs from PyPI in a clean environment.
3. The OpenAI extra installs with one command.
4. The CLI and pytest plugin both load from the installed wheel.
5. Package metadata, CLI version, and report version agree.
6. GitHub Actions records a successful trusted publication.
7. The README uses the real distribution name and install command.
8. A rollback/yank procedure is documented.

## Phase 2: Evaluate real OpenAI Agents projects

### 2.1 Evaluation repository layout

Add:

```text
evaluation/
  README.md
  projects.yaml
  labels/
  policies/
  patches/
  results/
  schemas/
scripts/
  evaluation/
```

Do not commit entire upstream repositories or raw sensitive traces.

`evaluation/projects.yaml` should record:

1. Project name and upstream URL.
2. Exact commit SHA.
3. License.
4. Entry point.
5. Required dependencies.
6. Whether a live model or hosted tool is required.
7. Scenario inputs.
8. Expected trace capabilities.
9. Applicable AgentLint policy.
10. Stored patch or integration instructions.

Check upstream projects into an ignored evaluation cache:

```text
.agentlint-eval/projects/
.agentlint-eval/traces/
```

### 2.2 Initial project cohort

Pin the official `openai/openai-agents-python` repository to a reviewed commit and
start with four project shapes:

| Project | Primary behavior | AgentLint coverage target |
| --- | --- | --- |
| `examples/customer_service` | Triage, tools, handoffs | Tool policy, approval, handoff fidelity |
| `examples/agent_patterns/human_in_the_loop.py` | Paused actions and decisions | Approval ordering and matching |
| `examples/financial_research_agent` | Agents as tools, search, synthesis | Tool boundaries, provenance availability |
| `examples/agent_patterns/input_guardrails.py` and `output_guardrails.py` | Guardrail events | Capture fidelity and unsupported-policy boundaries |

Use additional official examples only if one of these cannot run reproducibly.
Candidates include:

```text
examples/basic/tools.py
examples/agent_patterns/routing.py
examples/agent_patterns/agents_as_tools.py
examples/research_bot
examples/hosted_mcp/on_approval.py
```

The first pinned baseline observed while writing this plan was:

```text
repository: https://github.com/openai/openai-agents-python
commit: 4d9677850cb3392073b4c60d42a39e795a2fe9af
release: v0.18.2
```

Refresh and record the pin when implementation starts.

### 2.3 Scenarios per project

Each project must have:

1. At least one hand-labeled safe baseline.
2. At least one seeded unsafe variant that exercises a supported AgentLint rule.
3. One unannotated run.
4. One minimally annotated run when the framework cannot expose the required
   semantics.
5. A deterministic replay check over the same saved trace.

Seeded variants should alter project configuration, policy, scenario input, or a small
stored patch. Do not label a case from AgentLint's output. Labels must be written
before checking the trace.

Example seeded cases:

```text
customer service:
  refund tool called without approval

human in the loop:
  action occurs before approval
  approval applies to different arguments

financial research:
  private source declared to flow into public search
  final claim lacks explicit provenance

guardrails:
  guardrail fires but a later privileged action still occurs
```

Only count a case as a supported false-negative test if the required relationship is
represented in the trace or required by the policy. Missing semantics belong in the
`not_verifiable` analysis, not the false-negative count.

### 2.4 Run modes

Run every project in two modes:

#### Mode A: integration only

```text
install AgentLint
add instrument() or pytest activation
define policy
run scenario
check capture
```

No semantic helper calls are allowed.

#### Mode B: minimal semantics

Add only the approval, source/sink, or final-result records required for the policy.

The difference between Mode A and Mode B measures:

1. Annotation count.
2. Changed lines.
3. Integration time.
4. `not_verifiable` reduction.
5. Newly detected true violations.
6. Any new false positives.

### 2.5 Cost and reproducibility controls

1. Keep all analyzer runs offline.
2. Store exact dependency versions and upstream SHAs.
3. Use fixed scenario inputs.
4. Separate capture generation from repeated checking.
5. Recheck stored captures without additional model calls.
6. Record model and tool usage for live scenarios.
7. Set a pilot budget before running hosted examples.
8. Require explicit approval before enabling paid or externally mutating tools.
9. Replace email, refunds, database writes, and similar actions with local test tools.
10. Redact or synthesize private values before committing any trace-derived artifact.

## Phase 3: Measurement

### 3.1 Label schema

Create a versioned label file for every trace:

```yaml
version: 1
trace_id: trace_example
project: customer_service
mode: integration_only

expected:
  status: failed
  diagnostics:
    - code: MISSING_APPROVAL
      subject_event: issue_refund
  required_evidence:
    approvals: partial

review:
  reviewer: human
  notes: Refund action occurred with no approval record.
```

Labels should distinguish:

1. Expected violation.
2. Expected clean result.
3. Expected `not_verifiable`.
4. Out-of-scope behavior.
5. Ambiguous cases excluded from accuracy totals.

### 3.2 Accuracy unit

Use a trace-rule pair as the primary classification unit:

```text
one captured trace
x
one active policy rule
```

Count:

```text
true positive:
  labeled violation and matching AgentLint diagnostic

false positive:
  labeled clean but AgentLint reports a violation

false negative:
  labeled supported violation but AgentLint does not report it

true negative:
  labeled clean and no diagnostic
```

Report raw counts before percentages. The first cohort will be too small for precise
population-level claims.

### 3.3 `not_verifiable` measurements

Measure:

1. Trace-level `not_verifiable` rate.
2. Rate by project.
3. Rate by policy rule.
4. Missing capability frequency.
5. Mode A versus Mode B reduction.
6. Cases where a known violation is reported alongside unrelated missing evidence.
7. Cases that incorrectly pass despite required missing evidence.

Every `not_verifiable` result must map to a specific missing capability:

```text
tool calls
tool arguments
tool results
approvals
data flow
provenance
final answers
```

### 3.4 Annotation burden

Measure AgentLint-specific work separately from policy authoring:

1. Setup lines required to activate capture.
2. Number of semantic helper call sites.
3. Lines added for semantic helpers.
4. Policy boundary declarations.
5. Minutes required to integrate each project.
6. Number of project functions that must know about AgentLint.
7. Whether annotations contain values or only labels/event references.

Report:

```text
median and range per project
Mode A and Mode B separately
approval, data-flow, and provenance annotations separately
```

### 3.5 Adapter fidelity

For each trace, compare expected SDK events to normalized AgentLint events:

1. Agent runs.
2. Model calls.
3. Function tool calls.
4. Tool arguments.
5. Tool results.
6. Handoffs.
7. Guardrails.
8. Errors and retries.
9. Approval records.
10. Final results.

Record dropped, duplicated, mis-parented, or misordered events. Parent edges must not
be counted as data-flow or provenance edges.

### 3.6 Determinism and performance

For every stored capture:

1. Run AgentLint at least three times.
2. Compare normalized JSON reports after removing environment-specific paths.
3. Require identical statuses, diagnostics, evidence requirements, and paths.
4. Record import time, analysis time, and total time.
5. Record trace event and edge counts.
6. Test single traces and the complete cohort.

### 3.7 Result artifacts

Generate:

```text
evaluation/results/raw-results.jsonl
evaluation/results/summary.json
evaluation/results/summary.md
evaluation/results/annotation-burden.csv
evaluation/results/adapter-fidelity.csv
```

`summary.md` should include:

1. Project and scenario matrix.
2. TP, FP, FN, and TN counts.
3. `not_verifiable` breakdown.
4. Mode A versus Mode B comparison.
5. Annotation burden.
6. Adapter fidelity findings.
7. Determinism and performance.
8. Known limitations.
9. Links to reproducible commands and stored non-sensitive fixtures.

## Phase 4: Evidence gate before another framework

Do not begin another framework adapter until the evaluation report is reviewed.

### 4.1 Required review

Classify every finding as:

```text
adapter defect
policy/evidence defect
diagnostic defect
documentation defect
unsupported SDK capability
out of scope
```

Create one tracked issue for every unexplained false positive, supported false
negative, incorrect pass, or incorrect diagnostic path.

### 4.2 Go criteria

The OpenAI integration is ready for the next framework when:

1. There are no unexplained false positives in the reviewed safe baselines.
2. There are no missed seeded violations for checks whose evidence is present.
3. No trace passes when its active policy requires unavailable evidence.
4. Every `not_verifiable` result identifies the missing capability.
5. Rechecking the same stored trace is deterministic.
6. Diagnostic paths use only relationships present in the trace.
7. The minimal-annotation workflow is documented from observed projects.
8. The installed PyPI artifact passes the same evaluation harness as the source tree.
9. Remaining unsupported behavior is listed explicitly.

These are cohort acceptance criteria, not broad statistical claims about all agent
systems.

### 4.3 No-go response

If a criterion fails:

1. Stop framework expansion.
2. Fix the existing adapter, evidence model, diagnostics, or documentation.
3. Add the failing real trace as a sanitized regression fixture when licensing and
   privacy permit.
4. Publish `0.1.0a2` if installed-package behavior changes.
5. Rerun the complete cohort.

## Implementation sequence

Execute in this order:

1. Use the `agentlint-trace` distribution name.
2. Implement single-source versioning and `0.1.0a1` metadata.
3. Add changelog, build checks, wheel smoke tests, and release workflow.
4. Configure the PyPI trusted publisher.
5. Publish and verify `0.1.0a1`.
6. Create the evaluation schema, labels, checkout script, and result aggregator.
7. Pin the official OpenAI Agents project cohort.
8. Write policies and labels before running AgentLint.
9. Capture Mode A traces.
10. Add minimal annotations and capture Mode B traces.
11. Score accuracy, verifiability, annotations, fidelity, determinism, and
    performance.
12. Review findings against the evidence gate.
13. Fix and rerun until the gate passes or the limitation is explicitly accepted.

## Definition of done

All four steps are complete when:

1. An alpha package installs from PyPI using the selected distribution name.
2. Release artifacts are reproducible and published through trusted publishing.
3. At least four representative OpenAI Agents project shapes have been evaluated.
4. Safe, unsafe, unannotated, and minimally annotated runs are represented.
5. Accuracy and `not_verifiable` counts are hand-labeled and reproducible.
6. Annotation burden and adapter fidelity are measured.
7. Findings are resolved or documented.
8. The evidence gate records a go or no-go decision for another framework.

## Primary references

1. OpenAI Agents SDK overview:
   https://developers.openai.com/api/docs/guides/agents
2. OpenAI Agents tracing and observability:
   https://developers.openai.com/api/docs/guides/agents/integrations-observability
3. OpenAI Agents Python repository:
   https://github.com/openai/openai-agents-python
4. PyPI trusted publishing:
   https://docs.pypi.org/trusted-publishers/
5. Occupied `agentlint` PyPI distribution:
   https://pypi.org/project/agentlint/
