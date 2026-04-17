"""
Post-processing utilities for Y-Maze behavioral analysis.

Provides:
- Outcome measures calculation at trial, environment, and task levels
- Preference aggregation and classification
"""

from .outcome_measures import (
    TrialOutcome,
    EnvironmentOutcome,
    TaskOutcome,
    OutcomeMeasures,
    calculate_outcome_measures,
    aggregate_task_outcomes
)

from .preference_aggregation import (
    SubjectPreference,
    PreferenceClassification,
    aggregate_preferences,
    classify_preference
)

__all__ = [
    # Outcome measures
    'TrialOutcome',
    'EnvironmentOutcome',
    'TaskOutcome',
    'OutcomeMeasures',
    'calculate_outcome_measures',
    'aggregate_task_outcomes',
    # Preference aggregation
    'SubjectPreference',
    'PreferenceClassification',
    'aggregate_preferences',
    'classify_preference'
]
