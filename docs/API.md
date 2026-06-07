# Architecture
a worker thread when needed.
we're already inside an event loop (e.g. inside FastAPI) and offloads to
`asyncio.gather`; dependent ones chain. The sync wrapper detects whether
`exploration_risk_assessor`). Independent agents run concurrently via
`well_log_interpreter`) from dependent ones (`reservoir_characterizer`,
`_run_agents_parallel` separates independent specialists (`seismic_analyzer`,

## Async parallelism

the final summary under `escalation`.
outputs instead of cascading errors. The escalation status is surfaced in
deterministic skip notice. The workflow keeps producing tool-grounded
`_llm_escalated=True`, and subsequent calls short-circuit with a
failed LLM calls (`_llm_failure_threshold`), the manager flips
`_invoke_reasoning_llm` keeps a failure streak. After three consecutive

## Escalation (live API → sample mode)

the planner then loops, the retriever broadens, specialists re-run.
when missing evidence, weak outputs, or quality < threshold are detected;
The evaluator can **block** the report writer via `report_gate.may_publish`

   (retry the retriever with broader query variants).
3. **RAG coverage** — `weak` or `empty` triggers `_broaden_retrieval`
   flagged weak outputs, HIGH risk, or quality < threshold.
2. **Prior evaluation** — `force_risk` is set when the last critique
   `state.analysis_results` decides which specialists to delegate.
1. **Available evidence** — which keys are present in `user_input` and

The planner branches on three signals:

## Non-linear control flow

| Petrophysics    | `app/petrophysics.py` (LAS-driven physics tools)               |
| Process logs    | `app/logging_config.py` (JSON-lines in production)             |
| Per-run trace   | `app/logging_utils.py` (`logs/agent_trace_*.jsonl`)            |
| Observability   | `app/observability.py` (JSONL events + optional OTel spans)    |
| RAG             | `app/rag.py` (Compass embeddings → on-disk vectors)            |
| Persistent mem  | `app/memory.py` (`logs/persistent_memory.json`)                |
| Configuration   | `app/config.py` (env-driven, `.env` for dev, `safe_dict()` for `/info`) |
| --------------- | -------------------------------------------------------------- |
| Concern         | Where                                                          |

### 4. Cross-cutting

regardless of LLM availability — they are the ground truth.
reservoir, and risk analytics. Tools are the only path that *always* runs,
`app/tools.py` registers ~15 deterministic functions for seismic, well-log,

### 3. Tools layer

8. Workflow summary is persisted to memory + emitted as `workflow.end`.
7. **Report Writer** synthesizes (or is blocked).
6. Loop steps 3–5 up to `max_review_cycles` (default 2).
   `report_gate` that the Report Writer must respect.
5. **Evaluator**: scores quality, captures missing evidence, sets a
   `SAMPLE_MODE=true` or no API key).
   asks the LLM to synthesize (or falls back to deterministic output if
4. **Specialists**: each agent calls its registered tools first, then
   safe), and asks the retriever to broaden if RAG coverage is weak.
3. **Planner**: chooses which specialists to delegate (parallel where
   relevant doc chunks, recalls persistent memory.
2. **Research + RAG**: loads any local CSVs / LAS bundles, retrieves
1. Boots a fresh `AgentState` and a per-run trace file (`new_trace_file`).

(`app/agents.py`) implement the non-linear collaboration. Each run:
`WorkflowOrchestrator` (`app/workflows.py`) and `AgentExecutorManager`

### 2. Orchestration layer

|             |               | `info`, `examples`, `regen-outputs`.                 |
| CLI         | `cli.py`      | argparse driver: `analyze`, `batch`, `tools`,        |
| Dashboard   | `run_ui.py`   | Embedded HTML UI on `:8001` (calls back into API).   |
|             |               | gzip, structured logs, batch / single analyze.       |
| HTTP API    | `run.py`      | FastAPI app on `:8000`; request middleware, CORS,    |
| ----------- | ------------- | ---------------------------------------------------- |
| Component   | File          | Purpose                                              |

### 1. Surface layer

## Layers

```
           └──────────────────────────────────────────────────┘
           │   logs/events.jsonl   logs/persistent_memory.json│
           │   logs/agent_trace_<ts>_run_<id>.jsonl           │
           ┌──────────────────────────────────────────────────┐
                                         ▼
                                         │
            └──────────────────────────────────────────────────────┘
            │              └────────────────────────┘              │
            │              │   Report Generator     │              │
            │              ┌────────────────────────┐              │
            │                           ▼                          │
            │           approve ────────┤──── request_revision     │
            │                           │                          │
            │  └────────────────────────┬────────────────────────┘ │
            │  │  Evaluator (critique + quality gate)            │ │
            │  ┌─────────────────────────────────────────────────┐ │
            │                                                      │
            │            (tool registry — app/tools.py)            │
            │        ▼              ▼              ▼               │
            │        │              │              │               │
            │  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘        │
            │  │ Analyzer   │ │ Interpreter│ │ Character. │        │
            │  │  Seismic   │ │  Well Log  │ │ Reservoir  │  ...   │
            │  ┌────────────┐ ┌────────────┐ ┌────────────┐        │
            │       ▼                                              │
            │       │ delegate (parallel where independent)        │
            │       │                            └────────────┘    │
            │  └────┬───────┘   └────────────┘   │   Memory   │    │
            │  │  Planner   │──▶│  Research  │──▶│   RAG +    │    │
            │  ┌────────────┐   ┌────────────┐   ┌────────────┐    │
            │                                                      │
            │           (app/agents.py)                            │
            │           AgentExecutorManager                       │
            ┌──────────────────────────────────────────────────────┐
                                         ▼
                                         │
                       └─────────────────┬────────────────┘
                       │     (app/workflows.py)           │
                       │     WorkflowOrchestrator         │
                       ┌──────────────────────────────────┐
                                           ▼
                                           │
                            └──────────────┬───────────┘
                            │    run_ui.py)            │
                            │   (run.py / cli.py /     │
                            │   FastAPI / CLI / UI     │
                            ┌──────────────────────────┐
```

> A deployable, observable multi-agent stack for subsurface analytics.


