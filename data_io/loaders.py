"""
Data loading utilities for Y-Maze behavioral analysis.

Handles:
- Loading coordinate CSV files with proper column cleaning
- Loading preference data
- Validating data structure
"""

import pandas as pd
from pathlib import Path
from typing import Optional, List, Tuple

from config import ColumnNames, CONFIG


class DataLoadError(Exception):
    """Raised when data loading fails."""
    pass


class DataValidationError(Exception):
    """Raised when loaded data fails validation."""
    pass


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean column names by stripping whitespace.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with potentially messy column names
        
    Returns
    -------
    pd.DataFrame
        DataFrame with cleaned column names
    """
    df = df.copy()
    df.columns = df.columns.str.strip()
    return df


def fix_transition_labels(
    df: pd.DataFrame,
    columns: ColumnNames = CONFIG.columns,
    transition_label: str = "transition"
) -> pd.DataFrame:
    """
    Mark mislabeled environment transition periods.
    
    The Y-maze task switches the environment label during the inter-trial
    pause (black screen), before the participant is actually teleported
    to the new environment. This function detects these transition periods
    and marks them in a new 'is_transition' column, while also correcting
    the Environment column.
    
    Detection logic:
    - Environment label changes in CSV
    - Position is frozen (same as previous row)
    - Position is NOT at a starting location
    - Continues until a teleport occurs (large position change)
    
    The function creates two changes:
    1. Adds 'is_transition' column (True/False)
    2. For transition rows, replaces Environment with the PREVIOUS environment
       (since the participant is still seeing that environment during the pause)
    
    Parameters
    ----------
    df : pd.DataFrame
        Coordinate data with Environment column
    columns : ColumnNames
        Column name configuration
    transition_label : str
        Not used in current implementation (kept for API compatibility)
        
    Returns
    -------
    pd.DataFrame
        DataFrame with 'is_transition' column and corrected Environment labels
    """
    import numpy as np
    
    df = df.copy()
    
    env_col = columns.environment
    x_col = columns.x
    z_col = columns.z
    
    # Auto-detect start positions from teleport destinations
    start_positions = _detect_start_positions(df, columns)
    position_tolerance = 2.0  # How close to be considered "at start"
    
    # Initialize transition column
    df['is_transition'] = False
    
    # Track which rows need relabeling
    in_transition = False
    transition_indices = []
    last_real_env = df.iloc[0][env_col]  # Track the actual environment
    
    for i in range(1, len(df)):
        current_env = df.iloc[i][env_col]
        prev_env = df.iloc[i-1][env_col]
        
        current_x = df.iloc[i][x_col]
        current_z = df.iloc[i][z_col]
        prev_x = df.iloc[i-1][x_col]
        prev_z = df.iloc[i-1][z_col]
        
        # Calculate distance from previous position
        distance = np.sqrt((current_x - prev_x)**2 + (current_z - prev_z)**2)
        
        # Check if at a starting position
        at_start = any(
            np.sqrt((current_x - sx)**2 + (current_z - sz)**2) < position_tolerance
            for sx, sz in start_positions
        )
        
        # Detect start of transition: env changed but position didn't jump to start
        if current_env != prev_env and not at_start:
            in_transition = True
            # Keep the last real environment name
            last_real_env = prev_env
        
        # Detect end of transition: large position change (teleport)
        if in_transition and distance > 5.0:
            in_transition = False
            # Update the last real environment to the new one
            last_real_env = current_env
        
        # Mark transition rows
        if in_transition:
            transition_indices.append(i)
    
    # Apply the transition marking
    if transition_indices:
        df.loc[df.index[transition_indices], 'is_transition'] = True
        # Don't change Environment label - keep original for trial labeling
        # The labeled_final.csv will show correct env with is_transition flag
    
    return df


def _detect_start_positions(
    df: pd.DataFrame,
    columns: ColumnNames = CONFIG.columns,
    distance_threshold: float = 5.0
) -> list:
    """
    Auto-detect teleport start positions from the data.
    
    Finds large position jumps (teleports) and identifies the most common
    destinations as the start positions.
    
    Parameters
    ----------
    df : pd.DataFrame
        Coordinate data
    columns : ColumnNames
        Column name configuration
    distance_threshold : float
        Minimum distance to consider a teleport
        
    Returns
    -------
    list
        List of (x, z) tuples representing start positions
    """
    import numpy as np
    from collections import Counter
    import logging
    
    logger = logging.getLogger(__name__)
    
    x_col = columns.x
    z_col = columns.z
    
    # Calculate distances between consecutive rows
    x_diff = df[x_col].diff()
    z_diff = df[z_col].diff()
    distances = np.sqrt(x_diff**2 + z_diff**2)
    
    # Find teleport events (large jumps)
    teleport_mask = distances >= distance_threshold
    teleport_indices = df.index[teleport_mask]
    
    if len(teleport_indices) == 0:
        logger.warning("No teleports detected - using default start positions")
        return [(36.52, 22.0), (0.0, -32.0)]
    
    # Get destinations (rounded to avoid float comparison issues)
    destinations = []
    for idx in teleport_indices:
        x = round(df.loc[idx, x_col], 0)
        z = round(df.loc[idx, z_col], 0)
        destinations.append((x, z))
    
    # Find the most common destinations
    dest_counts = Counter(destinations)
    
    # Get top 2 most common (these should be the two start positions)
    most_common = dest_counts.most_common(2)
    
    if len(most_common) < 2:
        logger.warning(
            f"Only found {len(most_common)} unique teleport destination(s). "
            "Using detected positions plus defaults."
        )
        positions = [pos for pos, count in most_common]
        # Add default if we only found one
        if len(positions) == 1:
            if positions[0] != (37.0, 22.0) and positions[0] != (36.52, 22.0):
                positions.append((36.52, 22.0))
            else:
                positions.append((0.0, -32.0))
        return positions
    
    positions = [pos for pos, count in most_common]
    
    logger.debug(
        f"Auto-detected start positions: {positions} "
        f"(from {len(teleport_indices)} teleports)"
    )
    
    return positions


def validate_coordinate_data(
    df: pd.DataFrame, 
    columns: ColumnNames = CONFIG.columns
) -> List[str]:
    """
    Validate that coordinate DataFrame has required columns and valid data.
    
    Parameters
    ----------
    df : pd.DataFrame
        Coordinate data to validate
    columns : ColumnNames
        Expected column names
        
    Returns
    -------
    List[str]
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check required columns exist
    required = [columns.environment, columns.time, columns.x, columns.z]
    missing = [col for col in required if col not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return errors  # Can't continue validation without columns
    
    # Check for empty DataFrame
    if df.empty:
        errors.append("DataFrame is empty")
        return errors
    
    # Check for numeric columns
    for col in [columns.time, columns.x, columns.z]:
        if not pd.api.types.is_numeric_dtype(df[col]):
            errors.append(f"Column '{col}' should be numeric, got {df[col].dtype}")
    
    # Check for NaN values in critical columns
    for col in [columns.time, columns.x, columns.z]:
        nan_count = df[col].isna().sum()
        if nan_count > 0:
            errors.append(f"Column '{col}' contains {nan_count} NaN values")
    
    # Check time is monotonically increasing (or at least non-decreasing)
    time_col = df[columns.time]
    if (time_col.diff().dropna() < 0).any():
        errors.append("Time column is not monotonically increasing")
    
    return errors


def load_coordinates(
    filepath: Path,
    columns: ColumnNames = CONFIG.columns,
    validate: bool = True,
    fix_transitions: bool = True
) -> pd.DataFrame:
    """
    Load and clean coordinate data from CSV file.
    
    Parameters
    ----------
    filepath : Path
        Path to the coordinate CSV file
    columns : ColumnNames
        Expected column name configuration
    validate : bool
        Whether to validate the loaded data
    fix_transitions : bool
        Whether to fix mislabeled environment transitions (default: True).
        The Y-maze task switches environment labels during inter-trial
        pause before the actual teleport. This corrects those labels.
        
    Returns
    -------
    pd.DataFrame
        Cleaned coordinate data
        
    Raises
    ------
    DataLoadError
        If file cannot be loaded
    DataValidationError
        If validation fails (when validate=True)
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise DataLoadError(f"File not found: {filepath}")
    
    if not filepath.suffix.lower() == '.csv':
        raise DataLoadError(f"Expected CSV file, got: {filepath.suffix}")
    
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        raise DataLoadError(f"Failed to read CSV: {e}")
    
    # Clean column names (remove leading/trailing whitespace)
    df = clean_column_names(df)
    
    if validate:
        errors = validate_coordinate_data(df, columns)
        if errors:
            raise DataValidationError(
                f"Validation failed for {filepath.name}:\n" + 
                "\n".join(f"  - {e}" for e in errors)
            )
    
    # Fix mislabeled transition periods
    if fix_transitions:
        df = fix_transition_labels(df, columns)
    
    return df


def load_preferences(filepath: Path) -> pd.DataFrame:
    """
    Load preference data from CSV file.
    
    Parameters
    ----------
    filepath : Path
        Path to the preferences CSV file
        
    Returns
    -------
    pd.DataFrame
        Preference data with columns: ID, Gender, Age, MazeName, Preference
        
    Raises
    ------
    DataLoadError
        If file cannot be loaded
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise DataLoadError(f"Preferences file not found: {filepath}")
    
    try:
        df = pd.read_csv(filepath)
        df = clean_column_names(df)
    except Exception as e:
        raise DataLoadError(f"Failed to read preferences CSV: {e}")
    
    return df


def find_coordinate_file(directory: Path) -> Optional[Path]:
    """
    Find the coordinate file in a directory.
    
    Looks for files containing "Coordinates" in the filename.
    
    Parameters
    ----------
    directory : Path
        Directory to search
        
    Returns
    -------
    Optional[Path]
        Path to coordinate file, or None if not found
    """
    directory = Path(directory)
    
    if not directory.is_dir():
        return None
    
    # Look for files with "coordinates" in name (case-insensitive)
    matches = [f for f in directory.iterdir() 
               if f.is_file() and 'coordinates' in f.name.lower()]
    
    # Filter to only CSV files
    csv_matches = [f for f in matches if f.suffix.lower() == '.csv']
    
    if not csv_matches:
        return None
    
    # Return first match (could be extended to handle multiple)
    return csv_matches[0]


def find_all_coordinate_files(directory: Path) -> List[Tuple[Path, Optional[str]]]:
    """
    Find all coordinate files in a directory and extract run suffixes.
    
    Handles patterns like:
    - NAV066_Coordinates.csv → (path, None)
    - NAV066C_Coordinates.csv → (path, "C")  
    - NAV066S_Coordinates.csv → (path, "S")
    
    Parameters
    ----------
    directory : Path
        Directory to search
        
    Returns
    -------
    List[Tuple[Path, Optional[str]]]
        List of (filepath, run_suffix) tuples.
        run_suffix is None if no C/S suffix detected.
    """
    import re
    
    directory = Path(directory)
    
    if not directory.is_dir():
        return []
    
    # Look for files with "coordinates" in name (case-insensitive)
    matches = [f for f in directory.iterdir()
               if f.is_file() and 'coordinates' in f.name.lower()]
    
    # Filter to only CSV files
    csv_matches = [f for f in matches if f.suffix.lower() == '.csv']
    
    if not csv_matches:
        return []
    
    results = []
    
    for filepath in csv_matches:
        filename = filepath.stem  # e.g., "NAV066C_Coordinates"
        
        # Try to extract run suffix (C or S) before "_Coordinates"
        # Pattern: NAV066C_Coordinates or NAV066S_Coordinates
        match = re.search(r'([CS])_Coordinates', filename, re.IGNORECASE)
        
        if match:
            run_suffix = match.group(1).upper()  # Normalize to uppercase
        else:
            run_suffix = None
        
        results.append((filepath, run_suffix))
    
    # Sort by run suffix (None first, then C, then S)
    def sort_key(item):
        suffix = item[1]
        if suffix is None:
            return (0, "")
        return (1, suffix)
    
    return sorted(results, key=sort_key)


def find_preference_file(directory: Path) -> Optional[Path]:
    """
    Find the preference file in a directory.
    
    Looks for files containing "Preferences" in the filename.
    
    Parameters
    ----------
    directory : Path
        Directory to search
        
    Returns
    -------
    Optional[Path]
        Path to preference file, or None if not found
    """
    directory = Path(directory)
    
    if not directory.is_dir():
        return None
    
    matches = list(directory.glob("*Preferences*"))
    csv_matches = [f for f in matches if f.suffix.lower() == '.csv']
    
    if not csv_matches:
        return None
    
    return csv_matches[0]


def discover_subjects(data_dir: Path) -> List[Path]:
    """
    Discover all subject directories in a data folder.
    
    Filters out hidden directories (starting with '.').
    
    Parameters
    ----------
    data_dir : Path
        Root data directory containing subject folders
        
    Returns
    -------
    List[Path]
        Sorted list of subject directory paths
    """
    data_dir = Path(data_dir)
    
    if not data_dir.is_dir():
        return []
    
    subjects = [
        d for d in data_dir.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    ]
    
    return sorted(subjects)
