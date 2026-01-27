"""
I/O utilities for Y-Maze behavioral analysis.
"""

from .loaders import (
    load_coordinates,
    load_preferences,
    load_environment_preferences,
    find_coordinate_file,
    find_all_coordinate_files,
    find_preference_file,
    find_all_preference_files,
    find_matching_preference_file,
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
    write_labeled_trial_files_by_preference,
    ensure_directory,
    ProcessingReport,
    save_outcome_measures,
    save_aggregated_outcomes,
    save_aggregated_preferences
)

__all__ = [
    # Loaders
    'load_coordinates',
    'load_preferences',
    'load_environment_preferences',
    'find_coordinate_file',
    'find_all_coordinate_files',
    'find_preference_file',
    'find_all_preference_files',
    'find_matching_preference_file',
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
    'write_labeled_trial_files_by_preference',
    'ensure_directory',
    'ProcessingReport',
    'save_outcome_measures',
    'save_aggregated_outcomes',
    'save_aggregated_preferences'
]
