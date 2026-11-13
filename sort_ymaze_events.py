#!/usr/bin/env python3
"""
sort_ymaze_events.py: put the event timing files made by make_ymaze_events.py where MR.Flow reads them.

    python sort_ymaze_events.py --to <MRI folder>            # preview only: changes nothing
    python sort_ymaze_events.py --to <MRI folder> --apply    # copy the files

--from   make_ymaze_events.py's output (default: 05_analyses/mri/ymaze_events/output)
--to     a folder with one sub-<ID> folder per participant holding the DICOMs (e.g.
         03_data/rawdata/mri). For each participant in --from, the task BOLD folder (name has
         "BOLD" and "Task", not "rest") is found under --to/sub-<ID>/, and the FSL .txt files
         go into its events/ folder, which MR.Flow merges into the BIDS events.tsv.

Preview (default): lists, per participant, which .txt files are new, identical, would be
replaced, or would be removed (an old trial type that is no longer made), and writes
events_check.html next to --from (new events vs those now in --to; open it in a browser).

--apply: every file that would be replaced or removed is first copied into --archive
(default: a dated _replaced_<date> folder next to --from), checked, and only then
overwritten or deleted; then the new files are copied. Files that are not .txt (e.g.
ymaze.name) are never touched. A log of every action is written to the archive folder.

Folders whose name starts with "_" (_excluded, _archive, ...) are never read or written,
in --from or --to. Refuses to write into 06_releases. MR.Flow skips subjects whose BIDS
events.tsv already exists, so after replacing files, move that events.tsv aside before
re-running MR.Flow's conversion.
"""
import argparse
import csv
import filecmp
import json
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_ymaze_events import DEFAULT_OUTPUT, hidden, participants, task_bold   # noqa: E402

LANES = ['explore', 'cond1', 'cond2', 'cond3', 'preprobe', 'probe', 'other_trials', 'post_task', 'rest']


def read_txt_dir(d):
    """Events from a folder of FSL .txt files, trial_type = file name."""
    ev = []
    for f in sorted(Path(d).glob('*.txt')) if Path(d).is_dir() else []:
        for line in open(f):
            p = line.split()
            if len(p) >= 2:
                ev.append({'t': f.stem, 'on': round(float(p[0]), 2), 'du': round(float(p[1]), 2)})
    return sorted(ev, key=lambda e: e['on'])


def gaps(events, end):
    iv = sorted((max(0, e['on']), min(end, e['on'] + e['du'])) for e in events if e['on'] < end)
    out, cur = [], 0.0
    for a, b in iv:
        if a > cur + 0.05:
            out.append([round(cur, 2), round(a - cur, 2)])
        cur = max(cur, b)
    if end > cur + 0.05:
        out.append([round(cur, 2), round(end - cur, 2)])
    return out


def check_page(rows, out_html):
    """The events check page (events_check_template.html): new events vs the ones in --to."""
    subs = []
    for r in rows:
        new, old, end = r['new_events'], r['old_events'], r['scan_s']
        old_key = {(e['t'], e['on']): e for e in old}
        new_key = {(e['t'], e['on']): e for e in new}
        for e in new:
            o = old_key.get((e['t'], e['on']))
            e['s'] = 'same' if o and abs(o['du'] - e['du']) < 0.011 else ('short' if o else 'new')
            if e['s'] == 'short':
                e['old_du'] = o['du']
        removed = [dict(e, s='removed') for k, e in old_key.items() if k not in new_key]
        g_old, g_new = gaps(old, end), gaps(new, end)
        subs.append({
            'sub': r['sub'], 'end': end, 'events': new, 'removed': removed,
            'gaps_old': g_old, 'gaps_new': g_new,
            'n_new': sum(e['s'] == 'new' for e in new), 'n_short': sum(e['s'] == 'short' for e in new),
            'n_removed': len(removed), 'post_task': r['post_task_s'],
            'n_other': sum(e['t'] == 'other_trials' for e in new),
            'unl_old': round(sum(g[1] for g in g_old), 1), 'unl_new': round(sum(g[1] for g in g_new), 1),
            'max_gap_new': max([g[1] for g in g_new] or [0]),
            'old_past_end': sum(e['on'] + e['du'] > end + 0.5 for e in old),
        })
    html = (HERE / 'events_check_template.html').read_text()
    out_html.write_text(html.replace('/*DATA*/null', json.dumps({'lanes': LANES, 'subs': subs})))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--from', dest='src', type=Path, default=DEFAULT_OUTPUT, help=f'default: {DEFAULT_OUTPUT}')
    ap.add_argument('--to', type=Path, required=True, help='folder with sub-<ID>/.../<task BOLD>/ (e.g. 03_data/rawdata/mri)')
    ap.add_argument('--apply', action='store_true', help='copy the files (without it: preview only)')
    ap.add_argument('--archive', type=Path, default=None,
                    help='where replaced/removed files are kept (default: <from>/../_replaced_<date>)')
    a = ap.parse_args()
    if not a.src.is_dir() or not a.to.is_dir():
        sys.exit(f'Not found: {a.src if not a.src.is_dir() else a.to}')
    if '06_releases' in a.to.resolve().parts:
        sys.exit('Refusing to write into 06_releases (frozen).')
    if hidden(a.to.name):
        sys.exit(f'--to is a "{a.to.name}" folder; those are never written to.')
    archive = a.archive or a.src.parent / f'_replaced_{date.today().isoformat()}'
    log_in = {r['participant_id']: r for r in csv.DictReader(open(a.src / 'events_log.tsv'), delimiter='\t')}

    actions, check_rows = [], []
    print(f'{"participant":<12} {"new":>4} {"same":>5} {"replace":>8} {"remove":>7}  destination')
    for sub_dir in participants(a.src):
        pid = sub_dir.name[4:]
        bolds = task_bold(a.to, pid)
        if len(bolds) != 1:
            print(f'sub-{pid:<8} SKIPPED: {len(bolds)} task BOLD folders under {a.to / sub_dir.name}')
            actions.append({'participant_id': pid, 'file': '', 'action': 'skipped',
                            'destination': '', 'archived_to': '', 'note': f'{len(bolds)} task BOLD folders'})
            continue
        dest = bolds[0] / 'events'
        new_files = sorted(sub_dir.glob('*.txt'))
        new_names = {f.name for f in new_files}
        old_txt = sorted(dest.glob('*.txt')) if dest.is_dir() else []
        counts = {'new': 0, 'same': 0, 'replace': 0, 'remove': 0}
        for f in new_files:
            d = dest / f.name
            act = 'new' if not d.exists() else ('same' if filecmp.cmp(f, d, shallow=False) else 'replace')
            counts[act] += 1
            actions.append({'participant_id': pid, 'file': f.name, 'action': act, 'destination': str(d),
                            'archived_to': '', 'note': ''})
        for d in old_txt:
            if d.name not in new_names:
                counts['remove'] += 1
                actions.append({'participant_id': pid, 'file': d.name, 'action': 'remove', 'destination': str(d),
                                'archived_to': '', 'note': 'trial type no longer made'})
        print(f'sub-{pid:<8} {counts["new"]:>4} {counts["same"]:>5} {counts["replace"]:>8} {counts["remove"]:>7}  {dest}')
        lg = log_in.get(pid, {})
        check_rows.append({'sub': f'sub-{pid}', 'scan_s': float(lg.get('scan_s') or 0),
                           'post_task_s': float(lg.get('post_task_s') or 0),
                           'new_events': read_txt_dir(sub_dir), 'old_events': read_txt_dir(dest)})

    check = a.src.parent / 'events_check.html'
    check_page(check_rows, check)
    print(f'\nCheck page: {check}')
    todo = [x for x in actions if x['action'] in ('new', 'replace', 'remove')]
    if not a.apply:
        print(f'PREVIEW ONLY: {len(todo)} file changes. Nothing was copied; add --apply to do it.')
        return

    archive.mkdir(parents=True, exist_ok=True)
    for x in todo:
        d = Path(x['destination'])
        if x['action'] in ('replace', 'remove'):
            keep = archive / f"sub-{x['participant_id']}" / d.parent.parent.name / 'events' / d.name
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(d, keep)
            if not filecmp.cmp(d, keep, shallow=False):
                sys.exit(f'Archive copy differs from {d}; stopped before changing it.')
            x['archived_to'] = str(keep)
        if x['action'] == 'remove':
            d.unlink()
        else:
            d.parent.mkdir(parents=True, exist_ok=True)
            src = a.src / f"sub-{x['participant_id']}" / x['file']
            with open(src, 'rb') as fi, open(d, 'wb') as fo:   # write in place (the lab server can refuse renames)
                fo.write(fi.read())
            if not filecmp.cmp(src, d, shallow=False):
                sys.exit(f'Copy check failed for {d}')
    log = archive / f'sort_log_{date.today().isoformat()}.tsv'
    with open(log, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['participant_id', 'file', 'action', 'destination', 'archived_to', 'note'],
                           delimiter='\t')
        if f.tell() == 0:
            w.writeheader()
        w.writerows(actions)
    print(f'Done: {len(todo)} file changes. Log: {log}')


if __name__ == '__main__':
    main()
