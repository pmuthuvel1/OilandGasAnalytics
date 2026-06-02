"""Visualization module for Oil & Gas Well Analytics using Matplotlib and Seaborn."""

import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

logger = logging.getLogger(__name__)

# Set style for professional charts
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 10

# Oil & Gas specific colors
OIL_COLOR = "#8B4513"  # Brown
GAS_COLOR = "#FFD700"  # Gold
WATER_COLOR = "#4A90E2"  # Blue
ROCK_COLOR = "#A9A9A9"  # Gray
SHALE_COLOR = "#2F4F4F"  # Dark slate gray
SAND_COLOR = "#DEB887"  # Burlywood
FAULT_COLOR = "#FF0000"  # Red
TRAP_COLOR = "#00AA00"  # Green


class WellLogVisualizer:
    """Visualize well log data including lithology, gamma ray, resistivity, and fluid identification."""

    @staticmethod
    def create_well_log_track(well_data: Dict[str, Any], save_path: Optional[str] = None) -> plt.Figure:
        """
        Create a professional well log track visualization.
        
        Args:
            well_data: Dictionary containing well information and log data
            save_path: Optional path to save the figure
            
        Returns:
            matplotlib Figure object
        """
        fig, axes = plt.subplots(1, 4, figsize=(16, 10))
        fig.suptitle(f"Well Log Analysis: {well_data.get('well_name', 'Unknown')}", 
                     fontsize=16, fontweight='bold', y=0.98)
        
        # Extract data
        depth = well_data.get('depth_values', [])
        gamma_ray = well_data.get('gamma_ray', [])
        resistivity = well_data.get('resistivity', [])
        porosity = well_data.get('porosity', [])
        lithology = well_data.get('lithology_classification', [])
        fluid_type = well_data.get('fluid_type', [])
        
        if not depth:
            logger.warning("No depth values provided for well log visualization")
            return fig
        
        # Track 1: Gamma Ray
        ax1 = axes[0]
        ax1.plot(gamma_ray, depth, 'b-', linewidth=2)
        ax1.fill_betweenx(depth, 0, gamma_ray, alpha=0.3, color='blue')
        ax1.set_xlabel('Gamma Ray (API Units)', fontweight='bold')
        ax1.set_ylabel('Depth (m)', fontweight='bold')
        ax1.set_ylim(max(depth), min(depth))  # Depth increases downward
        ax1.grid(True, alpha=0.3)
        ax1.set_title('Gamma Ray Log', fontweight='bold')
        
        # Track 2: Resistivity
        ax2 = axes[1]
        ax2.semilogx(resistivity, depth, 'r-', linewidth=2)
        ax2.fill_betweenx(depth, 1, resistivity, alpha=0.3, color='red')
        ax2.set_xlabel('Resistivity (Ω·m)', fontweight='bold')
        ax2.set_ylim(max(depth), min(depth))
        ax2.grid(True, alpha=0.3, which='both')
        ax2.set_title('Resistivity Log', fontweight='bold')
        
        # Track 3: Porosity
        ax3 = axes[2]
        ax3.plot(porosity, depth, 'g-', linewidth=2)
        ax3.fill_betweenx(depth, 0, porosity, alpha=0.3, color='green')
        ax3.set_xlabel('Porosity (%)', fontweight='bold')
        ax3.set_xlim(0, max(porosity) * 1.1 if porosity else 50)
        ax3.set_ylim(max(depth), min(depth))
        ax3.grid(True, alpha=0.3)
        ax3.set_title('Porosity Log', fontweight='bold')
        
        # Track 4: Lithology/Fluid Type
        ax4 = axes[3]
        ax4.set_xlim(0, 1)
        ax4.set_ylim(max(depth), min(depth))
        
        # Color-code lithology
        lithology_colors = {
            'shale': SHALE_COLOR,
            'sand': SAND_COLOR,
            'sandstone': SAND_COLOR,
            'limestone': '#E0E0E0',
            'dolomite': '#D3D3D3',
            'coal': '#000000',
        }
        
        # Plot lithology zones
        depth_interval = depth[1] - depth[0] if len(depth) > 1 else 1
        for i, (d, lith) in enumerate(zip(depth, lithology)):
            color = lithology_colors.get(str(lith).lower(), '#CCCCCC')
            ax4.barh(d, 1, height=depth_interval * 0.9, color=color, edgecolor='black', linewidth=0.5)
        
        ax4.set_xlabel('Lithology', fontweight='bold')
        ax4.set_xticks([])
        ax4.set_title('Lithology Classification', fontweight='bold')
        ax4.grid(True, alpha=0.2, axis='y')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Well log visualization saved to {save_path}")
        
        return fig

    @staticmethod
    def create_lithology_summary(lithology_data: Dict[str, int], save_path: Optional[str] = None) -> plt.Figure:
        """Create lithology distribution pie chart."""
        fig, ax = plt.subplots(figsize=(10, 8))
        
        colors = [SHALE_COLOR, SAND_COLOR, '#E0E0E0', '#D3D3D3']
        wedges, texts, autotexts = ax.pie(
            lithology_data.values(),
            labels=lithology_data.keys(),
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            textprops={'fontsize': 11, 'fontweight': 'bold'}
        )
        
        # Enhance percentage text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        ax.set_title('Lithology Distribution in Well', fontsize=14, fontweight='bold', pad=20)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig


class SeismicVisualizer:
    """Visualize seismic data including amplitude, fault detection, and horizon picks."""

    @staticmethod
    def create_seismic_section(seismic_data: Dict[str, Any], save_path: Optional[str] = None) -> plt.Figure:
        """
        Create seismic section with amplitude display.
        
        Args:
            seismic_data: Dictionary with amplitude and depth values
            save_path: Optional path to save figure
            
        Returns:
            matplotlib Figure object
        """
        fig, ax = plt.subplots(figsize=(14, 8))
        
        amplitude = np.array(seismic_data.get('amplitude_values', []))
        depth = np.array(seismic_data.get('depth_values', []))
        
        if len(amplitude) == 0 or len(depth) == 0:
            logger.warning("No seismic data provided")
            return fig
        
        # Create depth grid for heatmap style visualization
        traces = np.column_stack([amplitude] * 5)  # Repeat for width
        im = ax.imshow(traces, aspect='auto', cmap='RdBu_r', origin='upper')
        
        # Set labels
        ax.set_xlabel('Seismic Traces', fontweight='bold')
        ax.set_ylabel('Depth (m)', fontweight='bold')
        ax.set_title('Seismic Section - Amplitude Envelope', fontsize=14, fontweight='bold')
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Amplitude (normalized)', fontweight='bold')
        
        # Overlay amplitude curve
        ax_overlay = ax.twinx()
        ax_overlay.plot(amplitude, depth, 'g-', linewidth=2, label='Amplitude Envelope')
        ax_overlay.set_ylabel('Amplitude', fontweight='bold', color='g')
        ax_overlay.tick_params(axis='y', labelcolor='g')
        ax_overlay.legend(loc='upper right')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig

    @staticmethod
    def create_fault_detection_map(faults: List[Dict[str, Any]], save_path: Optional[str] = None) -> plt.Figure:
        """Create visualization of detected faults."""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        if not faults:
            ax.text(0.5, 0.5, 'No faults detected', ha='center', va='center',
                   transform=ax.transAxes, fontsize=14)
            return fig
        
        # Extract fault data
        fault_depths = [f.get('depth', 0) for f in faults]
        fault_throws = [f.get('throw_m', 0) for f in faults]
        fault_confidence = [f.get('confidence', 0.5) for f in faults]
        
        # Create scatter plot with confidence as color
        scatter = ax.scatter(range(len(faults)), fault_depths, s=np.array(fault_throws)*10,
                            c=fault_confidence, cmap='RdYlGn', alpha=0.6, edgecolors='black', linewidth=2)
        
        ax.set_xlabel('Fault Number', fontweight='bold')
        ax.set_ylabel('Depth (m)', fontweight='bold')
        ax.set_title('Detected Fault Structures', fontsize=14, fontweight='bold')
        ax.invert_yaxis()
        ax.grid(True, alpha=0.3)
        
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Confidence Level', fontweight='bold')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig

    @staticmethod
    def create_horizon_picks(horizons: List[Dict[str, Any]], save_path: Optional[str] = None) -> plt.Figure:
        """Create visualization of picked seismic horizons."""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        if not horizons:
            ax.text(0.5, 0.5, 'No horizons picked', ha='center', va='center',
                   transform=ax.transAxes, fontsize=14)
            return fig
        
        # Extract horizon data
        colors_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        
        for idx, horizon in enumerate(horizons):
            horizon_name = horizon.get('name', f'Horizon {idx+1}')
            depths = horizon.get('depths', [])
            if depths:
                ax.plot(range(len(depths)), depths, linewidth=3, label=horizon_name,
                       color=colors_list[idx % len(colors_list)], marker='o', markersize=6)
        
        ax.set_xlabel('Lateral Position (traces)', fontweight='bold')
        ax.set_ylabel('Depth (m)', fontweight='bold')
        ax.set_title('Seismic Horizon Picks', fontsize=14, fontweight='bold')
        ax.invert_yaxis()
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=10)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig


class ReservoirVisualizer:
    """Visualize reservoir characterization including pressure, saturation, and permeability."""

    @staticmethod
    def create_reservoir_properties_panel(reservoir_data: Dict[str, Any], save_path: Optional[str] = None) -> plt.Figure:
        """
        Create multi-panel visualization of reservoir properties.
        
        Args:
            reservoir_data: Dictionary with permeability, saturation, pressure data
            save_path: Optional path to save figure
            
        Returns:
            matplotlib Figure object
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Reservoir Characterization Analysis', fontsize=16, fontweight='bold')
        
        # Panel 1: Permeability vs Depth
        ax1 = axes[0, 0]
        depth = reservoir_data.get('depth_values', [])
        permeability = reservoir_data.get('permeability_md', [])
        
        if permeability:
            ax1.semilogx(permeability, depth, 'b-', linewidth=2.5)
            ax1.fill_betweenx(depth, 1, permeability, alpha=0.3, color='blue')
            ax1.set_xlabel('Permeability (mD)', fontweight='bold')
            ax1.set_ylabel('Depth (m)', fontweight='bold')
            ax1.set_ylim(max(depth) if depth else 3000, min(depth) if depth else 0)
            ax1.grid(True, alpha=0.3, which='both')
            ax1.set_title('Permeability Profile', fontweight='bold')
        
        # Panel 2: Saturation Distribution
        ax2 = axes[0, 1]
        oil_saturation = reservoir_data.get('oil_saturation', [])
        water_saturation = reservoir_data.get('water_saturation', [])
        gas_saturation = reservoir_data.get('gas_saturation', [])
        
        if oil_saturation and depth:
            ax2.stackplot(depth, oil_saturation, water_saturation, gas_saturation,
                         labels=['Oil', 'Water', 'Gas'],
                         colors=[OIL_COLOR, WATER_COLOR, GAS_COLOR], alpha=0.7)
            ax2.set_xlabel('Depth (m)', fontweight='bold')
            ax2.set_ylabel('Saturation (%)', fontweight='bold')
            ax2.set_ylim(0, 100)
            ax2.legend(loc='best', fontsize=9)
            ax2.grid(True, alpha=0.3)
            ax2.set_title('Saturation Distribution', fontweight='bold')
        
        # Panel 3: Formation Pressure
        ax3 = axes[1, 0]
        formation_pressure = reservoir_data.get('formation_pressure_psi', [])
        
        if formation_pressure:
            ax3.plot(formation_pressure, depth, 'r-', linewidth=2.5)
            ax3.fill_betweenx(depth, min(formation_pressure), formation_pressure, alpha=0.3, color='red')
            ax3.set_xlabel('Formation Pressure (psi)', fontweight='bold')
            ax3.set_ylabel('Depth (m)', fontweight='bold')
            ax3.set_ylim(max(depth) if depth else 3000, min(depth) if depth else 0)
            ax3.grid(True, alpha=0.3)
            ax3.set_title('Formation Pressure Profile', fontweight='bold')
        
        # Panel 4: Porosity-Permeability Crossplot
        ax4 = axes[1, 1]
        porosity = reservoir_data.get('porosity_percent', [])
        
        if porosity and permeability:
            scatter = ax4.scatter(porosity, permeability, s=100, alpha=0.6,
                                 c=depth, cmap='viridis', edgecolors='black', linewidth=1)
            ax4.set_xlabel('Porosity (%)', fontweight='bold')
            ax4.set_ylabel('Permeability (mD)', fontweight='bold')
            ax4.set_yscale('log')
            ax4.grid(True, alpha=0.3, which='both')
            ax4.set_title('Porosity-Permeability Crossplot', fontweight='bold')
            cbar = plt.colorbar(scatter, ax=ax4)
            cbar.set_label('Depth (m)', fontweight='bold')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig

    @staticmethod
    def create_saturation_heatmap(saturation_grid: np.ndarray, save_path: Optional[str] = None) -> plt.Figure:
        """Create heatmap of saturation distribution."""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        sns.heatmap(saturation_grid, annot=False, cmap='RdYlGn', center=50,
                   ax=ax, cbar_kws={'label': 'Oil Saturation (%)'})
        
        ax.set_title('Oil Saturation Distribution - 2D Grid', fontsize=14, fontweight='bold')
        ax.set_xlabel('Lateral Position (X)', fontweight='bold')
        ax.set_ylabel('Depth (Z)', fontweight='bold')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig


class RiskAssessmentVisualizer:
    """Visualize risk assessment including risk scores, volumetrics, and trap geometry."""

    @staticmethod
    def create_risk_dashboard(risk_data: Dict[str, Any], save_path: Optional[str] = None) -> plt.Figure:
        """
        Create comprehensive risk assessment dashboard.
        
        Args:
            risk_data: Dictionary with risk scores and assessment data
            save_path: Optional path to save figure
            
        Returns:
            matplotlib Figure object
        """
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
        
        fig.suptitle('Exploration Risk Assessment Dashboard', fontsize=16, fontweight='bold')
        
        # Panel 1: Risk Score Gauge
        ax1 = fig.add_subplot(gs[0, 0])
        risk_score = risk_data.get('overall_risk_score', 0.5)
        
        # Create gauge chart
        categories = ['Very Low\n(0-0.2)', 'Low\n(0.2-0.4)', 'Moderate\n(0.4-0.6)', 'High\n(0.6-0.8)', 'Very High\n(0.8-1.0)']
        colors_gauge = ['#00AA00', '#90EE90', '#FFD700', '#FFA500', '#FF0000']
        positions = np.arange(len(categories))
        bars = ax1.bar(positions, [0.2]*5, color=colors_gauge, edgecolor='black', linewidth=2)
        ax1.axvline(risk_score * 5 - 0.5, color='black', linewidth=3, linestyle='--', label=f'Score: {risk_score:.2f}')
        ax1.set_xticks(positions)
        ax1.set_xticklabels(categories, fontsize=9)
        ax1.set_ylabel('Risk Level', fontweight='bold')
        ax1.set_ylim(0, 0.25)
        ax1.set_title('Overall Risk Score', fontweight='bold')
        ax1.legend(fontsize=10)
        
        # Panel 2: Component Risk Breakdown
        ax2 = fig.add_subplot(gs[0, 1])
        risk_components = risk_data.get('risk_components', {})
        
        if risk_components:
            components = list(risk_components.keys())
            scores = list(risk_components.values())
            colors_bar = ['#FF6B6B' if s > 0.7 else '#FFC93C' if s > 0.4 else '#6BCB77' for s in scores]
            bars = ax2.barh(components, scores, color=colors_bar, edgecolor='black', linewidth=1.5)
            ax2.set_xlabel('Risk Score', fontweight='bold')
            ax2.set_xlim(0, 1)
            ax2.set_title('Risk Component Breakdown', fontweight='bold')
            ax2.grid(True, alpha=0.3, axis='x')
            
            # Add value labels
            for i, (bar, score) in enumerate(zip(bars, scores)):
                ax2.text(score + 0.02, i, f'{score:.2f}', va='center', fontweight='bold')
        
        # Panel 3: Volumetric Estimates
        ax3 = fig.add_subplot(gs[1, 0])
        volumetrics = risk_data.get('volumetric_estimates', {})
        
        if volumetrics:
            volumes = {k: v for k, v in volumetrics.items() if isinstance(v, (int, float))}
            if volumes:
                ax3.bar(range(len(volumes)), list(volumes.values()), 
                       color=[OIL_COLOR, GAS_COLOR, WATER_COLOR][:len(volumes)],
                       edgecolor='black', linewidth=1.5)
                ax3.set_xticks(range(len(volumes)))
                ax3.set_xticklabels(volumes.keys(), fontsize=10)
                ax3.set_ylabel('Volume (MMBbl/BCF)', fontweight='bold')
                ax3.set_title('Volumetric Estimates', fontweight='bold')
                ax3.grid(True, alpha=0.3, axis='y')
                
                # Add value labels
                for i, v in enumerate(volumes.values()):
                    ax3.text(i, v + v*0.02, f'{v:.1f}', ha='center', fontweight='bold')
        
        # Panel 4: Trap Integrity Assessment
        ax4 = fig.add_subplot(gs[1, 1])
        trap_assessment = risk_data.get('trap_assessment', {})
        
        if trap_assessment:
            metrics = list(trap_assessment.keys())
            values = list(trap_assessment.values())
            colors_trap = ['#6BCB77' if v > 0.7 else '#FFC93C' if v > 0.4 else '#FF6B6B' for v in values]
            ax4.bar(range(len(metrics)), values, color=colors_trap, edgecolor='black', linewidth=1.5)
            ax4.set_xticks(range(len(metrics)))
            ax4.set_xticklabels(metrics, fontsize=9, rotation=45, ha='right')
            ax4.set_ylabel('Confidence Score', fontweight='bold')
            ax4.set_ylim(0, 1)
            ax4.set_title('Trap Integrity Metrics', fontweight='bold')
            ax4.grid(True, alpha=0.3, axis='y')
        
        # Panel 5: Drilling Risk Assessment
        ax5 = fig.add_subplot(gs[2, :])
        drilling_risks = risk_data.get('drilling_risks', {})
        
        if drilling_risks:
            risk_names = list(drilling_risks.keys())
            risk_values = list(drilling_risks.values())
            
            # Create horizontal stacked bar for multiple risks
            ax5.barh(range(len(risk_names)), risk_values, 
                    color=['#FF0000' if v == 'HIGH' else '#FFD700' if v == 'MEDIUM' else '#00AA00' 
                           for v in risk_values],
                    edgecolor='black', linewidth=1.5)
            ax5.set_yticks(range(len(risk_names)))
            ax5.set_yticklabels(risk_names, fontsize=10)
            ax5.set_xlabel('Risk Level', fontweight='bold')
            ax5.set_title('Drilling Risk Assessment', fontweight='bold')
            ax5.grid(True, alpha=0.3, axis='x')
            
            # Add legend
            high_patch = mpatches.Patch(color='#FF0000', label='HIGH')
            med_patch = mpatches.Patch(color='#FFD700', label='MEDIUM')
            low_patch = mpatches.Patch(color='#00AA00', label='LOW')
            ax5.legend(handles=[high_patch, med_patch, low_patch], loc='lower right', fontsize=10)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig

    @staticmethod
    def create_volumetric_chart(volumes: Dict[str, float], save_path: Optional[str] = None) -> plt.Figure:
        """Create volumetric estimates visualization."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Pie chart
        colors_vol = [OIL_COLOR, GAS_COLOR, WATER_COLOR]
        wedges, texts, autotexts = ax1.pie(volumes.values(), labels=volumes.keys(), autopct='%1.1f%%',
                                           colors=colors_vol, startangle=90,
                                           textprops={'fontsize': 11, 'fontweight': 'bold'})
        for autotext in autotexts:
            autotext.set_color('white')
        ax1.set_title('Volumetric Distribution', fontweight='bold')
        
        # Bar chart
        ax2.bar(volumes.keys(), volumes.values(), color=colors_vol, edgecolor='black', linewidth=2)
        ax2.set_ylabel('Volume (MMBbl/BCF)', fontweight='bold')
        ax2.set_title('Volumetric Estimates', fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Add value labels
        for i, (k, v) in enumerate(volumes.items()):
            ax2.text(i, v + v*0.02, f'{v:.1f}', ha='center', fontweight='bold')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig


class ComprehensiveAnalysisVisualizer:
    """Create comprehensive analysis reports combining all visualization types."""

    @staticmethod
    def create_analysis_summary_report(analysis_results: Dict[str, Any], output_dir: str = "./output_examples") -> Dict[str, str]:
        """
        Create a comprehensive set of visualizations for the entire analysis.
        
        Args:
            analysis_results: Complete analysis results from all agents
            output_dir: Directory to save visualizations
            
        Returns:
            Dictionary mapping visualization types to file paths
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        well_name = analysis_results.get('well_name', 'analysis').replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        visualization_files = {}
        
        # 1. Well Log Visualization
        if 'well_log_analysis' in analysis_results:
            well_log_data = analysis_results['well_log_analysis'].get('analysis', {})
            if well_log_data:
                fig = WellLogVisualizer.create_well_log_track(well_log_data)
                path = output_path / f"{well_name}_well_log_{timestamp}.png"
                plt.savefig(path, dpi=300, bbox_inches='tight')
                plt.close(fig)
                visualization_files['well_log'] = str(path)
                logger.info(f"Saved well log visualization: {path}")
        
        # 2. Seismic Section
        if 'seismic_analysis' in analysis_results:
            seismic_data = analysis_results['seismic_analysis'].get('analysis', {})
            if seismic_data:
                fig = SeismicVisualizer.create_seismic_section(seismic_data)
                path = output_path / f"{well_name}_seismic_section_{timestamp}.png"
                plt.savefig(path, dpi=300, bbox_inches='tight')
                plt.close(fig)
                visualization_files['seismic'] = str(path)
                logger.info(f"Saved seismic visualization: {path}")
        
        # 3. Fault Detection Map
        if 'seismic_analysis' in analysis_results:
            faults = analysis_results['seismic_analysis'].get('faults', [])
            if faults:
                fig = SeismicVisualizer.create_fault_detection_map(faults)
                path = output_path / f"{well_name}_faults_{timestamp}.png"
                plt.savefig(path, dpi=300, bbox_inches='tight')
                plt.close(fig)
                visualization_files['faults'] = str(path)
                logger.info(f"Saved fault visualization: {path}")
        
        # 4. Reservoir Properties Panel
        if 'reservoir_analysis' in analysis_results:
            reservoir_data = analysis_results['reservoir_analysis'].get('analysis', {})
            if reservoir_data:
                fig = ReservoirVisualizer.create_reservoir_properties_panel(reservoir_data)
                path = output_path / f"{well_name}_reservoir_{timestamp}.png"
                plt.savefig(path, dpi=300, bbox_inches='tight')
                plt.close(fig)
                visualization_files['reservoir'] = str(path)
                logger.info(f"Saved reservoir visualization: {path}")
        
        # 5. Risk Assessment Dashboard
        if 'risk_assessment' in analysis_results:
            risk_data = analysis_results['risk_assessment'].get('analysis', {})
            if risk_data:
                fig = RiskAssessmentVisualizer.create_risk_dashboard(risk_data)
                path = output_path / f"{well_name}_risk_dashboard_{timestamp}.png"
                plt.savefig(path, dpi=300, bbox_inches='tight')
                plt.close(fig)
                visualization_files['risk'] = str(path)
                logger.info(f"Saved risk assessment visualization: {path}")
        
        return visualization_files

    @staticmethod
    def figure_to_base64(fig: plt.Figure) -> str:
        """Convert matplotlib figure to base64 string for web display."""
        import base64
        
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode()
        buffer.close()
        plt.close(fig)
        
        return image_base64

    @staticmethod
    def create_html_report(analysis_results: Dict[str, Any], output_path: str = "analysis_report.html") -> str:
        """
        Create an interactive HTML report with embedded visualizations.
        
        Args:
            analysis_results: Complete analysis results
            output_path: Path to save HTML report
            
        Returns:
            Path to generated HTML file
        """
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Oil & Gas Well Analysis Report</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f5f5f5;
                }
                .header {
                    background-color: #1a472a;
                    color: white;
                    padding: 20px;
                    border-radius: 5px;
                }
                .section {
                    background-color: white;
                    margin: 20px 0;
                    padding: 20px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }
                .section h2 {
                    color: #1a472a;
                    border-bottom: 2px solid #FFD700;
                    padding-bottom: 10px;
                }
                img {
                    max-width: 100%;
                    height: auto;
                    margin: 10px 0;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 10px 0;
                }
                table th, table td {
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }
                table th {
                    background-color: #1a472a;
                    color: white;
                }
                table tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
                .metric {
                    display: inline-block;
                    margin: 10px 20px 10px 0;
                    padding: 10px;
                    background-color: #f0f0f0;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Oil & Gas Well Analysis Report</h1>
                <p>Well: """ + analysis_results.get('well_name', 'Unknown') + """</p>
                <p>Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            </div>
        """
        
        # Add sections for each analysis
        if 'well_log_analysis' in analysis_results:
            html_content += """
            <div class="section">
                <h2>Well Log Analysis</h2>
                <p>Lithology classification, fluid identification, and reservoir quality assessment.</p>
                <pre>""" + json.dumps(analysis_results['well_log_analysis'], indent=2)[:500] + """...</pre>
            </div>
            """
        
        if 'seismic_analysis' in analysis_results:
            html_content += """
            <div class="section">
                <h2>Seismic Analysis</h2>
                <p>Amplitude anomalies, fault detection, and horizon picking.</p>
                <pre>""" + json.dumps(analysis_results['seismic_analysis'], indent=2)[:500] + """...</pre>
            </div>
            """
        
        if 'reservoir_analysis' in analysis_results:
            html_content += """
            <div class="section">
                <h2>Reservoir Characterization</h2>
                <p>Permeability, saturation, and formation pressure estimates.</p>
                <pre>""" + json.dumps(analysis_results['reservoir_analysis'], indent=2)[:500] + """...</pre>
            </div>
            """
        
        if 'risk_assessment' in analysis_results:
            html_content += """
            <div class="section">
                <h2>Risk Assessment</h2>
                <p>Exploration risk, volumetric estimates, and drilling recommendations.</p>
                <pre>""" + json.dumps(analysis_results['risk_assessment'], indent=2)[:500] + """...</pre>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {output_path}")
        return output_path


# Convenience functions for quick visualization
def plot_well_log(well_data: Dict[str, Any], save_path: Optional[str] = None) -> plt.Figure:
    """Quick function to plot well logs."""
    return WellLogVisualizer.create_well_log_track(well_data, save_path)


def plot_seismic(seismic_data: Dict[str, Any], save_path: Optional[str] = None) -> plt.Figure:
    """Quick function to plot seismic section."""
    return SeismicVisualizer.create_seismic_section(seismic_data, save_path)


def plot_reservoir(reservoir_data: Dict[str, Any], save_path: Optional[str] = None) -> plt.Figure:
    """Quick function to plot reservoir properties."""
    return ReservoirVisualizer.create_reservoir_properties_panel(reservoir_data, save_path)


def plot_risk(risk_data: Dict[str, Any], save_path: Optional[str] = None) -> plt.Figure:
    """Quick function to plot risk assessment."""
    return RiskAssessmentVisualizer.create_risk_dashboard(risk_data, save_path)
