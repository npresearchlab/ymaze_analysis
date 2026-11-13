#!/usr/bin/env python3
"""
make_ymaze_events.py: scanner Y-maze logs -> event timing files for the fMRI models.

    python make_ymaze_events.py                       # default folders (below)
    python make_ymaze_events.py --input <dir> --mri <dir> --output <dir> [--no-plots]

For every participant folder (sub-<ID>) in --input that has a scanner Y-maze log
(ses-mri ..._task-ymaze_coordinates.csv):
  1. label the trials and extract their timing (create_ymaze_timing.process_subject:
     explore, cond1-3, preprobe, probe, other_trials, rest);
  2. read the length of the task fMRI scan from its DICOMs in --mri
     (number of volumes x TR; the BOLD folder whose name has "BOLD" and "Task");
  3. end-of-scan handling (make_events.apply_scan_end): drop events that start after the
     scan ends, shorten events that run past it, add `post_task` from 5 s after the last
     task trial to the end of the scan;
  4. write the events, as FSL 3-column files and as a BIDS events.tsv.

Writes only to --output, never anywhere else; placing the files where MR.Flow reads them is a
separate step (sort_ymaze_events.py). Output:
    <output>/sub-<ID>/<trial_type>.txt                 FSL timing: onset duration 1
    <output>/sub-<ID>/sub-<ID>_task-ymaze_events.tsv   the same events (onset, duration, trial_type)
    <output>/events_log.tsv                            per participant: scan length, counts, what changed at scan end
    <output>/timing_details/                           labeled trials, trial numbers, plots (from step 1)

Folders whose name starts with "_" (_excluded, _archive, ...) are never read: the input
folder decides who is processed. To make events for excluded people, run it on the
_excluded folder with its own --output (e.g. <output>/_excluded).
"""
import argparse
import csv
import logging
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
STUDY = HERE.parents[1]                                     # .../nav_study

from config import PipelineConfig                           # noqa: E402
from create_ymaze_timing import process_subject             # noqa: E402
from make_events import apply_scan_end, read_fsl            # noqa: E402

DEFAULT_INPUT = STUDY / '03_data' / 'rawdata' / 'ymaze_scanner'
DEFAULT_MRI = STUDY / '03_data' / 'rawdata' / 'mri'
DEFAULT_OUTPUT = STUDY / '05_analyses' / 'mri' / 'ymaze_events' / 'output'
COORDS = '_task-ymaze_coordinates.csv'
LOG_COLS = ['participant_id', 'status', 'bold_folder', 'n_volumes', 'tr_s', 'scan_s', 'n_events',
            'dropped', 'shortened', 'post_task_s', 'note']


def hidden(name):
    return name.startswith('_') or name.startswith('.')


def participants(root):
    """sub-<ID> folders directly in root (never inside a folder starting with '_')."""
    return sorted(d for d in Path(root).iterdir() if d.is_dir() and d.name.startswith('sub-'))


def walk(root):
    """os.walk that never enters folders starting with '_' or '.'."""
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not hidden(x))
        yield Path(d), dirs, files


def scanner_logs(sub_dir):
    """Scanner (ses-mri) Y-maze coordinate files of one participant."""
    return [d / f for d, _, files in walk(sub_dir) for f in sorted(files)
            if f.endswith(COORDS) and ('ses-mri' in d.relative_to(sub_dir).parts or '_ses-mri_' in f)]


def task_bold(mri_root, pid):
    """The task BOLD DICOM folder(s) of one participant: name has BOLD and Task, not rest."""
    sub = Path(mri_root) / f'sub-{pid}'
    if not sub.is_dir():
        return []
    found = []
    for d, dirs, _ in walk(sub):
        n = d.name.lower()
        if 'bold' in n and 'task' in n and 'rest' not in n:
            found.append(d)
            dirs[:] = []                                     # the series folder: don't look inside
    return found


def scan_length(bold_dir):
    """(scan seconds, volumes, TR seconds) from the DICOMs: one .dcm file per volume."""
    import pydicom
    dcms = sorted(p for p in bold_dir.iterdir() if p.suffix.lower() == '.dcm')
    if not dcms:
        raise ValueError(f'no .dcm files in {bold_dir}')
    tr = float(pydicom.dcmread(str(dcms[0]), stop_before_pixels=True).RepetitionTime) / 1000.0
    return len(dcms) * tr, len(dcms), tr


def write_events(events, dest):
    """FSL 3-column file per trial type + one BIDS events.tsv (same writing as make_events.py)."""
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob('*.txt'):
        old.unlink()                                         # a trial type may be gone since the last run
    for t in sorted({e['trial_type'] for e in events}):
        rows = sorted((e for e in events if e['trial_type'] == t), key=lambda e: e['onset'])
        with open(dest / f'{t}.txt', 'w') as f:
            for e in rows:
                f.write(f"{e['onset']:.2f} {e['duration']:.2f} 1\n")
    with open(dest / f'{dest.name}_task-ymaze_events.tsv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['onset', 'duration', 'trial_type'], delimiter='\t')
        w.writeheader()
        for e in events:
            w.writerow(e)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--input', type=Path, default=DEFAULT_INPUT, help=f'default: {DEFAULT_INPUT}')
    ap.add_argument('--mri', type=Path, default=DEFAULT_MRI, help=f'default: {DEFAULT_MRI}')
    ap.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help=f'default: {DEFAULT_OUTPUT}')
    ap.add_argument('--no-plots', action='store_true', help='skip the trajectory plots (faster)')
    a = ap.parse_args()
    for p in (a.input, a.mri):
        if not p.is_dir():
            sys.exit(f'Not found: {p}')
    try:
        import pydicom  # noqa: F401
    except ImportError:
        sys.exit('pydicom is not installed in this Python. In yb-nav: bash /Volumes/BorichLab/YB/tools/setup-venv/setup_env.sh')
    if hidden(a.input.name) and not hidden(a.output.name):
        sys.exit(f'--input is {a.input.name}/ but --output is not a "_" folder: '
                 f'give excluded people their own output, e.g. --output {a.output / a.input.name}')
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')

    config = PipelineConfig()
    details = a.output / 'timing_details'
    config.paths.output_dir = details
    log = []
    for sub_dir in participants(a.input):
        pid = sub_dir.name[4:]
        row = dict.fromkeys(LOG_COLS, '')
        row['participant_id'] = pid
        log.append(row)
        logs = scanner_logs(sub_dir)
        bolds = task_bold(a.mri, pid)
        if len(logs) != 1 or len(bolds) != 1:
            row['status'] = 'skipped'
            row['note'] = (f'{len(logs)} scanner Y-maze logs' if len(logs) != 1 else
                           f'{len(bolds)} task BOLD folders in --mri' if bolds else 'no task scan in --mri')
            print(f'{pid}: SKIPPED ({row["note"]})')
            continue
        try:
            process_subject(coord_file=logs[0], output_dir=details, subject_id=pid, config=config,
                            subject_folder=logs[0].parent, run_suffix='S', save_plots=not a.no_plots)
            events = []
            for txt in sorted((details / pid / 'S' / 'labeled_trials').glob('*.txt')):
                events += read_fsl(txt, txt.stem)
            events.sort(key=lambda e: e['onset'])
            scan_end, n, tr = scan_length(bolds[0])
            events, ch = apply_scan_end(events, scan_end)
            events.sort(key=lambda e: e['onset'])
            write_events(events, a.output / f'sub-{pid}')
        except Exception as e:                               # one bad file must not stop the others
            row['status'], row['note'] = 'error', str(e).replace('\t', ' ')
            print(f'{pid}: ERROR {e}')
            continue
        row.update(status='ok', bold_folder=bolds[0].name, n_volumes=n, tr_s=tr, scan_s=round(scan_end, 2),
                   n_events=len(events), dropped=ch['dropped'], shortened=ch['shortened'],
                   post_task_s=round(ch['post_task'], 2))
        print(f'{pid}: {len(events)} events, scan {scan_end:.0f} s')

    a.output.mkdir(parents=True, exist_ok=True)
    with open(a.output / 'events_log.tsv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLS, delimiter='\t')
        w.writeheader()
        w.writerows(log)
    done = {f'sub-{r["participant_id"]}' for r in log if r['status'] == 'ok'}
    stale = sorted(d.name for d in a.output.glob('sub-*') if d.is_dir() and d.name not in done)
    ok = sum(r['status'] == 'ok' for r in log)
    print(f'\n{ok} of {len(log)} participants written to {a.output}; details in events_log.tsv')
    if stale:
        print(f'WARNING: {len(stale)} sub- folders in the output are from an earlier run and were not '
              f'remade this time (not deleted): {", ".join(stale)}')


if __name__ == '__main__':
    main()
