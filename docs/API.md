# HTTP API reference

> Default base URL: `http://localhost:8000`. Set `API_BASE_URL` and `HOST`
> in `.env` to change. The dashboard UI proxies these endpoints from
> `:8001`.

All POSTs accept and return JSON. Every response carries an `X-Request-ID`
header. When `JSON_LOGS=true`, the same id appears in the process logs.

## Health & introspection

### `GET /health`

Liveness probe. Always returns 200 once the process is up.

```json
{
  "status": "healthy",
  "version": "1.1.0",
  "timestamp": "2026-06-05T07:21:00.123Z",
  "agents_available": 5
}
```

### `GET /readyz`

Readiness probe. Returns 200 only when an LLM API key is configured (or
`SAMPLE_MODE=true`).

### `GET /info`

System + configuration snapshot (secrets are redacted). Use this from
operators / admin UIs to verify which models are wired up.

## Analysis

### `POST /analyze`

Body fields:

| Field                 | Type            | Required | Notes                                    |
| --------------------- | --------------- | -------- | ---------------------------------------- |
| `well_name`           | string          | yes      | Used for memory key                      |
| `analysis_type`       | `"full"`/`"quick"` | no    | Defaults to `"full"`                     |
| `seismic_data`        | object          | no       | Inline arrays (see input examples)       |
| `well_log_data`       | object          | no       | Inline arrays                            |
| `seismic_csv_path`    | string          | no       | Path under `DATA_PATH`                   |
| `well_log_csv_path`   | string          | no       | Path under `DATA_PATH`                   |
| `seam_well_number`    | int             | no       | For SEAM LAS bundle                      |
| `user_notes`          | string          | no       | Free-form context                        |

Returns:

```json
{
  "workflow_id": "2026-06-05T07:21:00.123Z",
  "status": "success" | "partial" | "blocked" | "error",
  "results": { ... full orchestrator summary ... },
  "timestamp": "..."
}
```

The `results` block contains `planner_delegation`, `findings` per agent,
`evaluation` (quality + report gate), `collaboration_log`, `trace_id`,
`escalation`, and a flat `seismic_analysis`/`well_log_analysis`/etc.
mirror for convenient consumption.

### `POST /analyze/batch`

Accepts a JSON list of well payloads, runs each through the full workflow.

```bash
curl -X POST http://localhost:8000/analyze/batch \
  -H 'content-type: application/json' \
  -d '[ {"well_name":"A","well_log_data":{...}}, {"well_name":"B","...":"..."} ]'
```

### `GET /workflows/history?limit=10`

Returns the last `limit` orchestrator runs from the in-process history.

### `DELETE /workflows/history`

Clears the in-process history (does not touch persistent memory).

## Tools

### `GET /tools`

Lists all registered tools and their category buckets.

### `POST /tools/{tool_name}`

Calls a tool directly. The body is the tool's payload (same shape as the
deterministic tools in `app/tools.py`).

```bash
curl -X POST http://localhost:8000/tools/analyze_seismic_amplitude \
  -H 'content-type: application/json' \
  -d '{"depth_values":[1,2,3],"amplitude_values":[0.5,1.2,2.3]}'
```

## Data uploads

### `POST /upload/seismic` and `POST /upload/well-log`

Multipart uploads. Files are saved to `data/uploads/<timestamp>_<safe-name>`.
Maximum size is `MAX_REQUEST_BYTES` (10 MB by default).

### `GET /data/open-sources`

Returns the static SEG/SEAM open-data catalog used by the Research Agent.

## RAG

### `GET /rag/status`

Returns `{loaded, chunks, index_file}`.

### `POST /rag/build?force=true`

Forces a rebuild of the on-disk RAG index (requires embeddings, i.e. an
API key — unless an existing index can be loaded from disk).

### `GET /rag/search?q=<query>&k=4`

Top-k hits with score + snippet.

## Memory & observability

### `GET /memory/{key}?limit=5`

Recall up to `limit` prior workflow summaries for a well/asset key.

### `GET /events/tail?n=50`

Tail the JSONL observability log (`OBS_EVENT_FILE`, default
`logs/events.jsonl`).

### `GET /logs/download`

Download `LOG_FILE` (the per-request analysis log, default
`logs/agent_logs.json`).

## Error responses

```json
{
  "error": "internal_server_error",
  "request_id": "<uuid>"
}
```

400 errors caused by Compass / Azure HTTP quirks (e.g. extra fields) are
caught inside the agent layer and surfaced via the `result.llm_error`
field in the workflow summary, **not** as a 5xx — so the workflow keeps
returning useful tool output even when the LLM endpoint misbehaves.

