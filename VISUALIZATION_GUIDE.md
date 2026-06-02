# 🎨 Oil & Gas Well Analytics - Visualization Guide

## Overview

The Oil & Gas Analytics system includes comprehensive visualization capabilities using **Matplotlib** and **Seaborn** for professional, publication-quality charts tailored to oil & gas exploration and production analysis.

---

## 📊 Visualization Types

### 1. **Well Log Track** - Multi-Panel Well Log Display

**Purpose**: Professional well log visualization showing all key petrophysical curves

**Data Required**:
- `depth_values`: Array of depth measurements (m)
- `gamma_ray`: Array of gamma ray values (API units)
- `resistivity`: Array of resistivity values (Ω·m)
- `porosity`: Array of porosity values (%)
- `lithology_classification`: Array of lithology types
- `fluid_type`: Array of fluid types (oil/gas/water)

**Features**:
- Gamma ray curve with fill
- Resistivity log (logarithmic scale)
- Porosity curve
- Lithology zones with color coding
- Proper depth inversion (depth increases downward)

**Example**:
```python
from app.visualizations import WellLogVisualizer

well_data = {
    "well_name": "Northfield-1",
    "depth_values": [1000, 1010, 1020, ...],
    "gamma_ray": [85, 90, 88, ...],
    "resistivity": [50, 45, 60, ...],
    "porosity": [16, 14, 18, ...],
    "lithology_classification": ["shale", "sand", "shale", ...]
}

fig = WellLogVisualizer.create_well_log_track(well_data, save_path="well_log.png")
```

---

### 2. **Lithology Distribution** - Pie Chart

**Purpose**: Show percentage distribution of rock types in well

**Data Required**:
- Dictionary with lithology types and counts

**Example**:
```python
lithology_data = {
    "Shale": 60,
    "Sand": 30,
    "Limestone": 8,
    "Coal": 2
}

fig = WellLogVisualizer.create_lithology_summary(lithology_data, save_path="lithology.png")
```

---

### 3. **Seismic Section** - Amplitude Envelope Display

**Purpose**: Visualize seismic amplitude variations with depth

**Data Required**:
- `amplitude_values`: Array of seismic amplitudes (normalized)
- `depth_values`: Array of depth measurements (m)

**Features**:
- Heatmap-style seismic section
- Overlay amplitude envelope curve
- Color bar showing amplitude intensity

**Example**:
```python
from app.visualizations import SeismicVisualizer

seismic_data = {
    "amplitude_values": [0.5, 0.8, 1.2, ...],
    "depth_values": [1000, 1010, 1020, ...]
}

fig = SeismicVisualizer.create_seismic_section(seismic_data, save_path="seismic.png")
```

---

### 4. **Fault Detection Map** - Scatter Plot

**Purpose**: Show detected fault structures with depth, throw, and confidence

**Data Required**:
- List of fault dictionaries with:
  - `depth`: Fault depth (m)
  - `throw_m`: Vertical fault displacement (m)
  - `confidence`: Confidence score (0-1)

**Features**:
- Bubble size represents fault throw
- Color represents confidence level (red=low, green=high)
- Interactive sizing

**Example**:
```python
faults = [
    {"depth": 1500, "throw_m": 100, "confidence": 0.85},
    {"depth": 2000, "throw_m": 50, "confidence": 0.72},
]

fig = SeismicVisualizer.create_fault_detection_map(faults, save_path="faults.png")
```

---

### 5. **Horizon Picks** - Line Plot

**Purpose**: Show picked seismic horizons

**Data Required**:
- List of horizon dictionaries with:
  - `name`: Horizon name
  - `depths`: Array of depths for this horizon

**Example**:
```python
horizons = [
    {"name": "Top Seal", "depths": [1000, 1010, 1020, ...]},
    {"name": "Top Reservoir", "depths": [1200, 1210, 1220, ...]},
]

fig = SeismicVisualizer.create_horizon_picks(horizons, save_path="horizons.png")
```

---

### 6. **Reservoir Properties Panel** - Multi-Panel Dashboard

**Purpose**: Comprehensive reservoir characterization visualization (4 panels)

**Data Required**:
- `depth_values`: Array of depths (m)
- `permeability_md`: Array of permeability values (mD)
- `oil_saturation`: Array of oil saturation (%)
- `water_saturation`: Array of water saturation (%)
- `gas_saturation`: Array of gas saturation (%)
- `formation_pressure_psi`: Array of formation pressure (psi)
- `porosity_percent`: Array of porosity (%)

**Panels**:
1. **Permeability vs Depth** - Semilog plot
2. **Saturation Distribution** - Stacked area chart
3. **Formation Pressure** - Line plot with fill
4. **Porosity-Permeability Crossplot** - Scatter with depth color-coding

**Example**:
```python
from app.visualizations import ReservoirVisualizer

reservoir_data = {
    "depth_values": [1000, 1010, 1020, ...],
    "permeability_md": [100, 150, 120, ...],
    "porosity_percent": [16, 14, 18, ...],
    "oil_saturation": [60, 65, 62, ...],
    "water_saturation": [30, 25, 28, ...],
    "gas_saturation": [10, 10, 10, ...],
    "formation_pressure_psi": [5000, 5005, 5010, ...]
}

fig = ReservoirVisualizer.create_reservoir_properties_panel(reservoir_data, save_path="reservoir.png")
```

---

### 7. **Saturation Heatmap** - 2D Grid Visualization

**Purpose**: Show 2D saturation distribution across lateral and vertical dimensions

**Data Required**:
- `saturation_grid`: 2D NumPy array of oil saturation values (%)

**Example**:
```python
import numpy as np

saturation_grid = np.random.rand(10, 15) * 100  # 10 depth layers x 15 lateral traces
fig = ReservoirVisualizer.create_saturation_heatmap(saturation_grid, save_path="saturation.png")
```

---

### 8. **Risk Assessment Dashboard** - Multi-Panel Risk Visualization

**Purpose**: Comprehensive risk assessment dashboard (5 panels)

**Data Required**:
```python
risk_data = {
    "overall_risk_score": 0.62,  # 0-1
    "risk_components": {
        "Source Rock": 0.75,
        "Seal Integrity": 0.65,
        "Trap Geometry": 0.45,
        "Migration Path": 0.58,
        "Charge": 0.70
    },
    "volumetric_estimates": {
        "Oil (MMBbl)": 45.5,
        "Gas (BCF)": 120.0,
        "Water": 30.0
    },
    "trap_assessment": {
        "Geometry": 0.82,
        "Closure": 0.78,
        "Configuration": 0.75
    },
    "drilling_risks": {
        "Formation Integrity": "MEDIUM",
        "Pressure Regime": "HIGH",
        "Wellbore Stability": "MEDIUM",
        "Equipment Failure": "LOW"
    }
}
```

**Panels**:
1. **Risk Score Gauge** - Color-coded risk level indicator
2. **Risk Component Breakdown** - Horizontal bar chart
3. **Volumetric Estimates** - Bar chart with values
4. **Trap Integrity Metrics** - Confidence scores
5. **Drilling Risk Assessment** - Risk matrix

**Example**:
```python
from app.visualizations import RiskAssessmentVisualizer

fig = RiskAssessmentVisualizer.create_risk_dashboard(risk_data, save_path="risk_dashboard.png")
```

---

### 9. **Volumetric Chart** - Pie & Bar Chart

**Purpose**: Show volumetric estimates in multiple formats

**Example**:
```python
volumes = {
    "Oil (MMBbl)": 45.5,
    "Gas (BCF)": 120.0,
    "Water": 30.0
}

fig = RiskAssessmentVisualizer.create_volumetric_chart(volumes, save_path="volumetrics.png")
```

---

## 🎯 API Endpoints for Visualization

### Visualize Well Log
```bash
curl -X POST http://localhost:8000/visualize/well-log \
  -H "Content-Type: application/json" \
  -d '{
    "well_name": "Test-1",
    "depth_values": [1000, 1100],
    "gamma_ray": [85, 90],
    "resistivity": [50, 45],
    "porosity": [16, 14],
    "lithology_classification": ["shale", "sand"]
  }'
```

### Visualize Seismic
```bash
curl -X POST http://localhost:8000/visualize/seismic \
  -H "Content-Type: application/json" \
  -d '{
    "amplitude_values": [0.5, 0.8, 1.2],
    "depth_values": [1000, 1100, 1200]
  }'
```

### Visualize Faults
```bash
curl -X POST http://localhost:8000/visualize/faults \
  -H "Content-Type: application/json" \
  -d '{
    "faults": [
      {"depth": 1500, "throw_m": 100, "confidence": 0.85}
    ]
  }'
```

### Visualize Reservoir
```bash
curl -X POST http://localhost:8000/visualize/reservoir \
  -H "Content-Type: application/json" \
  -d '{
    "depth_values": [1000, 1100],
    "permeability_md": [100, 150],
    "porosity_percent": [16, 14],
    "oil_saturation": [60, 65],
    "water_saturation": [30, 25],
    "gas_saturation": [10, 10],
    "formation_pressure_psi": [5000, 5005]
  }'
```

### Visualize Risk
```bash
curl -X POST http://localhost:8000/visualize/risk \
  -H "Content-Type: application/json" \
  -d '{
    "overall_risk_score": 0.62,
    "risk_components": {...},
    "volumetric_estimates": {...},
    "trap_assessment": {...},
    "drilling_risks": {...}
  }'
```

### List Visualization Examples
```bash
curl http://localhost:8000/visualize/examples
```

---

## 🚀 Generating Sample Visualizations

Run the provided script to generate all sample visualizations:

```bash
python scripts/generate_visualizations.py
```

This will create:
- `01_well_log_track.png` - Professional well log display
- `02_lithology_distribution.png` - Lithology pie chart
- `03_seismic_section.png` - Seismic amplitude display
- `04_fault_detection.png` - Fault scatter plot
- `05_horizon_picks.png` - Horizon picking lines
- `06_reservoir_properties.png` - 4-panel reservoir dashboard
- `07_risk_dashboard.png` - 5-panel risk assessment
- `08_volumetric_chart.png` - Volumetric estimates
- `09_saturation_heatmap.png` - Saturation 2D grid
- `analysis_report.html` - Interactive HTML report

---

## 🎨 Color Scheme

Oil & Gas specific color palette:

```
OIL_COLOR = "#8B4513"        # Brown
GAS_COLOR = "#FFD700"        # Gold
WATER_COLOR = "#4A90E2"      # Blue
ROCK_COLOR = "#A9A9A9"       # Gray
SHALE_COLOR = "#2F4F4F"      # Dark slate gray
SAND_COLOR = "#DEB887"       # Burlywood
FAULT_COLOR = "#FF0000"      # Red
TRAP_COLOR = "#00AA00"       # Green
```

---

## 💾 Saving Visualizations

### Save to File
```python
from app.visualizations import WellLogVisualizer

fig = WellLogVisualizer.create_well_log_track(well_data)
fig.savefig("my_visualization.png", dpi=300, bbox_inches='tight')
```

### Convert to Base64 (for web)
```python
from app.visualizations import ComprehensiveAnalysisVisualizer

fig = WellLogVisualizer.create_well_log_track(well_data)
base64_image = ComprehensiveAnalysisVisualizer.figure_to_base64(fig)
# Use in HTML: <img src="data:image/png;base64,{base64_image}">
```

### Generate HTML Report
```python
from app.visualizations import ComprehensiveAnalysisVisualizer

analysis_results = {...}  # Full analysis output
html_path = ComprehensiveAnalysisVisualizer.create_html_report(
    analysis_results, 
    output_path="my_report.html"
)
```

---

## 📈 Integration with Analysis Pipeline

Visualizations can be automatically generated for analysis results:

```python
from app.visualizations import ComprehensiveAnalysisVisualizer

# After analysis completes
analysis_results = orchestrator.execute_full_analysis(user_input)

# Generate all visualizations
viz_files = ComprehensiveAnalysisVisualizer.create_analysis_summary_report(
    analysis_results,
    output_dir="./output_examples"
)

# viz_files = {
#     'well_log': 'path/to/well_log.png',
#     'seismic': 'path/to/seismic_section.png',
#     'faults': 'path/to/faults.png',
#     'reservoir': 'path/to/reservoir.png',
#     'risk': 'path/to/risk_dashboard.png'
# }
```

---

## 🔧 Customization

### Adjust Figure Size
```python
import matplotlib.pyplot as plt

plt.rcParams['figure.figsize'] = (16, 10)  # Width x Height in inches
```

### Adjust DPI (Resolution)
```python
fig.savefig("output.png", dpi=600)  # Higher DPI = higher resolution
```

### Change Color Palette
```python
import seaborn as sns

sns.set_palette("husl")  # Use different seaborn palette
```

### Modify Fonts
```python
plt.rcParams['font.size'] = 12
plt.rcParams['axes.titlesize'] = 14
```

---

## 📋 Dependencies

The visualization module requires:
- `matplotlib==3.9.2` - Plotting library
- `seaborn==0.13.2` - Statistical visualization
- `numpy==2.4.0` - Numerical operations
- `pandas==2.2.3` - Data manipulation

All included in `requirements.txt`

---

## ✅ Quality Assurance

All visualizations:
- ✅ Use publication-quality settings (300 DPI for export)
- ✅ Include clear titles, labels, and legends
- ✅ Use appropriate scales (logarithmic where needed)
- ✅ Have proper depth inversion for well data
- ✅ Include grid lines for readability
- ✅ Use oil & gas industry standard colors
- ✅ Support base64 encoding for web display
- ✅ Generate professional PNG outputs

