"""
Data writing utilities for Y-Maze behavioral analysis.

Handles:
- Saving processed DataFrames to CSV
- Writing FSL-format timing files
- Managing output directories
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def ensure_directory(path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Parameters
    ----------
    path : Path
        Directory path to ensure exists
        
    Returns
    -------
    Path
        The same path (for chaining)
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_dataframe(
    df: pd.DataFrame,
    output_dir: Path,
    filename: str,
    include_index: bool = False
) -> Path:
    """
    Save a DataFrame to CSV.
    
    Parameters
    ----------
    df : pd.DataFrame
        Data to save
    output_dir : Path
        Directory for output file
    filename : str
        Output filename (with or without .csv extension)
    include_index : bool
        Whether to include the DataFrame index in output
        
    Returns
    -------
    Path
        Path to the saved file
    """
    output_dir = ensure_directory(Path(output_dir))
    
    # Ensure .csv extension
    if not filename.endswith('.csv'):
        filename = f"{filename}.csv"
    
    output_path = output_dir / filename
    
    df.to_csv(output_path, index=include_index)
    logger.info(f"Saved DataFrame to {output_path}")
    
    return output_path


def save_labeled_data(
    df: pd.DataFrame,
    output_dir: Path,
    subject_id: str,
    suffix: str = "labeled",
    run_suffix: Optional[str] = None
) -> Path:
    """
    Save labeled trial data with standardized naming.
    
    Parameters
    ----------
    df : pd.DataFrame
        Labeled trial data
    output_dir : Path
        Subject's output directory
    subject_id : str
        Subject identifier (e.g., "sub-01")
    suffix : str
        Filename suffix (default: "labeled")
    run_suffix : Optional[str]
        Run identifier (e.g., "C" or "S"). If provided, adds to filename.
        
    Returns
    -------
    Path
        Path to saved file
        
    Examples
    --------
    >>> save_labeled_data(df, output, "sub-066", "labeled_final")
    # Saves: sub-066_labeled_final.csv
    
    >>> save_labeled_data(df, output, "sub-066", "labeled_final", run_suffix="C")
    # Saves: sub-066_C_labeled_final.csv
    """
    if run_suffix:
        filename = f"{subject_id}_{run_suffix}_{suffix}.csv"
    else:
        filename = f"{subject_id}_{suffix}.csv"
    return save_dataframe(df, output_dir, filename)


def format_fsl_timing_row(start: float, duration: float, weight: float = 1.0) -> str:
    """
    Format a single row for FSL timing file.
    
    FSL 3-column format: onset duration parametric_weight
    
    Parameters
    ----------
    start : float
        Event onset time (seconds)
    duration : float
        Event duration (seconds)
    weight : float
        Parametric weight (usually 1)
        
    Returns
    -------
    str
        Formatted timing row
    """
    return f"{start:.2f} {duration:.2f} {weight:.0f}"


def write_fsl_timing_file(
    trials: List[Dict],
    output_path: Path,
    weight: float = 1.0
) -> Path:
    """
    Write a single FSL timing file.
    
    Parameters
    ----------
    trials : List[Dict]
        List of trial dictionaries with 'start' and 'duration' keys
    output_path : Path
        Full path for output file
    weight : float
        Parametric weight for all events
        
    Returns
    -------
    Path
        Path to saved file
    """
    output_path = Path(output_path)
    ensure_directory(output_path.parent)
    
    with open(output_path, 'w') as f:
        for trial in trials:
            row = format_fsl_timing_row(
                trial['start'],
                trial['duration'],
                weight
            )
            f.write(row + "\n")
    
    logger.info(f"Wrote {len(trials)} events to {output_path}")
    return output_path


def write_rest_timing_file(
    last_event_end: float,
    output_path: Path,
    rest_duration: float = 400000.0
) -> Path:
    """
    Write the rest period timing file.
    
    This captures everything after the last task event.
    
    Parameters
    ----------
    last_event_end : float
        End time of the last task event
    output_path : Path
        Full path for output file
    rest_duration : float
        Duration of rest period (default: very large number)
        
    Returns
    -------
    Path
        Path to saved file
    """
    output_path = Path(output_path)
    ensure_directory(output_path.parent)
    
    with open(output_path, 'w') as f:
        row = format_fsl_timing_row(last_event_end, rest_duration, 1.0)
        f.write(row + "\n")
    
    logger.info(f"Wrote rest timing to {output_path}")
    return output_path


def write_all_fsl_timing_files(
    timing_data,  # TimingData object
    output_dir: Path,
    run_suffix: Optional[str] = None
) -> Dict[str, Path]:
    """
    Write FSL timing files for all trial numbers.
    
    Creates two output folders:
    1. trial_numbers/ - One file per trial number (trial_1.txt, trial_2.txt, etc.)
    2. labeled_trials/ - Semantically labeled files (explore.txt, cond1.txt, etc.)
    
    The labeled_trials folder only includes trials from COMPLETED environments
    (environments where the participant reached the probe trial).
    
    Parameters
    ----------
    timing_data : TimingData
        Timing data object with trials_by_num dict and trials list
    output_dir : Path
        Directory for output files
    run_suffix : Optional[str]
        Run identifier (e.g., "C" or "S"). If provided, adds to filenames.
        
    Returns
    -------
    Dict[str, Path]
        Dictionary mapping file type to saved path
    """
    output_dir = Path(output_dir)
    saved_files = {}
    
    # Create subfolders
    trial_numbers_dir = ensure_directory(output_dir / "trial_numbers")
    labeled_trials_dir = ensure_directory(output_dir / "labeled_trials")
    
    # ========================================
    # 1. Write trial_numbers files (all trials)
    # ========================================
    for trial_num, trials in timing_data.trials_by_num.items():
        if run_suffix:
            filename = f"trial_{trial_num}_{run_suffix}.txt"
        else:
            filename = f"trial_{trial_num}.txt"
        
        trial_dicts = [{'start': t.start, 'duration': t.duration} for t in trials]
        
        saved_files[f'trial_{trial_num}'] = write_fsl_timing_file(
            trial_dicts,
            trial_numbers_dir / filename
        )
    
    # Write rest file to trial_numbers
    if run_suffix:
        rest_filename = f"rest_{run_suffix}.txt"
    else:
        rest_filename = "rest.txt"
    
    saved_files['rest'] = write_rest_timing_file(
        timing_data.last_event_end,
        trial_numbers_dir / rest_filename
    )
    
    # ========================================
    # 2. Write labeled_trials files (completed envs only)
    # ========================================
    labeled_files = write_labeled_trial_files(
        timing_data,
        labeled_trials_dir,
        run_suffix
    )
    saved_files.update(labeled_files)
    
    return saved_files


def write_labeled_trial_files(
    timing_data,  # TimingData object
    output_dir: Path,
    run_suffix: Optional[str] = None
) -> Dict[str, Path]:
    """
    Write semantically labeled FSL timing files.
    
    Only includes trials from COMPLETED environments (those with probe trials).
    
    Labeling scheme (based on trial position relative to probe):
    - trial_1 → explore.txt (first trial)
    - max_num → probe.txt (last trial, must be 'p' type)
    - max_num - 1 → preprobe.txt
    - max_num - 2 → cond3.txt
    - max_num - 3 → cond2.txt
    - max_num - 4 → cond1.txt (unless this is trial_1, then skip)
    
    Parameters
    ----------
    timing_data : TimingData
        Timing data object
    output_dir : Path
        Directory for labeled trial files
    run_suffix : Optional[str]
        Run identifier
        
    Returns
    -------
    Dict[str, Path]
        Dictionary mapping label to saved path
    """
    from collections import defaultdict
    
    output_dir = Path(output_dir)
    
    # Group trials by environment
    env_trials = defaultdict(list)
    for trial in timing_data.trials:
        env_trials[trial.environment].append(trial)
    
    # Sort trials within each environment by trial_num
    for env in env_trials:
        env_trials[env].sort(key=lambda t: t.trial_num)
    
    # Identify completed environments (last trial is probe)
    completed_envs = {}
    incomplete_envs = []
    
    for env, trials in env_trials.items():
        if trials and trials[-1].trial_type == 'p':
            completed_envs[env] = trials
        else:
            incomplete_envs.append(env)
    
    if incomplete_envs:
        logger.warning(
            f"Excluding {len(incomplete_envs)} incomplete environments from labeled_trials: "
            f"{incomplete_envs}"
        )
    
    # Build labeled trial collections
    # Keys: 'explore', 'cond1', 'cond2', 'cond3', 'preprobe', 'probe'
    labeled_trials = defaultdict(list)
    
    for env, trials in completed_envs.items():
        max_num = len(trials)  # Since trial_num is 1-indexed and sequential
        
        for trial in trials:
            num = trial.trial_num
            
            # Determine label based on position
            if num == 1:
                label = 'explore'
            elif num == max_num:
                label = 'probe'
            elif num == max_num - 1:
                label = 'preprobe'
            elif num == max_num - 2:
                label = 'cond3'
            elif num == max_num - 3:
                label = 'cond2'
            elif num == max_num - 4:
                # Only label as cond1 if it's not trial_1
                if num != 1:
                    label = 'cond1'
                else:
                    label = 'explore'  # Already handled above, but defensive
            else:
                # Trials between explore and cond1 - not included in labeled files
                continue
            
            labeled_trials[label].append(trial)
    
    # Write labeled files
    saved_files = {}
    
    label_order = ['explore', 'cond1', 'cond2', 'cond3', 'preprobe', 'probe']
    
    for label in label_order:
        trials = labeled_trials.get(label, [])
        
        if not trials:
            continue
        
        if run_suffix:
            filename = f"{label}_{run_suffix}.txt"
        else:
            filename = f"{label}.txt"
        
        trial_dicts = [{'start': t.start, 'duration': t.duration} for t in trials]
        
        saved_files[f'labeled_{label}'] = write_fsl_timing_file(
            trial_dicts,
            output_dir / filename
        )
    
    # Also copy rest file to labeled_trials
    if timing_data.last_event_end > 0:
        if run_suffix:
            rest_filename = f"rest_{run_suffix}.txt"
        else:
            rest_filename = "rest.txt"
        
        saved_files['labeled_rest'] = write_rest_timing_file(
            timing_data.last_event_end,
            output_dir / rest_filename
        )
    
    return saved_files


class ProcessingReport:
    """
    Collects and saves a summary of processing results.
    """
    
    def __init__(self):
        self.subjects: List[Dict] = []
        self.errors: List[Dict] = []
    
    def add_subject(
        self,
        subject_id: str,
        original_folder: str,
        n_teleports: int,
        n_trials: int,
        n_environments: int,
        output_dir: Path
    ):
        """Record successful processing of a subject."""
        self.subjects.append({
            'subject_id': subject_id,
            'original_folder': original_folder,
            'n_teleports': n_teleports,
            'n_trials': n_trials,
            'n_environments': n_environments,
            'output_dir': str(output_dir)
        })
    
    def add_error(self, folder: str, error: str):
        """Record a processing error."""
        self.errors.append({
            'folder': folder,
            'error': error
        })
    
    def save(self, output_path: Path) -> Path:
        """Save report to CSV files."""
        output_path = Path(output_path)
        ensure_directory(output_path)
        
        # Save subjects summary
        if self.subjects:
            subjects_df = pd.DataFrame(self.subjects)
            subjects_df.to_csv(output_path / 'processing_summary.csv', index=False)
        
        # Save errors
        if self.errors:
            errors_df = pd.DataFrame(self.errors)
            errors_df.to_csv(output_path / 'processing_errors.csv', index=False)
        
        return output_path
    
    def print_summary(self):
        """Print a summary to console."""
        print(f"\n{'='*50}")
        print("PROCESSING SUMMARY")
        print(f"{'='*50}")
        print(f"Successfully processed: {len(self.subjects)} subjects")
        print(f"Errors encountered: {len(self.errors)}")
        
        if self.errors:
            print("\nErrors:")
            for err in self.errors:
                print(f"  - {err['folder']}: {err['error']}")
