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


def _source_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Carry source evidence through tool outputs when available."""

    return payload.get("source_metadata", {}) if isinstance(payload, dict) else {}


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
            "source_metadata": _source_metadata(seismic_data),
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
        depths = np.array(seismic_data.get("depth_values", list(range(len(amplitudes)))))

        return {
            "fault_count": int(len(fault_indices)),
            "fault_depths": [float(depths[i]) for i in fault_indices[:5]],
            "fault_severity": float(np.max(differences) / np.mean(amplitudes)) if np.mean(amplitudes) > 0 else 0,
            "risk_level": "HIGH"
            if len(fault_indices) > 3
            else "MEDIUM"
            if len(fault_indices) > 1
            else "LOW",
            "source_metadata": _source_metadata(seismic_data),
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
            "source_metadata": _source_metadata(seismic_data),
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
            "source_metadata": _source_metadata(well_data),
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
            "source_metadata": _source_metadata(well_data),
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
            "source_metadata": _source_metadata(well_data),
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
            "source_metadata": _source_metadata(well_data),
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
            "source_metadata": _source_metadata(well_data),
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
            "source_metadata": _source_metadata(well_data),
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
    porosity = analysis_data.get("porosity_fraction", 0.18)
    saturation = analysis_data.get("hydrocarbon_saturation", 0.6)

    reservoir = analysis_data.get("reservoir_properties", {})
    saturation_result = (
        reservoir.get("tool_results", {}).get("analyze_saturation", {})
        if isinstance(reservoir, dict)
        else {}
    )
    if saturation_result.get("hydrocarbon_saturation") is not None:
        saturation = float(saturation_result["hydrocarbon_saturation"])

    stock_tank_volume = gross_rock_volume * net_to_gross * porosity * saturation * 7.758

    return {
        "gross_rock_volume_mmbbl": gross_rock_volume,
        "stock_tank_volume_mmbbl": float(stock_tank_volume),
        "recovery_factor": 0.1,
        "recoverable_reserves_mmbbl": float(stock_tank_volume * 0.1),
        "input_assumptions": {
            "net_to_gross": net_to_gross,
            "porosity_fraction": porosity,
            "hydrocarbon_saturation": saturation,
        },
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


# ---------------------------------------------------------------------------
# PETROPHYSICS CO-PILOT TOOLS (Option A: real-physics, LAS-driven)
# ---------------------------------------------------------------------------
def load_well_log(data: Dict[str, Any]) -> Dict[str, Any]:
    """Load a LAS or CSV well-log file and return curve inventory + metadata."""
    try:
        path = data.get("path") or data.get("file_path") or data.get("well_file")
        if not path:
            return {"error": "Missing 'path' (LAS or CSV file path)"}
        las = petro.load_las_file(path)
        # Cache full LAS dict for downstream tools through a side channel.
        _LAS_CACHE[path] = las
        return {
            "well": las["well"],
            "field": las["field"],
            "depth_unit": las["depth_unit"],
            "depth_range": las["depth_range"],
            "n_samples": las["n_samples"],
            "curves_found": list(las["curves"].keys()),
            "curve_mapping": las["curve_mapping"],
            "raw_columns": las["raw_columns"],
            "source_path": las["source_path"],
        }
    except Exception as exc:
        return {"error": str(exc)}


def compute_petrophysics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Run Larionov Vsh, density-neutron porosity, Archie Sw, pay-zone detection."""
    try:
        path = data.get("path") or data.get("file_path") or data.get("well_file")
        las = _LAS_CACHE.get(path) if path else None
        if las is None and path:
            las = petro.load_las_file(path)
            _LAS_CACHE[path] = las
        if las is None:
            return {"error": "Provide 'path' to a LAS/CSV file (call load_well_log first)."}

        params = {
            "matrix_density": float(data.get("matrix_density", 2.65)),
            "fluid_density": float(data.get("fluid_density", 1.0)),
            "Rw": float(data.get("Rw", 0.03)),
            "a": float(data.get("a", 1.0)),
            "m": float(data.get("m", 2.0)),
            "n": float(data.get("n", 2.0)),
            "rock_age": str(data.get("rock_age", "tertiary")),
            "vsh_max": float(data.get("vsh_max", 0.40)),
            "phi_min": float(data.get("phi_min", 0.10)),
            "sw_max": float(data.get("sw_max", 0.50)),
            "min_thickness": float(data.get("min_thickness", 1.5)),
        }
        result = petro.run_full_petrophysics(las, **params)
        # Cache arrays for plotting tool, but strip from LLM-visible result.
        if "_arrays" in result:
            _ARRAY_CACHE[path] = result.pop("_arrays")
        result["parameters"] = params
        result["source_path"] = path
        return result
    except Exception as exc:
        return {"error": str(exc)}


def plot_well_logs(data: Dict[str, Any]) -> Dict[str, Any]:
    """Render a 3-track log plot (GR / RHOB-NPHI / RT) with pay zones shaded."""
    try:
        path = data.get("path") or data.get("file_path") or data.get("well_file")
        arrays = _ARRAY_CACHE.get(path)
        if arrays is None:
            # Recompute if cache empty.
            las = _LAS_CACHE.get(path) or petro.load_las_file(path)
            _LAS_CACHE[path] = las
            full = petro.run_full_petrophysics(las)
            arrays = full.get("_arrays", {})
            _ARRAY_CACHE[path] = arrays
        pay_zones = data.get("pay_zones") or []
        depth_window = data.get("depth_window")
        if depth_window and len(depth_window) == 2:
            depth_window = (float(depth_window[0]), float(depth_window[1]))
        else:
            depth_window = None
        well_name = data.get("well_name") or (_LAS_CACHE.get(path, {}).get("well") or "Well")
        return petro.plot_log_tracks(
            depth=arrays.get("depth", []),
            gr=arrays.get("GR"),
            rhob=arrays.get("RHOB"),
            nphi=arrays.get("NPHI"),
            rt=arrays.get("RT"),
            pay_zones=pay_zones,
            well_name=well_name,
            depth_window=depth_window,
        )
    except Exception as exc:
        return {"error": str(exc)}


def summarize_pay_zones(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build an executive summary from the petrophysics result + pay zones."""
    try:
        petro_result = data.get("petrophysics") or {}
        pay = petro_result.get("pay", {})
        zones = pay.get("zones", [])
        if not zones:
            return {
                "well": petro_result.get("well"),
                "verdict": "NO_PAY",
                "summary": "No intervals met the pay cutoffs. Consider relaxing cutoffs or reviewing data quality.",
                "net_pay": 0.0,
                "net_to_gross": 0.0,
                "zones": [],
            }
        best = max(zones, key=lambda z: z["thickness"] * z["avg_phi"] * (1 - z["avg_sw"]))
        return {
            "well": petro_result.get("well"),
            "verdict": "PAY_FOUND",
            "n_zones": len(zones),
            "net_pay": pay.get("net_pay"),
            "gross_interval": pay.get("gross_interval"),
            "net_to_gross": pay.get("net_to_gross"),
            "best_zone": best,
            "all_zones": zones,
            "cutoffs": pay.get("cutoffs"),
            "warnings": petro_result.get("warnings", []),
            "recommendation": _zone_recommendation(best),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _zone_recommendation(zone: Dict[str, Any]) -> str:
    phi = zone.get("avg_phi", 0)
    sw = zone.get("avg_sw", 1)
    thk = zone.get("thickness", 0)
    if phi > 0.18 and sw < 0.35 and thk > 4:
        return ("Strong completion candidate. Perforate "
                f"{zone['top']:.1f}-{zone['base']:.1f} and run formation pressure test.")
    if phi > 0.12 and sw < 0.5 and thk > 2:
        return ("Moderate-quality pay. Consider commingling with adjacent zones.")
    return "Marginal pay; further data acquisition (core, fluid sample) recommended."


def critique_petrophysics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic QC checks for the petrophysics result — feeds the evaluator agent."""
    try:
        petro_result = data.get("petrophysics") or {}
        issues: List[str] = []
        warnings: List[str] = list(petro_result.get("warnings", []))

        vsh = petro_result.get("vshale", {})
        if vsh.get("gr_clean_api", 0) >= vsh.get("gr_shale_api", 0):
            issues.append("Vsh baseline collapse: GR clean >= GR shale.")

        phi = petro_result.get("porosity", {}).get("mean_phi", 0)
        if phi <= 0 or phi > 0.45:
            issues.append(f"Implausible mean porosity ({phi:.3f}); check matrix density.")

        sw = petro_result.get("water_saturation", {}).get("mean_sw")
        if sw is not None and (sw < 0.05 or sw > 1.01):
            issues.append(f"Sw out of physical range ({sw:.3f}); verify Rw/a/m/n.")

        curves = petro_result.get("curves_used", [])
        for required in ("GR", "RHOB"):
            if required not in curves:
                issues.append(f"Missing required curve: {required}.")
        if "RT" not in curves:
            warnings.append("RT absent — Sw not computed.")
        if "NPHI" not in curves:
            warnings.append("NPHI absent — porosity from density only.")

        confidence = max(0.0, 1.0 - 0.2 * len(issues) - 0.05 * len(warnings))
        return {
            "approved": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "confidence": round(confidence, 2),
        }
    except Exception as exc:
        return {"error": str(exc)}


# In-process caches keyed by file path. Keeps heavy arrays out of LLM prompts.
_LAS_CACHE: Dict[str, Dict[str, Any]] = {}
_ARRAY_CACHE: Dict[str, Dict[str, Any]] = {}


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
