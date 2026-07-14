# AgentLint Glossary

This glossary defines the core terms used in AgentLint design and implementation documents.

## Adapter

A component that imports a source trace format and translates it into the AgentLint intermediate representation.

## Approval

A recorded human or system decision that authorizes or denies an action, usually a sensitive tool call. AgentLint verifies represented approval evidence; it does not initially collect or enforce approvals.

## Claim

A statement in a final answer or important agent message that may require supporting evidence.

## Diagnostic

A structured explanation emitted by AgentLint for a policy violation, malformed trace, unsupported input, or other actionable issue.

## Event

A discrete occurrence within a trace, such as a user message, model call, tool call, tool result, approval, or final answer.

## Intermediate Representation

The canonical AgentLint representation of an imported trace. It normalizes events, values, relationships, labels, and source references so checks can run independently of the original trace format.

## Policy

A developer-defined trace-conformance configuration that describes tool contracts, required approval evidence, explicit data-handling constraints, provenance requirements, severities, and exceptions. It is not a complete contextual authorization system.

## Provenance

An explicit relationship between a claim and prior observations or events declared as its evidence. Initial AgentLint checks validate the relationship's integrity, not whether the evidence semantically proves the claim.

## Sink

A destination where data can flow, especially one with policy-relevant visibility or risk. Examples include public web search queries, outbound emails, APIs, databases, or final answers.

## Source

An origin of data with policy-relevant sensitivity or trust. Examples include user input, private email content, secret environment variables, public web pages, or trusted internal databases.

## Tool Call

An agent action that invokes an external tool, API, function, browser, file system, database, or other capability outside the model itself.

## Tool Result

The observed result returned from a tool call.

## Trace

A recorded execution of an AI agent, represented as events and relationships between those events.

## Not Verifiable

The result for a structurally valid trace with no known policy violation when evidence required by the selected policy was unavailable, unknown, or below the required capture level. It is not a pass.

## Value

A piece of data that can be produced, consumed, labeled, or propagated through a trace.

## Violation

A concrete instance where a trace fails a structural rule or developer-defined policy.
