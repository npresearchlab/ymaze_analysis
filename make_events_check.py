"""
make_events_check.py: visual check of new vs current events.tsv files.

Builds one self-contained HTML page (open it in any browser) that compares each
subject's NEW events.tsv (e.g. from make_events.py) with the CURRENT one in BIDS:
  * overview of all subjects (task events colored unchanged / new / shortened / removed,
    old unlabeled time, end of scan)
  * per-subject view with every trial type in its own row, plus unlabeled time before/now
  * summary table with counts and flags (cut-off events, long post_task, gaps > 5.1 s)

Needs events_check_template.html in the same folder, and make_events_log.tsv
(written by make_events.py) in the new-events folder (used for scan length).

Usage:
  python make_events_check.py <new_events_dir> <bids_dir> <output.html>
"""
import csv, glob, json, os, sys
from pathlib import Path

ST = Path(sys.argv[1])          # staged events folder
BIDS = Path(sys.argv[2])        # bids_data
OUT = Path(sys.argv[3])         # html path

LANES = ['explore', 'cond1', 'cond2', 'cond3', 'preprobe', 'probe', 'other_trials', 'post_task', 'rest']


def read(p):
    with open(p, newline='') as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    return [{'t': r['trial_type'], 'on': round(float(r['onset']), 2), 'du': round(float(r['duration']), 2)} for r in rows]


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


log = {r['sub']: r for r in csv.DictReader(open(ST / 'make_events_log.tsv'), delimiter='\t')}
subs = []
for d in sorted(ST.glob('sub-*')):
    sub = d.name
    new_f = next(d.glob('*_events.tsv'))
    old_f = BIDS / sub / 'ses-01' / 'func' / new_f.name
    new, old = read(new_f), read(old_f)
    end = float(log[sub]['scan_s'])
    # exact scan length (log is rounded): use max of rounded value and clipped event ends
    old_key = {(e['t'], e['on']): e for e in old}
    new_key = {(e['t'], e['on']): e for e in new}
    for e in new:
        o = old_key.get((e['t'], e['on']))
        e['s'] = 'same' if o and abs(o['du'] - e['du']) < 0.011 else ('short' if o else 'new')
        if e['s'] == 'short':
            e['old_du'] = o['du']
    removed = [dict(e, s='removed') for k, e in old_key.items() if k not in new_key]
    task_new = [e for e in new if e['t'] != 'rest']
    subs.append({
        'sub': sub, 'end': end, 'events': new, 'removed': removed,
        'gaps_old': gaps(old, end), 'gaps_new': gaps(new, end),
        'n_new': sum(e['s'] == 'new' for e in new), 'n_short': sum(e['s'] == 'short' for e in new),
        'n_removed': len(removed), 'post_task': float(log[sub]['post_task_s']),
        'n_other': sum(e['t'] == 'other_trials' for e in new),
        'unl_old': round(sum(g[1] for g in gaps(old, end)), 1),
        'unl_new': round(sum(g[1] for g in gaps(new, end)), 1),
        'max_gap_new': max([g[1] for g in gaps(new, end)] or [0]),
        'old_past_end': sum(e['on'] + e['du'] > end + 0.5 for e in old),
    })

html = open(Path(__file__).with_name('events_check_template.html')).read()
html = html.replace('/*DATA*/null', json.dumps({'lanes': LANES, 'subs': subs}))
OUT.write_text(html)
print(f'wrote {OUT} ({len(subs)} subjects)')
