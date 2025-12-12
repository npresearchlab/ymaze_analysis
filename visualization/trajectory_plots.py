"""
Visualization utilities for Y-Maze behavioral data.

Creates trajectory plots showing:
- Movement paths
- Teleportation events
- Target positions
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from pathlib import Path
from typing import List, Tuple, Optional
import logging

from config import CONFIG, ColumnNames, TeleportConfig
from processing.teleport_detection import TeleportEvent

logger = logging.getLogger(__name__)


def create_trajectory_plot(
    df: pd.DataFrame,
    teleport_events: Optional[List[TeleportEvent]] = None,
    target_positions: Optional[List[Tuple[float, float]]] = None,
    title: str = "Y-Maze Trajectory",
    columns: ColumnNames = CONFIG.columns,
    figsize: Tuple[int, int] = (12, 8)
) -> Tuple[Figure, Axes]:
    """
    Create a trajectory plot showing movement and teleportation events.
    
    Parameters
    ----------
    df : pd.DataFrame
        Coordinate data with X and Z columns
    teleport_events : Optional[List[TeleportEvent]]
        List of detected teleportation events to highlight
    target_positions : Optional[List[Tuple[float, float]]]
        Target positions to mark on the plot
    title : str
        Plot title
    columns : ColumnNames
        Column name configuration
    figsize : Tuple[int, int]
        Figure size in inches
        
    Returns
    -------
    Tuple[Figure, Axes]
        Matplotlib figure and axes objects
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for plotting")
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No data to display", ha='center', va='center')
        return fig, ax
    
    # Use default target positions if not provided
    if target_positions is None:
        target_positions = CONFIG.teleport.target_positions
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot all positions as faint scatter
    ax.scatter(
        df[columns.x], 
        df[columns.z], 
        alpha=0.3, 
        s=10,
        label='Positions',
        color='blue'
    )
    
    # Plot movement path
    ax.plot(
        df[columns.x], 
        df[columns.z], 
        'b-', 
        alpha=0.2,
        linewidth=0.5
    )
    
    # Plot teleportation events
    if teleport_events:
        _plot_teleport_events(ax, df, teleport_events, columns)
    
    # Mark target positions
    for i, (x, z) in enumerate(target_positions):
        ax.scatter(
            [x], [z],
            c='green',
            s=200,
            marker='*',
            edgecolors='darkgreen',
            linewidths=1,
            label=f'Target {i+1}: ({x}, {z})',
            zorder=10
        )
    
    ax.set_xlabel('X Position')
    ax.set_ylabel('Z Position')
    ax.set_title(title)
    ax.legend(loc='best', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='datalim')
    
    plt.tight_layout()
    
    return fig, ax


def _plot_teleport_events(
    ax: Axes,
    df: pd.DataFrame,
    events: List[TeleportEvent],
    columns: ColumnNames
) -> None:
    """Add teleportation events to an existing axes."""
    if not events:
        return
    
    # Separate first vs regular teleports
    first_teleports = [e for e in events if e.is_first_to_target]
    regular_teleports = [e for e in events if not e.is_first_to_target]
    
    # Plot regular teleports
    if regular_teleports:
        ax.scatter(
            [e.x for e in regular_teleports],
            [e.z for e in regular_teleports],
            c='red',
            s=100,
            marker='o',
            label='Teleport returns',
            zorder=5
        )
    
    # Plot first teleports (highlighted)
    if first_teleports:
        ax.scatter(
            [e.x for e in first_teleports],
            [e.z for e in first_teleports],
            c='orange',
            s=150,
            marker='o',
            edgecolors='red',
            linewidths=2,
            label='First teleport to position',
            zorder=6
        )
        
        # Add annotations for first teleports
        for event in first_teleports:
            ax.annotate(
                f"First: t={event.timestamp:.1f}",
                xy=(event.x, event.z),
                xytext=(10, 10),
                textcoords='offset points',
                fontsize=8,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    fc="yellow",
                    alpha=0.7
                ),
                zorder=7
            )
    
    # Draw arrows for teleportations
    for event in events:
        # Get previous position from DataFrame
        if event.index > 0:
            prev_idx = event.index - 1
            if prev_idx in df.index:
                prev_x = df.loc[prev_idx, columns.x]
                prev_z = df.loc[prev_idx, columns.z]
                
                dx = event.x - prev_x
                dz = event.z - prev_z
                
                # Only draw arrow if there's significant distance
                if np.sqrt(dx**2 + dz**2) > 1:
                    ax.arrow(
                        prev_x, prev_z, dx, dz,
                        color='red',
                        width=0.1,
                        head_width=0.5,
                        alpha=0.5,
                        length_includes_head=True,
                        zorder=4
                    )


def save_trajectory_plot(
    fig: Figure,
    output_path: Path,
    filename: str = "trajectory.png",
    dpi: int = 150
) -> Path:
    """
    Save a trajectory plot to file.
    
    Parameters
    ----------
    fig : Figure
        Matplotlib figure to save
    output_path : Path
        Directory for output file
    filename : str
        Output filename
    dpi : int
        Resolution for raster formats
        
    Returns
    -------
    Path
        Path to saved file
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    
    filepath = output_path / filename
    fig.savefig(filepath, dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    
    logger.info(f"Saved trajectory plot to {filepath}")
    return filepath


def create_trial_timeline(
    timing_data,  # TimingData object
    title: str = "Trial Timeline",
    figsize: Tuple[int, int] = (14, 6)
) -> Tuple[Figure, Axes]:
    """
    Create a timeline visualization of trial events.
    
    Parameters
    ----------
    timing_data : TimingData
        Timing information from TimestampExtractor
    title : str
        Plot title
    figsize : Tuple[int, int]
        Figure size
        
    Returns
    -------
    Tuple[Figure, Axes]
        Matplotlib figure and axes
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    trials = timing_data.trials
    if not trials:
        ax.text(0.5, 0.5, "No trials to display", ha='center', va='center')
        return fig, ax
    
    # Color map for trial types
    colors = {
        'p': 'red',
        'np1': 'blue',
        'np2': 'green',
        'np3': 'purple',
        'np4': 'orange',
        'np5': 'brown'
    }
    
    # Get unique environments
    envs = list(set(t.environment for t in trials))
    env_positions = {env: i for i, env in enumerate(envs)}
    
    # Plot each trial as a horizontal bar
    for trial in trials:
        color = colors.get(trial.trial_type, 'gray')
        y_pos = env_positions.get(trial.environment, 0)
        
        ax.barh(
            y_pos,
            trial.duration,
            left=trial.start,
            height=0.6,
            color=color,
            alpha=0.7,
            edgecolor='black',
            linewidth=0.5,
            label=trial.trial_type
        )
    
    # Remove duplicate legend entries
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='upper right')
    
    ax.set_yticks(range(len(envs)))
    ax.set_yticklabels(envs)
    ax.set_xlabel('Time')
    ax.set_ylabel('Environment')
    ax.set_title(title)
    ax.grid(True, axis='x', alpha=0.3)
    
    plt.tight_layout()
    
    return fig, ax
