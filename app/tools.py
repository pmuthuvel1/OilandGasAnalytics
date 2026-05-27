"""Tools for Oil & Gas Analytics agents"""

import json
import numpy as np
from typing import Any, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field


class SeismicData(BaseModel):
    """Seismic data structure"""

    well_name: str
    depth_values: List[float]
    amplitude_values: List[float]
    frequency_content: Dict[str, float]


class WellLogData(BaseModel):
    """Well log data structure"""

    well_name: str
    depth_values: List[float]
    gamma_ray: List[float]
    resistivity: List[float]
    porosity: List[float]
    depth_unit: str = "feet"


class AnalysisResult(BaseModel):
    """Analysis result structure"""

    agent_name: str
    analysis_type: str
    confidence: float = Field(ge=0, le=1)
    findings: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# SEISMIC ANALYSIS TOOLS
def analyze_seismic_amplitude(seismic_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze seismic amplitude for anomalies and bright spots"""
    try:
        amplitudes = np.array(seismic_data.get("amplitude_values", []))
        if len(amplitudes) == 0:
            return {"error": "No amplitude data provided"}

        mean_amp = float(np.mean(amplitudes))
        std_amp = float(np.std(amplitudes))
        max_amp = float(np.max(amplitudes))
        bright_spots = float(np.sum(amplitudes > mean_amp + 2 * std_amp))

        return {
            "mean_amplitude": mean_amp,
            "std_amplitude": std_amp,
            "max_amplitude": max_amp,
            "bright_spot_count": int(bright_spots),
            "anomaly_ratio": float(bright_spots / len(amplitudes)) if len(amplitudes) > 0 else 0,
            "interpretation": "Potential hydrocarbon indicators detected"
            if bright_spots > 0
            else "No significant anomalies",
        }
    except Exception as e:
        return {"error": str(e)}


def detect_faults(seismic_data: Dict[str, Any]) -> Dict[str, Any]:
    """Detect potential fault structures in seismic data"""
    try:
        amplitudes = np.array(seismic_data.get("amplitude_values", []))
        if len(amplitudes) < 2:
            return {"error": "Insufficient data for fault detection"}

        # Detect discontinuities (simplified approach)
        differences = np.abs(np.diff(amplitudes))
        threshold = np.mean(differences) + 2 * np.std(differences)
        fault_indices = np.where(differences > threshold)[0]

        return {
            "fault_count": int(len(fault_indices)),
            "fault_depths": [float(amplitudes[i]) for i in fault_indices[:5]],  # Top 5
            "fault_severity": float(np.max(differences) / np.mean(amplitudes)) if np.mean(amplitudes) > 0 else 0,
            "risk_level": "HIGH"
            if len(fault_indices) > 3
            else "MEDIUM"
            if len(fault_indices) > 1
            else "LOW",
        }
    except Exception as e:
        return {"error": str(e)}


def pick_horizons(seismic_data: Dict[str, Any]) -> Dict[str, Any]:
    """Pick seismic horizons for structure mapping"""
    try:
        amplitudes = np.array(seismic_data.get("amplitude_values", []))
        depths = np.array(seismic_data.get("depth_values", list(range(len(amplitudes)))))

        if len(amplitudes) == 0:
            return {"error": "No data for horizon picking"}

        # Identify peaks as horizon candidates
        peaks = []
        for i in range(1, len(amplitudes) - 1):
            if amplitudes[i] > amplitudes[i - 1] and amplitudes[i] > amplitudes[i + 1]:
                peaks.append({"depth": float(depths[i]), "amplitude": float(amplitudes[i])})

        return {
            "horizons_picked": len(peaks),
            "top_horizons": sorted(peaks, key=lambda x: x["amplitude"], reverse=True)[:3],
            "coverage": float(len(peaks) / len(amplitudes) * 100) if len(amplitudes) > 0 else 0,
        }
    except Exception as e:
        return {"error": str(e)}


# WELL LOG INTERPRETATION TOOLS
def classify_lithology(well_data: Dict[str, Any]) -> Dict[str, Any]:
    """Classify lithology from well logs"""
    try:
        gamma_ray = np.array(well_data.get("gamma_ray", []))
        resistivity = np.array(well_data.get("resistivity", []))

        if len(gamma_ray) == 0 or len(resistivity) == 0:
            return {"error": "Incomplete well log data"}

        gr_mean = float(np.mean(gamma_ray))
        res_mean = float(np.mean(resistivity))

        # Simplified lithology classification
        if gr_mean < 50 and res_mean > 100:
            lithology = "Sandstone (potential reservoir)"
        elif gr_mean > 100 and res_mean < 50:
            lithology = "Shale (potential seal)"
        else:
            lithology = "Mixed lithology"

        return {
            "primary_lithology": lithology,
            "gamma_ray_avg": gr_mean,
            "resistivity_avg": res_mean,
            "quality_score": min(1.0, max(0, (150 - abs(gr_mean - 75)) / 150)),
        }
    except Exception as e:
        return {"error": str(e)}


def identify_fluids(well_data: Dict[str, Any]) -> Dict[str, Any]:
    """Identify fluid types from well logs"""
    try:
        resistivity = np.array(well_data.get("resistivity", []))
        porosity = np.array(well_data.get("porosity", []))

        if len(resistivity) == 0 or len(porosity) == 0:
            return {"error": "Incomplete data for fluid identification"}

        res_mean = float(np.mean(resistivity))
        por_mean = float(np.mean(porosity))

        if res_mean > 150 and por_mean > 15:
            fluid_type = "Oil bearing"
            confidence = 0.85
        elif res_mean < 50 and por_mean > 20:
            fluid_type = "Water bearing"
            confidence = 0.9
        else:
            fluid_type = "Gas bearing"
            confidence = 0.7

        return {
            "primary_fluid": fluid_type,
            "confidence": confidence,
            "resistivity_avg": res_mean,
            "porosity_avg": por_mean,
        }
    except Exception as e:
        return {"error": str(e)}


def estimate_porosity(well_data: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate porosity from well logs"""
    try:
        porosity = np.array(well_data.get("porosity", []))

        if len(porosity) == 0:
            return {"error": "No porosity data available"}

        por_mean = float(np.mean(porosity))
        por_max = float(np.max(porosity))
        por_min = float(np.min(porosity))

        return {
            "average_porosity": por_mean,
            "max_porosity": por_max,
            "min_porosity": por_min,
            "porosity_quality": "Good" if por_mean > 15 else "Fair" if por_mean > 10 else "Poor",
        }
    except Exception as e:
        return {"error": str(e)}


# RESERVOIR CHARACTERIZATION TOOLS
def estimate_permeability(well_data: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate permeability from porosity"""
    try:
        porosity = np.array(well_data.get("porosity", []))
        if len(porosity) == 0:
            return {"error": "No porosity data"}

        por_mean = float(np.mean(porosity))
        # Simplified Archie-based estimation
        permeability = por_mean ** 2.5 * 100

        return {
            "estimated_permeability_md": permeability,
            "permeability_class": "High" if permeability > 100 else "Moderate" if permeability > 10 else "Low",
            "basis": "Porosity-based estimation",
        }
    except Exception as e:
        return {"error": str(e)}


def analyze_saturation(well_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze fluid saturation"""
    try:
        resistivity = np.array(well_data.get("resistivity", []))
        porosity = np.array(well_data.get("porosity", []))

        if len(resistivity) == 0:
            return {"error": "No resistivity data"}

        # Simplified water saturation estimation
        water_sat = float(1.0 / (1.0 + np.mean(resistivity) / 100))

        return {
            "water_saturation": water_sat,
            "hydrocarbon_saturation": 1.0 - water_sat,
            "saturation_confidence": 0.75,
        }
    except Exception as e:
        return {"error": str(e)}


def predict_pressure(well_data: Dict[str, Any]) -> Dict[str, Any]:
    """Predict formation pressure"""
    try:
        depths = np.array(well_data.get("depth_values", []))
        gamma_ray = np.array(well_data.get("gamma_ray", []))

        if len(depths) == 0:
            return {"error": "No depth data"}

        # Simplified pressure prediction
        avg_depth = float(np.mean(depths))
        normal_pressure = avg_depth * 0.465  # psi/ft
        gr_mean = float(np.mean(gamma_ray))
        abnormal_factor = 1.1 if gr_mean > 100 else 1.0

        predicted_pressure = normal_pressure * abnormal_factor

        return {
            "predicted_pressure_psi": predicted_pressure,
            "normal_pressure_gradient": 0.465,
            "abnormal_pressure": gr_mean > 100,
        }
    except Exception as e:
        return {"error": str(e)}


# EXPLORATION RISK ASSESSMENT TOOLS
def evaluate_trap(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate trap geometry and integrity"""
    return {
        "trap_type": analysis_data.get("trap_type", "structural"),
        "closure_area_sq_km": analysis_data.get("closure_area", 10.5),
        "trap_integrity": 0.85,
        "spill_point_depth_m": analysis_data.get("spill_depth", 2500),
        "risk_assessment": "Low to Moderate",
    }


def calculate_volumes(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate volumetric estimates"""
    gross_rock_volume = analysis_data.get("grv", 50.0)  # Millions of barrels
    net_to_gross = 0.7
    porosity = 0.18
    saturation = 0.6

    stock_tank_volume = gross_rock_volume * net_to_gross * porosity * saturation * 7.758

    return {
        "gross_rock_volume_mmbbl": gross_rock_volume,
        "stock_tank_volume_mmbbl": float(stock_tank_volume),
        "recovery_factor": 0.1,
        "recoverable_reserves_mmbbl": float(stock_tank_volume * 0.1),
    }


def assess_seal_integrity(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """Assess seal rock integrity"""
    return {
        "seal_type": "Shale",
        "seal_thickness_m": 200,
        "seal_integrity_score": 0.9,
        "leakage_risk": "Low",
        "confidence": 0.85,
    }


# REPORT GENERATION TOOLS
def synthesize_analysis(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Synthesize results from all agents"""
    summary = {
        "total_analyses": len(analyses),
        "agents_involved": [a.get("agent_name") for a in analyses],
        "overall_confidence": float(np.mean([a.get("confidence", 0.5) for a in analyses])),
        "synthesis_timestamp": datetime.now().isoformat(),
    }
    return summary


def create_visualizations(analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    """Create visualization specifications"""
    return {
        "visualizations": [
            {
                "type": "seismic_cross_section",
                "title": "Seismic Interpretation",
                "data_fields": ["depth", "amplitude"],
            },
            {
                "type": "well_log_correlation",
                "title": "Well Log Correlation",
                "data_fields": ["gamma_ray", "resistivity", "porosity"],
            },
            {
                "type": "volumetric_estimate",
                "title": "Volumetric Calculations",
                "data_fields": ["grv", "stock_tank_volume", "recoverable_reserves"],
            },
        ],
        "export_formats": ["pdf", "html", "json"],
    }


def format_recommendations(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Format final recommendations"""
    return {
        "recommendations": [
            "Proceed with detailed seismic reprocessing",
            "Schedule wellsite visits for validation",
            "Conduct volumetric uncertainty analysis",
            "Initiate farmout discussions",
        ],
        "next_steps": ["Acquire 3D seismic", "Drill exploratory well", "Monitor drilling results"],
        "risk_mitigation": ["Reduce drilling cost estimate", "Increase data acquisition"],
    }


# Tool registry
TOOLS = {
    "analyze_seismic_amplitude": analyze_seismic_amplitude,
    "detect_faults": detect_faults,
    "pick_horizons": pick_horizons,
    "classify_lithology": classify_lithology,
    "identify_fluids": identify_fluids,
    "estimate_porosity": estimate_porosity,
    "estimate_permeability": estimate_permeability,
    "analyze_saturation": analyze_saturation,
    "predict_pressure": predict_pressure,
    "evaluate_trap": evaluate_trap,
    "calculate_volumes": calculate_volumes,
    "assess_seal_integrity": assess_seal_integrity,
    "synthesize_analysis": synthesize_analysis,
    "create_visualizations": create_visualizations,
    "format_recommendations": format_recommendations,
}
