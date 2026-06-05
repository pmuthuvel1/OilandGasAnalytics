# Troubleshooting

Quick fixes for the issues that crop up most often. Every situation
below is **already handled** in the code — this doc explains why and how
to verify.

## 1. `400 Bad Request — You may not have a quota or access to use this model`

**Root cause.** Core42's `gpt-5.1` (and a few Azure deployments) reject
requests that include any field beyond `model` + `messages`. LangChain's
`ChatOpenAI` adds `temperature`, `top_p`, `stream_options`, etc. by
default — which earns this misleading 400.

**Fix already in repo.** The reasoning model calls go through a raw
OpenAI client (`_create_raw_openai_client` in `app/agents.py`) that mirrors
the Compass sample exactly:

```python
client.chat.completions.create(
    model=self.reasoning_model,
    messages=messages,
)
```

You'll see logs like `Calling LLM role=planner model='gpt-5.1' base_url=...`
followed by a `200 OK`. If you still see a 400 it's almost always one of:

- API key not active for that model — check the response body in the log
- Wrong base URL (must be `https://api.core42.ai/v1`)
- Request body too large — the manager retries once with `MAX_CONTEXT_CHARS / 4`

## 2. `LLM synthesis skipped because OPENAI_API_KEY is not configured`

The loader **intentionally** ignores `OPENAI_API_KEY=` (empty) lines in
`.env` so they cannot mask a real `export` from your shell. Verify which
value the process actually picked up:

```bash
python -c "from app.config import get_config; c=get_config(); print('len:',len(c.OPENAI_API_KEY),'enabled:',c.llm_enabled,'sample:',c.SAMPLE_MODE)"
```

If `len: 0`, fix one of:

1. Set a value in `.env`: `OPENAI_API_KEY=sk-...`
2. Export in your shell: `export OPENAI_API_KEY=sk-...`
3. Run in sample mode: `export SAMPLE_MODE=true`

The UI server also prints a masked key at startup
(`OPENAI_API_KEY = abcd...wxyz (len=...)`). Set
`DEBUG_PRINT_API_KEY=true` only when you're debugging — it logs the raw
value.

## 3. `python run_ui.py` warns: `You must pass the application as an import string`

Fixed. `run_ui.py` already passes `"run_ui:app"` to uvicorn (not the app
object), and only enables `reload`/`workers` when the env vars
`UVICORN_RELOAD=true` / `WEB_CONCURRENCY>1` are set.

## 4. `result.mode = "tool_only"` but you wanted LLM output

You're in SAMPLE_MODE, or no API key is set, or the LLM provider is
returning errors. Check `escalation.escalated_to_sample_mode` in the
workflow summary — after 3 consecutive LLM failures the manager flips to
deterministic mode and stays there for the rest of the run. Restart the
process to reset.

## 5. Long LLM response times

The reasoning model can take 10–30 seconds for complex synthesis tasks.
Look for log lines like:

```
INFO Calling LLM role=report_generator model='gpt-5.1' base_url=... user_chars=23398
INFO HTTP Request: POST https://api.core42.ai/v1/chat/completions "HTTP/1.1 200 OK"
```

If the user_chars value is huge, lower `MAX_CONTEXT_CHARS` in `.env` or
pre-summarize big inputs. The system already truncates payloads to that
cap and retries on size-related 400 errors.

> The application does **not** download anything at runtime (no model
> weights, no datasets). Long latency is purely the upstream provider.

## 6. `corrupt JSON` / `JSON_DECODE_ERROR` from `metadata.json`

The original `metadata.json` shipped without an opening `{` (an upstream
typo). It has been replaced with a valid version that includes the full
agent roster and the new capability list.

## 7. `pip install` fails on system Python (PEP 668)

Modern macOS / Debian Python installs are "externally managed". Use:

```bash
make venv             # creates .venv
source .venv/bin/activate
make install-dev
```

…or pass `--break-system-packages` if you really mean to install globally.

## 8. CI: "output_examples are out of sync"

The `scripts/generate_outputs.py --check` step failed. Locally:

```bash
make examples         # regenerate snapshots
git diff output_examples/
git add output_examples/ && git commit
```

## 9. Multiple workers can't share memory / RAG

When running with `WEB_CONCURRENCY>1` (gunicorn workers), each worker
keeps its own in-process orchestrator. The persistent files
(`PERSISTENT_MEMORY_FILE`, `RAG_INDEX_FILE`, `OBS_EVENT_FILE`) are
shared, but the in-memory history (`/workflows/history`) is per-worker.
For a single source of truth across workers, mount those files on a
shared volume and rebuild RAG once (`POST /rag/build?force=true`).

## 10. Reverse-line corruption seen in some files

If you ever see a Python file whose content is line-reversed below the
first line, that's almost always a misbehaving IDE plugin (a JetBrains
"Rearrange Code"-style action). Re-save the file from a clean editor or
restore from `git checkout`. The repo's `.pre-commit-config.yaml`
includes `end-of-file-fixer` and `mixed-line-ending --fix=lf` to catch
common formatting drift.

