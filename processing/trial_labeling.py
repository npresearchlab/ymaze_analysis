"""
Trial labeling for Y-Maze behavioral data.

Labels teleportation events as:
- 'np1', 'np2', etc.: Non-probe trials
- 'p': Probe trials (last teleportation in each environment)
- 'np1end', 'np2end', 'pend': End markers for each trial type
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

from config import CONFIG, ColumnNames

logger = logging.getLogger(__name__)


@dataclass
class LabelingSummary:
    """Summary of labeling results."""
    n_teleports: int
    n_environments: int
    n_probes: int
    n_non_probes: int
    n_end_markers: int
    labels_by_type: Dict[str, int]


class TrialLabeler:
    """
    Labels teleportation events with trial type markers.
    
    Labeling scheme:
    - First row is always 'np1' (start of first non-probe trial)
    - Each teleportation is labeled based on position in sequence
    - Last teleportation in each environment is 'p' (probe)
    - End markers ('np1end', 'pend', etc.) mark trial endings
    
    Parameters
    ----------
    columns : ColumnNames
        Column name configuration
        
    Example
    -------
    >>> labeler = TrialLabeler()
    >>> labeled_df, summary = labeler.label(teleport_detected_df)
    >>> print(f"Found {summary.n_probes} probe trials")
    """
    
    def __init__(self, columns: ColumnNames = CONFIG.columns):
        self.columns = columns
    
    def _get_environments(self, df: pd.DataFrame) -> np.ndarray:
        """Get unique environments in order of appearance."""
        # Get unique environments preserving order
        seen = set()
        environments = []
        for env in df[self.columns.environment]:
            if pd.notna(env) and env not in seen:
                seen.add(env)
                environments.append(env)
        return np.array(environments)
    
    def _label_teleport_types(
        self,
        df: pd.DataFrame,
        environments: np.ndarray
    ) -> pd.DataFrame:
        """
        First pass: Label teleportations as 'np#' or 'p'.
        
        - Non-probe trials get numbered labels (np1, np2, ...)
        - Probe trials are identified by teleporting to a DIFFERENT destination
          than the other trials in that environment
        - If all teleports go to the same destination, the environment is
          incomplete and all teleports are labeled as non-probe
        """
        df = df.copy()
        df['teleport_type'] = pd.NA
        
        # Label first row as np1 (start of first trial)
        if len(df) > 0:
            df.loc[df.index[0], 'teleport_type'] = 'np1'
        
        # Process each environment
        first_env = True
        
        for env in environments:
            # Skip transition periods
            if env == 'transition':
                continue
                
            # Get teleportation rows for this environment
            env_mask = (df[self.columns.environment] == env) & (df['is_teleport'] == True)
            env_teleports = df[env_mask]
            
            if len(env_teleports) == 0:
                first_env = False
                continue
            
            # Get destinations for each teleport (rounded to avoid float comparison issues)
            destinations = []
            for idx in env_teleports.index:
                dest = (round(df.loc[idx, self.columns.x], 0), 
                       round(df.loc[idx, self.columns.z], 0))
                destinations.append((idx, dest))
            
            # Determine if last teleport is a probe (different destination)
            last_idx, last_dest = destinations[-1]
            other_dests = [d for _, d in destinations[:-1]]
            
            # Check if last destination differs from the others
            is_probe = False
            if other_dests:
                from collections import Counter
                dest_counts = Counter(other_dests)
                majority_dest = dest_counts.most_common(1)[0][0]
                is_probe = (last_dest != majority_dest)
            
            if not is_probe:
                logger.warning(
                    f"Environment '{env}' appears incomplete: last teleport "
                    f"goes to same destination as NP trials ({last_dest})"
                )
            
            # Counter: start at 2 for first env (np1 used for first row), 1 otherwise
            np_counter = 2 if first_env else 1
            
            for idx, dest in destinations:
                if idx == last_idx and is_probe:
                    # Last teleportation with different destination = probe
                    df.loc[idx, 'teleport_type'] = 'p'
                else:
                    # Non-probe teleportation
                    df.loc[idx, 'teleport_type'] = f'np{np_counter}'
                    np_counter += 1
            
            first_env = False
        
        return df
    
    def _find_trial_end_position(
        self,
        df: pd.DataFrame,
        current_idx: int,
        search_start_idx: int
    ) -> Optional[int]:
        """
        Find where a trial ends by looking for stationary period.
        
        Searches backward from current_idx to find where coordinates
        stopped changing (indicating participant stopped before teleport).
        
        Returns
        -------
        Optional[int]
            Index of first row in stationary period, or None
        """
        if current_idx <= 0 or current_idx <= search_start_idx:
            return None
        
        # Get pre-teleport position
        pre_idx = current_idx - 1
        pre_x = df.loc[pre_idx, self.columns.x]
        pre_z = df.loc[pre_idx, self.columns.z]
        
        # Search backward for start of stationary period
        chunk_start = pre_idx
        
        for back_idx in range(pre_idx - 1, search_start_idx, -1):
            if (df.loc[back_idx, self.columns.x] != pre_x or 
                df.loc[back_idx, self.columns.z] != pre_z):
                # Found where position changed - next row is chunk start
                chunk_start = back_idx + 1
                break
        
        # Don't return if it's the first row or same as pre_idx
        if chunk_start != pre_idx and chunk_start != 0:
            return chunk_start
        
        return None
    
    def _find_trial_end_forward(
        self,
        df: pd.DataFrame,
        start_idx: int
    ) -> Optional[int]:
        """
        Find trial end by looking forward for stationary period after teleport.
        
        Used for the last teleportation in each environment.
        """
        if start_idx >= len(df) - 1:
            return None
        
        post_idx = start_idx + 1
        post_x = df.loc[post_idx, self.columns.x]
        post_z = df.loc[post_idx, self.columns.z]
        
        # Look forward for end of stationary period
        chunk_end = post_idx
        
        for forward_idx in range(post_idx + 1, len(df)):
            if (df.loc[forward_idx, self.columns.x] != post_x or
                df.loc[forward_idx, self.columns.z] != post_z):
                break
            chunk_end = forward_idx
        
        # Only return if we found a chunk (more than one row)
        if chunk_end > post_idx:
            return post_idx
        
        return None
    
    def _label_end_markers(
        self,
        df: pd.DataFrame,
        environments: np.ndarray
    ) -> pd.DataFrame:
        """
        Second pass: Add end markers for each trial.
        
        End markers indicate where participant stopped moving
        before being teleported.
        """
        df = df.copy()
        
        for env_idx, env in enumerate(environments):
            env_mask = (df[self.columns.environment] == env) & (df['is_teleport'] == True)
            env_teleports = df[env_mask].sort_index()
            
            if len(env_teleports) == 0:
                continue
            
            for i, (current_idx, row) in enumerate(env_teleports.iterrows()):
                # Skip first row (labeled as np1)
                if current_idx == 0:
                    continue
                
                # Determine previous label
                if i == 0:
                    # First teleport in environment
                    if env_idx == 0:
                        previous_label = 'np1'
                    else:
                        # Get last teleport label from previous environment
                        prev_env = environments[env_idx - 1]
                        prev_mask = (df[self.columns.environment] == prev_env) & (df['is_teleport'] == True)
                        prev_teleports = df[prev_mask]
                        
                        if len(prev_teleports) > 0:
                            previous_label = df.loc[prev_teleports.index[-1], 'teleport_type']
                        else:
                            previous_label = 'np1'
                else:
                    # Use previous teleport's label in this environment
                    previous_idx = env_teleports.index[i - 1]
                    previous_label = df.loc[previous_idx, 'teleport_type']
                
                # Determine search boundary
                if i == 0:
                    if env_idx == 0:
                        search_start = 0
                    else:
                        prev_env = environments[env_idx - 1]
                        prev_mask = (df[self.columns.environment] == prev_env) & (df['is_teleport'] == True)
                        prev_teleports = df[prev_mask]
                        search_start = prev_teleports.index[-1] if len(prev_teleports) > 0 else 0
                else:
                    search_start = env_teleports.index[i - 1]
                
                # Find and label end position
                end_idx = self._find_trial_end_position(df, current_idx, search_start)
                if end_idx is not None:
                    df.loc[end_idx, 'teleport_type'] = f"{previous_label}end"
            
            # Handle last teleportation's end marker (looking forward)
            last_idx = env_teleports.index[-1]
            last_label = df.loc[last_idx, 'teleport_type']
            
            end_idx = self._find_trial_end_forward(df, last_idx)
            if end_idx is not None:
                df.loc[end_idx, 'teleport_type'] = f"{last_label}end"
        
        return df
    
    def _cleanup_pend_labels(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """
        Remove 'pend' labels that immediately follow 'p' labels.
        
        Returns the cleaned DataFrame and count of removed labels.
        """
        df = df.copy()
        removed_count = 0
        
        for i in range(len(df) - 1):
            if pd.notna(df.loc[df.index[i], 'teleport_type']):
                if df.loc[df.index[i], 'teleport_type'] == 'p':
                    next_idx = df.index[i + 1]
                    if pd.notna(df.loc[next_idx, 'teleport_type']):
                        if df.loc[next_idx, 'teleport_type'] == 'pend':
                            df.loc[next_idx, 'teleport_type'] = pd.NA
                            removed_count += 1
        
        return df, removed_count
    
    def _ensure_final_pend(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure the last row has appropriate end label.
        
        Only adds 'pend' if the last environment completed with a probe.
        Otherwise adds the appropriate 'np#end' label.
        """
        df = df.copy()
        if len(df) == 0:
            return df
        
        # Find the last teleport to determine what end label to use
        teleport_rows = df[df['is_teleport'] == True]
        
        if len(teleport_rows) > 0:
            last_teleport_idx = teleport_rows.index[-1]
            last_teleport_type = df.loc[last_teleport_idx, 'teleport_type']
            
            if pd.notna(last_teleport_type):
                # Add the appropriate end label
                df.loc[df.index[-1], 'teleport_type'] = f'{last_teleport_type}end'
        
        return df
    
    def _compute_summary(self, df: pd.DataFrame, environments: np.ndarray) -> LabelingSummary:
        """Compute labeling statistics."""
        labels = df['teleport_type'].fillna('').astype(str)
        
        # Count by type
        labels_by_type = {}
        for label in labels[labels != '']:
            labels_by_type[label] = labels_by_type.get(label, 0) + 1
        
        return LabelingSummary(
            n_teleports=len(df[df['is_teleport'] == True]),
            n_environments=len(environments),
            n_probes=len(df[labels == 'p']),
            n_non_probes=len(df[labels.str.match(r'^np\d+$', na=False)]),
            n_end_markers=len(df[labels.str.contains('end', na=False)]),
            labels_by_type=labels_by_type
        )
    
    def label(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, LabelingSummary]:
        """
        Label all trials in the coordinate data.
        
        Parameters
        ----------
        df : pd.DataFrame
            Coordinate data with 'is_teleport' column from detection step
            
        Returns
        -------
        Tuple[pd.DataFrame, LabelingSummary]
            - DataFrame with 'teleport_type' column added
            - Summary of labeling results
        """
        if 'is_teleport' not in df.columns:
            raise ValueError(
                "DataFrame must have 'is_teleport' column. "
                "Run teleport detection first."
            )
        
        environments = self._get_environments(df)
        
        # Pass 1: Label teleport types (np#, p)
        labeled_df = self._label_teleport_types(df, environments)
        
        # Pass 2: Add end markers
        labeled_df = self._label_end_markers(labeled_df, environments)
        
        # Pass 3: Cleanup adjacent p/pend
        labeled_df, removed_count = self._cleanup_pend_labels(labeled_df)
        
        # Ensure final pend
        labeled_df = self._ensure_final_pend(labeled_df)
        
        # Compute summary
        summary = self._compute_summary(labeled_df, environments)
        
        # Log results
        logger.info(
            f"Labeled {summary.n_teleports} teleports across "
            f"{summary.n_environments} environments: "
            f"{summary.n_probes} probes, {summary.n_non_probes} non-probes, "
            f"{summary.n_end_markers} end markers"
        )
        
        if removed_count > 0:
            logger.debug(f"Removed {removed_count} redundant 'pend' labels")
        
        return labeled_df, summary


def label_trials(df: pd.DataFrame) -> Tuple[pd.DataFrame, LabelingSummary]:
    """
    Convenience function for labeling trials.
    
    Parameters
    ----------
    df : pd.DataFrame
        Coordinate data with teleport detection already applied
        
    Returns
    -------
    Tuple[pd.DataFrame, LabelingSummary]
        Labeled DataFrame and summary statistics
    """
    labeler = TrialLabeler()
    return labeler.label(df)
