#!/usr/bin/env python3
"""
Run the Y-maze pipeline for nav_study, in order:

  1. strategy   classify_strategy.py      rawdata/ymaze_computer + ymaze_scanner
                                          -> 03_data/derivatives/ymaze/strategy_*.tsv
  2. outcomes   create_ymaze_outcomes.py  rawdata/ymaze_computer + ymaze_scanner
                                          -> 03_data/derivatives/ymaze/outcomes/
  3. events     make_ymaze_events.py      rawdata/ymaze_scanner + rawdata/mri (scan length)
                                          -> 05_analyses/mri/ymaze_events/output/

    python run_all.py                       # all three
    python run_all.py --only events         # one step (strategy, outcomes, events)
    python run_all.py --mri <folder>        # where the task fMRI DICOMs are (step 3)

Every step reads only the main rawdata folders: folders starting with "_" (_excluded,
_archive) are never read. Placing the event files where MR.Flow reads them is NOT done here:
check 05_analyses/mri/ymaze_events/ first, then run sort_ymaze_events.py yourself.
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ['strategy', 'outcomes', 'events']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', nargs='+', choices=STEPS, help='run only these steps')
    ap.add_argument('--mri', help='task fMRI DICOM folder for step 3 (default: 03_data/rawdata/mri)')
    ap.add_argument('--no-plots', action='store_true', help='step 3: skip the trajectory plots')
    a = ap.parse_args()

    cmds = {
        'strategy': [sys.executable, str(HERE / 'classify_strategy.py')],
        'outcomes': [sys.executable, str(HERE / 'create_ymaze_outcomes.py')],
        'events':   [sys.executable, str(HERE / 'make_ymaze_events.py')]
                    + (['--mri', a.mri] if a.mri else []) + (['--no-plots'] if a.no_plots else []),
    }
    for step in a.only or STEPS:
        print(f"\n{'=' * 60}\n  {step}: {Path(cmds[step][1]).name}\n{'=' * 60}\n", flush=True)
        r = subprocess.run(cmds[step], cwd=HERE)
        if r.returncode != 0:
            sys.exit(f'\nERROR: step "{step}" failed (exit code {r.returncode}); later steps not run.')
    print(f"\n{'=' * 60}\n  Done. Event files are NOT placed for MR.Flow: check them, then run "
          f"sort_ymaze_events.py.\n{'=' * 60}")


if __name__ == '__main__':
    main()
