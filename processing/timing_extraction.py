"""
Timing extraction for Y-Maze behavioral data.

Extracts trial timestamps and converts to FSL-compatible timing format.
Combines functionality from:
- collapse_labels.py (extracting start/end timestamps)
- create_timing.py (generating FSL timing files)
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import logging

from config import CONFIG, ColumnNames

logger = logging.getLogger(__name__)


@dataclass
class Trial:
    """Represents a single trial with timing information."""
    environment: str
    trial_type: str  # e.g., 'np1', 'np2', 'p'
    start: float
    end: float
    
    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass 
class TimingData:
    """Complete timing data for a subject."""
    trials: List[Trial]
    first_np_trials: List[Trial]  # First non-probe before each probe
    last_np_trials: List[Trial]   # Last non-probe before each probe
    probe_trials: List[Trial]     # All probe trials
    last_event_end: float         # For rest period calculation
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert trials to DataFrame."""
        return pd.DataFrame([
            {
                'env': t.environment,
                'trial': t.trial_type,
                'start': t.start,
                'end': t.end,
                'duration': t.duration
            }
            for t in self.trials
        ])


class TimestampExtractor:
    """
    Extracts trial timestamps from labeled coordinate data.
    
    Pairs start markers (np1, np2, p) with their corresponding
    end markers (np1end, np2end, pend) to determine trial timing.
    
    Parameters
    ----------
    columns : ColumnNames
        Column name configuration
    normalize_timestamps : bool
        Whether to normalize timestamps relative to first event
        
    Example
    -------
    >>> extractor = TimestampExtractor()
    >>> timing_data = extractor.extract(labeled_df)
    >>> print(f"Found {len(timing_data.probe_trials)} probe trials")
    """
    
    def __init__(
        self,
        columns: ColumnNames = CONFIG.columns,
        normalize_timestamps: bool = True
    ):
        self.columns = columns
        self.normalize_timestamps = normalize_timestamps
    
    def _extract_trial_pairs(self, df: pd.DataFrame) -> List[Trial]:
        """
        Extract start-end pairs for each trial.
        
        Returns list of Trial objects with absolute timestamps.
        """
        trials = []
        current_trials = {}  # Active trials waiting for end marker
        current_env = None
        
        for idx, row in df.iterrows():
            # Track environment
            env = row[self.columns.environment]
            if pd.notna(env):
                current_env = env
            
            teleport_type = row['teleport_type']
            timestamp = row[self.columns.time]
            
            # Skip empty labels
            if pd.isna(teleport_type) or teleport_type == '':
                continue
            
            teleport_type = str(teleport_type)
            
            if teleport_type.endswith('end'):
                # This is an end marker
                base_type = teleport_type.replace('end', '')
                
                if base_type in current_trials:
                    # Found matching start - create trial
                    start_info = current_trials[base_type]
                    
                    trial = Trial(
                        environment=start_info['env'],
                        trial_type=base_type,
                        start=start_info['time'],
                        end=timestamp
                    )
                    trials.append(trial)
                    
                    del current_trials[base_type]
                else:
                    logger.warning(
                        f"Found end marker '{teleport_type}' without "
                        f"matching start at index {idx}"
                    )
            else:
                # This is a start marker
                current_trials[teleport_type] = {
                    'time': timestamp,
                    'env': current_env
                }
        
        # Warn about unmatched start markers
        if current_trials:
            logger.warning(
                f"Unmatched start markers: {list(current_trials.keys())}"
            )
        
        return trials
    
    def _normalize_trials(self, trials: List[Trial]) -> List[Trial]:
        """Normalize all timestamps relative to first event."""
        if not trials:
            return trials
        
        min_start = min(t.start for t in trials)
        
        return [
            Trial(
                environment=t.environment,
                trial_type=t.trial_type,
                start=t.start - min_start,
                end=t.end - min_start
            )
            for t in trials
        ]
    
    def _sort_trials(self, trials: List[Trial]) -> List[Trial]:
        """Sort trials by start time."""
        return sorted(trials, key=lambda t: t.start)
    
    def _categorize_trials(
        self,
        trials: List[Trial]
    ) -> Tuple[List[Trial], List[Trial], List[Trial]]:
        """
        Categorize trials into first_np, last_np, and probe lists.
        
        For FSL timing files, we need:
        - first_np: First non-probe trial before each probe
        - last_np: Last non-probe trial before each probe  
        - probe: All probe trials
        """
        first_np_trials = []
        last_np_trials = []
        probe_trials = []
        
        # Group by environment
        env_trials = {}
        for trial in trials:
            if trial.environment not in env_trials:
                env_trials[trial.environment] = []
            env_trials[trial.environment].append(trial)
        
        # Process each environment
        for env, env_trial_list in env_trials.items():
            # Sort by start time within environment
            sorted_trials = sorted(env_trial_list, key=lambda t: t.start)
            
            np_trials_before_probe = []
            
            for trial in sorted_trials:
                if trial.trial_type.startswith('np'):
                    np_trials_before_probe.append(trial)
                elif trial.trial_type == 'p':
                    probe_trials.append(trial)
                    
                    if np_trials_before_probe:
                        first_np_trials.append(np_trials_before_probe[0])
                        last_np_trials.append(np_trials_before_probe[-1])
                    
                    # Reset for next probe
                    np_trials_before_probe = []
        
        return first_np_trials, last_np_trials, probe_trials
    
    def extract(self, df: pd.DataFrame) -> TimingData:
        """
        Extract timing data from labeled coordinate DataFrame.
        
        Parameters
        ----------
        df : pd.DataFrame
            Labeled coordinate data with 'teleport_type' column
            
        Returns
        -------
        TimingData
            Complete timing information for all trials
        """
        if 'teleport_type' not in df.columns:
            raise ValueError(
                "DataFrame must have 'teleport_type' column. "
                "Run trial labeling first."
            )
        
        # Extract trial pairs
        trials = self._extract_trial_pairs(df)
        
        # Sort by start time
        trials = self._sort_trials(trials)
        
        # Normalize if requested
        if self.normalize_timestamps:
            trials = self._normalize_trials(trials)
        
        # Categorize for FSL
        first_np, last_np, probes = self._categorize_trials(trials)
        
        # Calculate last event end time
        last_end = max(t.end for t in trials) if trials else 0.0
        
        logger.info(
            f"Extracted timing for {len(trials)} trials: "
            f"{len(probes)} probes, {len(first_np)} first_np, {len(last_np)} last_np"
        )
        
        return TimingData(
            trials=trials,
            first_np_trials=first_np,
            last_np_trials=last_np,
            probe_trials=probes,
            last_event_end=last_end
        )


def extract_timing(
    df: pd.DataFrame,
    normalize: bool = True
) -> TimingData:
    """
    Convenience function for extracting timing data.
    
    Parameters
    ----------
    df : pd.DataFrame
        Labeled coordinate data
    normalize : bool
        Whether to normalize timestamps to start at 0
        
    Returns
    -------
    TimingData
        Complete timing information
    """
    extractor = TimestampExtractor(normalize_timestamps=normalize)
    return extractor.extract(df)


def trials_to_dict_list(trials: List[Trial]) -> List[Dict]:
    """
    Convert Trial objects to list of dicts (for FSL writers).
    
    Parameters
    ----------
    trials : List[Trial]
        Trial objects
        
    Returns
    -------
    List[Dict]
        List of dicts with 'start' and 'duration' keys
    """
    return [
        {'start': t.start, 'duration': t.duration}
        for t in trials
    ]
