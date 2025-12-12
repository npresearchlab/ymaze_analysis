"""
I/O utilities for Y-Maze behavioral analysis.
"""

from .loaders import (
    load_coordinates,
    load_preferences,
    find_coordinate_file,
    find_preference_file,
    discover_subjects,
    clean_column_names,
    validate_coordinate_data,
    DataLoadError,
    DataValidationError
)

from .writers import (
    save_dataframe,
    save_labeled_data,
    write_fsl_timing_file,
    write_rest_timing_file,
    write_all_fsl_timing_files,
    ensure_directory,
    ProcessingReport
)

__all__ = [
    # Loaders
    'load_coordinates',
    'load_preferences', 
    'find_coordinate_file',
    'find_preference_file',
    'discover_subjects',
    'clean_column_names',
    'validate_coordinate_data',
    'DataLoadError',
    'DataValidationError',
    # Writers
    'save_dataframe',
    'save_labeled_data',
    'write_fsl_timing_file',
    'write_rest_timing_file',
    'write_all_fsl_timing_files',
    'ensure_directory',
    'ProcessingReport'
]
