# Agent contracts

This document is the single source of truth for what each agent reads,
writes, and is allowed to delegate to. All names match the ones used in
`app/agents.py` and the per-run trace logs.

## Planner

| Attribute      | Value                                                |
| -------------- | ---------------------------------------------------- |
| File / class   | `AgentExecutorManager._planner_delegate`             |
| Trace name     | `PlannerAgent`                                       |
| Reads          | `user_input`, prior `last_evaluation`, RAG coverage  |
| Writes         | `shared_memory["needs"]`, collaboration_log entries  |
| Delegates to   | Research + Retriever (always), specialists (per evidence) |
| Branching      | Quick mode skips seismic; HIGH risk / weak quality forces risk re-evaluation |
| Actions logged | `workflow_start`, `delegate`, `requested_retrieval`, `revision_requested`, `workflow_end` |

## Research Agent

| Attribute      | Value                                                |
| -------------- | ---------------------------------------------------- |
| File / class   | `_research_missing_context`                          |
| Trace name     | `ResearchAgent`                                      |
| Reads          | `user_input` (CSV paths, SEAM well numbers)          |
| Writes         | `user_input["data_sources"]`, evidence_register, open-data catalog |
| Tools          | `app/data_sources.py::enrich_with_reference_data`    |
| Actions logged | `load_context`                                       |

## Retriever / RAG Agent

| Attribute      | Value                                                |
| -------------- | ---------------------------------------------------- |
| File / class   | `_broaden_retrieval`, `_augment_with_rag_and_memory` |
| Trace names    | `RetrieverAgent`, `RAGAgent`, `MemoryAgent`          |
| Reads          | `user_input["user_notes"]`, `well_name`, `needs`     |
| Writes         | `shared_memory["rag_retrieval"]`, `rag_context`, `prior_memory` |
| Tools          | `app/rag.py::retrieve_with_retry`, `app/memory.py::recall` |
| Retry          | Broadens query until `coverage == "ok"` or budget exhausted |
| Actions logged | `retrieve`, `broaden_retry`, `recall`                |

## Specialist agents

All specialists share the same contract: they receive a task, run their
configured tools first (the source of truth), then optionally ask the LLM
to synthesize. If the LLM is unavailable or in SAMPLE_MODE, tool outputs
ship as-is with `mode = "tool_only"`.

| Agent                          | Tools (`AGENT_CONFIGS`)                                                   |
| ------------------------------ | ------------------------------------------------------------------------- |
| `seismic_analyzer`             | `analyze_seismic_amplitude`, `detect_faults`, `pick_horizons`             |
| `well_log_interpreter`         | `classify_lithology`, `identify_fluids`, `estimate_porosity`              |
| `reservoir_characterizer`      | `estimate_permeability`, `analyze_saturation`, `predict_pressure`         |
| `exploration_risk_assessor`    | `evaluate_trap`, `calculate_volumes`, `assess_seal_integrity`             |
| `report_generator`             | `synthesize_analysis`, `create_visualizations`, `format_recommendations`  |

Specialist outputs are stored under `state.analysis_results[<agent>]` with
this shape:

```json
{
  "status": "success",
  "agent": "seismic_analyzer",
  "agent_name": "SeismicAnalyzer",
  "description": "...",
  "tool_results": { "<tool>": { ... } },
  "result": {
    "mode": "llm" | "tool_only" | "tool_only_after_llm_error" | "llm_skipped" | "llm_error",
    "summary": "<text or rationale>",
    "tool_results": { ... }
  },
  "timestamp": "..."
}
```

## Evaluator

| Attribute      | Value                                                |
| -------------- | ---------------------------------------------------- |
| File / class   | `_evaluate_iteration`                                |
| Trace name     | `EvaluatorAgent`                                     |
| Reads          | All `state.analysis_results`, evidence_register, RAG coverage |
| Writes         | `shared_memory["last_evaluation"]`, `report_gate`    |
| Quality score  | Weighted blend of tool errors, LLM synthesis status, evidence count, RAG coverage, missing-data penalty |
| Authority      | Sets `report_gate.may_publish=False` to **block** the Report Writer |
| Actions logged | `evaluate`, `block_report_writer`                    |

Default threshold is `quality_threshold = 0.6`; callers can override it per
request (e.g. example 4 sets 0.65, example 8 sets 0.7).

## Report Generator

| Attribute      | Value                                                |
| -------------- | ---------------------------------------------------- |
| File / class   | `_finalize_report`                                   |
| Trace name     | `ReportGeneratorAgent`                               |
| Reads          | All `state.analysis_results`, `evaluation`, evidence |
| Writes         | `state.final_report`                                 |
| Gate           | Returns `mode = "blocked_by_evaluator"` with reasons when the gate denies publication |
| Actions logged | `produce_final_answer`, `block_report_writer` (when blocked) |

## Trace record schema

Every agent emits one JSONL line per action via `app/logging_utils.py`:

```json
{
  "timestamp": "2026-05-24T10:15:31.420Z",
  "trace_id": "run_abc12345",
  "agent_name": "EvaluatorAgent",
  "action": "evaluate",
  "input_summary": "{...}",
  "output_summary": "{...}",
  "target_agent": "ReportGeneratorAgent",
  "confidence": 0.79,
  "retry_count": 1,
  "status": "request_revision",
  "extra": { "report_gate": { "may_publish": false, "...": "..." } }
}
```

Trace files are at `logs/agent_trace_<UTC>_<trace_id>.jsonl`. The
generator output in [docs/SAMPLE_MODE.md](SAMPLE_MODE.md) shows a complete
end-to-end stream from a SAMPLE_MODE run.

