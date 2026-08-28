# Architecture notes

## State flow

`AdState` is the contract between nodes. Each node returns a small update rather than mutating a shared object. `log` and `trace` use reducers so a later node cannot erase earlier evidence.

```text
brief
  -> parse(spec)
  -> plan(plan)
  -> component(components)
  -> codegen(html)
  -> qa(qa_report)
       | pass
       v
  human_review -> END
       ^
       | fail and fix budget remains
       +------ codegen
```

## Reliability boundaries

- The model client is an adapter, not the orchestrator. Mock and live clients share the same node contract.
- The retrieval index falls back to a stable local hash embedding when a remote embedding service is unavailable.
- QA uses explicit Python predicates. There is no `eval` over generated or model-provided text.
- A generated artifact is not considered delivered until the HTML audit passes.

## Why the trace matters

`src/telemetry.py` records each node's status, duration, and current repair round. That makes a portfolio demo inspectable: the viewer can see where time was spent and whether QA caused a loop, without adding a hosted observability dependency.
