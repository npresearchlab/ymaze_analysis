#!/usr/bin/env python3
"""
Y-Maze Preference Analysis

Standalone script for aggregating preference data across subjects.
Discovers preference CSV files, aggregates by subject, and applies
classification schemes to determine navigation strategy.

Usage:
    python run_preference_analysis.py                    # Use default paths
    python run_preference_analysis.py --data-dir /path   # Override data directory
    python run_preference_analysis.py --help             # Show all options
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from data_io import (
    find_all_preference_files,
    ensure_directory,
    save_dataframe
)

from post import (
    aggregate_preferences
)


def setup_logging(verbose: bool = False, log_file: Path = None):
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


def run_preference_analysis(
    data_dir: Path,
    output_dir: Path,
    verbose: bool = False
) -> Path:
    """
    Run preference analysis on all discovered preference files.

    Parameters
    ----------
    data_dir : Path
        Directory to search for preference files
    output_dir : Path
        Directory for output files
    verbose : bool
        Enable verbose logging

    Returns
    -------
    Path
        Path to the saved aggregated preferences CSV
    """
    logger = logging.getLogger(__name__)

    # Discover preference files
    logger.info(f"Searching for preference files in: {data_dir}")
    preference_files = find_all_preference_files(data_dir)

    if not preference_files:
        logger.warning("No preference files found")
        return None

    logger.info(f"Found {len(preference_files)} preference files")

    for pf in preference_files:
        logger.debug(f"  - {pf}")

    # Aggregate preferences
    logger.info("Aggregating preferences...")
    df = aggregate_preferences(preference_files)

    if df.empty:
        logger.warning("No preferences to aggregate")
        return None

    # Save results
    ensure_directory(output_dir)
    output_path = save_dataframe(
        df,
        output_dir,
        "all_preferences.csv"
    )

    # Print summary
    print(f"\n{'='*50}")
    print("PREFERENCE ANALYSIS SUMMARY")
    print(f"{'='*50}")
    print(f"Subjects analyzed: {len(df)}")
    print(f"Output file: {output_path}")

    # Classification distribution
    print(f"\nClassification Distribution:")
    print(f"  Majority scheme:")
    majority_counts = df['majority'].value_counts()
    for strategy, count in majority_counts.items():
        pct = count / len(df) * 100
        print(f"    - {strategy}: {count} ({pct:.1f}%)")

    print(f"  Ego_Presence scheme:")
    ego_pres_counts = df['ego_presence'].value_counts()
    for strategy, count in ego_pres_counts.items():
        pct = count / len(df) * 100
        print(f"    - {strategy}: {count} ({pct:.1f}%)")

    print(f"  Ego_Exclusive scheme:")
    ego_excl_counts = df['ego_exclusive'].value_counts()
    for strategy, count in ego_excl_counts.items():
        pct = count / len(df) * 100
        print(f"    - {strategy}: {count} ({pct:.1f}%)")

    return output_path


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Y-Maze Preference Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              Analyze using ./data and ./output
  %(prog)s --data-dir /path/to/data     Override data directory
  %(prog)s --verbose                    Enable verbose logging

Classification Schemes:
  - Majority: allocentric if >= 50%% Place responses
  - Ego_Presence: allocentric only if 100%% Place responses
  - Ego_Exclusive: egocentric only if 0%% Place responses
        """
    )

    parser.add_argument(
        '--data-dir', '-d',
        type=Path,
        default=Path('./data'),
        help='Path to data directory containing preference files (default: ./data)'
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./output'),
        help='Path to output directory (default: ./output)'
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
    logger.info(f"Starting preference analysis at {datetime.now().isoformat()}")

    # Validate data directory
    if not args.data_dir.is_dir():
        logger.error(f"Data directory not found: {args.data_dir}")
        sys.exit(1)

    try:
        result = run_preference_analysis(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            verbose=args.verbose
        )

        if result is None:
            logger.warning("No results generated")
            sys.exit(1)

    except Exception as e:
        logger.exception("Preference analysis failed with error")
        sys.exit(1)


if __name__ == "__main__":
    main()
