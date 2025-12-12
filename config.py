"""
Configuration settings for Y-Maze behavioral analysis pipeline.

This file centralizes all configurable parameters, making it easy to:
- Adjust paths for different machines/users
- Modify detection thresholds
- Change target positions for different maze configurations

Usage:
    from config import CONFIG
    threshold = CONFIG["teleport"]["distance_threshold"]
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class PathConfig:
    """File path configuration."""
    data_dir: Path = Path("/Volumes/YB_Drive/YB/1_data/behavior/")
    output_dir: Path = Path("/Volumes/YB_Drive/YB/2_analysis/behavior/")
    
    def validate(self) -> List[str]:
        """Check that required directories exist. Returns list of errors."""
        errors = []
        if not self.data_dir.is_dir():
            errors.append(f"Data directory not found: {self.data_dir}")
        if not self.output_dir.is_dir():
            errors.append(f"Output directory not found: {self.output_dir}")
        return errors


@dataclass
class TeleportConfig:
    """Teleportation detection parameters."""
    # Minimum distance (in game units) to consider a movement as teleportation
    distance_threshold: float = 5.0
    
    # How close to a target position counts as "at" that position
    position_tolerance: float = 1.0
    
    # Target positions in the maze: (x, z) coordinates
    # Position 1: Starting area
    # Position 2: Alternative starting point
    target_positions: List[Tuple[float, float]] = field(
        default_factory=lambda: [(36.52, 22.0), (0.0, -32.0)]
    )


@dataclass
class OutputConfig:
    """Output file naming conventions."""
    # Prefix for subject folders (e.g., "sub-01", "sub-02")
    subject_prefix: str = "sub"
    
    # Whether to save intermediate processing files (for debugging)
    save_intermediate_files: bool = False
    
    # FSL timing file names
    timing_files: dict = field(default_factory=lambda: {
        "first_np": "firstnp.txt",
        "last_np": "lastnp.txt",
        "probe": "probe.txt",
        "rest": "rest.txt"
    })


@dataclass
class ColumnNames:
    """
    Expected column names in coordinate CSV files.
    
    Note: Original files have leading spaces in column names.
    These are the CLEANED names (after stripping whitespace).
    """
    environment: str = "Environment"
    time: str = "Cummulative_Time"  # Note: typo preserved from original data
    x: str = "X"
    z: str = "Z"
    rotation: str = "Rotation"


@dataclass
class PipelineConfig:
    """Master configuration combining all settings."""
    paths: PathConfig = field(default_factory=PathConfig)
    teleport: TeleportConfig = field(default_factory=TeleportConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    columns: ColumnNames = field(default_factory=ColumnNames)
    
    def validate(self) -> List[str]:
        """Validate all configuration settings. Returns list of errors."""
        errors = self.paths.validate()
        
        if self.teleport.distance_threshold <= 0:
            errors.append("Distance threshold must be positive")
        
        if self.teleport.position_tolerance <= 0:
            errors.append("Position tolerance must be positive")
        
        if not self.teleport.target_positions:
            errors.append("At least one target position must be specified")
        
        return errors


# Default configuration instance
CONFIG = PipelineConfig()


def load_config_from_dict(config_dict: dict) -> PipelineConfig:
    """
    Create a PipelineConfig from a dictionary (e.g., loaded from JSON/YAML).
    
    Parameters
    ----------
    config_dict : dict
        Configuration dictionary with nested structure matching dataclass fields
        
    Returns
    -------
    PipelineConfig
        Configured pipeline settings
    """
    paths = PathConfig(
        data_dir=Path(config_dict.get("data_dir", CONFIG.paths.data_dir)),
        output_dir=Path(config_dict.get("output_dir", CONFIG.paths.output_dir))
    )
    
    teleport = TeleportConfig(
        distance_threshold=config_dict.get("distance_threshold", CONFIG.teleport.distance_threshold),
        position_tolerance=config_dict.get("position_tolerance", CONFIG.teleport.position_tolerance),
        target_positions=config_dict.get("target_positions", CONFIG.teleport.target_positions)
    )
    
    output = OutputConfig(
        subject_prefix=config_dict.get("subject_prefix", CONFIG.output.subject_prefix),
        save_intermediate_files=config_dict.get("save_intermediate", CONFIG.output.save_intermediate_files)
    )
    
    return PipelineConfig(paths=paths, teleport=teleport, output=output)
