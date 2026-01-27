"""
Data writing utilities for Y-Maze behavioral analysis.

Handles:
- Saving processed DataFrames to CSV
- Writing FSL-format timing files
- Managing output directories
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
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
    timing_data,  # TimingData object
    output_path: Path,
    min_rest_duration: float = 0.01
) -> Path:
    """
    Write the rest period timing file with all inter-trial intervals.

    Calculates rest periods as the gaps between consecutive trials
    (between end of one trial and start of the next).

    Parameters
    ----------
    timing_data : TimingData
        Timing data object with sorted trials list
    output_path : Path
        Full path for output file
    min_rest_duration : float
        Minimum duration to include as a rest period (default: 0.01s)

    Returns
    -------
    Path
        Path to saved file
    """
    output_path = Path(output_path)
    ensure_directory(output_path.parent)

    # Get trials sorted by start time
    trials = sorted(timing_data.trials, key=lambda t: t.start)

    rest_intervals = []

    # Calculate gaps between consecutive trials
    for i in range(len(trials) - 1):
        current_trial_end = trials[i].end
        next_trial_start = trials[i + 1].start

        gap_duration = next_trial_start - current_trial_end

        # Only include if there's actually a gap
        if gap_duration >= min_rest_duration:
            rest_intervals.append({
                'start': current_trial_end,
                'duration': gap_duration
            })

    with open(output_path, 'w') as f:
        if rest_intervals:
            for interval in rest_intervals:
                row = format_fsl_timing_row(interval['start'], interval['duration'], 1.0)
                f.write(row + "\n")
        else:
            # No rest intervals found - write placeholder
            f.write("0 0 0\n")

    logger.info(f"Wrote {len(rest_intervals)} rest intervals to {output_path}")
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
        timing_data,
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


def write_labeled_trial_files_by_preference(
    timing_data,  # TimingData object
    output_dir: Path,
    env_preferences: Dict[str, str],
    run_suffix: Optional[str] = None
) -> Tuple[Dict[str, Path], List[str]]:
    """
    Write semantically labeled FSL timing files separated by probe preference.

    Only includes trials from COMPLETED environments (those with probe trials)
    that have a matching preference entry.

    Creates files like:
    - explore_place.txt, explore_response.txt
    - cond1_place.txt, cond1_response.txt
    - etc.

    Parameters
    ----------
    timing_data : TimingData
        Timing data object
    output_dir : Path
        Directory for labeled trial files (will create labeled_trials_bypref subfolder)
    env_preferences : Dict[str, str]
        Mapping of environment name to preference ("place" or "response")
    run_suffix : Optional[str]
        Run identifier

    Returns
    -------
    Tuple[Dict[str, Path], List[str]]
        - Dictionary mapping label to saved path
        - List of environments missing preference data (for error reporting)
    """
    from collections import defaultdict

    output_dir = Path(output_dir)
    bypref_dir = ensure_directory(output_dir / "labeled_trials_bypref")

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
            f"Excluding {len(incomplete_envs)} incomplete environments from labeled_trials_bypref: "
            f"{incomplete_envs}"
        )

    # Track environments missing preference data
    missing_pref_envs = []

    # Build labeled trial collections separated by preference
    # Keys: 'explore_place', 'explore_response', 'cond1_place', etc.
    labeled_trials = defaultdict(list)

    for env, trials in completed_envs.items():
        # Look up preference for this environment
        preference = env_preferences.get(env)

        if preference is None:
            logger.warning(
                f"Environment '{env}' has no preference data - skipping for bypref output"
            )
            missing_pref_envs.append(env)
            continue

        max_num = len(trials)  # Since trial_num is 1-indexed and sequential

        for trial in trials:
            num = trial.trial_num

            # Determine base label based on position
            if num == 1:
                base_label = 'explore'
            elif num == max_num:
                base_label = 'probe'
            elif num == max_num - 1:
                base_label = 'preprobe'
            elif num == max_num - 2:
                base_label = 'cond3'
            elif num == max_num - 3:
                base_label = 'cond2'
            elif num == max_num - 4:
                if num != 1:
                    base_label = 'cond1'
                else:
                    base_label = 'explore'
            else:
                # Trials between explore and cond1 - not included
                continue

            # Add preference suffix
            full_label = f"{base_label}_{preference}"
            labeled_trials[full_label].append(trial)

    # Write labeled files
    saved_files = {}

    label_order = ['explore', 'cond1', 'cond2', 'cond3', 'preprobe', 'probe']
    pref_order = ['place', 'response']

    for base_label in label_order:
        for pref in pref_order:
            full_label = f"{base_label}_{pref}"
            trials = labeled_trials.get(full_label, [])

            if not trials:
                continue

            if run_suffix:
                filename = f"{full_label}_{run_suffix}.txt"
            else:
                filename = f"{full_label}.txt"

            trial_dicts = [{'start': t.start, 'duration': t.duration} for t in trials]

            saved_files[f'bypref_{full_label}'] = write_fsl_timing_file(
                trial_dicts,
                bypref_dir / filename
            )

    # Create empty placeholder files for missing preference types
    # Ensure all trial types have both place and response files
    for base_label in label_order:
        for pref in pref_order:
            full_label = f"{base_label}_{pref}"
            if f'bypref_{full_label}' not in saved_files:
                # This label/preference combo is missing - create empty placeholder
                if run_suffix:
                    filename = f"{full_label}_{run_suffix}.txt"
                else:
                    filename = f"{full_label}.txt"

                output_path = bypref_dir / filename
                with open(output_path, 'w') as f:
                    f.write("0 0 0\n")

                logger.info(f"Created empty placeholder: {output_path}")
                saved_files[f'bypref_{full_label}'] = output_path

    # Also write rest file to labeled_trials_bypref
    if timing_data.trials:
        if run_suffix:
            rest_filename = f"rest_{run_suffix}.txt"
        else:
            rest_filename = "rest.txt"

        saved_files['bypref_rest'] = write_rest_timing_file(
            timing_data,
            bypref_dir / rest_filename
        )

    return saved_files, missing_pref_envs


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
    if timing_data.trials:
        if run_suffix:
            rest_filename = f"rest_{run_suffix}.txt"
        else:
            rest_filename = "rest.txt"

        saved_files['labeled_rest'] = write_rest_timing_file(
            timing_data,
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
        self.preference_errors: List[Dict] = []
        self.timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

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

    def add_preference_error(
        self,
        subject_id: str,
        error_type: str,
        details: str
    ):
        """
        Record a preference-related error.

        Parameters
        ----------
        subject_id : str
            Subject identifier
        error_type : str
            Type of error: "missing_file" or "missing_environment"
        details : str
            Additional details about the error
        """
        self.preference_errors.append({
            'subject_id': subject_id,
            'error_type': error_type,
            'details': details
        })

    def save(self, output_path: Path) -> Path:
        """Save report to CSV files."""
        output_path = Path(output_path)
        ensure_directory(output_path)

        # Save subjects summary
        if self.subjects:
            subjects_df = pd.DataFrame(self.subjects)
            subjects_df.to_csv(output_path / 'processing_summary.csv', index=False)

        # Save errors to logs subdirectory
        logs_path = output_path / 'logs'
        logs_path.mkdir(parents=True, exist_ok=True)

        if self.errors:
            errors_df = pd.DataFrame(self.errors)
            errors_df.to_csv(logs_path / f'create_timing_errors_{self.timestamp}.csv', index=False)

        # Save preference errors
        if self.preference_errors:
            pref_errors_df = pd.DataFrame(self.preference_errors)
            pref_errors_df.to_csv(logs_path / f'run_preference_errors_{self.timestamp}.csv', index=False)

        return output_path

    @property
    def has_preference_errors(self) -> bool:
        """Check if there are any preference-related errors."""
        return len(self.preference_errors) > 0

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

        # Print preference errors prominently
        if self.preference_errors:
            print(f"\n{'='*50}")
            print("PREFERENCE ERRORS - ACTION REQUIRED")
            print(f"{'='*50}")
            print(f"Found {len(self.preference_errors)} preference-related issue(s).")
            print("These must be resolved and the script re-run to generate")
            print("complete labeled_trials_bypref output.\n")

            # Group by error type for clearer output
            missing_files = [e for e in self.preference_errors if e['error_type'] == 'missing_file']
            missing_envs = [e for e in self.preference_errors if e['error_type'] == 'missing_environment']

            if missing_files:
                print("Missing preferences files:")
                for err in missing_files:
                    print(f"  - {err['subject_id']}: {err['details']}")

            if missing_envs:
                print("\nEnvironments missing preference data:")
                for err in missing_envs:
                    print(f"  - {err['subject_id']}: {err['details']}")


def save_outcome_measures(
    outcome_measures,  # OutcomeMeasures object
    output_dir: Path,
    subject_id: str,
    run_suffix: Optional[str] = None
) -> Dict[str, Path]:
    """
    Save per-subject outcome measures at all levels.

    Creates three CSV files:
    - sub-XXX_trial_outcomes.csv: Trial-level outcomes
    - sub-XXX_env_outcomes.csv: Environment-level outcomes
    - sub-XXX_task_outcomes.csv: Task-level outcomes

    Parameters
    ----------
    outcome_measures : OutcomeMeasures
        Calculated outcome measures for a subject
    output_dir : Path
        Subject's output directory
    subject_id : str
        Subject identifier (e.g., "sub-066")
    run_suffix : Optional[str]
        Run identifier (e.g., "C" or "S")

    Returns
    -------
    Dict[str, Path]
        Dictionary mapping outcome type to saved file path
    """
    output_dir = Path(output_dir)
    ensure_directory(output_dir)

    saved_files = {}

    # Build filename prefix
    if run_suffix:
        prefix = f"{subject_id}_{run_suffix}"
    else:
        prefix = subject_id

    # Save trial-level outcomes
    trial_df = outcome_measures.trial_outcomes_to_dataframe()
    if not trial_df.empty:
        saved_files['trial_outcomes'] = save_dataframe(
            trial_df,
            output_dir,
            f"{prefix}_trial_outcomes.csv"
        )

    # Save environment-level outcomes
    env_df = outcome_measures.env_outcomes_to_dataframe()
    if not env_df.empty:
        saved_files['env_outcomes'] = save_dataframe(
            env_df,
            output_dir,
            f"{prefix}_env_outcomes.csv"
        )

    # Save task-level outcomes
    task_df = outcome_measures.task_outcome_to_dataframe()
    if not task_df.empty:
        saved_files['task_outcomes'] = save_dataframe(
            task_df,
            output_dir,
            f"{prefix}_task_outcomes.csv"
        )

    logger.info(f"Saved outcome measures for {subject_id} to {output_dir}")

    return saved_files


def save_aggregated_outcomes(
    aggregated_df: pd.DataFrame,
    output_dir: Path,
    filename: str = "all_outcomes.csv"
) -> Path:
    """
    Save aggregated task-level outcomes across all subjects.

    Parameters
    ----------
    aggregated_df : pd.DataFrame
        Aggregated task-level outcomes
    output_dir : Path
        Output directory
    filename : str
        Output filename

    Returns
    -------
    Path
        Path to saved file
    """
    return save_dataframe(aggregated_df, output_dir, filename)


def save_aggregated_preferences(
    preferences_df: pd.DataFrame,
    output_dir: Path,
    filename: str = "all_preferences.csv"
) -> Path:
    """
    Save aggregated preference classifications.

    Parameters
    ----------
    preferences_df : pd.DataFrame
        Aggregated preference data with classifications
    output_dir : Path
        Output directory
    filename : str
        Output filename

    Returns
    -------
    Path
        Path to saved file
    """
    return save_dataframe(preferences_df, output_dir, filename)
