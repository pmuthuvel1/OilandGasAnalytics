# Deployment guide

## Local development

```bash
make install-dev
make ci                # ruff + mypy + 39 pytest tests in SAMPLE_MODE
make run               # API on :8000, UI on :8001
```

For one-off analyses without spinning up servers:

```bash
SAMPLE_MODE=true python cli.py analyze \
  --input input_examples/example_4_deepwater_gulf.json
```

## Docker

```bash
docker build -t oga:1.1.0 .
docker run --rm -p 8000:8000 -p 8001:8001 \
  --env-file production.env \
  -v $(pwd)/logs:/app/logs \
  oga:1.1.0
```

Image notes:

- Multi-stage `python:3.12-slim` base
- `tini` as PID 1 for clean signal handling
- Non-root `app` user
- Built-in `HEALTHCHECK` hitting `/health`
- `JSON_LOGS=true` by default for SIEM-friendly logging
- `entrypoint.sh` validates `OPENAI_API_KEY` when `APP_ENV=production`
  and `SAMPLE_MODE != true`

To try the image without any API key:

```bash
docker run --rm -p 8000:8000 -p 8001:8001 \
  -e APP_ENV=development -e SAMPLE_MODE=true oga:1.1.0
```

## Kubernetes (sketch)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: oil-gas-analytics }
spec:
  replicas: 2
  selector: { matchLabels: { app: oga } }
  template:
    metadata: { labels: { app: oga } }
    spec:
      containers:
        - name: oga
          image: ghcr.io/your-org/oga:1.1.0
          ports:
            - { containerPort: 8000, name: api }
            - { containerPort: 8001, name: ui }
          env:
            - { name: APP_ENV, value: production }
            - { name: JSON_LOGS, value: "true" }
            - { name: WEB_CONCURRENCY, value: "4" }
            - { name: CORS_ORIGINS, value: "https://app.example.com" }
            - { name: OPENAI_BASE_URL, value: "https://api.core42.ai/v1" }
            - { name: COMPASS_CHAT_MODEL, value: "gpt-4.1" }
            - { name: COMPASS_REASONING_MODEL, value: "gpt-5.1" }
          envFrom:
            - secretRef: { name: oga-secrets }     # holds OPENAI_API_KEY
          readinessProbe:
            httpGet: { path: /readyz, port: api }
            initialDelaySeconds: 10
          livenessProbe:
            httpGet: { path: /health, port: api }
            periodSeconds: 30
          volumeMounts:
            - { name: logs, mountPath: /app/logs }
          resources:
            requests: { cpu: "250m", memory: "512Mi" }
            limits:   { cpu: "1",    memory: "1Gi"   }
      volumes:
        - name: logs
          persistentVolumeClaim: { claimName: oga-logs }
```

For multi-replica setups, point `OBS_EVENT_FILE`,
`PERSISTENT_MEMORY_FILE`, and `RAG_INDEX_FILE` at a shared volume (e.g.
EFS, NFS) so memory and the RAG index are stable across pods.

## gunicorn tuning

`entrypoint.sh` already spawns gunicorn with uvicorn workers in
production. Useful knobs:

| Variable             | Meaning                                | Default |
| -------------------- | -------------------------------------- | ------- |
| `WEB_CONCURRENCY`    | Number of workers                      | 2       |
| `GUNICORN_TIMEOUT`   | Worker timeout in seconds              | 120     |
| `OPENAI_REQUEST_TIMEOUT` | Per-LLM-call timeout (in seconds)  | 60      |
| `AGENT_TIMEOUT`      | Max wall-clock per LangChain agent     | 300     |
| `MAX_ITERATIONS`     | Max tool-iterations per LangChain agent| 10      |
| `MAX_CONTEXT_CHARS`  | Hard cap on prompt body size           | 24000   |

When you tighten `MAX_CONTEXT_CHARS` for cost reasons, the manager
already retries each LLM call with a quarter-budget before giving up, so
the system gracefully degrades under tight token limits.

## Secrets handling

- **Never commit `.env` with a real key.** The loader explicitly ignores
  empty values so `OPENAI_API_KEY=` in the file cannot shadow a real
  `export` from your shell.
- In production, inject via `--env-file`, Docker secrets, Kubernetes
  `Secret`, or your secret manager (AWS Secrets Manager, GCP Secret
  Manager, Vault).
- The system refuses to start with `CORS_ORIGINS=*` when
  `APP_ENV=production` — set an explicit allow-list.

## Backup / restore

Stateful artefacts you may want to back up:

| File                              | Purpose                              |
| --------------------------------- | ------------------------------------ |
| `logs/persistent_memory.json`     | Cross-run findings per well          |
| `logs/rag_index.json`             | Compass-embedded vector store        |
| `logs/agent_trace_*.jsonl`        | Per-run audit trail                  |
| `logs/events.jsonl`               | Workflow span / event log            |
| `data/uploads/`                   | Files uploaded via `/upload/*`       |

A simple cron job copying `logs/` and `data/uploads/` to object storage
is normally enough.

## Smoke testing a release

```bash
# 1. Build
docker build -t oga:test .

# 2. Boot in SAMPLE_MODE (no API key needed)
docker run -d --rm --name oga-smoke -p 8000:8000 -p 8001:8001 \
  -e SAMPLE_MODE=true -e APP_ENV=development oga:test

# 3. Verify
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/info | jq '.config.sample_mode'

# 4. Run an analysis
curl -fsS -X POST http://127.0.0.1:8000/analyze \
  -H 'content-type: application/json' \
  -d @input_examples/example_1_northfield.json | jq '.status'

# 5. Tear down
docker stop oga-smoke
```

This is exactly what `.github/workflows/ci.yml` runs on every PR.

