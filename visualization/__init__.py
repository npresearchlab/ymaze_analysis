"""
Visualization utilities for Y-Maze behavioral analysis.
"""

from .trajectory_plots import (
    create_trajectory_plot,
    save_trajectory_plot,
    create_trial_timeline
)

__all__ = [
    'create_trajectory_plot',
    'save_trajectory_plot',
    'create_trial_timeline'
]
