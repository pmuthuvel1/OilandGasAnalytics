# 🧠 Multi-Agent Interaction Architecture

## 📊 Full Analysis Workflow (5 Agents)

```mermaid
graph TD
    START([User Input:<br/>Well Data & Seismic]) --> SEISMIC["🔷 SeismicAnalyzer<br/>Detect Faults, Pick Horizons<br/>Identify Amplitude Anomalies"]
    
    SEISMIC -->|seismic_findings| WELLLOG["🟦 WellLogInterpreter<br/>Classify Lithology<br/>Identify Fluids<br/>Estimate Porosity"]
    
    WELLLOG -->|well_log_findings| RESERVOIR["🟩 ReservoirCharacterizer<br/>Estimate Permeability<br/>Analyze Saturation<br/>Predict Formation Pressure"]
    
    RESERVOIR -->|reservoir_properties| RISK["🟧 ExplorationRiskAssessor<br/>Evaluate Trap Integrity<br/>Calculate Reserves<br/>Assess Drilling Risk"]
    
    RISK -->|risk_findings| REPORT["📄 ReportGenerator<br/>Synthesize All Findings<br/>Create Recommendations<br/>Format for Stakeholders"]
    
    REPORT --> END([✅ Final Report<br/>Executive Summary<br/>Technical Findings<br/>Drilling Recommendations])
    
    style START fill:#e1f5ff
    style END fill:#c8e6c9
    style SEISMIC fill:#bbdefb
    style WELLLOG fill:#b3e5fc
    style RESERVOIR fill:#b2dfdb
    style RISK fill:#ffe0b2
    style REPORT fill:#f5f5f5
```

---

## ⚡ Quick Analysis Workflow (3 Agents)

```mermaid
graph TD
    START([User Input:<br/>Well Data & Seismic]) --> WELLLOG["🟦 WellLogInterpreter<br/>Classify Lithology<br/>Identify Fluids<br/>Estimate Porosity"]
    
    WELLLOG -->|well_log_findings| RISK["🟧 ExplorationRiskAssessor<br/>Evaluate Trap Integrity<br/>Calculate Reserves<br/>Assess Drilling Risk"]
    
    RISK -->|risk_findings| REPORT["📄 ReportGenerator<br/>Synthesize Key Findings<br/>Create Recommendations"]
    
    REPORT --> END([✅ Quick Report<br/>Key Findings<br/>Drilling Recommendations])
    
    style START fill:#e1f5ff
    style END fill:#c8e6c9
    style WELLLOG fill:#b3e5fc
    style RISK fill:#ffe0b2
    style REPORT fill:#f5f5f5
```

---

## 🔄 Agent Data Flow & State Management

```mermaid
graph LR
    subgraph "Input State"
        INPUT["workflow_id<br/>user_input<br/>messages<br/>errors"]
    end
    
    subgraph "Seismic Agent"
        SA["📌 Analyzes Seismic Data<br/><br/>Tools:<br/>• analyze_seismic_amplitude<br/>• detect_faults<br/>• pick_horizons<br/><br/>Output: seismic_analysis"]
    end
    
    subgraph "Well Log Agent"
        WL["📌 Interprets Well Logs<br/><br/>Tools:<br/>• classify_lithology<br/>• identify_fluids<br/>• estimate_porosity<br/>• estimate_permeability<br/>• analyze_saturation<br/>• predict_pressure<br/><br/>Input: user_input<br/>Output: well_log_analysis"]
    end
    
    subgraph "Reservoir Agent"
        RC["📌 Characterizes Reservoir<br/><br/>Input: seismic_findings<br/>well_log_findings<br/><br/>Tools:<br/>• All well log tools<br/>• Additional pressure modeling<br/><br/>Output: reservoir_analysis"]
    end
    
    subgraph "Risk Agent"
        RA["📌 Assesses Exploration Risk<br/><br/>Input: seismic_interpretation<br/>petrophysics<br/>reservoir_properties<br/><br/>Tools:<br/>• evaluate_trap_integrity<br/>• calculate_volumetrics<br/>• assess_drilling_risk<br/><br/>Output: risk_assessment"]
    end
    
    subgraph "Report Agent"
        RG["📌 Generates Report<br/><br/>Input: All 4 previous outputs<br/>workflow_id<br/>errors<br/><br/>Tools:<br/>• synthesize_analysis<br/>• format_recommendations<br/><br/>Output: final_report"]
    end
    
    INPUT --> SA
    SA --> WL
    WL --> RC
    RC --> RA
    RA --> RG
    
    style INPUT fill:#e1f5ff
    style SA fill:#bbdefb
    style WL fill:#b3e5fc
    style RC fill:#b2dfdb
    style RA fill:#ffe0b2
    style RG fill:#f5f5f5
```

---

## 🎯 Agent Coordination Mechanism

```mermaid
graph TD
    subgraph "Execution Model"
        A["WorkflowOrchestrator<br/>(run_api or run_ui)"]
        B["AgentExecutorManager<br/>(Manages LLM calls)"]
        C["LangGraph StateGraph<br/>(Defines workflow edges)"]
    end
    
    subgraph "Node Execution"
        N1["create_seismic_analysis_node"]
        N2["create_well_log_analysis_node"]
        N3["create_reservoir_analysis_node"]
        N4["create_risk_assessment_node"]
        N5["create_report_generation_node"]
    end
    
    subgraph "Specialized Agents"
        AG1["seismic_analyzer<br/>ChatOpenAI + Tools"]
        AG2["well_log_interpreter<br/>ChatOpenAI + Tools"]
        AG3["reservoir_characterizer<br/>ChatOpenAI + Tools"]
        AG4["exploration_risk_assessor<br/>ChatOpenAI + Tools"]
        AG5["report_generator<br/>ChatOpenAI + Tools"]
    end
    
    A -->|invokes| B
    B -->|orchestrates| C
    C -->|creates| N1
    C -->|creates| N2
    C -->|creates| N3
    C -->|creates| N4
    C -->|creates| N5
    
    N1 -->|executes| AG1
    N2 -->|executes| AG2
    N3 -->|executes| AG3
    N4 -->|executes| AG4
    N5 -->|executes| AG5
    
    AG1 -->|uses| T1["15+ Domain Tools"]
    AG2 -->|uses| T1
    AG3 -->|uses| T1
    AG4 -->|uses| T1
    AG5 -->|uses| T1
    
    style A fill:#bbdefb
    style B fill:#b3e5fc
    style C fill:#b2dfdb
    style T1 fill:#f8bbd0
```

---

## 📤 Complete State Transitions

```mermaid
stateDiagram-v2
    [*] --> InitialState: User submits analysis request
    
    InitialState --> SeismicAnalysis: workflow_id, user_input added
    
    SeismicAnalysis --> SeismicDone: seismic_analysis populated
    SeismicDone --> WellLogAnalysis: State passed with seismic results
    
    WellLogAnalysis --> WellLogDone: well_log_analysis populated
    WellLogDone --> ReservoirAnalysis: State includes seismic + welllog findings
    
    ReservoirAnalysis --> ReservoirDone: reservoir_analysis populated
    ReservoirDone --> RiskAssessment: State includes all 3 prior analyses
    
    RiskAssessment --> RiskDone: risk_assessment populated
    RiskDone --> ReportGeneration: State includes all 4 analyses
    
    ReportGeneration --> ReportDone: final_report populated
    ReportDone --> [*]: Complete with comprehensive analysis
    
    SeismicAnalysis --> ErrorHandled: Error in agent execution
    WellLogAnalysis --> ErrorHandled: Error in agent execution
    ReservoirAnalysis --> ErrorHandled: Error in agent execution
    RiskAssessment --> ErrorHandled: Error in agent execution
    ReportGeneration --> ErrorHandled: Error in agent execution
    
    ErrorHandled --> [*]: Return partial results + error details
```

---

## 🛠️ Tool Distribution Across Agents

```mermaid
graph LR
    TOOLS["15+ Domain Tools"]
    
    TOOLS --> SEISMIC["SeismicAnalyzer<br/>3 tools<br/>Amplitude Analysis<br/>Fault Detection<br/>Horizon Picking"]
    TOOLS --> WELLLOG["WellLogInterpreter<br/>6 tools<br/>Lithology Classification<br/>Fluid ID<br/>Porosity/Permeability<br/>Saturation<br/>Pressure Prediction"]
    TOOLS --> RESERVOIR["ReservoirCharacterizer<br/>4+ tools<br/>Permeability Est.<br/>Saturation Analysis<br/>Pressure Modeling<br/>Flow Characteristics"]
    TOOLS --> RISK["ExplorationRiskAssessor<br/>3+ tools<br/>Trap Evaluation<br/>Volumetric Calc<br/>Risk Assessment"]
    TOOLS --> REPORT["ReportGenerator<br/>2 tools<br/>Analysis Synthesis<br/>Recommendation Format"]
    
    style TOOLS fill:#f8bbd0
    style SEISMIC fill:#bbdefb
    style WELLLOG fill:#b3e5fc
    style RESERVOIR fill:#b2dfdb
    style RISK fill:#ffe0b2
    style REPORT fill:#f5f5f5
```

---

## 📋 Agent Specialization & Responsibilities

| Agent | Role | Input Dependencies | Output | Tools Used |
|-------|------|-------------------|--------|-----------|
| **SeismicAnalyzer** 🔷 | Subsurface interpretation | User seismic data | Fault maps, horizon picks | 3 seismic tools |
| **WellLogInterpreter** 🟦 | Petrophysics analysis | User well log data | Lithology, fluids, porosity | 6 well log tools |
| **ReservoirCharacterizer** 🟩 | Property estimation | Seismic + well log findings | Permeability, saturation, pressure | 4+ reservoir tools |
| **ExplorationRiskAssessor** 🟧 | Risk & volumetrics | All prior analyses | Reserves, trap integrity, risk score | 3+ risk tools |
| **ReportGenerator** 📄 | Synthesis & recommendations | All 4 analyses + errors | Executive summary, recommendations | 2 formatting tools |

---

## 🔗 Data Flow Example: Full Analysis

```
User Input:
├── well_name: "Northfield-1"
├── seismic_data: [amplitude values, depth]
└── well_log_data: [gamma_ray, resistivity, porosity]

↓ SeismicAnalyzer executes

seismic_analysis:
├── amplitude_anomalies: [...]
├── fault_structures: [...]
└── horizon_picks: [...]

↓ WellLogInterpreter executes

well_log_analysis:
├── lithology_classes: [...]
├── fluid_types: [...]
└── porosity_estimates: [...]

↓ ReservoirCharacterizer receives BOTH seismic_analysis + well_log_analysis

reservoir_analysis:
├── permeability_model: [...]
├── saturation_distribution: [...]
└── formation_pressure: [...]

↓ ExplorationRiskAssessor receives seismic + welllog + reservoir data

risk_assessment:
├── trap_integrity_score: 0.85
├── volumetric_estimate: 50MMBbl
└── drilling_risk: HIGH

↓ ReportGenerator synthesizes ALL findings

final_report:
├── executive_summary: "High-confidence structural trap..."
├── technical_findings: [consolidated results]
└── drilling_recommendations: ["Drill at 3500m TVD"]

Output delivered to user via API or Dashboard
```

---

## 🎛️ Workflow Orchestration Details

### **Execution Model**
- **LangGraph-based state machine** with 5-node directed graph
- **Sequential execution** with state carry-over between agents
- **Error handling** at each node (errors collected in state list)
- **Message logging** for audit trail and debugging

### **State Management** (AnalysisState)
- `workflow_id`: Unique execution identifier
- `user_input`: Original analysis request
- `seismic_analysis`: 1st agent output
- `well_log_analysis`: 2nd agent output
- `reservoir_analysis`: 3rd agent output
- `risk_assessment`: 4th agent output
- `final_report`: 5th agent output (synthesis)
- `messages`: Execution log (timestamps, completion status)
- `errors`: Error collection (for resilience)

### **Recovery Mechanism**
- Each agent captures errors in state without stopping workflow
- Final report includes error summary
- Partial results returned to user if errors occur
- Allows graceful degradation instead of complete failure

---

## 🚀 Deployment Architecture

```mermaid
graph LR
    USER["👤 User"]
    
    USER -->|HTTP| API["🔧 API Server<br/>port 8000<br/>run.py"]
    USER -->|Browser| UI["🖥️ Web Dashboard<br/>port 8001<br/>run_ui.py"]
    
    API -->|creates| WO["WorkflowOrchestrator"]
    UI -->|creates| WO
    
    WO -->|instantiates| MGR["AgentExecutorManager"]
    MGR -->|calls| LLM["ChatOpenAI<br/>GPT-4<br/>OPENAI_API_KEY"]
    
    MGR -->|executes| G["LangGraph<br/>Workflow"]
    G -->|runs| N["5 Agent Nodes<br/>Sequential<br/>State Passing"]
    
    N -->|calls| TOOLS["Tool Registry<br/>15+ Domain Tools"]
    TOOLS -->|returns| N
    
    N -->|completes| OUTPUT["Final Report<br/>JSON"]
    OUTPUT -->|returns| API
    OUTPUT -->|renders| UI
    
    style USER fill:#e8f5e9
    style API fill:#bbdefb
    style UI fill:#b3e5fc
    style WO fill:#b2dfdb
    style MGR fill:#ffe0b2
    style LLM fill:#f8bbd0
    style TOOLS fill:#ffccbc
    style OUTPUT fill:#c8e6c9
```

