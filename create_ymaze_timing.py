#!/usr/bin/env python3
"""
Y-Maze FSL Timing File Generator

Processes Y-Maze coordinate data from Unity to generate FSL-compatible timing files.

Pipeline steps:
1. Detect teleportation events
2. Label trials (probe vs non-probe)
3. Extract timing information
4. Generate FSL timing files

Usage:
    python create_ymaze_timing.py                          # Use default paths (./data, ./output)
    python create_ymaze_timing.py --data-dir /path         # Override data directory
    python create_ymaze_timing.py --debug                  # Save intermediate files
    python create_ymaze_timing.py --help                   # Show all options
"""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, TextIO
from datetime import datetime


class TeeOutput:
    """
    Duplicates stdout/stderr to both console and a log file.

    Usage:
        with TeeOutput(log_file_path):
            print("This goes to both console and file")
    """

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_file: Optional[TextIO] = None
        self.original_stdout: Optional[TextIO] = None
        self.original_stderr: Optional[TextIO] = None

    def __enter__(self):
        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Open log file
        self.log_file = open(self.log_path, 'w', encoding='utf-8')

        # Save original streams
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        # Replace with tee streams
        sys.stdout = TeeStream(self.original_stdout, self.log_file)
        sys.stderr = TeeStream(self.original_stderr, self.log_file)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original streams
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

        # Close log file
        if self.log_file:
            self.log_file.close()

        return False


class TeeStream:
    """A stream that writes to both a primary stream and a log file."""

    def __init__(self, primary: TextIO, log_file: TextIO):
        self.primary = primary
        self.log_file = log_file

    def write(self, data: str):
        self.primary.write(data)
        self.log_file.write(data)
        self.log_file.flush()  # Ensure immediate write to file

    def flush(self):
        self.primary.flush()
        self.log_file.flush()

    def isatty(self):
        return self.primary.isatty()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import CONFIG, PipelineConfig, PathConfig

from data_io import (
    load_coordinates,
    find_coordinate_file,
    find_all_coordinate_files,
    find_matching_preference_file,
    load_environment_preferences,
    discover_subjects,
    save_dataframe,
    save_labeled_data,
    write_all_fsl_timing_files,
    write_labeled_trial_files_by_preference,
    ensure_directory,
    ProcessingReport,
    DataLoadError,
    DataValidationError
)

from processing import (
    detect_teleportations,
    label_trials,
    extract_timing
)

from visualization import (
    create_trajectory_plot,
    save_trajectory_plot
)


def extract_participant_number(folder_name: str, prefix: str = "sub") -> Tuple[Optional[str], Optional[str]]:
    """
    Extract participant number from folder name.

    Handles formats like:
    - NAV066 → "066" → "sub-066"
    - NAV123 → "123" → "sub-123"
    - sub-05 → "05" → "sub-05"
    - participant_42 → "42" → "sub-42"

    Parameters
    ----------
    folder_name : str
        Name of the subject folder
    prefix : str
        Prefix for subject ID (default: "sub")

    Returns
    -------
    Tuple[Optional[str], Optional[str]]
        (participant_number, subject_id) or (None, None) if no number found
    """
    # Pattern 1: NAV followed by digits (e.g., NAV066)
    match = re.search(r'NAV(\d+)', folder_name, re.IGNORECASE)
    if match:
        num = match.group(1)
        return num, f"{prefix}-{num}"

    # Pattern 2: sub- followed by digits (e.g., sub-01)
    match = re.search(r'sub-?(\d+)', folder_name, re.IGNORECASE)
    if match:
        num = match.group(1)
        return num, f"{prefix}-{num}"

    # Pattern 3: Any digits in the name (fallback)
    match = re.search(r'(\d+)', folder_name)
    if match:
        num = match.group(1)
        return num, f"{prefix}-{num}"

    # No number found
    return None, None


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None):
    """Configure logging for the pipeline."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler()]

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def process_subject(
    coord_file: Path,
    output_dir: Path,
    subject_id: str,
    config: PipelineConfig,
    subject_folder: Path,
    run_suffix: Optional[str] = None,
    save_intermediate: bool = False,
    save_plots: bool = True
) -> dict:
    """
    Process a single coordinate file for a subject.

    Parameters
    ----------
    coord_file : Path
        Path to the coordinate CSV file
    output_dir : Path
        Path for output files
    subject_id : str
        Subject identifier (e.g., "sub-066")
    config : PipelineConfig
        Pipeline configuration
    subject_folder : Path
        Path to the subject's data folder (for finding preferences file)
    run_suffix : Optional[str]
        Run identifier (e.g., "C" for computer, "S" for scanner).
        If provided, adds suffix to output filenames.
    save_intermediate : bool
        Whether to save intermediate processing files
    save_plots : bool
        Whether to generate and save trajectory plots

    Returns
    -------
    dict
        Processing results including counts, file paths, and preference errors
    """
    logger = logging.getLogger(__name__)

    # Build display name for logging
    run_label = f" (run {run_suffix})" if run_suffix else ""
    logger.info(f"Processing {subject_id}{run_label}: {coord_file.name}")

    # Create output directory (with subfolder for run suffix if present)
    if run_suffix:
        subject_output = ensure_directory(output_dir / subject_id / run_suffix)
    else:
        subject_output = ensure_directory(output_dir / subject_id)

    # Step 1: Load and validate data
    df = load_coordinates(coord_file, columns=config.columns)
    logger.debug(f"Loaded {len(df)} rows from {coord_file.name}")

    # Step 2: Detect teleportations
    teleport_df, teleport_events = detect_teleportations(
        df,
        target_positions=config.teleport.target_positions,
        distance_threshold=config.teleport.distance_threshold,
        position_tolerance=config.teleport.position_tolerance
    )

    # Build filename prefix based on run_suffix
    if run_suffix:
        file_prefix = f"{subject_id}_{run_suffix}"
    else:
        file_prefix = subject_id

    if save_intermediate:
        save_dataframe(teleport_df, subject_output, f"{file_prefix}_teleport_detected")

    # Step 3: Label trials
    labeled_df, labeling_summary = label_trials(teleport_df)

    if save_intermediate:
        save_dataframe(labeled_df, subject_output, f"{file_prefix}_trials_labeled")

    # Step 4: Extract timing
    timing_data = extract_timing(labeled_df, normalize=True)

    # Save final labeled data
    timing_df = timing_data.to_dataframe()
    save_labeled_data(
        timing_df,
        subject_output,
        subject_id,
        suffix="labeled_final",
        run_suffix=None  # No suffix needed - files are in separate folders
    )

    # Step 5: Generate FSL timing files (one per trial number)
    fsl_files = write_all_fsl_timing_files(
        timing_data=timing_data,
        output_dir=subject_output,
        run_suffix=None  # No suffix needed - files are in separate folders
    )

    # Step 5b: Generate preference-based labeled timing files
    preference_errors = {
        'missing_file': False,
        'missing_envs': []
    }

    pref_file = find_matching_preference_file(subject_folder, run_suffix)

    if pref_file is None:
        logger.warning(
            f"No preferences file found for {subject_id}"
            f"{' (run ' + run_suffix + ')' if run_suffix else ''} - "
            f"skipping labeled_trials_bypref output"
        )
        preference_errors['missing_file'] = True
    else:
        logger.info(f"Loading preferences from: {pref_file.name}")
        try:
            env_preferences = load_environment_preferences(pref_file)

            bypref_files, missing_envs = write_labeled_trial_files_by_preference(
                timing_data=timing_data,
                output_dir=subject_output,
                env_preferences=env_preferences,
                run_suffix=None  # No suffix needed - files are in separate folders
            )

            fsl_files.update(bypref_files)
            preference_errors['missing_envs'] = missing_envs

        except Exception as e:
            logger.error(f"Failed to load preferences: {e}")
            preference_errors['missing_file'] = True

    # Step 6: Generate visualizations
    if save_plots:
        if run_suffix:
            plot_title = f"Trajectory: {subject_id} (run {run_suffix})"
            plot_filename = f"{subject_id}_{run_suffix}_trajectory.png"
        else:
            plot_title = f"Trajectory: {subject_id}"
            plot_filename = f"{subject_id}_trajectory.png"

        fig, ax = create_trajectory_plot(
            df,
            teleport_events=teleport_events,
            target_positions=config.teleport.target_positions,
            title=plot_title,
            columns=config.columns
        )
        save_trajectory_plot(fig, subject_output, plot_filename)

    return {
        'subject_id': subject_id,
        'run_suffix': run_suffix,
        'n_rows': len(df),
        'n_teleports': len(teleport_events),
        'n_trials': len(timing_data.trials),
        'max_trial_num': timing_data.max_trial_num,
        'n_environments': labeling_summary.n_environments,
        'output_dir': subject_output,
        'fsl_files': fsl_files,
        'preference_errors': preference_errors
    }


def run_pipeline(
    data_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    subject_prefix: str = "sub",
    save_intermediate: bool = False,
    save_plots: bool = True,
    verbose: bool = False
) -> ProcessingReport:
    """
    Run the timing extraction pipeline on all subjects.

    Subject IDs are derived from folder names by extracting the numeric portion.
    For example: NAV066 → sub-066, NAV123 → sub-123

    Parameters
    ----------
    data_dir : Optional[Path]
        Override default data directory
    output_dir : Optional[Path]
        Override default output directory
    subject_prefix : str
        Prefix for subject IDs (default: "sub").
        E.g., with prefix="sub", NAV066 becomes sub-066
    save_intermediate : bool
        Save intermediate processing files for debugging
    save_plots : bool
        Generate trajectory visualizations
    verbose : bool
        Enable verbose logging

    Returns
    -------
    ProcessingReport
        Summary of processing results and any errors
    """
    logger = logging.getLogger(__name__)

    # Configure paths
    config = PipelineConfig()

    if data_dir:
        config.paths.data_dir = Path(data_dir)
    if output_dir:
        config.paths.output_dir = Path(output_dir)

    config.output.subject_prefix = subject_prefix
    config.output.save_intermediate_files = save_intermediate

    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(error)
        raise ValueError(f"Configuration validation failed: {errors}")

    # Initialize report
    report = ProcessingReport()

    # Discover subjects
    subjects = discover_subjects(config.paths.data_dir)
    logger.info(f"Found {len(subjects)} subject folders to process")

    if not subjects:
        logger.warning("No subject folders found")
        return report

    # Process each subject
    for subject_folder in subjects:
        # Extract participant number from folder name
        participant_num, subject_id = extract_participant_number(
            subject_folder.name,
            prefix=subject_prefix
        )

        if subject_id is None:
            logger.warning(
                f"Could not extract participant number from '{subject_folder.name}', skipping"
            )
            report.add_error(subject_folder.name, "Could not extract participant number")
            continue

        logger.info(f"\n{'='*50}")
        logger.info(f"Processing {subject_folder.name} → {subject_id}")
        logger.info(f"{'='*50}")

        # Find all coordinate files in this subject's folder
        coord_files = find_all_coordinate_files(subject_folder)

        if not coord_files:
            logger.warning(f"No coordinate files found in {subject_folder.name}")
            report.add_error(subject_folder.name, "No coordinate files found")
            continue

        logger.info(f"Found {len(coord_files)} coordinate file(s)")

        # Process each coordinate file
        for coord_file, run_suffix in coord_files:
            try:
                results = process_subject(
                    coord_file=coord_file,
                    output_dir=config.paths.output_dir,
                    subject_id=subject_id,
                    config=config,
                    subject_folder=subject_folder,
                    run_suffix=run_suffix,
                    save_intermediate=save_intermediate,
                    save_plots=save_plots
                )

                # Build display label for reporting
                run_label = f" (run {run_suffix})" if run_suffix else ""

                report.add_subject(
                    subject_id=f"{results['subject_id']}{run_label}",
                    original_folder=subject_folder.name,
                    n_teleports=results['n_teleports'],
                    n_trials=results['n_trials'],
                    n_environments=results['n_environments'],
                    output_dir=results['output_dir']
                )

                # Track preference errors for final report
                pref_errors = results.get('preference_errors', {})
                subject_display = f"{subject_id}{run_label}"

                if pref_errors.get('missing_file'):
                    report.add_preference_error(
                        subject_id=subject_display,
                        error_type='missing_file',
                        details=f"No preferences file found for run"
                    )

                for missing_env in pref_errors.get('missing_envs', []):
                    report.add_preference_error(
                        subject_id=subject_display,
                        error_type='missing_environment',
                        details=f"Environment '{missing_env}' has no preference entry"
                    )

                logger.info(
                    f"✓ Completed {subject_id}{run_label}: "
                    f"{results['n_trials']} trials, "
                    f"{results['max_trial_num']} max trial num"
                )

            except (DataLoadError, DataValidationError) as e:
                run_label = f" (run {run_suffix})" if run_suffix else ""
                logger.error(f"✗ Failed to process {subject_folder.name}{run_label}: {e}")
                report.add_error(f"{subject_folder.name}{run_label}", str(e))
                continue

            except Exception as e:
                run_label = f" (run {run_suffix})" if run_suffix else ""
                logger.exception(f"✗ Unexpected error processing {subject_folder.name}{run_label}")
                report.add_error(f"{subject_folder.name}{run_label}", str(e))
                continue

    # Save report
    report.save(config.paths.output_dir)
    report.print_summary()

    return report


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Y-Maze FSL Timing File Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              Process using ./data and ./output
  %(prog)s --data-dir /path/to/data     Override data directory
  %(prog)s --debug --verbose            Debug mode with verbose logging
  %(prog)s --no-plots                   Skip trajectory visualizations
        """
    )

    parser.add_argument(
        '--data-dir', '-d',
        type=Path,
        help='Path to data directory (default: ./data)'
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        help='Path to output directory (default: ./output)'
    )

    parser.add_argument(
        '--subject-prefix', '-p',
        default='sub',
        help='Prefix for subject IDs, e.g., "sub" gives sub-066 (default: sub)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Save intermediate processing files'
    )

    parser.add_argument(
        '--no-plots',
        action='store_true',
        help='Skip trajectory visualizations'
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

    parser.add_argument(
        '--no-output-log',
        action='store_true',
        help='Disable automatic output logging to logs/log_preference.txt'
    )

    args = parser.parse_args()

    # Determine output directory for log file location
    output_dir = args.output_dir if args.output_dir else CONFIG.paths.output_dir
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_output_path = output_dir / 'logs' / f'log_preference_{timestamp}.txt'

    def run_main_logic():
        """Encapsulates main logic to allow optional TeeOutput wrapping."""
        # Setup logging
        setup_logging(verbose=args.verbose, log_file=args.log_file)

        logger = logging.getLogger(__name__)
        logger.info(f"Starting Y-Maze timing extraction at {datetime.now().isoformat()}")

        try:
            report = run_pipeline(
                data_dir=args.data_dir,
                output_dir=args.output_dir,
                subject_prefix=args.subject_prefix,
                save_intermediate=args.debug,
                save_plots=not args.no_plots,
                verbose=args.verbose
            )

            # Exit with error code if there were failures
            if report.errors:
                sys.exit(1)

        except Exception as e:
            logger.exception("Pipeline failed with error")
            sys.exit(1)

    # Run with or without output logging
    if args.no_output_log:
        run_main_logic()
    else:
        with TeeOutput(log_output_path):
            print("=" * 50)
            print(f"RUN TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 50)
            print(f"Log file: {log_output_path}\n")
            run_main_logic()


if __name__ == "__main__":
    main()
