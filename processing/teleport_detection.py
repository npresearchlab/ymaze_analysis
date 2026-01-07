"""
Teleportation detection for Y-Maze behavioral data.

Detects when participants are teleported back to starting positions
based on sudden changes in X, Z coordinates.
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
import logging

from config import CONFIG, TeleportConfig, ColumnNames

logger = logging.getLogger(__name__)


@dataclass
class TeleportEvent:
    """Represents a single teleportation event."""
    index: int
    timestamp: float
    x: float
    z: float
    target_index: int
    target_position: Tuple[float, float]
    distance_traveled: float
    is_first_to_target: bool = False


class TeleportDetector:
    """
    Detects teleportation events in Y-Maze coordinate data.
    
    A teleportation is detected when the distance between consecutive 
    positions exceeds a threshold (indicating a sudden jump rather than
    normal movement).
    
    Parameters
    ----------
    config : TeleportConfig
        Configuration for detection thresholds and target positions
    columns : ColumnNames
        Column name configuration for the DataFrame
        
    Example
    -------
    >>> detector = TeleportDetector()
    >>> df, events = detector.detect(coordinate_df)
    >>> print(f"Found {len(events)} teleportation events")
    """

    def __init__(
        self,
        config: TeleportConfig = CONFIG.teleport,
        columns: ColumnNames = CONFIG.columns
    ):
        self.config = config
        self.columns = columns
        
        # Track first teleport to each position
        self._first_teleport_seen = {}
    
    def _calculate_position_changes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add columns tracking position changes between consecutive rows."""
        df = df.copy()
        
        # Previous positions
        df['_x_prev'] = df[self.columns.x].shift(1)
        df['_z_prev'] = df[self.columns.z].shift(1)
        
        # Euclidean distance between consecutive positions
        df['_position_change'] = np.sqrt(
            (df[self.columns.x] - df['_x_prev'])**2 +
            (df[self.columns.z] - df['_z_prev'])**2
        )
        
        return df
    
    def _check_target_proximity(
        self,
        x: float,
        z: float
    ) -> Optional[Tuple[int, Tuple[float, float]]]:
        """
        Check if position is close to any target position.
        
        Returns
        -------
        Optional[Tuple[int, Tuple[float, float]]]
            (target_index, target_position) if near a target, else None
        """
        for idx, (target_x, target_z) in enumerate(self.config.target_positions):
            distance = np.sqrt((x - target_x)**2 + (z - target_z)**2)
            
            if distance <= self.config.position_tolerance:
                return idx, (target_x, target_z)
        
        return None
    
    def detect(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[TeleportEvent]]:
        """
        Detect and label teleportation events in coordinate data.
        
        Parameters
        ----------
        df : pd.DataFrame
            Coordinate data with X, Z, and time columns
            
        Returns
        -------
        Tuple[pd.DataFrame, List[TeleportEvent]]
            - DataFrame with teleportation labels added
            - List of TeleportEvent objects for further analysis
        """
        # Reset first teleport tracking
        self._first_teleport_seen = {
            i: False for i in range(len(self.config.target_positions))
        }
        
        # Work on a copy
        labeled_df = df.copy()
        
        # Calculate position changes
        labeled_df = self._calculate_position_changes(labeled_df)
        
        # Initialize labeling columns
        labeled_df['is_teleport'] = False
        labeled_df['teleport_to'] = None
        
        # Collect teleport events
        events: List[TeleportEvent] = []
        
        # Process each row (skip first - no previous position)
        for idx in range(1, len(labeled_df)):
            row = labeled_df.iloc[idx]
            
            # Check for significant position change
            if row['_position_change'] < self.config.distance_threshold:
                continue
            
            # Any large position change is a teleport
            # (We no longer require landing at a specific target position)
            current_pos = (row[self.columns.x], row[self.columns.z])
            
            # Try to match to a known target for logging purposes
            target_result = self._check_target_proximity(
                row[self.columns.x],
                row[self.columns.z]
            )
            
            if target_result is not None:
                target_idx, target_pos = target_result
            else:
                # Unknown target - still count as teleport
                target_idx = -1
                target_pos = current_pos
            
            # This is a teleportation!
            actual_idx = labeled_df.index[idx]
            labeled_df.at[actual_idx, 'is_teleport'] = True
            labeled_df.at[actual_idx, 'teleport_to'] = (
                f"Target {target_idx + 1}: ({target_pos[0]}, {target_pos[1]})"
            )
            
            # Check if first teleport to this target
            if target_idx >= 0:
                is_first = not self._first_teleport_seen[target_idx]
                if is_first:
                    self._first_teleport_seen[target_idx] = True
            else:
                is_first = False  # Unknown target, don't track as "first"
            
            # Create event record
            event = TeleportEvent(
                index=actual_idx,
                timestamp=row[self.columns.time],
                x=row[self.columns.x],
                z=row[self.columns.z],
                target_index=target_idx,
                target_position=target_pos,
                distance_traveled=row['_position_change'],
                is_first_to_target=is_first
            )
            events.append(event)
        
        # Clean up temporary columns
        labeled_df = labeled_df.drop(columns=['_x_prev', '_z_prev', '_position_change'])
        
        # Log summary
        logger.info(
            f"Detected {len(events)} teleportation events "
            f"({sum(1 for e in events if e.is_first_to_target)} first-time)"
        )
        
        return labeled_df, events


def detect_teleportations(
    df: pd.DataFrame,
    target_positions: Optional[List[Tuple[float, float]]] = None,
    distance_threshold: Optional[float] = None,
    position_tolerance: Optional[float] = None
) -> Tuple[pd.DataFrame, List[TeleportEvent]]:
    """
    Convenience function for detecting teleportations with custom parameters.
    
    This is a simpler interface than using TeleportDetector directly.
    
    Parameters
    ----------
    df : pd.DataFrame
        Coordinate data
    target_positions : Optional[List[Tuple[float, float]]]
        Override default target positions
    distance_threshold : Optional[float]
        Override default distance threshold
    position_tolerance : Optional[float]
        Override default position tolerance
        
    Returns
    -------
    Tuple[pd.DataFrame, List[TeleportEvent]]
        Labeled DataFrame and list of events
    """
    # Build custom config if any overrides provided
    config = TeleportConfig(
        target_positions=target_positions or CONFIG.teleport.target_positions,
        distance_threshold=distance_threshold or CONFIG.teleport.distance_threshold,
        position_tolerance=position_tolerance or CONFIG.teleport.position_tolerance
    )
    
    detector = TeleportDetector(config=config)
    return detector.detect(df)


def get_teleport_summary(events: List[TeleportEvent]) -> pd.DataFrame:
    """
    Create a summary DataFrame from teleport events.
    
    Parameters
    ----------
    events : List[TeleportEvent]
        List of detected teleport events
        
    Returns
    -------
    pd.DataFrame
        Summary with columns: index, timestamp, x, z, target, is_first
    """
    if not events:
        return pd.DataFrame(columns=[
            'index', 'timestamp', 'x', 'z', 'target', 'is_first'
        ])
    
    return pd.DataFrame([
        {
            'index': e.index,
            'timestamp': e.timestamp,
            'x': e.x,
            'z': e.z,
            'target': f"Target {e.target_index + 1}",
            'is_first': e.is_first_to_target
        }
        for e in events
    ])
