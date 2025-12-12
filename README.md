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
# Clone or download the pipeline
cd behavior_analysis

# Install dependencies
pip install pandas numpy matplotlib
```

## Quick Start

```bash
# Run with default settings
python run_ymaze_analysis.py

# Specify custom paths
python run_ymaze_analysis.py --data-dir /path/to/data --output-dir /path/to/output

# Debug mode (saves intermediate files)
python run_ymaze_analysis.py --debug --verbose
```

## Project Structure

```
behavior_analysis/
├── config.py                 # Configuration settings
├── run_ymaze_analysis.py           # Main entry point
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

## Configuration

Edit `config.py` to customize settings. 
- Edit Lines 22-23 to customize data directory and output directory.

```python
@dataclass
class PathConfig:
    data_dir: Path = Path("/Volumes/YB_Drive/YB/1_data/behavior/")
    output_dir: Path = Path("/Volumes/YB_Drive/YB/2_analysis/behavior/")
```

If using the provided version of the y-maze all other parameters should be the same. The `config.py` file provides a few other ways to customize settings if original task design and parameters are changed (i.e., distance threshold, position tolerance, target positions). If needed, you may:
- Edit Line 39 for distance threshold
- Edit Line 42 for position tolerance
- Edit Lines 47-48 for target positions

```python
@dataclass
class TeleportConfig:
    distance_threshold: float = 5.0      # Min distance for teleportation
    position_tolerance: float = 1.0       # Tolerance for target matching
    target_positions: List[Tuple[float, float]] = field(
        default_factory=lambda: [(36.52, 22.0), (0.0, -32.0)]
    )
```

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

Note: you may also have other y-maze files in the subject folders --- this pipeline will ignore them, as long as they don't have the keyword "Coordinates" in them. For example, the following folder will work properly in this analysis pipeline.

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

## Usage Examples

### Basic Usage
```python
from run_ymaze_analysis import run_pipeline

# Run with defaults
report = run_pipeline()

# Check results
print(f"Processed {len(report.subjects)} subjects")
print(f"Errors: {len(report.errors)}")
```

### Custom Processing
```python
from io import load_coordinates
from processing import detect_teleportations, label_trials, extract_timing

# Load data
df = load_coordinates("/path/to/coordinates.csv")

# Detect teleportations
teleport_df, events = detect_teleportations(df)

# Label trials
labeled_df, summary = label_trials(teleport_df)

# Extract timing
timing = extract_timing(labeled_df)

print(f"Found {len(timing.probe_trials)} probe trials")
```

### Using Custom Target Positions
```python
from processing import detect_teleportations

df = load_coordinates("/path/to/coordinates.csv")

# Custom maze configuration
custom_targets = [(10.0, 20.0), (-5.0, 15.0)]

teleport_df, events = detect_teleportations(
    df,
    target_positions=custom_targets,
    distance_threshold=3.0
)
```

## Trial Labeling Scheme

| Label | Description |
|-------|-------------|
| `np1` | First non-probe trial (always assigned to first row) |
| `np2`, `np3`, ... | Subsequent non-probe trials |
| `p` | Probe trial (last teleportation in each environment) |
| `np1end`, `np2end`, ... | End markers for non-probe trials |
| `pend` | End marker for probe trials |

## Command Line Options

```
usage: run_ymaze_analysis.py [-h] [--data-dir PATH] [--output-dir PATH]
                             [--subject-prefix PREFIX] [--debug] [--no-plots]
                             [--verbose] [--log-file PATH]

options:
  --data-dir, -d        Path to data directory
  --output-dir, -o      Path to output directory
  --subject-prefix, -p  Prefix for subject IDs (default: sub)
                        Numbers are extracted from folder names:
                        NAV066 → sub-066, NAV123 → sub-123
  --debug               Save intermediate processing files
  --no-plots            Skip trajectory visualizations
  --verbose, -v         Enable verbose logging
  --log-file            Save logs to file
```

## Troubleshooting

### "No coordinate file found"
- Check that files contain "Coordinates" in the filename
- Verify files have `.csv` extension

### "Missing required columns"
- Column names may have leading spaces (the loader handles this)
- Ensure columns exist: Environment, Cummulative_Time, X, Z

### "Configuration validation failed"
- Verify data and output directories exist
- Check that target_positions is not empty

## Migration from Original Scripts

| Original File | New Location |
|--------------|--------------|
| `0_run_all_behavior.py` | `run_ymaze_analysis.py` |
| `detect_teleport.py` | `processing/teleport_detection.py` |
| `label_trials.py` | `processing/trial_labeling.py` |
| `collapse_labels.py` | `processing/timing_extraction.py` |
| `create_timing.py` | `processing/timing_extraction.py` + `io/writers.py` |
| `util.py` | `io/writers.py` |

## Contributing

When extending this pipeline:

1. Add new processing steps in `processing/`
2. Add new I/O functions in `io/`
3. Update `config.py` for new parameters
4. Include type hints and docstrings
5. Write unit tests (see `tests/` directory)
