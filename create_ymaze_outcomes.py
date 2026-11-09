#!/usr/bin/env python3
"""
Y-Maze Outcome Measures Calculator

Calculates behavioral outcome measures at trial, environment, and task levels.

This script can run in two modes:
1. If labeled_final.csv files exist (from create_ymaze_timing.py), use those
2. If not, process raw coordinate files directly from the data directory

Usage:
    python create_ymaze_outcomes.py --output-dir ../analysis
    python create_ymaze_outcomes.py --data-dir ../data --output-dir ../analysis
    python create_ymaze_outcomes.py --help
"""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

import pandas as pd
import numpy as np
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import PipelineConfig

from data_io import (
    load_coordinates,
    find_all_coordinate_files,
    discover_subjects,
    ensure_directory,
    save_dataframe,
    save_outcome_measures,
    save_aggregated_outcomes,
    DataLoadError,
    DataValidationError
)

from processing import (
    detect_teleportations,
    label_trials,
    extract_timing
)

from post.outcome_measures import (
    TrialOutcome,
    EnvironmentOutcome,
    TaskOutcome,
    OutcomeMeasures,
    aggregate_task_outcomes,
    calculate_outcome_measures
)


from data_io.loaders import is_rawdata_dir, find_rawdata_runs


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None):
    """Configure logging for the script."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler()]

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def extract_participant_number(folder_name: str, prefix: str = "sub") -> Tuple[Optional[str], Optional[str]]:
    """Extract participant number from folder name."""
    # Pattern 1: NAV followed by digits
    match = re.search(r'NAV(\d+)', folder_name, re.IGNORECASE)
    if match:
        num = match.group(1)
        return num, f"{prefix}-{num}"

    # Pattern 2: sub- followed by digits
    match = re.search(r'sub-?(\d+)', folder_name, re.IGNORECASE)
    if match:
        num = match.group(1)
        return num, f"{prefix}-{num}"

    # Pattern 3: Any digits (fallback)
    match = re.search(r'(\d+)', folder_name)
    if match:
        num = match.group(1)
        return num, f"{prefix}-{num}"

    return None, None


def find_labeled_final_files(output_dir: Path) -> List[Tuple[Path, str, Optional[str]]]:
    """
    Find all labeled_final.csv files in the output directory.

    Returns list of (filepath, subject_id, run_suffix) tuples.
    """
    logger = logging.getLogger(__name__)

    output_dir = Path(output_dir)

    if not output_dir.is_dir():
        return []

    files = list(output_dir.rglob("*_labeled_final.csv"))

    results = []

    for filepath in files:
        parent = filepath.parent
        grandparent = parent.parent

        if parent.name in ['C', 'S']:
            run_suffix = parent.name
            subject_id = grandparent.name
        else:
            run_suffix = None
            subject_id = parent.name

        results.append((filepath, subject_id, run_suffix))

    results.sort(key=lambda x: (x[1], x[2] or ""))

    if results:
        logger.info(f"Found {len(results)} existing labeled_final.csv files")

    return results


def calculate_outcomes_from_dataframe(
    df: pd.DataFrame,
    subject_id: str,
    run_suffix: Optional[str] = None
) -> OutcomeMeasures:
    """
    Calculate outcome measures from a labeled_final DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with columns: env, trial, trial_num, start, end, duration
    subject_id : str
        Subject identifier
    run_suffix : Optional[str]
        Run identifier (e.g., "C" or "S")

    Returns
    -------
    OutcomeMeasures
        Complete outcome measures at all levels
    """
    logger = logging.getLogger(__name__)

    # Calculate trial-level outcomes
    trial_outcomes = []

    for _, row in df.iterrows():
        trial_type = 'p' if row['trial'] == 'p' else 'np'

        outcome = TrialOutcome(
            subject_id=subject_id,
            environment=row['env'],
            trial_num=int(row['trial_num']),
            trial_type=trial_type,
            duration=float(row['duration']),
            start_time=float(row['start']),
            end_time=float(row['end'])
        )
        trial_outcomes.append(outcome)

    # Calculate environment-level outcomes
    env_trials = defaultdict(list)
    for trial in trial_outcomes:
        env_trials[trial.environment].append(trial)

    env_outcomes = []

    for env, trials in env_trials.items():
        np_trials = [t for t in trials if t.trial_type == 'np']
        probe_trials = [t for t in trials if t.trial_type == 'p']

        n_np_trials = len(np_trials)
        has_probe = len(probe_trials) > 0

        all_trials_sorted = sorted(trials, key=lambda t: t.start_time)
        total_time = (
            all_trials_sorted[-1].end_time - all_trials_sorted[0].start_time
            if all_trials_sorted else 0.0
        )

        avg_np_duration = (
            np.mean([t.duration for t in np_trials])
            if np_trials else 0.0
        )

        probe_duration = (
            probe_trials[0].duration if probe_trials else None
        )

        outcome = EnvironmentOutcome(
            subject_id=subject_id,
            environment=env,
            n_np_trials=n_np_trials,
            total_time=total_time,
            avg_np_duration=avg_np_duration,
            probe_duration=probe_duration,
            has_probe=has_probe
        )
        env_outcomes.append(outcome)

    env_outcomes.sort(key=lambda o: o.environment)

    # Calculate task-level outcomes
    n_environments = len(env_outcomes)
    n_complete = sum(1 for e in env_outcomes if e.has_probe)

    if trial_outcomes:
        sorted_trials = sorted(trial_outcomes, key=lambda t: t.start_time)
        total_time = sorted_trials[-1].end_time - sorted_trials[0].start_time
    else:
        total_time = 0.0

    np_trials = [t for t in trial_outcomes if t.trial_type == 'np']
    probe_trials = [t for t in trial_outcomes if t.trial_type == 'p']

    total_np_trials = len(np_trials)
    total_probe_trials = len(probe_trials)

    avg_np_per_env = (
        total_np_trials / n_environments
        if n_environments > 0 else 0.0
    )

    # Trials-to-criterion: average trials only across environments that actually
    # reached criterion (has_probe=True). Avoids inflation/deflation from
    # incomplete environments (e.g. timed-out attempts).
    complete_envs = [e for e in env_outcomes if e.has_probe]
    avg_np_per_complete_env = (
        float(np.mean([e.n_np_trials for e in complete_envs]))
        if complete_envs else 0.0
    )

    avg_env_duration = (
        np.mean([e.total_time for e in env_outcomes])
        if env_outcomes else 0.0
    )

    avg_np_duration = (
        np.mean([t.duration for t in np_trials])
        if np_trials else 0.0
    )

    avg_probe_duration = (
        np.mean([t.duration for t in probe_trials])
        if probe_trials else None
    )

    task_outcome = TaskOutcome(
        subject_id=subject_id,
        run_suffix=run_suffix,
        n_environments=n_environments,
        n_complete_environments=n_complete,
        total_time=total_time,
        total_np_trials=total_np_trials,
        total_probe_trials=total_probe_trials,
        avg_np_per_environment=avg_np_per_env,
        avg_np_per_complete_environment=avg_np_per_complete_env,
        avg_env_duration=avg_env_duration,
        avg_np_duration=avg_np_duration,
        avg_probe_duration=avg_probe_duration
    )

    logger.debug(
        f"Calculated outcomes for {subject_id}: "
        f"{len(trial_outcomes)} trials, {len(env_outcomes)} environments"
    )

    return OutcomeMeasures(
        subject_id=subject_id,
        run_suffix=run_suffix,
        trial_outcomes=trial_outcomes,
        env_outcomes=env_outcomes,
        task_outcome=task_outcome
    )


def process_coordinate_file(
    coord_file: Path,
    subject_id: str,
    run_suffix: Optional[str],
    config: PipelineConfig
) -> OutcomeMeasures:
    """
    Process a coordinate file and calculate outcomes directly.

    Parameters
    ----------
    coord_file : Path
        Path to coordinate CSV file
    subject_id : str
        Subject identifier
    run_suffix : Optional[str]
        Run identifier
    config : PipelineConfig
        Pipeline configuration

    Returns
    -------
    OutcomeMeasures
        Calculated outcome measures
    """
    logger = logging.getLogger(__name__)

    # Load coordinates
    df = load_coordinates(coord_file, columns=config.columns)

    # Detect teleportations
    teleport_df, _ = detect_teleportations(
        df,
        target_positions=config.teleport.target_positions,
        distance_threshold=config.teleport.distance_threshold,
        position_tolerance=config.teleport.position_tolerance
    )

    # Label trials
    labeled_df, _ = label_trials(teleport_df)

    # Extract timing
    timing_data = extract_timing(labeled_df, normalize=True)

    # Calculate outcomes from timing data
    outcomes = calculate_outcome_measures(timing_data, subject_id, run_suffix)

    return outcomes


def run_from_labeled_files(
    output_dir: Path,
    labeled_files: List[Tuple[Path, str, Optional[str]]]
) -> List[OutcomeMeasures]:
    """
    Calculate outcomes from existing labeled_final.csv files.
    """
    logger = logging.getLogger(__name__)
    logger.info("Using existing labeled_final.csv files")

    all_outcomes = []

    for filepath, subject_id, run_suffix in labeled_files:
        run_label = f" (run {run_suffix})" if run_suffix else ""
        logger.info(f"Processing {subject_id}{run_label}")

        try:
            df = pd.read_csv(filepath)
            outcomes = calculate_outcomes_from_dataframe(df, subject_id, run_suffix)

            # Save to same directory as the labeled_final.csv
            subject_output = filepath.parent
            save_outcome_measures(outcomes, subject_output, subject_id, run_suffix)

            all_outcomes.append(outcomes)
            logger.info(f"✓ Saved outcomes for {subject_id}{run_label}")

        except Exception as e:
            logger.error(f"✗ Failed to process {subject_id}{run_label}: {e}")
            continue

    return all_outcomes


def run_from_coordinates(
    data_dir: Path,
    output_dir: Path,
    subject_prefix: str = "sub"
) -> List[OutcomeMeasures]:
    """
    Process coordinate files directly and calculate outcomes.
    """
    logger = logging.getLogger(__name__)
    logger.info("Processing raw coordinate files (no labeled_final.csv found)")

    config = PipelineConfig()

    # Discover subjects (nav_study rawdata layout: sub-<ID>/ses-<session>/ymaze/)
    rawdata = is_rawdata_dir(data_dir)
    if rawdata:
        subjects = sorted(d for d in Path(data_dir).glob('sub-*') if d.is_dir())
    else:
        subjects = discover_subjects(data_dir)
    logger.info(f"Found {len(subjects)} subject folders")

    if not subjects:
        return []

    all_outcomes = []

    for subject_folder in subjects:
        # Use folder name directly as subject ID
        subject_id = subject_folder.name[4:] if rawdata else subject_folder.name  # sub-NAV066 -> NAV066

        if rawdata:
            coord_files = [(f, suf) for f, suf, _ in find_rawdata_runs(subject_folder)]
        else:
            coord_files = find_all_coordinate_files(subject_folder)

        if not coord_files:
            logger.warning(f"No coordinate files found in {subject_folder.name}")
            continue

        for coord_file, run_suffix in coord_files:
            run_label = f" (run {run_suffix})" if run_suffix else ""
            logger.info(f"Processing {subject_id}{run_label}: {coord_file.name}")

            try:
                outcomes = process_coordinate_file(
                    coord_file, subject_id, run_suffix, config
                )

                # Determine output directory
                if run_suffix:
                    subject_output = ensure_directory(output_dir / subject_id / run_suffix)
                else:
                    subject_output = ensure_directory(output_dir / subject_id)

                save_outcome_measures(outcomes, subject_output, subject_id, run_suffix)

                all_outcomes.append(outcomes)
                logger.info(f"✓ Saved outcomes for {subject_id}{run_label}")

            except (DataLoadError, DataValidationError) as e:
                logger.error(f"✗ Failed to process {subject_folder.name}{run_label}: {e}")
                continue
            except Exception as e:
                logger.error(f"✗ Unexpected error processing {subject_folder.name}{run_label}: {e}")
                continue

    return all_outcomes


def run_outcome_calculation(
    data_dir: Optional[Path],
    output_dir: Path,
    subject_prefix: str = "sub"
) -> int:
    """
    Calculate outcome measures for all subjects.

    Automatically detects whether to use existing labeled_final.csv files
    or process raw coordinate files.

    Parameters
    ----------
    data_dir : Optional[Path]
        Directory containing raw coordinate files (used if no labeled files found)
    output_dir : Path
        Output directory
    subject_prefix : str
        Prefix for subject IDs

    Returns
    -------
    int
        Number of subjects processed
    """
    logger = logging.getLogger(__name__)

    # First, check for existing labeled_final.csv files
    labeled_files = find_labeled_final_files(output_dir)

    if labeled_files:
        # Use existing labeled files
        all_outcomes = run_from_labeled_files(output_dir, labeled_files)
    elif data_dir and data_dir.is_dir():
        # Process from raw coordinates
        all_outcomes = run_from_coordinates(data_dir, output_dir, subject_prefix)
    else:
        logger.error(
            "No labeled_final.csv files found in output directory, "
            "and no valid data directory specified.\n"
            "Either:\n"
            "  1. Run create_ymaze_timing.py first, or\n"
            "  2. Specify --data-dir with path to raw coordinate files"
        )
        return 0

    # Aggregate and save all outcomes
    if all_outcomes:
        aggregated_df = aggregate_task_outcomes(all_outcomes)
        save_aggregated_outcomes(aggregated_df, output_dir)
        logger.info(f"Saved aggregated outcomes for {len(all_outcomes)} subject/runs")

    # Print summary
    print(f"\n{'='*50}")
    print("OUTCOME CALCULATION SUMMARY")
    print(f"{'='*50}")
    print(f"Subjects processed: {len(all_outcomes)}")
    print(f"Output files saved to: {output_dir}")
    print(f"  - Per-subject: sub-XXX_trial_outcomes.csv, sub-XXX_env_outcomes.csv, sub-XXX_task_outcomes.csv")
    print(f"  - Aggregated: all_outcomes.csv")

    return len(all_outcomes)


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Y-Maze Outcome Measures Calculator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --output-dir ../analysis
      Use existing labeled_final.csv files in ../analysis

  %(prog)s --data-dir ../data --output-dir ../analysis
      Process raw coordinate files if no labeled_final.csv found

  %(prog)s --data-dir ../data --output-dir ../analysis --verbose
      Verbose output

This script can run in two modes:
  1. If labeled_final.csv files exist (from create_ymaze_timing.py), use those
  2. If not, process raw coordinate files directly from --data-dir

Output files:
  - Per-subject: sub-XXX_trial_outcomes.csv, sub-XXX_env_outcomes.csv, sub-XXX_task_outcomes.csv
  - Aggregated: all_outcomes.csv
        """
    )

    parser.add_argument(
        '--data-dir', '-d',
        type=Path,
        help='Path to data directory with raw coordinate files (used if no labeled_final.csv found)'
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./output'),
        help='Path to output directory (default: ./output)'
    )

    parser.add_argument(
        '--subject-prefix', '-p',
        default='sub',
        help='Prefix for subject IDs when processing raw files (default: sub)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--log-file',
        type=Path,
        help='Save logs to file'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose, log_file=args.log_file)

    logger = logging.getLogger(__name__)
    logger.info(f"Starting outcome calculation at {datetime.now().isoformat()}")

    # Ensure output directory exists
    ensure_directory(args.output_dir)

    try:
        n_processed = run_outcome_calculation(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            subject_prefix=args.subject_prefix
        )

        if n_processed == 0:
            logger.warning("No subjects processed")
            sys.exit(1)

    except Exception as e:
        logger.exception("Outcome calculation failed with error")
        sys.exit(1)


if __name__ == "__main__":
    main()
