#!/usr/bin/env python3
"""
Classify each Y-maze run's navigation strategy (allocentric / egocentric), by age group.

Replaces the old classify_c_subjects.py, classify_s_subjects.py and compare_cs_consistency.py
(projects/4-all-ymaze/code/classifications), which guessed computer vs scanner from a C/S
letter in the file name and kept their own hard-coded exclusion list.

Reads (all from the nav_study folder this repo sits in, ../../):
  03_data/rawdata/sub-*/ses-*/ymaze/*_task-ymaze_preferences.csv   one file per run
      ses-beh = testing computer, ses-mri = scanner, ses-y1 = year-1 visit (computer)
  02_participants/demographics.tsv    age_group
  02_participants/participants.tsv    incl_ymaze_computer / incl_ymaze_scanner (built from exclusions.tsv)
  02_participants/exclusions.tsv      the reason, when a run is not used

Writes (03_data/derivatives/ymaze/):
  strategy_by_run.tsv               one row per run, every run (included or not)
  strategy_computer_vs_scanner.tsv  people with an included computer AND scanner run: do they match?
  strategy_counts.tsv               counts per run type x age group x majority label (included runs)

Rules (from post/preference_aggregation.classify_preference, shared with run_preference_analysis.py):
  majority:      allocentric if >= 50% Place, else egocentric   (a 5/5 tie counts as allocentric)
  ego_presence:  allocentric only if 100% Place
  ego_exclusive: egocentric only if 0% Place
Minimum: runs with fewer than MIN_ENVIRONMENTS finished environments get NA labels (labelled = no).
Inclusion: participants.tsv value 1 = included; ? = undecided, included for now (pending = yes);
anything else = not included. Exclusions are decided ONLY in 02_participants/exclusions.tsv.

Usage:  python3 classify_strategy.py [--study-root /path/to/nav_study]
"""
import sys, csv, argparse, collections
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from post.preference_aggregation import classify_preference

MIN_ENVIRONMENTS = 3  # runs with fewer finished environments get no strategy label (NA). Proposed 2026-11-09, to review with advisor (01_methods/analysis_decisions.md #2)
RUN_TYPE = {'ses-beh': 'computer', 'ses-y1': 'computer', 'ses-mri': 'scanner'}
INCL_COL = {'computer': 'incl_ymaze_computer', 'scanner': 'incl_ymaze_scanner'}
EXCL_CODES = {'computer': ('ymaze_computer', 'all_behavior'), 'scanner': ('ymaze_scanner',)}


def read_tsv(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f, delimiter='\t'))


def write_tsv(p, cols, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter='\t', lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--study-root', type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument('--min-environments', type=int, default=MIN_ENVIRONMENTS,
                    help=f'minimum finished environments for a label (default {MIN_ENVIRONMENTS}); use 0 or 10 for sensitivity checks')
    a = ap.parse_args()
    root = a.study_root
    raw = root / '03_data' / 'rawdata'
    out = root / '03_data' / 'derivatives' / 'ymaze'
    parts = root / '02_participants'

    age = {r['participant_id']: (r['age_group'] or '').strip() for r in read_tsv(parts / 'demographics.tsv')}
    incl = {r['participant_id']: r for r in read_tsv(parts / 'participants.tsv')}
    excl = read_tsv(parts / 'exclusions.tsv')

    def reason(pid, run_type):
        rs = [r for r in excl if r['participant_id'] == pid and
              (r['irb_category'] == 'Screen Failure' and r['status'] == 'excluded'
               or any(c in r['data_excluded'].split(', ') or c == r['data_excluded'] for c in EXCL_CODES[run_type]))]
        return '; '.join(f"{r['status']}: {r['reason']}" for r in rs)

    rows = []
    for f in sorted(raw.glob('sub-*/ses-*/ymaze/*_task-ymaze_preferences.csv')):
        pid, ses = f.parts[-4][4:], f.parts[-3]
        run_type = RUN_TYPE.get(ses)
        if not run_type:
            print(f'WARNING: unknown session {ses} for {pid}; skipped')
            continue
        with open(f, encoding='utf-8') as fh:
            prefs = [r['preference'] for r in csv.DictReader(fh)]
        n = len(prefs)
        n_place = sum(p == 'Place' for p in prefs)
        n_resp = sum(p == 'Response' for p in prefs)
        g = age.get(pid, '')
        status = incl.get(pid, {}).get(INCL_COL[run_type], '')
        included = 'yes' if status in ('1', '?') else 'no'
        row = {'participant_id': pid, 'session': ses, 'run_type': run_type, 'age_group': g,
               'n_environments': n, 'n_place': n_place, 'n_response': n_resp,
               'pct_place': f'{100 * n_place / n:.1f}' if n else 'NA',
               'majority': 'NA', 'ego_presence': 'NA', 'ego_exclusive': 'NA', 'classification': 'NA',
               'included': included, 'decision_pending': 'yes' if status == '?' else 'no',
               'participants_tsv_value': status or 'NA',
               'exclusion_reason': reason(pid, run_type) if included == 'no' or status == '?' else ''}
        row['labelled'] = 'yes' if n and n >= a.min_environments else 'no'
        if row['labelled'] == 'yes':
            c = classify_preference(100 * n_place / n)
            short = 'allo' if c.majority == 'allocentric' else 'ego'
            row.update(majority=c.majority, ego_presence=c.ego_presence, ego_exclusive=c.ego_exclusive,
                       classification=f'{g.lower()}-{short}' if g else f'unknown-{short}')
        if not g:
            print(f'WARNING: no age group for {pid} in demographics.tsv')
        rows.append(row)

    cols = list(rows[0].keys())
    write_tsv(out / 'strategy_by_run.tsv', cols, rows)

    # computer vs scanner (baseline computer run only, both included)
    by = collections.defaultdict(dict)
    for r in rows:
        if r['included'] == 'yes' and r['majority'] != 'NA' and r['session'] in ('ses-beh', 'ses-mri'):
            by[r['participant_id']][r['run_type']] = r
    cs = []
    for pid, d in sorted(by.items()):
        if 'computer' in d and 'scanner' in d:
            c, s = d['computer'], d['scanner']
            cs.append({'participant_id': pid, 'age_group': c['age_group'],
                       'majority_computer': c['majority'], 'majority_scanner': s['majority'],
                       'classification_computer': c['classification'], 'classification_scanner': s['classification'],
                       'match': 'yes' if c['majority'] == s['majority'] else 'no',
                       'decision_pending': 'yes' if 'yes' in (c['decision_pending'], s['decision_pending']) else 'no'})
    write_tsv(out / 'strategy_computer_vs_scanner.tsv',
              ['participant_id', 'age_group', 'majority_computer', 'majority_scanner',
               'classification_computer', 'classification_scanner', 'match', 'decision_pending'], cs)

    cnt = collections.Counter((r['run_type'], r['session'], r['age_group'], r['majority'])
                              for r in rows if r['included'] == 'yes' and r['majority'] != 'NA')
    crow = [{'run_type': k[0], 'session': k[1], 'age_group': k[2], 'majority': k[3], 'n': v} for k, v in sorted(cnt.items())]
    write_tsv(out / 'strategy_counts.tsv', ['run_type', 'session', 'age_group', 'majority', 'n'], crow)

    short = [f"{r['participant_id']} {r['session']} ({r['n_environments']})" for r in rows if r['included'] == 'yes' and r['labelled'] == 'no']
    if short:
        print(f'Not labelled (fewer than {a.min_environments} environments):', ', '.join(short))
    print(f'{len(rows)} runs ({sum(r["included"] == "yes" for r in rows)} included) -> {out}/strategy_by_run.tsv')
    for k in crow:
        print(f"  {k['run_type']:8s} {k['session']:7s} {k['age_group']:3s} {k['majority']:11s} {k['n']}")
    m = sum(r['match'] == 'yes' for r in cs)
    print(f'Computer vs scanner: {m} of {len(cs)} match -> strategy_computer_vs_scanner.tsv')
    pend = sorted({r['participant_id'] for r in rows if r['decision_pending'] == 'yes'})
    if pend:
        print('Included for now, decision pending:', ', '.join(pend))


if __name__ == '__main__':
    main()
