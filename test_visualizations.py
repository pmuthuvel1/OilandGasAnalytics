"""Test visualization module"""
import sys
sys.path.insert(0, '.')

from app.visualizations import (
    WellLogVisualizer,
    SeismicVisualizer,
    ReservoirVisualizer,
    RiskAssessmentVisualizer,
)
import numpy as np
from pathlib import Path

# Create output directory
output_dir = Path("output_examples/visualizations")
output_dir.mkdir(parents=True, exist_ok=True)

print("🎨 Testing Oil & Gas Well Analytics Visualizations\n")
print("=" * 70)

# Sample data
well_data = {
    "well_name": "Northfield-1",
    "depth_values": list(range(1000, 3000, 10)),
    "gamma_ray": [85 + (i % 50) for i in range(200)],
    "resistivity": [50 + (i % 100) for i in range(200)],
    "porosity": [16 + (i % 15) for i in range(200)],
    "lithology_classification": ["shale", "sand", "shale", "sandstone"] * 50,
}

seismic_data = {
    "amplitude_values": [0.5 + 0.3 * (i % 10) for i in range(200)],
    "depth_values": list(range(1000, 3000, 10)),
}

faults = [
    {"depth": 1500, "throw_m": 100, "confidence": 0.85},
    {"depth": 2000, "throw_m": 50, "confidence": 0.72},
]

reservoir_data = {
    "depth_values": list(range(1000, 3000, 10)),
    "permeability_md": [100 + (i % 500) for i in range(200)],
    "porosity_percent": [16 + (i % 15) for i in range(200)],
    "oil_saturation": [60 + (i % 30) for i in range(200)],
    "water_saturation": [30 + (i % 20) for i in range(200)],
    "gas_saturation": [10 + (i % 15) for i in range(200)],
    "formation_pressure_psi": [5000 + i * 0.5 for i in range(200)],
}

risk_data = {
    "overall_risk_score": 0.62,
    "risk_components": {
        "Source Rock": 0.75,
        "Seal Integrity": 0.65,
        "Trap Geometry": 0.45,
    },
    "volumetric_estimates": {
        "Oil (MMBbl)": 45.5,
        "Gas (BCF)": 120.0,
    },
    "trap_assessment": {
        "Geometry": 0.82,
        "Closure": 0.78,
    },
    "drilling_risks": {
        "Formation Integrity": "MEDIUM",
        "Pressure Regime": "HIGH",
    },
}

try:
    # 1. Well Log
    print("\n✓ 1. Creating well log visualization...")
    fig = WellLogVisualizer.create_well_log_track(well_data)
    fig.savefig(str(output_dir / "01_well_log.png"), dpi=150, bbox_inches='tight')
    print(f"  Saved: output_examples/visualizations/01_well_log.png")
    
    # 2. Seismic
    print("\n✓ 2. Creating seismic visualization...")
    fig = SeismicVisualizer.create_seismic_section(seismic_data)
    fig.savefig(str(output_dir / "02_seismic.png"), dpi=150, bbox_inches='tight')
    print(f"  Saved: output_examples/visualizations/02_seismic.png")
    
    # 3. Faults
    print("\n✓ 3. Creating fault detection visualization...")
    fig = SeismicVisualizer.create_fault_detection_map(faults)
    fig.savefig(str(output_dir / "03_faults.png"), dpi=150, bbox_inches='tight')
    print(f"  Saved: output_examples/visualizations/03_faults.png")
    
    # 4. Reservoir
    print("\n✓ 4. Creating reservoir properties visualization...")
    fig = ReservoirVisualizer.create_reservoir_properties_panel(reservoir_data)
    fig.savefig(str(output_dir / "04_reservoir.png"), dpi=150, bbox_inches='tight')
    print(f"  Saved: output_examples/visualizations/04_reservoir.png")
    
    # 5. Risk
    print("\n✓ 5. Creating risk assessment visualization...")
    fig = RiskAssessmentVisualizer.create_risk_dashboard(risk_data)
    fig.savefig(str(output_dir / "05_risk_dashboard.png"), dpi=150, bbox_inches='tight')
    print(f"  Saved: output_examples/visualizations/05_risk_dashboard.png")
    
    print("\n" + "=" * 70)
    print("\n✅ All visualizations generated successfully!")
    print(f"\n📁 Output location: {output_dir.absolute()}\n")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
