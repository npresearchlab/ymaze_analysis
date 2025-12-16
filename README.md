# Y-Maze Behavioral Analysis Pipeline

A Python pipeline for processing Y-Maze behavioral data from Unity experiments.

## Overview

This pipeline processes coordinate data collected during Y-Maze tasks to:

1. **Detect teleportation events** - Identify when participants are teleported back to starting positions
2. **Label trials** - Categorize events as probe (p) or non-probe (np1, np2, etc.)
3. **Extract timing** - Calculate trial onset times and durations
4. **Generate FSL files** - Create timing files for neuroimaging analysis

## Installation

```bash
# Install dependencies
pip install pandas numpy matplotlib
```

## Quick Start

### 1. Set up your folder structure

```
your_project/
├── data/                        ← Put your raw data here
│   ├── NAV066/
│   │   └── NAV066_Coordinates.csv
│   ├── NAV067/
│   │   └── NAV067_Coordinates.csv
│   └── ...
├── output/                      ← Results will go here (create this folder)
└── run_ymaze_analysis.py        ← The analysis script
```

### 2. Run the analysis

```bash
# If your data is in ./data and you want output in ./output:
python run_ymaze_analysis.py

# Or specify custom paths:
python run_ymaze_analysis.py --data-dir /path/to/data --output-dir /path/to/output
```

That's it! The script will process all participants and generate FSL timing files.

## Input Data Format

### Coordinate Files

CSV files with columns (note: original files may have leading spaces):
- `Environment` - Environment identifier
- `Cummulative_Time` - Timestamp
- `X` - X coordinate
- `Z` - Z coordinate
- `Rotation` - Rotation angle

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
│   └── NAV066_Coordinates.csv
├── NAV067/
│   └── NAV067_Coordinates.csv
└── ...
```

**Multiple runs per subject:** If a subject has multiple coordinate files (e.g., scanner and computer runs), place them in the same folder with `C` or `S` suffixes:

```
NAV066/
├── NAV066C_Coordinates.csv   ← Computer/desktop run
├── NAV066S_Coordinates.csv   ← Scanner run
```

Note: The pipeline only processes files with "Coordinates" in the filename — all other files are ignored:

```
NAV066/
├── NAV066_Coordinates.csv    ← ✓ Processed
├── NAV066_Preferences.csv    ← Ignored
├── NAV066_Log.txt            ← Ignored
├── notes.docx                ← Ignored
└── .DS_Store                 ← Ignored
```

## Output Files

For each subject, the original participant number is preserved (e.g., NAV066 → `sub-066`):

**Single run:**
```
output/
└── sub-066/
    ├── sub-066_labeled_final.csv      # Full labeled data with trial_num column
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
└── sub-066/
    ├── sub-066_C_labeled_final.csv
    ├── sub-066_S_labeled_final.csv
    │
    ├── trial_numbers/
    │   ├── trial_1_C.txt
    │   ├── trial_1_S.txt
    │   ├── ... (etc.)
    │   ├── rest_C.txt
    │   └── rest_S.txt
    │
    ├── labeled_trials/
    │   ├── explore_C.txt
    │   ├── explore_S.txt
    │   ├── ... (etc.)
    │   ├── rest_C.txt
    │   └── rest_S.txt
    │
    ├── sub-066_C_trajectory.png
    └── sub-066_S_trajectory.png
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

## Command Line Options

```
usage: run_ymaze_analysis.py [-h] [--data-dir PATH] [--output-dir PATH]
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
- Check that files contain "Coordinates" in the filename
- Verify files have `.csv` extension

### "Missing required columns"
- Column names may have leading spaces (the loader handles this)
- Ensure columns exist: Environment, Cummulative_Time, X, Z

---

## Project Structure

```
behavior_analysis/
├── config.py                 # Configuration settings
├── run_ymaze_analysis.py     # Main entry point
│
├── data_io/                  # Input/output utilities
│   ├── __init__.py
│   ├── loaders.py           # CSV loading & validation
│   └── writers.py           # Saving results & FSL files
│
├── processing/               # Core analysis modules
│   ├── __init__.py
│   ├── teleport_detection.py # Teleport event detection
│   ├── trial_labeling.py     # Trial type labeling
│   └── timing_extraction.py  # Timestamp extraction
│
└── visualization/            # Plotting utilities
    ├── __init__.py
    └── trajectory_plots.py   # Trajectory visualization
```

## Advanced Configuration

Most users won't need to change these settings, but if you're using a different maze configuration, you can edit `config.py`:

```python
@dataclass
class TeleportConfig:
    distance_threshold: float = 5.0      # Min distance for teleportation detection
    position_tolerance: float = 1.0       # Tolerance for target position matching
    target_positions: List[Tuple[float, float]] = field(
        default_factory=lambda: [(36.52, 22.0), (0.0, -32.0)]  # Y-maze start positions
    )
```

## Advanced Usage

### Processing a single subject programmatically

```python
from data_io import load_coordinates
from processing import detect_teleportations, label_trials, extract_timing

# Load data
df = load_coordinates("/path/to/NAV066_Coordinates.csv")

# Detect teleportations
teleport_df, events = detect_teleportations(df)

# Label trials
labeled_df, summary = label_trials(teleport_df)

# Extract timing
timing = extract_timing(labeled_df)

print(f"Found {len(timing.trials)} total trials")
print(f"Max trial number: {timing.max_trial_num}")
```
