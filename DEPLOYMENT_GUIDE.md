# DEPLOYMENT & EXECUTION GUIDE

## 🚀 Starting the System

### Prerequisites
- Python 3.11+
- OpenAI API Key (for GPT-4)
- 8GB RAM recommended

### Step 1: Environment Setup

```bash
# Navigate to project directory
cd c:\work\OilandGasAnalytics

# Copy environment template
copy .env.example .env

# Edit .env and add your OpenAI API Key
# OPENAI_API_KEY=sk-your-key-here
```

### Step 2: Install Dependencies

```bash
# Windows
scripts\quickstart.bat

# OR Linux/Mac
bash scripts/quickstart.sh

# OR Manual
pip install -r requirements.txt
mkdir -p logs data/uploads
```

### Step 3: Start the Services

**Option A: Direct Python Execution (Recommended for Development)**

Terminal 1 - Start API on port 8000:
```bash
python run.py
```
✓ API accessible at: http://localhost:8000

Terminal 2 - Start UI on port 8001:
```bash
python run_ui.py
```
✓ Dashboard accessible at: http://localhost:8001

**Option B: Docker Deployment (Recommended for Production)**

```bash
# Build image
docker build -t oil-gas-analytics:1.0 .

# Run container
docker run -d \
  --name oil-analytics \
  -p 8000:8000 \
  -p 8001:8001 \
  --env-file .env \
  oil-gas-analytics:1.0

# View logs
docker logs -f oil-analytics
```

---

## 📊 Using the System

### Via Dashboard (http://localhost:8001)

1. Enter well name
2. Select analysis type (Full or Quick)
3. Paste JSON data for seismic and well logs
4. Click "Submit Analysis"
5. View results and recommendations

**Load Example Data:**
Click "Load Example Data" button to populate sample data for testing.

### Via API (http://localhost:8000)

**Analyze a well:**
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "well_name": "Test-Well-001",
    "analysis_type": "full",
    "seismic_data": {
      "amplitude_values": [0.5, 1.2, 2.3, 1.8],
      "depth_values": [1000, 1100, 1200, 1300]
    },
    "well_log_data": {
      "gamma_ray": [85, 120, 95, 75],
      "resistivity": [50, 30, 100, 120],
      "porosity": [16, 8, 22, 20]
    }
  }'
```

**Check API health:**
```bash
curl http://localhost:8000/health
```

**View system info:**
```bash
curl http://localhost:8000/info
```

**List available tools:**
```bash
curl http://localhost:8000/tools
```

**View analysis history:**
```bash
curl http://localhost:8000/workflows/history
```

**Download logs:**
```bash
curl http://localhost:8000/logs/download -o logs.json
```

---

## 🧪 Test with Examples

Use provided example input files in `input_examples/` directory:

```bash
# Test with North Field exploration example
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @input_examples/example_1_northfield.json

# Test with Central Basin development example
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @input_examples/example_2_central_basin.json

# Test with quick assessment
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @input_examples/example_3_eastern.json
```

See `output_examples/` for expected analysis results.

---

## 📈 System Architecture

```
┌─────────────────────────────────────────────┐
│     Oil & Gas Analytics Dashboard           │
│           (http://8001)                     │
├─────────────────────────────────────────────┤
│                                             │
│         REST API Gateway (port 8000)        │
│  ┌──────────────────────────────────────┐  │
│  │  /analyze                            │  │
│  │  /analyze/batch                      │  │
│  │  /tools                              │  │
│  │  /workflows/history                  │  │
│  │  /upload/*                           │  │
│  └──────────────────────────────────────┘  │
│                                             │
│    ┌────────────────────────────────────┐  │
│    │  Multi-Agent Workflow Orchestrator │  │
│    │         (LangGraph)                │  │
│    └────────────────────────────────────┘  │
│           │                                │
│    ┌──────┴───────┬────────────────────┐  │
│    │              │                    │  │
│    ▼              ▼                    ▼  │
│  ┌────────┐  ┌────────┐  ┌──────────┐   │
│  │Seismic │  │Well Log│  │Reservoir │   │
│  │Analyzer│  │Interpr │  │Characterer  │
│  └────────┘  └────────┘  └──────────┘   │
│    │              │                    │
│    └──────┬───────┴────────┬──────────┘  │
│           │                │             │
│    ┌──────┴─────────────────┴──────┐    │
│    │  Exploration Risk Assessor    │    │
│    └──────┬──────────────────────────┘   │
│           │                              │
│    ┌──────┴──────────────────────┐      │
│    │    Report Generator         │      │
│    │  (Final Recommendations)    │      │
│    └─────────────────────────────┘      │
│                                         │
│  Database: logs/agent_logs.json        │
│  Cache: data/uploads/*                 │
│                                         │
└─────────────────────────────────────────────┘
```

---

## 🔍 Monitoring & Debugging

### Check Logs

```bash
# View recent logs
tail -50 logs/agent_logs.json | jq .

# View specific workflow
grep "North Field" logs/agent_logs.json | jq .

# Count analyses by day
cat logs/agent_logs.json | jq '.timestamp' | cut -d'T' -f1 | sort | uniq -c
```

### API Documentation

Visit http://localhost:8000/docs for interactive Swagger documentation.

### Performance Metrics

Expected execution times:
- **Full Analysis**: 4-7 minutes (all 5 agents)
- **Quick Analysis**: 1-2 minutes (2 agents: risk & reporting)
- **Single Tool**: 5-30 seconds

### Troubleshooting

**API won't start:**
```
Error: Port 8000 already in use
→ Change API_PORT in .env or kill process on 8000
```

**OpenAI API errors:**
```
Error: Invalid API key
→ Verify OPENAI_API_KEY in .env
→ Check API key has GPT-4 access
```

**Agent timeout:**
```
Error: Agent execution exceeded 300 seconds
→ Increase AGENT_TIMEOUT in .env
→ Check OpenAI API rate limits
```

---

## 📦 Project Contents Checklist

✅ **Core Application**
- app/__init__.py - Package initialization
- app/config.py - Configuration management
- app/tools.py - 15+ analysis tools
- app/agents.py - LangGraph agent definitions
- app/workflows.py - Multi-agent orchestration

✅ **Entry Points**
- run.py - API server (port 8000)
- run_ui.py - Web dashboard (port 8001)
- entrypoint.sh - Docker entry point

✅ **Configuration**
- requirements.txt - Python dependencies
- .env.example - Environment template
- Dockerfile - Container configuration
- metadata.json - Project metadata

✅ **Data & Examples**
- input_examples/ - 3 sample input files
- output_examples/ - 3 sample output files
- data/sample_seismic.csv - Sample seismic data
- data/sample_welllog.csv - Sample well log data

✅ **Documentation**
- README.md - Complete documentation
- DEPLOYMENT_GUIDE.md - This file
- logs/ - Execution logs directory

✅ **Utilities**
- scripts/quickstart.sh - Unix quick start
- scripts/quickstart.bat - Windows quick start

---

## 🎯 Next Steps

1. ✅ **Start the system** (run.py + run_ui.py)
2. ✅ **Access dashboard** (http://localhost:8001)
3. ✅ **Load example data** (use "Load Example Data" button)
4. ✅ **Submit analysis** (click "Submit Analysis")
5. ✅ **Review results** (comprehensive technical report)
6. ✅ **Test API** (curl examples above)
7. ✅ **Deploy to production** (Docker recommended)

---

## 📞 Support Resources

- **API Documentation**: http://localhost:8000/docs
- **System Info**: http://localhost:8000/info
- **Health Check**: http://localhost:8000/health
- **Example Inputs**: `input_examples/` directory
- **Example Outputs**: `output_examples/` directory
- **Main README**: README.md

---

**Version**: 1.0.0  
**Last Updated**: May 27, 2026  
**Status**: Production Ready
