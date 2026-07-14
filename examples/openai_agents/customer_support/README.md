# M10 Customer-Support Example

This zero-cost example uses real OpenAI Agents SDK trace and span objects without making a model API request. It demonstrates:

1. An approved `issue_refund` call that passes.
2. An `issue_refund` call without approval that fails.
3. A trace with unavailable approval evidence that is `not_verifiable`.

Run it with Python 3.12 after installing the OpenAI Agents extra:

```powershell
py -3.12 examples\openai_agents\customer_support\demo.py
```

The policy requires partial tool-call and approval evidence. Partial means AgentLint can evaluate represented function-tool and explicit approval records; it does not prove that every application approval or every OpenAI tool family was captured.
