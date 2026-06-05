"""Real petrophysics engine for the Petrophysics Co-Pilot agents.

Implements industry-standard formulae:
  * Larionov (Tertiary) shale volume from gamma ray.
  * Density porosity and density-neutron average porosity.
  * Archie water saturation (Sw).
  * Pay-zone detection with configurable cutoffs.
  * Log-track plotting (GR / RHOB-NPHI / RT) with pay-zone shading.

All inputs/outputs are plain dicts so the LangChain tool layer can call them
without any special serialization.
"""

from __future__ import annotations

import logging
import math
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Curve aliases — map common log mnemonics to canonical names.
# --------------------------------------------------------------------------- #
CURVE_ALIASES: Dict[str, List[str]] = {
    "DEPT": ["DEPT", "DEPTH", "MD", "TVD", "TVDSS"],
    "GR":   ["GR", "GRGC", "GAMMA", "GR_API", "SGR", "CGR"],
    "RHOB": ["RHOB", "RHOZ", "DEN", "DENS", "DENSITY"],
    "NPHI": ["NPHI", "NPOR", "TNPH", "NPSS", "PHIN"],
    "RT":   ["RT", "RESD", "RESDEEP", "RILD", "LLD", "AT90", "RT_HRLT"],
    "DTC":  ["DTC", "DT", "AC", "DTCO"],
    "CALI": ["CALI", "CAL", "HCAL"],
}


def _pick_curve(columns: List[str], canonical: str) -> Optional[str]:
    upper = {c.upper(): c for c in columns}
    for alias in CURVE_ALIASES.get(canonical, [canonical]):
        if alias.upper() in upper:
            return upper[alias.upper()]
    return None


# --------------------------------------------------------------------------- #
# LAS / CSV loading
# --------------------------------------------------------------------------- #
def load_las_file(path: str) -> Dict[str, Any]:
    """Load a LAS file (preferred) or fall back to CSV with depth-indexed curves.

    Returns a dict with keys:
        well, field, depth_unit, depth, curves (dict of canonical -> list),
        raw_columns, null_value, depth_range, n_samples, source_path.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"LAS/CSV file not found: {path}")

    if p.suffix.lower() in {".las", ".LAS"} or p.suffix.lower() == ".las":
        return _load_las(p)
    return _load_csv_well(p)


def _load_las(path: Path) -> Dict[str, Any]:
    try:
        import lasio  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "lasio is required to read LAS files. Install with `pip install lasio`."
        ) from exc

    las = lasio.read(str(path))
    df = las.df()
    depth = np.array(df.index.tolist(), dtype=float)
    columns = list(df.columns)

    canonical: Dict[str, List[float]] = {}
    mapping: Dict[str, str] = {}
    for name in ("GR", "RHOB", "NPHI", "RT", "DTC", "CALI"):
        col = _pick_curve(columns, name)
        if col is not None:
            canonical[name] = [float(v) for v in df[col].to_numpy()]
            mapping[name] = col

    well_name = ""
    field = ""
    depth_unit = "m"
    try:
        well_name = str(las.well.WELL.value) if las.well.WELL.value else ""
        field = str(las.well.FLD.value) if "FLD" in las.well else ""
        depth_unit = str(las.curves[0].unit) if las.curves else "m"
    except Exception:  # pragma: no cover - LAS header variations
        pass

    return {
        "well": well_name or path.stem,
        "field": field,
        "depth_unit": depth_unit,
        "depth": depth.tolist(),
        "curves": canonical,
        "curve_mapping": mapping,
        "raw_columns": columns,
        "null_value": float(las.well.NULL.value) if "NULL" in las.well else -999.25,
        "depth_range": [float(depth.min()), float(depth.max())] if depth.size else [0.0, 0.0],
        "n_samples": int(depth.size),
        "source_path": str(path),
    }


def _load_csv_well(path: Path) -> Dict[str, Any]:
    import pandas as pd

    df = pd.read_csv(path)
    depth_col = _pick_curve(list(df.columns), "DEPT")
    if depth_col is None:
        raise ValueError(f"CSV {path} must contain a depth column (DEPT/DEPTH/MD).")
    df = df.sort_values(depth_col).reset_index(drop=True)
    depth = df[depth_col].to_numpy(dtype=float)

    canonical: Dict[str, List[float]] = {}
    mapping: Dict[str, str] = {}
    for name in ("GR", "RHOB", "NPHI", "RT", "DTC", "CALI"):
        col = _pick_curve(list(df.columns), name)
        if col is not None:
            canonical[name] = [float(v) for v in df[col].to_numpy()]
            mapping[name] = col

    return {
        "well": path.stem,
        "field": "",
        "depth_unit": "m",
        "depth": depth.tolist(),
        "curves": canonical,
        "curve_mapping": mapping,
        "raw_columns": list(df.columns),
        "null_value": -999.25,
        "depth_range": [float(depth.min()), float(depth.max())],
        "n_samples": int(depth.size),
        "source_path": str(path),
    }


# --------------------------------------------------------------------------- #
# Petrophysical computations
# --------------------------------------------------------------------------- #
def _clean(arr: List[float], null_value: float = -999.25) -> np.ndarray:
    a = np.asarray(arr, dtype=float)
    a[a == null_value] = np.nan
    return a


def compute_vshale_larionov(
    gr: List[float],
    gr_clean: Optional[float] = None,
    gr_shale: Optional[float] = None,
    rock_age: str = "tertiary",
    null_value: float = -999.25,
) -> Dict[str, Any]:
    """Larionov shale volume from gamma ray.

    Tertiary:  Vsh = 0.083 * (2^(3.7*Igr) - 1)
    Older:     Vsh = 0.33  * (2^(2 * Igr) - 1)
    """
    g = _clean(gr, null_value)
    valid = g[~np.isnan(g)]
    if valid.size == 0:
        return {"error": "no valid gamma-ray samples"}
    if gr_clean is None:
        gr_clean = float(np.nanpercentile(valid, 5))
    if gr_shale is None:
        gr_shale = float(np.nanpercentile(valid, 95))
    denom = max(gr_shale - gr_clean, 1e-6)
    igr = np.clip((g - gr_clean) / denom, 0.0, 1.0)

    if rock_age.lower().startswith("tert"):
        vsh = 0.083 * (np.power(2.0, 3.7 * igr) - 1.0)
    else:
        vsh = 0.33 * (np.power(2.0, 2.0 * igr) - 1.0)
    vsh = np.clip(vsh, 0.0, 1.0)
    return {
        "vsh": vsh.tolist(),
        "gr_clean_api": gr_clean,
        "gr_shale_api": gr_shale,
        "rock_age": rock_age,
        "mean_vsh": float(np.nanmean(vsh)),
        "method": "Larionov",
    }


def compute_density_porosity(
    rhob: List[float],
    matrix_density: float = 2.65,
    fluid_density: float = 1.0,
    null_value: float = -999.25,
) -> Dict[str, Any]:
    """Density porosity:  PHID = (rho_ma - rho_b) / (rho_ma - rho_f)."""
    r = _clean(rhob, null_value)
    phid = (matrix_density - r) / (matrix_density - fluid_density)
    phid = np.clip(phid, 0.0, 0.6)
    return {
        "phid": phid.tolist(),
        "matrix_density": matrix_density,
        "fluid_density": fluid_density,
        "mean_phid": float(np.nanmean(phid)),
    }


def compute_phi_avg(
    phid: List[float],
    nphi: Optional[List[float]] = None,
    null_value: float = -999.25,
) -> Dict[str, Any]:
    """Density-neutron average porosity (simple arithmetic mean when both present)."""
    d = _clean(phid, null_value)
    if nphi is None:
        phi = d
        method = "density_only"
    else:
        n = _clean(nphi, null_value)
        phi = np.where(np.isnan(n), d, (d + n) / 2.0)
        method = "density_neutron_average"
    phi = np.clip(phi, 0.0, 0.6)
    return {
        "phi": phi.tolist(),
        "mean_phi": float(np.nanmean(phi)),
        "method": method,
    }


def compute_sw_archie(
    rt: List[float],
    phi: List[float],
    Rw: float = 0.03,
    a: float = 1.0,
    m: float = 2.0,
    n: float = 2.0,
    null_value: float = -999.25,
) -> Dict[str, Any]:
    """Archie water saturation:  Sw = ((a * Rw) / (phi^m * Rt))^(1/n)."""
    rt_a = _clean(rt, null_value)
    phi_a = _clean(phi, null_value)
    phi_safe = np.where(phi_a > 0.01, phi_a, np.nan)
    rt_safe = np.where(rt_a > 0.01, rt_a, np.nan)
    numerator = a * Rw
    denominator = np.power(phi_safe, m) * rt_safe
    sw = np.power(numerator / denominator, 1.0 / n)
    sw = np.clip(sw, 0.0, 1.0)
    return {
        "sw": sw.tolist(),
        "Rw": Rw,
        "a": a,
        "m": m,
        "n": n,
        "mean_sw": float(np.nanmean(sw)),
        "method": "Archie",
    }


# --------------------------------------------------------------------------- #
# Pay zone detection
# --------------------------------------------------------------------------- #
def detect_pay_zones(
    depth: List[float],
    vsh: List[float],
    phi: List[float],
    sw: List[float],
    vsh_max: float = 0.40,
    phi_min: float = 0.10,
    sw_max: float = 0.50,
    min_thickness: float = 1.5,
) -> Dict[str, Any]:
    """Flag continuous intervals that pass Vsh / Phi / Sw cutoffs."""
    d = np.asarray(depth, dtype=float)
    v = np.asarray(vsh, dtype=float)
    p = np.asarray(phi, dtype=float)
    s = np.asarray(sw, dtype=float)

    pay_mask = (v <= vsh_max) & (p >= phi_min) & (s <= sw_max)
    pay_mask = np.nan_to_num(pay_mask, nan=False).astype(bool)

    zones: List[Dict[str, Any]] = []
    in_zone = False
    start_idx = 0
    for i, flag in enumerate(pay_mask):
        if flag and not in_zone:
            in_zone = True
            start_idx = i
        elif not flag and in_zone:
            in_zone = False
            zones.append(_make_zone(d, v, p, s, start_idx, i - 1))
    if in_zone:
        zones.append(_make_zone(d, v, p, s, start_idx, len(pay_mask) - 1))

    zones = [z for z in zones if z["thickness"] >= min_thickness]
    for i, z in enumerate(zones, start=1):
        z["zone_id"] = f"PZ-{i}"

    net_pay = float(sum(z["thickness"] for z in zones))
    gross = float(d.max() - d.min()) if d.size else 0.0
    return {
        "zones": zones,
        "net_pay": net_pay,
        "gross_interval": gross,
        "net_to_gross": float(net_pay / gross) if gross > 0 else 0.0,
        "cutoffs": {"vsh_max": vsh_max, "phi_min": phi_min, "sw_max": sw_max,
                    "min_thickness": min_thickness},
        "n_zones": len(zones),
    }


def _make_zone(depth, v, p, s, i0: int, i1: int) -> Dict[str, Any]:
    top, base = float(depth[i0]), float(depth[i1])
    return {
        "top": top,
        "base": base,
        "thickness": abs(base - top),
        "avg_vsh": float(np.nanmean(v[i0:i1 + 1])),
        "avg_phi": float(np.nanmean(p[i0:i1 + 1])),
        "avg_sw": float(np.nanmean(s[i0:i1 + 1])),
        "samples": int(i1 - i0 + 1),
    }


# --------------------------------------------------------------------------- #
# Plotting
# --------------------------------------------------------------------------- #
def plot_log_tracks(
    depth: List[float],
    gr: Optional[List[float]] = None,
    rhob: Optional[List[float]] = None,
    nphi: Optional[List[float]] = None,
    rt: Optional[List[float]] = None,
    pay_zones: Optional[List[Dict[str, Any]]] = None,
    well_name: str = "Well",
    output_dir: str = "data/plots",
    depth_window: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """Render a 3-track log plot (GR | RHOB-NPHI | RT) with pay shading."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(output_dir, exist_ok=True)
    d = np.asarray(depth, dtype=float)
    if depth_window:
        lo, hi = depth_window
        mask = (d >= lo) & (d <= hi)
    else:
        mask = np.ones_like(d, dtype=bool)

    fig, axes = plt.subplots(1, 3, figsize=(10, 9), sharey=True)

    if gr is not None:
        g = np.asarray(gr, dtype=float)[mask]
        axes[0].plot(g, d[mask], color="green", lw=0.8)
        axes[0].set_xlabel("GR (API)")
        axes[0].set_xlim(0, max(150, float(np.nanmax(g)) if g.size else 150))
        axes[0].invert_yaxis()
        axes[0].grid(alpha=0.3)
    axes[0].set_ylabel(f"Depth ({well_name})")

    if rhob is not None:
        r = np.asarray(rhob, dtype=float)[mask]
        axes[1].plot(r, d[mask], color="red", lw=0.8, label="RHOB")
        axes[1].set_xlim(1.95, 2.95)
        axes[1].set_xlabel("RHOB g/cc")
    if nphi is not None:
        n = np.asarray(nphi, dtype=float)[mask]
        ax2 = axes[1].twiny()
        ax2.plot(n, d[mask], color="blue", lw=0.8, label="NPHI")
        ax2.set_xlim(0.45, -0.15)
        ax2.set_xlabel("NPHI v/v")
    axes[1].grid(alpha=0.3)

    if rt is not None:
        t = np.asarray(rt, dtype=float)[mask]
        t = np.where(t > 0, t, np.nan)
        axes[2].semilogx(t, d[mask], color="black", lw=0.8)
        axes[2].set_xlim(0.2, 2000)
        axes[2].set_xlabel("RT (Ωm, log)")
        axes[2].grid(which="both", alpha=0.3)

    for zone in pay_zones or []:
        for ax in axes:
            ax.axhspan(zone["top"], zone["base"], alpha=0.18, color="gold")

    fig.suptitle(f"Petrophysics — {well_name}", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    filename = f"{well_name.replace('/', '_')}_{uuid.uuid4().hex[:8]}.png"
    out_path = os.path.join(output_dir, filename)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)

    return {
        "plot_path": out_path,
        "plot_url": f"/static/plots/{filename}",
        "depth_window": list(depth_window) if depth_window else None,
        "tracks": ["GR", "RHOB+NPHI", "RT"],
    }


# --------------------------------------------------------------------------- #
# Convenience pipeline used by tools.py
# --------------------------------------------------------------------------- #
def run_full_petrophysics(
    las: Dict[str, Any],
    matrix_density: float = 2.65,
    fluid_density: float = 1.0,
    Rw: float = 0.03,
    a: float = 1.0,
    m: float = 2.0,
    n: float = 2.0,
    rock_age: str = "tertiary",
    vsh_max: float = 0.40,
    phi_min: float = 0.10,
    sw_max: float = 0.50,
    min_thickness: float = 1.5,
) -> Dict[str, Any]:
    """End-to-end Vsh/Phi/Sw + pay-zone computation from a loaded LAS dict."""
    curves = las.get("curves", {})
    null_value = las.get("null_value", -999.25)
    depth = las.get("depth", [])

    warnings: List[str] = []
    if "GR" not in curves:
        return {"error": "GR curve missing; cannot compute Vsh"}
    if "RHOB" not in curves:
        return {"error": "RHOB curve missing; cannot compute porosity"}
    if "RT" not in curves:
        warnings.append("RT missing; Sw set to NaN")

    vsh_res = compute_vshale_larionov(curves["GR"], rock_age=rock_age, null_value=null_value)
    phid_res = compute_density_porosity(curves["RHOB"], matrix_density, fluid_density, null_value)
    phi_res = compute_phi_avg(phid_res["phid"], curves.get("NPHI"), null_value)
    if "RT" in curves:
        sw_res = compute_sw_archie(curves["RT"], phi_res["phi"], Rw, a, m, n, null_value)
        sw_values = sw_res["sw"]
    else:
        sw_res = {"sw": [float("nan")] * len(depth), "method": "skipped"}
        sw_values = sw_res["sw"]

    pay = detect_pay_zones(
        depth, vsh_res["vsh"], phi_res["phi"], sw_values,
        vsh_max=vsh_max, phi_min=phi_min, sw_max=sw_max, min_thickness=min_thickness,
    )

    return {
        "well": las.get("well"),
        "field": las.get("field"),
        "depth_unit": las.get("depth_unit"),
        "n_samples": las.get("n_samples"),
        "depth_range": las.get("depth_range"),
        "vshale": {k: v for k, v in vsh_res.items() if k != "vsh"},
        "porosity": {
            "mean_phi": phi_res["mean_phi"],
            "method": phi_res["method"],
            "matrix_density": matrix_density,
            "fluid_density": fluid_density,
        },
        "water_saturation": {k: v for k, v in sw_res.items() if k != "sw"},
        "pay": pay,
        "curves_used": list(curves.keys()),
        "warnings": warnings,
        "computed_at": datetime.now().isoformat(),
        # Heavy arrays kept separately for downstream plotting only.
        "_arrays": {
            "depth": depth,
            "GR": curves.get("GR"),
            "RHOB": curves.get("RHOB"),
            "NPHI": curves.get("NPHI"),
            "RT": curves.get("RT"),
            "vsh": vsh_res["vsh"],
            "phi": phi_res["phi"],
            "sw": sw_values,
        },
    }

