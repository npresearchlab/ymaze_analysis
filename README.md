# Y-Maze Behavioral Analysis Pipeline

A Python pipeline for processing Y-Maze behavioral data from Unity experiments.

## Overview

This pipeline provides three standalone scripts:

| Script | Purpose |
|--------|---------|
| `create_ymaze_timing.py` | Process coordinates → FSL timing files |
| `create_ymaze_outcomes.py` | Calculate behavioral outcome measures |
| `run_preference_analysis.py` | Aggregate preference classifications |

The timing script processes coordinate data to:

1. **Detect teleportation events** - Identify when participants are teleported back to starting positions
2. **Label trials** - Categorize events as probe (p) or non-probe (np1, np2, etc.)
3. **Extract timing** - Calculate trial onset times and durations
4. **Generate FSL files** - Create timing files for neuroimaging analysis

## Installation

This pipeline uses the shared lab virtual environment `yb-nav`. Activate it before running any scripts:

```bash
source ~/.venvs/yb-nav/bin/activate
```

To deactivate when done: `deactivate`

If the environment doesn't exist yet, create it by running the setup script at `/Volumes/BorichLab/YB/tools/setup-venv/setup_env.sh`:

```bash
bash /Volumes/BorichLab/YB/tools/setup-venv/setup_env.sh
```

## Quick Start

### 1. Download the pipeline

Download the `ymaze_analysis` folder from GitHub: [link to repo]

### 2. Set up your folder structure

```
your_project/
├── data/                        ← Put your raw data here
│   ├── NAV066/
│   │   ├── coordinates_NAV066C.csv
│   │   ├── coordinates_NAV066S.csv
│   │   ├── preferences_NAV066C.csv
│   │   └── preferences_NAV066S.csv
│   ├── NAV067/
│   │   ├── coordinates_NAV067.csv
│   │   └── preferences_NAV067.csv
│   └── ...
├── output/                      ← Results will go here (create this folder)
│
└── ymaze_analysis/              ← The analysis pipeline (from GitHub)
    ├── create_ymaze_timing.py   # Generate FSL timing files from coordinates
    ├── create_ymaze_outcomes.py # Calculate behavioral outcome measures
    ├── run_preference_analysis.py  # Aggregate preference data
    ├── config.py                # Configuration settings
    ├── README.md
    │
    ├── data_io/                 # Input/output utilities
    │   ├── __init__.py
    │   ├── loaders.py
    │   └── writers.py
    │
    ├── processing/              # Core analysis modules
    │   ├── __init__.py
    │   ├── teleport_detection.py
    │   ├── trial_labeling.py
    │   └── timing_extraction.py
    │
    ├── post/                    # Post-processing and aggregation
    │   ├── __init__.py
    │   ├── outcome_measures.py
    │   └── preference_aggregation.py
    │
    └── visualization/           # Plotting utilities
        ├── __init__.py
        └── trajectory_plots.py
```

### 3. Run the analysis

```bash
# Navigate to the ymaze_analysis folder
cd ymaze_analysis

# Step 1: Generate FSL timing files from coordinate data
python create_ymaze_timing.py --data-dir ../data --output-dir ../output

# Step 2 (optional): Calculate behavioral outcome measures
python create_ymaze_outcomes.py --output-dir ../output

# Step 3 (optional): Aggregate preference data
python run_preference_analysis.py --data-dir ../data --output-dir ../output
```

The timing script processes all participants and generates FSL timing files.

## Input Data Format

### Coordinate Files

CSV files with columns (note: original files may have leading spaces):
- `Environment` - Environment identifier
- `Cummulative_Time` - Timestamp
- `X` - X coordinate
- `Z` - Z coordinate
- `Rotation` - Rotation angle

### Task Restart Handling

If a coordinate file contains multiple header rows (indicating the task was restarted), the pipeline automatically keeps only the data from the **last restart**. A log message will indicate when this occurs:

```
Found 1 task restart(s) in coordinates_BNC21.csv, using data from last restart (row 236)
```

### Preference Files

The preference analysis script (`run_preference_analysis.py`) looks for files with "preferences" in the filename. These should follow the same naming convention as coordinate files:

```
preferences_SUBID[C|S][_N].csv
```

### Transition Period Handling

The Y-maze task switches environment labels during inter-trial pauses (black screen) *before* the participant is actually teleported to the new environment. The pipeline automatically detects and marks these ~6 second transition periods:

- An `is_transition` column is added to the raw data (`True` during pauses)
- Environment labels are preserved for correct trial attribution
- This ensures probe trials are correctly assigned to their actual environment

### Probe Trial Detection

Probe trials are identified by their **destination**, not just position in the sequence:

- NP trials teleport to one position (e.g., 36.52, 22.00)
- Probe trials teleport to the **opposite** position (e.g., 0.00, -32.00)

**Auto-detection:** The pipeline automatically detects the two start positions by analyzing teleport destinations in the data. This means it works with any maze configuration — no hardcoded coordinates.

If a participant stops mid-environment (incomplete), the last teleport still goes to the NP position — so it's correctly labeled as an NP trial, not a probe. A warning is logged when incomplete environments are detected.

### Expected Directory Structure

```
data/
├── NAV066/
│   ├── coordinates_NAV066C.csv
│   ├── coordinates_NAV066S.csv
│   ├── preferences_NAV066C.csv
│   └── preferences_NAV066S.csv
├── NAV067/
│   ├── coordinates_NAV067.csv
│   └── preferences_NAV067.csv
├── _excluded/                    ← Ignored (starts with '_')
│   └── NAV999/
└── ...
```

### Excluding Subjects

To exclude subjects from processing, place them in a folder starting with `_` (e.g., `_excluded`, `_archive`, `_bad_data`). The pipeline automatically skips:
- Any folder whose name starts with `_`
- Any files inside folders starting with `_`

This is useful for temporarily removing problematic data without deleting it.

### File Naming Convention

Files must follow this naming pattern:

| File Type | Pattern | Examples |
|-----------|---------|----------|
| Coordinates | `coordinates_SUBID[C\|S][_N].csv` | `coordinates_NAV066.csv`, `coordinates_NAV066C.csv`, `coordinates_NAV090S_2.csv` |
| Preferences | `preferences_SUBID[C\|S][_N].csv` | `preferences_NAV066.csv`, `preferences_NAV066S.csv`, `preferences_NAV090S_2.csv` |

Where:
- `SUBID` = Subject ID (e.g., `NAV066`, `BNC21`)
- `C` or `S` = Optional run marker (Computer or Scanner)
- `_N` = Optional run number for repeat runs (e.g., `_2`, `_3`)

**Multiple runs per subject:** If a subject has multiple runs (e.g., scanner and computer), add `C` or `S` after the subject ID:

```
NAV066/
├── coordinates_NAV066C.csv   ← Computer/desktop run
├── coordinates_NAV066S.csv   ← Scanner run
├── preferences_NAV066C.csv
└── preferences_NAV066S.csv
```

**Repeat runs:** If a run was repeated, add a number suffix:

```
NAV090/
├── coordinates_NAV090S.csv     ← First scanner run
├── coordinates_NAV090S_2.csv   ← Second scanner run (repeat)
├── preferences_NAV090S.csv
└── preferences_NAV090S_2.csv
```

Note: The pipeline only processes files with "coordinates" (case-insensitive) in the filename for timing analysis. Preference files are processed separately by `run_preference_analysis.py`.

```
NAV066/
├── coordinates_NAV066C.csv   ← ✓ Processed by create_ymaze_timing.py
├── preferences_NAV066C.csv   ← ✓ Processed by run_preference_analysis.py
├── NAV066_Log.txt            ← Ignored
├── notes.docx                ← Ignored
└── .DS_Store                 ← Ignored
```

## Output Files

For each subject, the original participant number is preserved (e.g., NAV066 → `sub-066`):

**Single run:**
```
output/
├── all_outcomes.csv                    # Aggregated task outcomes (from create_ymaze_outcomes.py)
├── all_preferences.csv                 # Aggregated preferences (from run_preference_analysis.py)
│
└── sub-066/
    ├── sub-066_labeled_final.csv       # Full labeled data with trial_num column
    ├── sub-066_trial_outcomes.csv      # Trial-level outcomes (from create_ymaze_outcomes.py)
    ├── sub-066_env_outcomes.csv        # Environment-level outcomes (from create_ymaze_outcomes.py)
    ├── sub-066_task_outcomes.csv       # Task-level outcomes (from create_ymaze_outcomes.py)
    │
    ├── trial_numbers/                  # Raw trial-numbered FSL files
    │   ├── trial_1.txt                 # All 1st trials across environments
    │   ├── trial_2.txt
    │   ├── trial_3.txt
    │   ├── ...                         # (varies by participant)
    │   └── rest.txt
    │
    ├── labeled_trials/                 # Semantically labeled FSL files
    │   ├── explore.txt                 # First trial (trial_1)
    │   ├── cond1.txt                   # Conditioning trial 1
    │   ├── cond2.txt                   # Conditioning trial 2
    │   ├── cond3.txt                   # Conditioning trial 3
    │   ├── preprobe.txt                # Trial before probe
    │   ├── probe.txt                   # Probe trials
    │   └── rest.txt
    │
    └── sub-066_trajectory.png          # Trajectory visualization
```

**Multiple runs (C and S):**
```
output/
├── all_outcomes.csv                    # Aggregated across all subjects/runs
│
└── sub-066/
    ├── C/
    │   ├── sub-066_labeled_final.csv
    │   ├── sub-066_trial_outcomes.csv  # Outcome files (from create_ymaze_outcomes.py)
    │   ├── sub-066_env_outcomes.csv
    │   ├── sub-066_task_outcomes.csv
    │   ├── sub-066_trajectory.png
    │   ├── trial_numbers/
    │   │   └── ...
    │   └── labeled_trials/
    │       └── ...
    │
    └── S/
        ├── sub-066_labeled_final.csv
        ├── sub-066_trial_outcomes.csv
        ├── sub-066_env_outcomes.csv
        ├── sub-066_task_outcomes.csv
        ├── sub-066_trajectory.png
        ├── trial_numbers/
        │   └── ...
        └── labeled_trials/
            └── ...
```

### Labeled Trials Scheme

The `labeled_trials/` folder maps trial numbers to semantic labels based on position relative to the probe:

| Trial Position | Label | Description |
|----------------|-------|-------------|
| trial_1 | explore | First/exploration trial |
| max - 4 | cond1 | Conditioning trial 1 (skipped if = trial_1) |
| max - 3 | cond2 | Conditioning trial 2 |
| max - 2 | cond3 | Conditioning trial 3 |
| max - 1 | preprobe | Trial immediately before probe |
| max (last) | probe | Probe trial |

**Note:** Only COMPLETED environments (those with a probe trial) are included in `labeled_trials/`. If a participant stopped mid-environment, those trials are excluded from labeled files but remain in `trial_numbers/`.

**labeled_final.csv columns:**
| Column | Description |
|--------|-------------|
| `env` | Environment name |
| `trial` | Trial type label (np1, np2, p, etc.) |
| `trial_num` | Sequential trial number within environment (1, 2, 3...) |
| `start` | Trial start time (normalized) |
| `end` | Trial end time |
| `duration` | Trial duration |

### FSL Timing Format

Three-column format: `onset duration weight`
```
0.00 15.23 1
45.67 12.89 1
...
```

## Outcome Measures

The `create_ymaze_outcomes.py` script reads `labeled_final.csv` files and calculates behavioral outcome measures at three levels.

```bash
# Run after create_ymaze_timing.py has generated labeled_final.csv files
python create_ymaze_outcomes.py --output-dir ../output
```

### Trial-Level Outcomes (`sub-XXX_trial_outcomes.csv`)

One row per trial:

| Column | Description |
|--------|-------------|
| `subject_id` | Subject identifier |
| `environment` | Environment name |
| `trial_num` | Trial number within environment (1, 2, 3...) |
| `trial_type` | `np` (non-probe) or `p` (probe) |
| `duration` | Trial duration in seconds |
| `start_time` | Trial start time (normalized) |
| `end_time` | Trial end time |

### Environment-Level Outcomes (`sub-XXX_env_outcomes.csv`)

One row per environment:

| Column | Description |
|--------|-------------|
| `subject_id` | Subject identifier |
| `environment` | Environment name |
| `n_np_trials` | Number of non-probe trials |
| `total_time` | Total time for this environment |
| `avg_np_duration` | Average non-probe trial duration |
| `probe_duration` | Probe trial duration (if exists) |
| `has_probe` | Whether environment had a probe trial |

### Task-Level Outcomes (`sub-XXX_task_outcomes.csv`)

One row per subject/run:

| Column | Description |
|--------|-------------|
| `subject_id` | Subject identifier |
| `run_suffix` | `C`, `S`, or empty |
| `n_environments` | Number of environments processed |
| `n_complete_environments` | Environments with probe trials |
| `total_time` | Total task time |
| `total_np_trials` | Total non-probe trials across all environments |
| `total_probe_trials` | Total probe trials |
| `avg_np_per_environment` | Average non-probe trials per environment (all started envs, including incomplete) |
| `avg_np_per_complete_environment` | Average non-probe trials per environment, restricted to envs that reached the probe (trials-to-criterion) |
| `avg_env_duration` | Average environment duration |
| `avg_np_duration` | Average non-probe trial duration (across all) |
| `avg_probe_duration` | Average probe trial duration (across all) |

### Group-Level Aggregation (`all_outcomes.csv`)

Task-level outcomes aggregated across all subjects, saved to the output root directory.

## Preference Aggregation

The preference analysis script aggregates preference responses and applies classification schemes.

### Usage

```bash
# Aggregate preferences from all subjects
python run_preference_analysis.py --data-dir ../data --output-dir ../output
```

### Input Format

Preference CSV files with columns:
- `ID` - Subject identifier
- `MazeName` - Environment/maze name
- `Preference` - `Place` or `Response`

### Output (`all_preferences.csv`)

| Column | Description |
|--------|-------------|
| `subject_id` | Subject identifier |
| `n_environments` | Number of environments with preference data |
| `n_place` | Number of Place responses |
| `n_response` | Number of Response responses |
| `pct_place` | Percentage Place responses |
| `pct_response` | Percentage Response responses |
| `majority` | Classification: allocentric if >= 50% Place |
| `ego_presence` | Classification: allocentric only if 100% Place |
| `ego_exclusive` | Classification: egocentric only if 0% Place |

### Classification Schemes

| Scheme | Allocentric | Egocentric |
|--------|-------------|------------|
| Majority | >= 50% Place | < 50% Place |
| Ego_Presence | 100% Place | < 100% Place |
| Ego_Exclusive | > 0% Place | 0% Place |

## Command Line Options

### FSL Timing Generator (`create_ymaze_timing.py`)

```
usage: create_ymaze_timing.py [-h] [--data-dir PATH] [--output-dir PATH]
                               [--subject-prefix PREFIX] [--debug] [--no-plots]
                               [--verbose] [--log-file PATH]

options:
  --data-dir, -d        Path to data directory (default: ./data)
  --output-dir, -o      Path to output directory (default: ./output)
  --subject-prefix, -p  Prefix for subject IDs (default: sub)
                        Numbers are extracted from folder names:
                        NAV066 → sub-066, NAV123 → sub-123
  --debug               Save intermediate processing files
  --no-plots            Skip trajectory visualizations
  --verbose, -v         Enable verbose logging
  --log-file            Save logs to file
```

### Outcome Measures Calculator (`create_ymaze_outcomes.py`)

This script can run in two modes:
1. **Use existing files**: If `labeled_final.csv` files exist (from `create_ymaze_timing.py`), use those
2. **Process raw data**: If no labeled files found, process raw coordinate files directly from `--data-dir`

```
usage: create_ymaze_outcomes.py [-h] [--data-dir PATH] [--output-dir PATH]
                                 [--subject-prefix PREFIX] [--verbose] [--log-file PATH]

options:
  --data-dir, -d        Path to data directory with raw coordinate files
                        (used only if no labeled_final.csv files found)
  --output-dir, -o      Path to output directory (default: ./output)
  --subject-prefix, -p  Prefix for subject IDs when processing raw files (default: sub)
  --verbose, -v         Enable verbose logging
  --log-file            Save logs to file
```

### Preference Aggregation (`run_preference_analysis.py`)

```
usage: run_preference_analysis.py [-h] [--data-dir PATH] [--output-dir PATH]
                                   [--verbose] [--log-file PATH]

options:
  --data-dir, -d        Path to data directory containing preference files (default: ./data)
  --output-dir, -o      Path to output directory (default: ./output)
  --verbose, -v         Enable verbose logging
  --log-file            Save logs to file
```

## Trial Labeling Scheme

| Label | Description |
|-------|-------------|
| `np1` | First non-probe trial (always assigned to first row) |
| `np2`, `np3`, ... | Subsequent non-probe trials |
| `p` | Probe trial (last teleportation in each environment) |
| `np1end`, `np2end`, ... | End markers for non-probe trials |
| `pend` | End marker for probe trials |

## Troubleshooting

### "Data directory not found"
- Make sure you have a `data/` folder in your current directory, OR
- Specify the path explicitly: `--data-dir /your/path/to/data`

### "Output directory not found"
- Create an `output/` folder in your current directory, OR
- Specify the path explicitly: `--output-dir /your/path/to/output`

### "No coordinate file found"
- Check that files follow the naming convention: `coordinates_SUBID.csv` (e.g., `coordinates_NAV066.csv`)
- Files must contain "coordinates" (case-insensitive) in the filename
- Verify files have `.csv` extension

### "Missing required columns"
- Column names may have leading spaces (the loader handles this)
- Ensure columns exist: Environment, Cummulative_Time, X, Z

---

## Advanced Configuration

Most users won't need to change these settings, but if needed, you can edit `config.py`:

```python
@dataclass
class TeleportConfig:
    distance_threshold: float = 5.0      # Min distance to count as a teleport
    target_positions: List[Tuple[float, float]] = field(
        default_factory=lambda: [(36.52, 22.0), (0.0, -32.0)]  # Used for visualization only
    )
```

**Note:** The pipeline auto-detects start positions from the data, so `target_positions` is only used as a fallback for visualization if no teleports are found.

## Advanced Usage

### Processing a single subject programmatically

```python
from data_io import load_coordinates
from processing import detect_teleportations, label_trials, extract_timing

# Load data
df = load_coordinates("/path/to/coordinates_NAV066.csv")

# Detect teleportations
teleport_df, events = detect_teleportations(df)

# Label trials
labeled_df, summary = label_trials(teleport_df)

# Extract timing
timing = extract_timing(labeled_df)

print(f"Found {len(timing.trials)} total trials")
print(f"Max trial number: {timing.max_trial_num}")
```

### Calculating outcome measures programmatically

```python
from post import calculate_outcome_measures

# After extracting timing (see above)
outcomes = calculate_outcome_measures(timing, subject_id="sub-066")

# Access outcome data
print(f"Total trials: {len(outcomes.trial_outcomes)}")
print(f"Environments: {len(outcomes.env_outcomes)}")
print(f"Task duration: {outcomes.task_outcome.total_time:.1f}s")

# Convert to DataFrames
trial_df = outcomes.trial_outcomes_to_dataframe()
env_df = outcomes.env_outcomes_to_dataframe()
task_df = outcomes.task_outcome_to_dataframe()
```
