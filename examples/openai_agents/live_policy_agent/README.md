# Live OpenAI Policy Agent

This folder runs three actual OpenAI Agents SDK workflows against the OpenAI API and checks their captured traces with AgentLint:

1. `issue_refund` records an explicit approval inside the function tool before its synthetic side effect and should pass.
2. `diagnose_ticket` is intentionally absent from the policy and should fail with `UNKNOWN_TOOL`.
3. `lookup_status` is allowed, but the shared policy requires approval coverage; because that trace contains no explicit approval record, it should be `not_verifiable`.

All tools are local and synthetic. The example does not contact ticketing, payment, web-search, or other external systems.

```powershell
$env:OPENAI_API_KEY = "..."
py -3.12 examples\openai_agents\live_policy_agent\run.py
```

The default model is `gpt-5.4-mini`. Override it with `AGENTLINT_OPENAI_MODEL`. The run makes three short model requests and is not part of the default test suite. Snapshots are written beneath the ignored `generated` directory.

The approval helper records represented application approval semantics. It does not prove that every approval path in the application is instrumented.
