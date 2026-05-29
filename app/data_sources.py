"""Data loading and evidence catalog helpers for subsurface analysis."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .config import get_config


SEG_OPEN_DATA_SOURCES = [
    {
        "name": "SEAM Time Lapse Pilot Sample",
        "url": "https://seg.org/seam/open-data/",
        "size": "16.3 MB",
        "formats": ["SEG-Y", "PDF documentation"],
        "use_case": "Small open seismic sample suitable for workflow testing.",
    },
    {
        "name": "SEAM Phase I Interpretation Challenge",
        "url": "https://seg.org/seam/open-data/",
        "size": "3 GB per depth/time challenge package",
        "formats": ["SEG-Y", "interpretation challenge data"],
        "use_case": "Large seismic interpretation benchmark when local storage allows.",
    },
    {
        "name": "SEAM Phase I Elastic Earth Model Subset 2D",
        "url": "https://seg.org/seam/open-data/",
        "size": "600 KB",
        "formats": ["SEG-Y"],
        "use_case": "Tiny synthetic earth-model subset for smoke tests and demos.",
    },
    {
        "name": "SEG Open Data Wiki Catalog",
        "url": "https://wiki.seg.org/wiki/Open_data",
        "size": "varies; many seismic/well-log packages are hundreds of MB or larger",
        "formats": ["SEG-Y", "well logs", "velocity models", "documentation"],
        "use_case": "Browse candidate real-world public seismic and well-log datasets.",
    },
]


def _safe_path(path_value: str) -> Path:
    """Resolve a data path while keeping it under the configured data root."""

    config = get_config()
    data_root = Path(config.DATA_PATH).resolve()
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = data_root / candidate
    candidate = candidate.resolve()
    if data_root not in candidate.parents and candidate != data_root:
        raise ValueError(f"Data path must stay under {data_root}: {candidate}")
    if not candidate.exists():
        raise FileNotFoundError(str(candidate))
    if candidate.stat().st_size > config.MAX_FILE_SIZE:
        raise ValueError(
            f"{candidate.name} is larger than MAX_FILE_SIZE={config.MAX_FILE_SIZE}"
        )
    return candidate


def _first_existing(paths: List[str]) -> Optional[Path]:
    for path in paths:
        try:
            return _safe_path(path)
        except (FileNotFoundError, ValueError):
            continue
    return None


def _as_float_list(frame: pd.DataFrame, candidates: List[str]) -> List[float]:
    for column in candidates:
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce").dropna().astype(float).tolist()
    return []


def _summarize_frame(frame: pd.DataFrame, source_path: Path) -> Dict[str, Any]:
    numeric = frame.select_dtypes(include="number")
    return {
        "source_path": str(source_path),
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "numeric_summary": numeric.describe().round(4).to_dict() if not numeric.empty else {},
    }


def load_seismic_csv(path_value: str) -> Dict[str, Any]:
    """Load seismic CSV data into the normalized schema used by the tools."""

    path = _safe_path(path_value)
    frame = pd.read_csv(path)
    amplitudes = _as_float_list(frame, ["amplitude_values", "amplitude", "trace_amplitude"])
    depths = _as_float_list(frame, ["depth_values", "depth_m", "depth_ft", "time_ms"])
    frequencies = _as_float_list(frame, ["frequency_hz", "dominant_frequency_hz"])
    return {
        "well_name": str(frame.get("well_name", pd.Series(["SEG/local seismic"])).iloc[0]),
        "depth_values": depths or list(range(len(amplitudes))),
        "amplitude_values": amplitudes,
        "frequency_content": {
            "mean_frequency_hz": float(pd.Series(frequencies).mean()) if frequencies else 0.0
        },
        "source_metadata": _summarize_frame(frame, path),
    }


def load_well_log_csv(path_value: str) -> Dict[str, Any]:
    """Load well-log CSV data into the normalized schema used by the tools."""

    path = _safe_path(path_value)
    frame = pd.read_csv(path)
    return {
        "well_name": str(frame.get("well_name", pd.Series(["local well log"])).iloc[0]),
        "depth_values": _as_float_list(frame, ["depth_values", "depth_ft", "depth_m", "md_ft"]),
        "gamma_ray": _as_float_list(frame, ["gamma_ray", "gamma_ray_api", "gr_api"]),
        "resistivity": _as_float_list(frame, ["resistivity", "resistivity_ohm", "rt_ohm_m"]),
        "porosity": _as_float_list(frame, ["porosity", "porosity_percent", "phi_percent"]),
        "depth_unit": "feet" if "depth_ft" in frame.columns else "meters",
        "source_metadata": _summarize_frame(frame, path),
    }


def _read_seam_curve(path: Path) -> Tuple[List[float], List[float]]:
    depths: List[float] = []
    values: List[float] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                depths.append(float(parts[0]))
                values.append(float(parts[1]))
            except ValueError:
                continue
    return depths, values


def _scale_fraction_curve(values: List[float]) -> List[float]:
    """Convert SEAM fraction curves to percent when they appear normalized."""

    if not values:
        return []
    max_value = max(values)
    return [value * 100.0 for value in values] if max_value <= 1.5 else values


def load_seam_well_logs(
    path_value: str,
    well_number: int = 1,
    extended: bool = False,
) -> Dict[str, Any]:
    """Load SEAM Phase I paired ASCII curves for one well into agent schema."""

    path = _safe_path(path_value)
    logs_dir = path
    if path.is_dir() and (path / "Logs_In_Ascii").exists():
        logs_dir = path / ("Logs_In_Ascii_E" if extended else "Logs_In_Ascii")
    if path.is_file():
        logs_dir = path.parent

    suffix = ".E" if extended else ""
    well_label = f"Well.{well_number}"
    curve_files = {
        "gamma_proxy": logs_dir / f"Vshale.{well_label}{suffix}",
        "gamma": logs_dir / f"Gamma.{well_label}{suffix}",
        "resistivity": logs_dir / f"ResistivityNormal.{well_label}{suffix}",
        "porosity_effective": logs_dir / f"PorosityEffective.{well_label}{suffix}",
        "porosity_total": logs_dir / f"PorosityTotal.{well_label}{suffix}",
        "density": logs_dir / f"Density.{well_label}{suffix}",
        "vp": logs_dir / f"Vp.{well_label}{suffix}",
        "vs": logs_dir / f"VsElasticSim.{well_label}{suffix}",
    }

    missing_required = [
        name
        for name in ("gamma_proxy", "resistivity", "porosity_effective")
        if not curve_files[name].exists()
    ]
    if missing_required:
        raise FileNotFoundError(
            f"Missing SEAM curve(s) for {well_label}: {', '.join(missing_required)}"
        )

    curves: Dict[str, List[float]] = {}
    depths: List[float] = []
    for curve_name, curve_path in curve_files.items():
        if not curve_path.exists():
            continue
        curve_depths, values = _read_seam_curve(curve_path)
        if not depths:
            depths = curve_depths
        curves[curve_name] = values

    frame = pd.DataFrame(
        {
            "depth_m": depths,
            "gamma_ray_proxy_api": [value * 150.0 for value in curves["gamma_proxy"]],
            "resistivity_ohm_m": curves["resistivity"],
            "porosity_effective_percent": _scale_fraction_curve(curves["porosity_effective"]),
        }
    )

    return {
        "well_name": f"SEAM Phase I {well_label}",
        "depth_values": frame["depth_m"].astype(float).tolist(),
        "gamma_ray": frame["gamma_ray_proxy_api"].astype(float).tolist(),
        "resistivity": frame["resistivity_ohm_m"].astype(float).tolist(),
        "porosity": frame["porosity_effective_percent"].astype(float).tolist(),
        "depth_unit": "meters",
        "additional_curves": {
            "porosity_total_percent": _scale_fraction_curve(curves.get("porosity_total", [])),
            "density_g_cc": curves.get("density", []),
            "vp_m_s": curves.get("vp", []),
            "vs_m_s": curves.get("vs", []),
            "seam_gamma_anisotropy": curves.get("gamma", []),
        },
        "source_metadata": {
            "source_path": str(logs_dir),
            "dataset": "SEAM Phase I Well Log Delivery",
            "well_number": well_number,
            "extended_format": extended,
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "curve_files": {
                name: str(curve_path)
                for name, curve_path in curve_files.items()
                if curve_path.exists()
            },
            "numeric_summary": frame.describe().round(4).to_dict(),
            "normalization_notes": [
                "Vshale was scaled by 150 to provide a gamma-ray-like shale proxy for existing tools.",
                "Porosity fraction curves were converted to percent.",
            ],
        },
    }


def load_well_log_data(path_value: str, well_number: int = 1) -> Dict[str, Any]:
    """Load either CSV well logs or SEAM Phase I ASCII well-log directories."""

    path = _safe_path(path_value)
    if path.is_dir() or path.suffix.lower() not in {".csv", ".txt"}:
        return load_seam_well_logs(str(path), well_number=well_number)
    return load_well_log_csv(str(path))


def enrich_with_reference_data(user_input: Dict[str, Any]) -> Dict[str, Any]:
    """Attach local data evidence when the request omits inline arrays."""

    enriched = dict(user_input)
    data_sources: List[Dict[str, Any]] = []

    seismic_path = enriched.get("seismic_csv_path") or enriched.get("seismic_file")
    if not seismic_path and not enriched.get("seismic_data"):
        candidate = _first_existing(["sample_seismic.csv", "uploads/sample_seismic.csv"])
        seismic_path = os.fspath(candidate) if candidate else None
    if seismic_path and not enriched.get("seismic_data"):
        seismic_data = load_seismic_csv(str(seismic_path))
        enriched["seismic_data"] = seismic_data
        data_sources.append(seismic_data["source_metadata"])

    well_path = enriched.get("well_log_csv_path") or enriched.get("well_log_file")
    if not well_path and not enriched.get("well_log_data"):
        candidate = _first_existing(["sample_welllog.csv", "uploads/sample_welllog.csv"])
        well_path = os.fspath(candidate) if candidate else None
    if well_path and not enriched.get("well_log_data"):
        well_log_data = load_well_log_data(
            str(well_path),
            well_number=int(enriched.get("seam_well_number", 1) or 1),
        )
        enriched["well_log_data"] = well_log_data
        data_sources.append(well_log_data["source_metadata"])

    enriched["data_sources"] = data_sources
    enriched["open_data_catalog"] = SEG_OPEN_DATA_SOURCES
    return enriched
