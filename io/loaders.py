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
    validate: bool = True
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
    
    # Look for files with "Coordinates" in name
    matches = list(directory.glob("*Coordinates*"))
    
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
    
    # Look for files with "Coordinates" in name
    matches = list(directory.glob("*Coordinates*"))
    
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
