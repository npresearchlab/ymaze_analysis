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
    first_np_trials: List[Dict],
    last_np_trials: List[Dict],
    probe_trials: List[Dict],
    last_event_end: float,
    output_dir: Path,
    file_names: Optional[Dict[str, str]] = None,
    run_suffix: Optional[str] = None
) -> Dict[str, Path]:
    """
    Write all four FSL timing files for a subject.
    
    Parameters
    ----------
    first_np_trials : List[Dict]
        First non-probe trials before each probe
    last_np_trials : List[Dict]
        Last non-probe trials before each probe
    probe_trials : List[Dict]
        Probe trials
    last_event_end : float
        End time of the last event (for rest file)
    output_dir : Path
        Directory for output files
    file_names : Optional[Dict[str, str]]
        Custom file names. Keys: 'first_np', 'last_np', 'probe', 'rest'
    run_suffix : Optional[str]
        Run identifier (e.g., "C" or "S"). If provided, adds to filenames.
        
    Returns
    -------
    Dict[str, Path]
        Dictionary mapping file type to saved path
        
    Examples
    --------
    >>> write_all_fsl_timing_files(..., run_suffix=None)
    # Creates: firstnp.txt, lastnp.txt, probe.txt, rest.txt
    
    >>> write_all_fsl_timing_files(..., run_suffix="C")
    # Creates: firstnp_C.txt, lastnp_C.txt, probe_C.txt, rest_C.txt
    """
    output_dir = Path(output_dir)
    
    # Default file names
    names = {
        'first_np': 'firstnp.txt',
        'last_np': 'lastnp.txt',
        'probe': 'probe.txt',
        'rest': 'rest.txt'
    }
    if file_names:
        names.update(file_names)
    
    # Add run suffix to filenames if provided
    if run_suffix:
        for key in names:
            # Insert suffix before .txt extension
            base = names[key].replace('.txt', '')
            names[key] = f"{base}_{run_suffix}.txt"
    
    saved_files = {}
    
    # Write each timing file
    saved_files['first_np'] = write_fsl_timing_file(
        first_np_trials,
        output_dir / names['first_np']
    )
    
    saved_files['last_np'] = write_fsl_timing_file(
        last_np_trials,
        output_dir / names['last_np']
    )
    
    saved_files['probe'] = write_fsl_timing_file(
        probe_trials,
        output_dir / names['probe']
    )
    
    saved_files['rest'] = write_rest_timing_file(
        last_event_end,
        output_dir / names['rest']
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
        n_probes: int,
        n_environments: int,
        output_dir: Path
    ):
        """Record successful processing of a subject."""
        self.subjects.append({
            'subject_id': subject_id,
            'original_folder': original_folder,
            'n_teleports': n_teleports,
            'n_probes': n_probes,
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
