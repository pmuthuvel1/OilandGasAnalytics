"""Example script demonstrating Oil & Gas Well Analytics visualization capabilities."""

import json
from pathlib import Path
from app.visualizations import (
    WellLogVisualizer,
    SeismicVisualizer,
    ReservoirVisualizer,
    RiskAssessmentVisualizer,
    ComprehensiveAnalysisVisualizer,
)

# Sample well log data
SAMPLE_WELL_LOG = {
    "well_name": "Northfield-1",
    "depth_values": list(range(1000, 3000, 10)),
    "gamma_ray": [85 + (i % 50) for i in range(200)],
    "resistivity": [50 + (i % 100) for i in range(200)],
    "porosity": [16 + (i % 15) for i in range(200)],
    "lithology_classification": ["shale", "sand", "shale", "sandstone"] * 50,
    "fluid_type": ["water", "oil", "oil", "gas"] * 50,
}

# Sample seismic data
SAMPLE_SEISMIC = {
    "amplitude_values": [0.5 + 0.3 * (i % 10) for i in range(200)],
    "depth_values": list(range(1000, 3000, 10)),
    "faults": [
        {"depth": 1500, "throw_m": 100, "confidence": 0.85},
        {"depth": 2000, "throw_m": 50, "confidence": 0.72},
        {"depth": 2400, "throw_m": 200, "confidence": 0.91},
    ],
    "horizons": [
        {"name": "Top Seal", "depths": list(range(1000, 1200, 10))},
        {"name": "Top Reservoir", "depths": list(range(1200, 1500, 10))},
        {"name": "Basement", "depths": list(range(2500, 2800, 10))},
    ],
}

# Sample reservoir data
SAMPLE_RESERVOIR = {
    "depth_values": list(range(1000, 3000, 10)),
    "permeability_md": [100 + (i % 500) for i in range(200)],
    "porosity_percent": [16 + (i % 15) for i in range(200)],
    "oil_saturation": [60 + (i % 30) for i in range(200)],
    "water_saturation": [30 + (i % 20) for i in range(200)],
    "gas_saturation": [10 + (i % 15) for i in range(200)],
    "formation_pressure_psi": [5000 + i * 0.5 for i in range(200)],
}

# Sample risk assessment data
SAMPLE_RISK = {
    "overall_risk_score": 0.62,
    "risk_components": {
        "Source Rock": 0.75,
        "Seal Integrity": 0.65,
        "Trap Geometry": 0.45,
        "Migration Path": 0.58,
        "Charge": 0.70,
    },
    "volumetric_estimates": {
        "Oil (MMBbl)": 45.5,
        "Gas (BCF)": 120.0,
        "Water": 30.0,
    },
    "trap_assessment": {
        "Geometry": 0.82,
        "Closure": 0.78,
        "Configuration": 0.75,
    },
    "drilling_risks": {
        "Formation Integrity": "MEDIUM",
        "Pressure Regime": "HIGH",
        "Wellbore Stability": "MEDIUM",
        "Equipment Failure": "LOW",
    },
}


def create_sample_visualizations():
    """Generate all sample visualizations."""
    
    output_dir = Path("output_examples/visualizations")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🎨 Generating Oil & Gas Well Analytics Visualizations\n")
    print("=" * 70)
    
    # 1. Well Log Track
    print("\n📊 1. Creating Well Log Track Visualization...")
    fig = WellLogVisualizer.create_well_log_track(SAMPLE_WELL_LOG)
    fig.savefig(output_dir / "01_well_log_track.png", dpi=300, bbox_inches='tight')
    print(f"   ✓ Saved: output_examples/visualizations/01_well_log_track.png")
    
    # 2. Lithology Distribution
    print("\n📊 2. Creating Lithology Distribution Pie Chart...")
    lithology_dist = {"Shale": 60, "Sand": 30, "Limestone": 8, "Coal": 2}
    fig = WellLogVisualizer.create_lithology_summary(lithology_dist)
    fig.savefig(output_dir / "02_lithology_distribution.png", dpi=300, bbox_inches='tight')
    print(f"   ✓ Saved: output_examples/visualizations/02_lithology_distribution.png")
    
    # 3. Seismic Section
    print("\n📊 3. Creating Seismic Section Visualization...")
    fig = SeismicVisualizer.create_seismic_section(SAMPLE_SEISMIC)
    fig.savefig(output_dir / "03_seismic_section.png", dpi=300, bbox_inches='tight')
    print(f"   ✓ Saved: output_examples/visualizations/03_seismic_section.png")
    
    # 4. Fault Detection Map
    print("\n📊 4. Creating Fault Detection Map...")
    fig = SeismicVisualizer.create_fault_detection_map(SAMPLE_SEISMIC["faults"])
    fig.savefig(output_dir / "04_fault_detection.png", dpi=300, bbox_inches='tight')
    print(f"   ✓ Saved: output_examples/visualizations/04_fault_detection.png")
    
    # 5. Horizon Picks
    print("\n📊 5. Creating Seismic Horizon Picks...")
    fig = SeismicVisualizer.create_horizon_picks(SAMPLE_SEISMIC["horizons"])
    fig.savefig(output_dir / "05_horizon_picks.png", dpi=300, bbox_inches='tight')
    print(f"   ✓ Saved: output_examples/visualizations/05_horizon_picks.png")
    
    # 6. Reservoir Properties Panel
    print("\n📊 6. Creating Reservoir Properties Panel...")
    fig = ReservoirVisualizer.create_reservoir_properties_panel(SAMPLE_RESERVOIR)
    fig.savefig(output_dir / "06_reservoir_properties.png", dpi=300, bbox_inches='tight')
    print(f"   ✓ Saved: output_examples/visualizations/06_reservoir_properties.png")
    
    # 7. Risk Assessment Dashboard
    print("\n📊 7. Creating Risk Assessment Dashboard...")
    fig = RiskAssessmentVisualizer.create_risk_dashboard(SAMPLE_RISK)
    fig.savefig(output_dir / "07_risk_dashboard.png", dpi=300, bbox_inches='tight')
    print(f"   ✓ Saved: output_examples/visualizations/07_risk_dashboard.png")
    
    # 8. Volumetric Chart
    print("\n📊 8. Creating Volumetric Estimates Chart...")
    volumetrics = SAMPLE_RISK["volumetric_estimates"]
    fig = RiskAssessmentVisualizer.create_volumetric_chart(volumetrics)
    fig.savefig(output_dir / "08_volumetric_chart.png", dpi=300, bbox_inches='tight')
    print(f"   ✓ Saved: output_examples/visualizations/08_volumetric_chart.png")
    
    # 9. Saturation Heatmap
    print("\n📊 9. Creating Saturation Distribution Heatmap...")
    import numpy as np
    saturation_grid = np.random.rand(10, 15) * 100
    fig = ReservoirVisualizer.create_saturation_heatmap(saturation_grid)
    fig.savefig(output_dir / "09_saturation_heatmap.png", dpi=300, bbox_inches='tight')
    print(f"   ✓ Saved: output_examples/visualizations/09_saturation_heatmap.png")
    
    # 10. Comprehensive Analysis Summary
    print("\n📊 10. Creating Comprehensive Analysis Summary Report...")
    analysis_results = {
        "well_name": "Northfield-1",
        "well_log_analysis": {"analysis": SAMPLE_WELL_LOG},
        "seismic_analysis": {"analysis": SAMPLE_SEISMIC, "faults": SAMPLE_SEISMIC["faults"]},
        "reservoir_analysis": {"analysis": SAMPLE_RESERVOIR},
        "risk_assessment": {"analysis": SAMPLE_RISK},
    }
    
    viz_files = ComprehensiveAnalysisVisualizer.create_analysis_summary_report(analysis_results, str(output_dir))
    for viz_type, path in viz_files.items():
        print(f"   ✓ Saved: {path}")
    
    # 11. HTML Report
    print("\n📊 11. Creating Interactive HTML Report...")
    html_path = ComprehensiveAnalysisVisualizer.create_html_report(analysis_results, str(output_dir / "analysis_report.html"))
    print(f"   ✓ Saved: {html_path}")
    
    print("\n" + "=" * 70)
    print("\n✅ All visualizations generated successfully!")
    print(f"\n📁 Output Location: {output_dir.absolute()}")
    print("\n📋 Generated Files:")
    
    for i, file in enumerate(sorted(output_dir.glob("*.png")), 1):
        print(f"   {i}. {file.name}")


if __name__ == "__main__":
    create_sample_visualizations()
