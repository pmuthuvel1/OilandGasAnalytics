# 🔑 LLM Configuration Guide

## Overview

The Oil & Gas Analytics system now supports flexible LLM configuration via environment variables. You can use:
- ✅ OpenAI's official API
- ✅ OpenAI-compatible providers (Core42, Ollama, etc.)
- ✅ Local LLM servers
- ✅ Any OpenAI API-compatible endpoint

---

## Environment Variables

### Required
- **`OPENAI_API_KEY`** - Your API key for the LLM provider
  - Format: Usually starts with `sk-` for OpenAI or similar for other providers
  - Required: Yes

### Optional
- **`OPENAI_BASE_URL`** - Base URL for the LLM API endpoint
  - Default: Empty (uses OpenAI official API)
  - Format: Complete URL without trailing slash (e.g., `https://api.openai.com/v1`)
  - Required: No

### Optional Model Roles
- **`OPENAI_PRIMARY_MODEL`** - Primary text generation and most agent tasks. Default: `gpt-4.1`
- **`OPENAI_REASONING_MODEL`** - Planning, evaluation, final synthesis, and complex multi-step logic. Default: `gpt-5.1`
- **`OPENAI_EMBEDDING_MODEL`** - Embeddings, RAG, document retrieval, and semantic search. Default: `text-embedding-3-large`
- **`OPENAI_TRANSCRIPTION_MODEL`** - Speech-to-text for audio and voice use cases. Default: `whisper-1`
- **`OPENAI_MODEL`** - Backward-compatible alias for older deployments. Prefer `OPENAI_PRIMARY_MODEL`.

---

## Configuration Examples

### 1. OpenAI Official API (Default)

```env
OPENAI_API_KEY=sk-proj-xxx-your-key-here
OPENAI_PRIMARY_MODEL=gpt-4.1
OPENAI_REASONING_MODEL=gpt-5.1
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_TRANSCRIPTION_MODEL=whisper-1
OPENAI_BASE_URL=
```

**Setup:**
```bash
cp .env.example .env
# Edit .env and paste your OpenAI API key
python run.py
```

---

### 2. Core42 (OpenAI-Compatible Provider)

```env
OPENAI_API_KEY=your-core42-api-key
OPENAI_PRIMARY_MODEL=your-core42-primary-model-name
OPENAI_REASONING_MODEL=your-core42-reasoning-model-name
OPENAI_BASE_URL=https://api.core42.ai/v1
```

**Setup:**
```bash
cp .env.example .env
# Edit .env with your Core42 credentials
python run.py
```

---

### 3. Ollama (Local LLM Server)

**Prerequisites:**
- Ollama installed and running on your machine
- Model pulled: `ollama pull mistral` (or your preferred model)

```env
OPENAI_API_KEY=ollama  # Dummy key, not used by Ollama
OPENAI_PRIMARY_MODEL=mistral    # Your pulled model name
OPENAI_REASONING_MODEL=mistral
OPENAI_BASE_URL=http://localhost:11434/v1
```

**Setup:**
```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Pull a model
ollama pull mistral

# Terminal 3: Configure and run the analytics system
cp .env.example .env
# Edit .env with Ollama settings above
python run.py
```

---

### 4. LM Studio (Local LLM Server)

**Prerequisites:**
- LM Studio installed and running
- Model loaded in LM Studio

```env
OPENAI_API_KEY=local-key  # Dummy key
OPENAI_PRIMARY_MODEL=your-model    # Model name in LM Studio
OPENAI_REASONING_MODEL=your-model
OPENAI_BASE_URL=http://localhost:1234/v1
```

---

### 5. Azure OpenAI

```env
OPENAI_API_KEY=your-azure-api-key
OPENAI_PRIMARY_MODEL=your-azure-primary-deployment-name
OPENAI_REASONING_MODEL=your-azure-reasoning-deployment-name
OPENAI_BASE_URL=https://your-resource.openai.azure.com/v1
```

---

### 6. Self-Hosted OpenAI-Compatible API

For any server running OpenAI-compatible API (vLLM, text-generation-webui, etc.):

```env
OPENAI_API_KEY=your-api-key
OPENAI_PRIMARY_MODEL=model-name
OPENAI_REASONING_MODEL=reasoning-model-name
OPENAI_BASE_URL=https://your-server.com:8000/v1
```

---

## How It Works

### Code Implementation

The system routes model usage by task:

```python
# From app/agents.py
config = get_config()
llm_params = {
    "api_key": config.OPENAI_API_KEY,
    "model": config.OPENAI_PRIMARY_MODEL,
    "temperature": 0.2,
}
if config.OPENAI_BASE_URL:
    llm_params["base_url"] = config.OPENAI_BASE_URL

agent_llm = ChatOpenAI(**llm_params)
reasoning_llm = ChatOpenAI(
    api_key=config.OPENAI_API_KEY,
    model=config.OPENAI_REASONING_MODEL,
)
```

**Key Features:**
- ✅ All 5 agents use the same configuration
- ✅ Agents: SeismicAnalyzer, WellLogInterpreter, ReservoirCharacterizer, ExplorationRiskAssessor, ReportGenerator
- ✅ Automatic fallback to OpenAI official API if OPENAI_BASE_URL is empty
- ✅ Supports any OpenAI-compatible endpoint

---

## Configuration Priority

The system reads environment variables in this order:
1. **Environment file** (`.env` file in project root)
2. **System environment variables**
3. **Default values**

This allows you to:
- Set `.env` locally for development
- Use system environment variables for Docker/production
- Override via command line if needed

---

## Docker Deployment with Custom LLM

### Using Docker Environment Variables

```bash
docker build -t oil-gas-analytics .

# With OpenAI Official API
docker run \
  -e OPENAI_API_KEY=sk-your-key \
  -e OPENAI_BASE_URL= \
  -p 8000:8000 -p 8001:8001 \
  oil-gas-analytics

# With Core42
docker run \
  -e OPENAI_API_KEY=core42-key \
  -e OPENAI_BASE_URL=https://api.core42.ai/v1 \
  -p 8000:8000 -p 8001:8001 \
  oil-gas-analytics

# With Local Ollama
docker run \
  -e OPENAI_API_KEY=ollama \
  -e OPENAI_BASE_URL=http://host.docker.internal:11434/v1 \
  -p 8000:8000 -p 8001:8001 \
  oil-gas-analytics
```

### Using .env File with Docker

```bash
# Create .env file with your configuration
cat > .env << EOF
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://your-api.com/v1
OPENAI_MODEL=gpt-5.5
EOF

# Run container with .env file
docker run --env-file .env -p 8000:8000 -p 8001:8001 oil-gas-analytics
```

---

## Troubleshooting

### Issue: "Invalid API key"
- **Solution**: Check that `OPENAI_API_KEY` is correctly set in `.env`
- **Solution**: Verify API key hasn't expired or been revoked

### Issue: "Connection refused" or "Cannot reach API"
- **Solution**: Verify `OPENAI_BASE_URL` is correct and accessible
- **Solution**: Check firewall/network settings for outbound connections
- **Solution**: For local servers, ensure they're running on expected port

### Issue: "Model not found"
- **Solution**: Check `OPENAI_MODEL` name matches provider's available models
- **Solution**: For Ollama, run `ollama list` to see available models

### Issue: ".env file not found"
- **Solution**: Create `.env` from template: `cp .env.example .env`
- **Solution**: Ensure `.env` is in the project root directory

### Issue: Changes to .env not taking effect
- **Solution**: Restart the application: `python run.py`
- **Solution**: Clear any cached configuration: `python -c "from app.config import get_config; print(get_config().OPENAI_BASE_URL)"`

---

## Testing LLM Connection

### Verify Configuration

```bash
# Test imports
python -c "from app.config import get_config; config = get_config(); print(f'API Key: {config.OPENAI_API_KEY[:10]}...'); print(f'Base URL: {config.OPENAI_BASE_URL}'); print(f'Model: {config.OPENAI_MODEL}')"

# Test agent creation
python -c "from app.agents import create_seismic_analyzer_agent; agent = create_seismic_analyzer_agent(); print('✓ Agent created successfully')"

# Test full workflow
python run.py
```

### Sample Request

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @input_examples/example_1_northfield.json
```

---

## Performance Considerations

### Latency
- **OpenAI Official**: ~1-2 seconds per agent (depends on model)
- **Cloud Providers**: ~1-3 seconds (depends on distance/region)
- **Local LLM (Ollama)**: ~5-15 seconds (depends on hardware)

### Cost
- **OpenAI**: Pay per token
- **Alternative Providers**: Varies (some free, some subscription-based)
- **Local LLM**: Only compute cost

### Recommendations

| Use Case | Recommended Setup |
|----------|------------------|
| **Production** | OpenAI official or Azure OpenAI |
| **Development** | Local Ollama (free, self-contained) |
| **Cost-Conscious** | Core42 or other alternative providers |
| **Privacy-Required** | Local LLM (Ollama, LM Studio) |
| **Testing** | Mock/synthetic mode |

---

## Advanced Configuration

### Custom LLM Parameters (Future Enhancement)

Current supported configuration:
- API Key
- Base URL
- Model name
- Temperature (hardcoded per agent)

To support additional parameters (future):
- Add new config variables to `app/config.py`
- Update agent instantiation in `app/agents.py`
- Document new variables in `.env.example`

---

## Support & Documentation

- **LangChain Docs**: https://python.langchain.com/docs/integrations/llms/openai
- **OpenAI API Docs**: https://platform.openai.com/docs/api-reference
- **Ollama Docs**: https://ollama.ai
- **LM Studio**: https://lmstudio.ai

---

**Version**: 1.0.0  
**Last Updated**: May 29, 2026  
**Status**: Production Ready
