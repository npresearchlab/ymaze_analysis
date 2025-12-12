# Y-Maze Behavioral Analysis Pipeline

A Python pipeline for processing desktop Y-Maze behavioral data.

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

*Note that you may have other files in each subject folder. More information under "Expected Directory Structure" below.*
```

### 2. Run the analysis

Navigate to your project folder, and type the following into the bash terminal. 

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

### Expected Directory Structure

```
data/
├── NAV066/
│   └── NAV066_Coordinates.csv
├── NAV067/
│   └── NAV067_Coordinates.csv
└── ...
```

Note: The pipeline only processes files with "Coordinates" in the filename — all other files are ignored. For example:

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

```
output/
└── sub-066/
    ├── sub-066_labeled_final.csv   # Full labeled data
    ├── firstnp.txt                  # FSL timing: first NP before probe
    ├── lastnp.txt                   # FSL timing: last NP before probe
    ├── probe.txt                    # FSL timing: probe trials
    ├── rest.txt                     # FSL timing: rest period
    └── sub-066_trajectory.png       # Trajectory visualization
```

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
├── io/                       # Input/output utilities
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
from io import load_coordinates
from processing import detect_teleportations, label_trials, extract_timing

# Load data
df = load_coordinates("/path/to/NAV066_Coordinates.csv")

# Detect teleportations
teleport_df, events = detect_teleportations(df)

# Label trials
labeled_df, summary = label_trials(teleport_df)

# Extract timing
timing = extract_timing(labeled_df)

print(f"Found {len(timing.probe_trials)} probe trials")
```
