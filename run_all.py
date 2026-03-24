#!/usr/bin/env python3
"""Run all three Y-maze analysis steps in sequence."""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run the full Y-maze analysis pipeline")
    parser.add_argument("--data-dir", "-d", default="../data", help="Path to data directory (default: ../data)")
    parser.add_argument("--output-dir", "-o", default="../output", help="Path to output directory (default: ../output)")
    parser.add_argument("--subject-prefix", "-p", default="sub", help="Prefix for subject IDs (default: sub)")
    parser.add_argument("--no-plots", action="store_true", help="Skip trajectory visualizations")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    common = []
    if args.verbose:
        common.append("--verbose")

    steps = [
        {
            "name": "Step 1: Generate FSL timing files",
            "cmd": [
                sys.executable, str(script_dir / "create_ymaze_timing.py"),
                "--data-dir", args.data_dir,
                "--output-dir", args.output_dir,
                "--subject-prefix", args.subject_prefix,
            ] + (["--no-plots"] if args.no_plots else []) + common,
        },
        {
            "name": "Step 2: Calculate behavioral outcomes",
            "cmd": [
                sys.executable, str(script_dir / "create_ymaze_outcomes.py"),
                "--output-dir", args.output_dir,
            ] + common,
        },
        {
            "name": "Step 3: Aggregate preferences",
            "cmd": [
                sys.executable, str(script_dir / "run_preference_analysis.py"),
                "--data-dir", args.data_dir,
                "--output-dir", args.output_dir,
            ] + common,
        },
    ]

    for step in steps:
        print(f"\n{'='*60}")
        print(f"  {step['name']}")
        print(f"{'='*60}\n")
        result = subprocess.run(step["cmd"])
        if result.returncode != 0:
            print(f"\nERROR: {step['name']} failed (exit code {result.returncode})")
            sys.exit(result.returncode)

    print(f"\n{'='*60}")
    print("  All steps completed successfully!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
