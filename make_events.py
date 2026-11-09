"""
make_events.py: build BIDS events.tsv for the Y-maze task from labeled_trials/*.txt.

Replicates mrflow's event conversion (modules/event_conversion.py): every .txt in
labeled_trials/ becomes trial_type = file name, rows sorted by onset, written as
onset/duration/trial_type TSV. Optionally applies scan-end handling:

  --scan-end   * drop events that start at/after the last volume
               * shorten events that run past the last volume
               * add a `post_task` event from (last task trial end + POST_TASK_GAP)
                 to the end of the scan, if that span is > 0

Scan length = n_volumes x TR, read from the BIDS BOLD NIfTI header.

Usage:
  python make_events.py --labeled-root <dir with NAVxxx/S/labeled_trials>
                        --bids-dir <bids_data> --out-dir <dir> [--scan-end]
Writes <out-dir>/sub-XXX/<same filename as the existing events.tsv>.
Never writes into bids_data itself.
"""
import argparse, csv, glob, os, sys
from pathlib import Path

import nibabel as nib

POST_TASK_GAP = 5.0          # s; one typical rest gap before post_task starts
NON_TASK = {'rest'}          # trial types that are not task trials


def read_fsl(path, trial_type):
    rows = []
    for line in open(path):
        p = line.split()
        if len(p) >= 2:
            rows.append({'onset': float(p[0]), 'duration': float(p[1]), 'trial_type': trial_type})
    return rows


def scan_length(bold):
    img = nib.load(str(bold))
    n = img.shape[3]
    tr = float(img.header.get_zooms()[3])
    return n * tr, n, tr


def apply_scan_end(events, scan_end):
    out, log = [], {'dropped': 0, 'shortened': 0, 'post_task': 0.0}
    for e in events:
        if e['onset'] >= scan_end:
            log['dropped'] += 1
            continue
        if e['onset'] + e['duration'] > scan_end:
            e = dict(e, duration=round(scan_end - e['onset'], 2))
            log['shortened'] += 1
        out.append(e)
    task = [e for e in out if e['trial_type'] not in NON_TASK]
    if task:
        last_end = max(e['onset'] + e['duration'] for e in task)
        start = round(last_end + POST_TASK_GAP, 2)
        if start < scan_end:
            dur = round(scan_end - start, 2)
            out.append({'onset': start, 'duration': dur, 'trial_type': 'post_task'})
            log['post_task'] = dur
    return out, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--labeled-root', required=True)
    ap.add_argument('--bids-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--scan-end', action='store_true')
    a = ap.parse_args()

    bids, out_root = Path(a.bids_dir), Path(a.out_dir)
    if out_root.resolve() == bids.resolve() or bids.resolve() in out_root.resolve().parents:
        sys.exit('Refusing to write inside bids_dir; write elsewhere and review first.')

    print('sub\tscan_s\tevents\tdropped\tshortened\tpost_task_s')
    for lt in sorted(Path(a.labeled_root).glob('NAV*/S/labeled_trials')):
        sub = 'sub-' + lt.parts[-3][3:]
        func = bids / sub / 'ses-01' / 'func'
        existing = [p for p in func.glob('*_events.tsv') if 'task-rest' not in p.name]
        bolds = [p for p in func.glob('*_bold.nii.gz') if 'task-rest' not in p.name]
        if len(existing) != 1 or len(bolds) != 1:
            print(f'{sub}\tSKIPPED (events files: {len(existing)}, task BOLD files: {len(bolds)})')
            continue

        events = []
        for txt in lt.glob('*.txt'):
            events += read_fsl(txt, txt.stem)
        events.sort(key=lambda e: e['onset'])

        scan_end, n, tr = scan_length(bolds[0])
        log = {'dropped': 0, 'shortened': 0, 'post_task': 0.0}
        if a.scan_end:
            events, log = apply_scan_end(events, scan_end)
            events.sort(key=lambda e: e['onset'])

        dest = out_root / sub / existing[0].name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, 'w', newline='') as f:  # csv default line ending matches mrflow output
            w = csv.DictWriter(f, fieldnames=['onset', 'duration', 'trial_type'], delimiter='\t')
            w.writeheader()
            for e in events:
                w.writerow(e)
        print(f"{sub}\t{scan_end:.0f}\t{len(events)}\t{log['dropped']}\t{log['shortened']}\t{log['post_task']:.0f}")


if __name__ == '__main__':
    main()
