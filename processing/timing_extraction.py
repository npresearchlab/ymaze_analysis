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
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import logging

from config import CONFIG, ColumnNames

logger = logging.getLogger(__name__)


@dataclass
class Trial:
    """Represents a single trial with timing information."""
    environment: str
    trial_type: str  # e.g., 'np1', 'np2', 'p'
    trial_num: int   # Sequential number within environment (1, 2, 3, ...)
    start: float
    end: float
    
    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass 
class TimingData:
    """Complete timing data for a subject."""
    trials: List[Trial]
    trials_by_num: Dict[int, List[Trial]]  # Grouped by trial_num for FSL output
    max_trial_num: int  # Highest trial number seen
    last_event_end: float  # For rest period calculation
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert trials to DataFrame."""
        return pd.DataFrame([
            {
                'env': t.environment,
                'trial': t.trial_type,
                'trial_num': t.trial_num,
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
    >>> print(f"Found {len(timing_data.trials)} total trials")
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
        env_trial_counter = {}  # Track trial number per environment
        
        for idx, row in df.iterrows():
            # Track environment
            env = row[self.columns.environment]
            if pd.notna(env):
                if env != current_env:
                    # New environment - reset counter
                    current_env = env
                    if current_env not in env_trial_counter:
                        env_trial_counter[current_env] = 0
            
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
                        trial_num=start_info['trial_num'],
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
                # This is a start marker - increment trial counter for this env
                env_trial_counter[current_env] = env_trial_counter.get(current_env, 0) + 1
                trial_num = env_trial_counter[current_env]
                
                current_trials[teleport_type] = {
                    'time': timestamp,
                    'env': current_env,
                    'trial_num': trial_num
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
                trial_num=t.trial_num,
                start=t.start - min_start,
                end=t.end - min_start
            )
            for t in trials
        ]
    
    def _sort_trials(self, trials: List[Trial]) -> List[Trial]:
        """Sort trials by start time."""
        return sorted(trials, key=lambda t: t.start)
    
    def _group_by_trial_num(self, trials: List[Trial]) -> Tuple[Dict[int, List[Trial]], int]:
        """
        Group trials by their trial number for FSL output.
        
        Returns dict mapping trial_num to list of trials, and max trial num.
        """
        trials_by_num = defaultdict(list)
        max_num = 0
        
        for trial in trials:
            trials_by_num[trial.trial_num].append(trial)
            max_num = max(max_num, trial.trial_num)
        
        return dict(trials_by_num), max_num
    
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
        
        # Group by trial number
        trials_by_num, max_trial_num = self._group_by_trial_num(trials)
        
        # Calculate last event end time
        last_end = max(t.end for t in trials) if trials else 0.0
        
        logger.info(
            f"Extracted timing for {len(trials)} trials "
            f"(max trial_num: {max_trial_num})"
        )
        
        return TimingData(
            trials=trials,
            trials_by_num=trials_by_num,
            max_trial_num=max_trial_num,
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
