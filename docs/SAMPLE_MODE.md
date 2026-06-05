# SAMPLE_MODE

> The system runs end-to-end **with no API key**. Every agent still
> participates, the planner still delegates, the evaluator still gates,
> and the report writer still respects the gate. The only thing that
> changes is that LLM calls are skipped (or use deterministic tool
> output as the synthesis).

## When to use it

- 30-second demo on a laptop without provisioning an OpenAI key
- CI workflows (`make test`, `scripts/generate_outputs.py`)
- Smoke-testing Docker images (`.github/workflows/ci.yml`)
- Reproducing customer issues offline
- Generating golden output snapshots (`output_examples/`)

## How to enable

Any one of:

```bash
export SAMPLE_MODE=true
SAMPLE_MODE=true python cli.py analyze --input <file>
docker run -e SAMPLE_MODE=true ...
```

In `.env`:

```dotenv
SAMPLE_MODE=true
```

The `Config.llm_enabled` flag becomes `False` and the orchestrator routes
every LLM call through `_invoke_reasoning_llm`, which short-circuits with:

```json
{
  "mode": "llm_skipped",
  "reason": "OPENAI_API_KEY is not configured or openai package is unavailable.",
  "escalated": false
}
```

## What you still get

Even with no LLM:

| Feature                              | Active in SAMPLE_MODE? |
| ------------------------------------ | ---------------------- |
| Planner → Specialists → Evaluator    | ✅                     |
| Async parallel execution             | ✅                     |
| Tool execution (`app/tools.py`)      | ✅ (the source of truth)|
| Per-run JSONL trace logging          | ✅                     |
| Quality scoring + report-writer gate | ✅                     |
| Persistent memory (`memory.py`)      | ✅                     |
| Local CSV + SEAM LAS ingestion       | ✅                     |
| RAG retrieval                        | ⚠️ (empty, since embeddings need an API key) |
| LLM synthesis text                   | ❌ — replaced by `mode = "llm_skipped"` |

This makes SAMPLE_MODE genuinely useful for behavior testing: the entire
control flow, retry/escalation, and observability pipeline exercises end
to end.

## Live trace sample

Below is a real fragment from a SAMPLE_MODE run of `example_1_northfield`,
captured straight from `logs/agent_trace_*.jsonl`. Every line is a single
JSON record.

```json
{"timestamp":"2026-06-05T07:38:54.516Z","trace_id":"run_d3041","agent_name":"PlannerAgent","action":"workflow_start","input_summary":"{\"well\":\"North Field-001\",\"quick\":false}","output_summary":"Workflow initialized","status":"success"}
{"timestamp":"2026-06-05T07:38:54.520Z","trace_id":"run_d3041","agent_name":"ResearchAgent","action":"load_context","output_summary":"{\"keys_added\":[\"data_sources\",\"open_data_catalog\"]}","status":"success"}
{"timestamp":"2026-06-05T07:38:54.555Z","trace_id":"run_d3041","agent_name":"RetrieverAgent","action":"broaden_retry","output_summary":"{\"coverage\":\"empty\",\"hits\":0}","retry_count":4,"status":"empty"}
{"timestamp":"2026-06-05T07:38:54.608Z","trace_id":"run_d3041","agent_name":"PlannerAgent","action":"delegate","output_summary":"{\"delegated\":[\"seismic_analyzer\",\"well_log_interpreter\",\"reservoir_characterizer\",\"exploration_risk_assessor\"]}","target_agent":"seismic_analyzer,well_log_interpreter,reservoir_characterizer,exploration_risk_assessor","status":"success"}
{"timestamp":"2026-06-05T07:38:54.616Z","trace_id":"run_d3041","agent_name":"SeismicAnalyzer","action":"execute","output_summary":"{\"tools\":[\"analyze_seismic_amplitude\",\"detect_faults\",\"pick_horizons\"],\"mode\":\"tool_only\"}","status":"success"}
{"timestamp":"2026-06-05T07:38:54.620Z","trace_id":"run_d3041","agent_name":"WellLogInterpreter","action":"execute","output_summary":"{\"tools\":[\"classify_lithology\",\"identify_fluids\",\"estimate_porosity\"],\"mode\":\"tool_only\"}","status":"success"}
{"timestamp":"2026-06-05T07:38:54.626Z","trace_id":"run_d3041","agent_name":"ReservoirCharacterizer","action":"execute","output_summary":"{\"tools\":[\"estimate_permeability\",\"analyze_saturation\",\"predict_pressure\"],\"mode\":\"tool_only\"}","status":"success"}
{"timestamp":"2026-06-05T07:38:54.631Z","trace_id":"run_d3041","agent_name":"ExplorationRiskAssessor","action":"execute","output_summary":"{\"tools\":[\"evaluate_trap\",\"calculate_volumes\",\"assess_seal_integrity\"],\"mode\":\"tool_only\"}","status":"success"}
{"timestamp":"2026-06-05T07:38:54.636Z","trace_id":"run_d3041","agent_name":"EvaluatorAgent","action":"evaluate","output_summary":"{\"approved\":false,\"quality_score\":0.475,\"report_gate\":{\"may_publish\":false,\"blocking_reasons\":[\"quality_score=0.475<0.5\"]}}","target_agent":"ReportGeneratorAgent","confidence":0.475,"status":"request_revision"}
{"timestamp":"2026-06-05T07:38:54.637Z","trace_id":"run_d3041","agent_name":"PlannerAgent","action":"revision_requested","retry_count":1,"status":"request_revision"}
{"timestamp":"2026-06-05T07:38:54.681Z","trace_id":"run_d3041","agent_name":"RetrieverAgent","action":"broaden_retry","output_summary":"{\"coverage\":\"empty\",\"hits\":0}","retry_count":4,"status":"empty"}
{"timestamp":"2026-06-05T07:38:54.683Z","trace_id":"run_d3041","agent_name":"EvaluatorAgent","action":"block_report_writer","target_agent":"ReportGeneratorAgent","status":"blocked"}
{"timestamp":"2026-06-05T07:38:54.693Z","trace_id":"run_d3041","agent_name":"PlannerAgent","action":"workflow_end","output_summary":"{\"status\":\"blocked\",\"quality_score\":0.475,\"escalated\":false}","confidence":0.475,"status":"blocked"}
```

Reading the trace top-to-bottom you can clearly see:

1. Planner starts → ResearchAgent loads context → RetrieverAgent broadens
   (4 retries, still `empty` because there are no embeddings).
2. Planner delegates to all four specialists; each runs in
   `tool_only` mode and returns successfully.
3. Evaluator scores quality at **0.475**, below the default
   threshold of **0.5**, sets `report_gate.may_publish=false`, requests
   revision.
4. Planner re-delegates (iteration 2); same outcome.
5. Evaluator **blocks** the Report Writer with a clear reason.
6. Workflow ends with status `blocked` — the entire critique loop is
   exercised and visible.

Run any of the 10 bundled examples to see the same flow against different
inputs; or set a real `OPENAI_API_KEY` to add LLM synthesis lines on top
of these tool-grounded steps.

