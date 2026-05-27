# Oil & Gas Analytics Multi-Agent AI System

**Production-ready multi-agent AI system using LangGraph for oil & gas exploration, well analysis, and reservoir characterization.**

---

## 🎯 Project Overview

This is a **real, deployable multi-agent AI system** that solves genuine business problems in oil & gas exploration and production. It orchestrates 5 specialized AI agents using LangGraph to perform comprehensive subsurface analysis:

- **SeismicAnalyzer**: Interprets seismic data for structural traps and hydrocarbon indicators
- **WellLogInterpreter**: Classifies lithology, identifies fluids, and estimates reservoir quality
- **ReservoirCharacterizer**: Predicts permeability, saturation, and formation pressures
- **ExplorationRiskAssessor**: Evaluates trap integrity, calculates reserves, assesses drilling risks
- **ReportGenerator**: Synthesizes findings into actionable technical reports

### Key Capabilities

✅ Multi-well concurrent analysis  
✅ Seismic interpretation & fault detection  
✅ Well log petrophysics & lithology classification  
✅ Reservoir property estimation & pressure prediction  
✅ Volumetric calculation & risk assessment  
✅ Technical report generation with recommendations  
✅ Batch analysis and workflow history tracking  

---

## 📋 Prerequisites

- **Python 3.11+**
- **OpenAI API Key** (GPT-4 or compatible)
- **Docker** (optional, for containerized deployment)
- **8GB RAM minimum** for concurrent agent execution

---

## 🚀 Quick Start

### 1. Clone/Setup Project

```bash
cd OilandGasAnalytics
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 4. Run the System

**Option A: Docker (Recommended)**
```bash
docker build -t oil-gas-analytics .
docker run -p 8000:8000 -p 8001:8001 --env-file .env oil-gas-analytics
```

**Option B: Direct Python**

Terminal 1 - Start API (port 8000):
```bash
python run.py
```

Terminal 2 - Start UI (port 8001):
```bash
python run_ui.py
```

### 5. Access the System

- **API Documentation**: http://localhost:8000/docs
- **Dashboard UI**: http://localhost:8001
- **Health Check**: http://localhost:8000/health

---

## 📁 Project Structure

```
OilandGasAnalytics/
│
├── app/                           # Core agent logic
│   ├── __init__.py               # Package initialization
│   ├── config.py                 # Configuration management
│   ├── tools.py                  # 15+ analysis tools
│   ├── agents.py                 # LangGraph agent definitions
│   └── workflows.py              # Multi-agent orchestration
│
├── data/                          # Static datasets & uploads
│   ├── sample_seismic.csv        # Example seismic data
│   ├── sample_welllog.csv        # Example well log data
│   └── uploads/                  # User-uploaded files
│
├── scripts/                       # Helper utilities
│   └── (optional batch processors)
│
├── input_examples/               # 3+ sample input files
│   ├── example_1_northfield.json
│   ├── example_2_central_basin.json
│   └── example_3_eastern.json
│
├── output_examples/              # 3+ sample outputs
│   ├── example_1_northfield_output.json
│   ├── example_2_central_basin_output.json
│   └── example_3_eastern_quick_output.json
│
├── logs/                         # Agent interaction logs
│   └── agent_logs.json
│
├── run.py                        # API entry point (port 8000)
├── run_ui.py                     # UI entry point (port 8001)
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container configuration
├── entrypoint.sh                 # Docker startup script
├── .env.example                  # Environment variables template
├── metadata.json                 # Project metadata
└── README.md                     # This file
```

---

## 🔧 Usage

### A. Via Dashboard UI (http://localhost:8001)

1. **Submit Analysis**
   - Enter well name
   - Choose analysis type (full/quick)
   - Paste seismic & well log data (JSON)
   - Click "Submit Analysis"

2. **View Results**
   - See comprehensive multi-agent analysis
   - Review findings from each agent
   - Access technical recommendations

3. **Check History**
   - View all previous analysis workflows
   - Download logs and reports

### B. Via REST API

**Submit Analysis Request**
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @input_examples/example_1_northfield.json
```

**Response**
```json
{
  "workflow_id": "2026-05-27T14:30:45.123456",
  "status": "success",
  "results": {
    "seismic_analysis": {...},
    "well_log_analysis": {...},
    "reservoir_analysis": {...},
    "risk_assessment": {...},
    "final_report": {...}
  },
  "timestamp": "2026-05-27T14:35:12.654321"
}
```

**Get Workflow History**
```bash
curl http://localhost:8000/workflows/history
```

**List Available Tools**
```bash
curl http://localhost:8000/tools
```

**Execute Single Tool**
```bash
curl -X POST http://localhost:8000/tools/analyze_seismic_amplitude \
  -H "Content-Type: application/json" \
  -d '{"amplitude_values": [0.5, 1.2, 2.3, 1.8]}'
```

---

## 📊 API Endpoints

### Analysis
- `POST /analyze` - Submit analysis request
- `POST /analyze/batch` - Batch analysis on multiple wells
- `GET /workflows/history` - Retrieve analysis history
- `DELETE /workflows/history` - Clear history

### Tools
- `GET /tools` - List all available tools
- `POST /tools/{tool_name}` - Execute specific tool

### Data Upload
- `POST /upload/seismic` - Upload seismic data
- `POST /upload/well-log` - Upload well log data

### System
- `GET /` - Root endpoint with API info
- `GET /health` - Health check
- `GET /info` - System information
- `GET /logs/download` - Download analysis logs

---

## 🧠 Agent Architecture

### Agent Sequence (Full Analysis)

```
1. SeismicAnalyzer
   ├─ Analyze amplitude anomalies
   ├─ Detect fault structures
   └─ Pick seismic horizons
       ↓
2. WellLogInterpreter
   ├─ Classify lithology
   ├─ Identify fluid types
   └─ Estimate porosity
       ↓
3. ReservoirCharacterizer
   ├─ Estimate permeability
   ├─ Analyze saturation
   └─ Predict pressure
       ↓
4. ExplorationRiskAssessor
   ├─ Evaluate trap geometry
   ├─ Calculate volumetric reserves
   └─ Assess seal integrity
       ↓
5. ReportGenerator
   ├─ Synthesize all findings
   ├─ Create visualizations
   └─ Format recommendations
```

### Data Flow

```
User Input (Seismic + Well Logs)
    ↓
[Multi-Agent Workflow via LangGraph]
    ↓
Parallel Tool Execution (15+ specialized tools)
    ↓
Inter-Agent Communication & Context Passing
    ↓
Consolidated Technical Report
    ↓
Actionable Business Recommendations
```

---

## 💾 Data Formats

### Input - Seismic Data

```json
{
  "well_name": "Well-001",
  "depth_values": [1000, 1100, 1200, ...],
  "amplitude_values": [0.5, 1.2, 2.3, ...],
  "frequency_content": {
    "low_freq_10_20Hz": 0.25,
    "mid_freq_20_50Hz": 0.5,
    "high_freq_50_100Hz": 0.25
  }
}
```

### Input - Well Log Data

```json
{
  "well_name": "Well-001",
  "depth_values": [2000, 2100, 2200, ...],
  "gamma_ray": [85, 78, 125, ...],
  "resistivity": [45, 135, 28, ...],
  "porosity": [16, 24, 6, ...],
  "depth_unit": "feet"
}
```

### Output - Analysis Results

See `output_examples/` for complete examples including:
- Seismic interpretation findings
- Petrophysical analysis
- Reservoir characterization
- Risk assessment metrics
- Technical recommendations
- Executive summaries

---

## 🔬 Analysis Tools Reference

### Seismic Analysis (3 tools)
| Tool | Purpose | Output |
|------|---------|--------|
| `analyze_seismic_amplitude` | Detect bright spots, anomalies | Amplitude statistics, anomaly count |
| `detect_faults` | Identify fault structures | Fault locations, severity score |
| `pick_horizons` | Identify seismic reflectors | Horizon depths, amplitudes |

### Well Log Interpretation (3 tools)
| Tool | Purpose | Output |
|------|---------|--------|
| `classify_lithology` | Rock type identification | Lithology class, quality score |
| `identify_fluids` | Fluid type detection | Fluid type, confidence, saturation |
| `estimate_porosity` | Porosity prediction | Porosity range, quality grade |

### Reservoir Characterization (3 tools)
| Tool | Purpose | Output |
|------|---------|--------|
| `estimate_permeability` | Flow capacity prediction | Permeability (md), quality class |
| `analyze_saturation` | Fluid saturation calculation | Water/HC saturation ratio |
| `predict_pressure` | Formation pressure estimation | Pressure (psi), abnormality detection |

### Exploration Risk (3 tools)
| Tool | Purpose | Output |
|------|---------|--------|
| `evaluate_trap` | Trap geometry assessment | Trap integrity score, risk level |
| `calculate_volumes` | Volumetric estimation | GRV, stock tank volume, recoverable reserves |
| `assess_seal_integrity` | Seal quality evaluation | Seal integrity score, leakage risk |

### Reporting (3 tools)
| Tool | Purpose | Output |
|------|---------|--------|
| `synthesize_analysis` | Multi-agent result consolidation | Summary statistics |
| `create_visualizations` | Visualization specifications | Chart types, data fields |
| `format_recommendations` | Business recommendations | Action items, next steps |

---

## 📈 Example Workflow: Real Analysis

**Input**: North Field-001 well data (see `input_examples/example_1_northfield.json`)

**Workflow Execution** (~5 minutes for full analysis):

1. **Seismic Analysis** → Detects 3 bright spots, identifies 2 faults, picks 4 horizons
2. **Well Log Interpretation** → Confirms sandstone with 18.5% porosity, identifies oil bearing
3. **Reservoir Characterization** → Estimates 6,300 md permeability, 75% HC saturation
4. **Risk Assessment** → Evaluates trap, calculates 6.2 MMbbl recoverable, low risk
5. **Report Generation** → Creates technical report with drilling recommendations

**Output**: Comprehensive analysis with executive summary, technical findings, and business recommendations

---

## 🚢 Deployment

### Docker Deployment

**Build**
```bash
docker build -t oil-gas-analytics:latest .
```

**Run**
```bash
docker run -d \
  --name oil-analytics \
  -p 8000:8000 \
  -p 8001:8001 \
  --env-file .env \
  oil-gas-analytics:latest
```

**View Logs**
```bash
docker logs oil-analytics -f
```

### Cloud Deployment (AWS/GCP/Azure)

1. **Push to Registry**
   ```bash
   docker tag oil-gas-analytics:latest myregistry/oil-analytics:latest
   docker push myregistry/oil-analytics:latest
   ```

2. **Deploy to Kubernetes**
   ```bash
   kubectl apply -f deployment.yaml
   kubectl expose deployment oil-analytics --port=8000,8001
   ```

3. **Environment Variables**
   - Set `OPENAI_API_KEY` via ConfigMap/Secrets
   - Configure persistence volumes for `logs/` and `data/`

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```
# OpenAI Configuration
OPENAI_API_KEY=sk-... (required)
OPENAI_MODEL=gpt-4

# Server Configuration
API_PORT=8000
UI_PORT=8001
HOST=0.0.0.0

# Agent Configuration
MAX_ITERATIONS=10
AGENT_TIMEOUT=300

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/agent_logs.json

# Data
DATA_PATH=data/
MAX_FILE_SIZE=500000000
```

### Agent Configuration (`app/config.py`)

Modify `AGENT_CONFIGS` dictionary to customize agent behavior, tools, and prompts.

---

## 📊 Sample Data & Examples

### Run with Examples

```bash
# Load example 1: North Field exploration
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @input_examples/example_1_northfield.json

# Load example 2: Central Basin development
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @input_examples/example_2_central_basin.json

# Load example 3: Quick farm-out assessment
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @input_examples/example_3_eastern.json
```

### Output Examples

See `output_examples/` directory for complete analysis outputs including:
- Full technical reports
- Executive summaries
- Volumetric calculations
- Risk assessments
- Drilling recommendations

---

## 🔍 Logging & Monitoring

### Application Logs

- **Location**: `logs/agent_logs.json`
- **Format**: JSON lines with analysis metadata
- **Contains**: Workflow IDs, agent execution times, errors, findings summary

### Download Logs

```bash
curl http://localhost:8000/logs/download -o agent_logs.json
```

### Monitor Agent Execution

```bash
# Watch real-time logs
tail -f logs/agent_logs.json | jq .

# View specific workflow
grep "workflow_id" logs/agent_logs.json | jq .
```

---

## 🧪 Testing

### Test with Sample Data

```bash
# Test seismic analyzer
python -c "
from app.tools import analyze_seismic_amplitude
result = analyze_seismic_amplitude({'amplitude_values': [0.5, 1.2, 2.3, 1.8]})
print(result)
"

# Test well log interpreter
python -c "
from app.tools import classify_lithology
result = classify_lithology({'gamma_ray': [85, 120], 'resistivity': [50, 30]})
print(result)
"
```

### Integration Tests

```bash
# Run API health check
curl http://localhost:8000/health

# Test analysis endpoint
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"well_name": "test", "analysis_type": "quick", "well_log_data": {"gamma_ray": [80], "resistivity": [100], "porosity": [20]}}'
```

---

## 📚 Real-World Use Cases

### 1. Exploration Well Pre-Drill Assessment
- Analyze seismic for trap geometry
- Interpret analog well data
- Calculate volumetric ranges
- Assess drilling risks
- Generate AFE documentation

### 2. Development Well Placement Optimization
- Analyze reservoir properties across field
- Identify high-porosity zones
- Assess fault connectivity
- Optimize well spacing
- Predict production rates

### 3. Farm-Out Due Diligence
- Quick multi-prospect analysis
- Risk ranking for portfolio
- Volumetric comparison
- Seal integrity assessment
- Executive summary generation

### 4. Acquisition Evaluation
- Rapid basin assessment
- Comparative volumetric analysis
- Trap integrity evaluation
- Business case development
- Recommendation reports

### 5. Enhanced Oil Recovery Planning
- Reservoir characterization
- Pressure/saturation mapping
- Injection point optimization
- Production history correlation
- Scenario analysis

---

## 🐛 Troubleshooting

### Issue: API Connection Error
```
Error: Failed to connect to API at localhost:8000
```
**Solution**: Ensure `python run.py` is running in a terminal

### Issue: OpenAI API Error
```
Error: Invalid API key or API key not found
```
**Solution**: 
1. Verify `OPENAI_API_KEY` is set in `.env`
2. Check API key has GPT-4 access
3. Verify API key hasn't expired

### Issue: Agent Timeout
```
Error: Agent execution exceeded timeout (300s)
```
**Solution**: 
1. Increase `AGENT_TIMEOUT` in `.env`
2. Reduce data size in request
3. Check OpenAI API rate limits

### Issue: Memory Issues
```
MemoryError: Unable to allocate memory
```
**Solution**:
1. Close other applications
2. Reduce batch size for batch analysis
3. Process smaller datasets

---

## 📞 Support & Documentation

- **API Docs**: http://localhost:8000/docs
- **Example Inputs**: `input_examples/` directory
- **Example Outputs**: `output_examples/` directory
- **System Info**: http://localhost:8000/info
- **Available Tools**: http://localhost:8000/tools

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🤝 Contributing

This is a production-ready system. For contributions:

1. Test with provided examples
2. Maintain backward compatibility
3. Update documentation
4. Follow existing code patterns

---

## 🎓 Architecture Highlights

✅ **Production-Ready**: Deployed with real business workflows  
✅ **Scalable**: Handles concurrent analyses with queue management  
✅ **Extensible**: Easy to add new agents and tools  
✅ **Observable**: Comprehensive logging and monitoring  
✅ **Validated**: 3+ complete end-to-end examples included  
✅ **Documented**: Full API documentation and user guides  

---

**Last Updated**: May 27, 2026  
**Version**: 1.0.0  
**Status**: Production Ready
