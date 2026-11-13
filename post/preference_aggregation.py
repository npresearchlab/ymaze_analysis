"""
Preference aggregation for Y-Maze behavioral analysis.

Aggregates preference data across subjects and applies classification schemes
to determine navigation strategy (allocentric vs egocentric).

Classification schemes:
- Majority: allocentric if >= 50% Place responses, else egocentric
- Ego_Presence: allocentric only if 100% Place responses
- Ego_Exclusive: egocentric only if 0% Place responses (else allocentric)
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class PreferenceClassification:
    """Classification results for a single subject."""
    majority: str  # 'allocentric' or 'egocentric'
    ego_presence: str  # 'allocentric' or 'egocentric'
    ego_exclusive: str  # 'allocentric' or 'egocentric'


@dataclass
class SubjectPreference:
    """Aggregated preference data for a single subject."""
    subject_id: str
    n_environments: int
    n_place: int
    n_response: int
    pct_place: float
    pct_response: float
    classification: PreferenceClassification

    def to_dict(self) -> Dict:
        """Convert to dictionary for DataFrame creation."""
        return {
            'subject_id': self.subject_id,
            'n_environments': self.n_environments,
            'n_place': self.n_place,
            'n_response': self.n_response,
            'pct_place': self.pct_place,
            'pct_response': self.pct_response,
            'majority': self.classification.majority,
            'ego_presence': self.classification.ego_presence,
            'ego_exclusive': self.classification.ego_exclusive
        }


def classify_preference(pct_place: float) -> PreferenceClassification:
    """
    Apply classification schemes to a preference percentage.

    Parameters
    ----------
    pct_place : float
        Percentage of Place responses (0-100)

    Returns
    -------
    PreferenceClassification
        Classification results under all schemes

    Classification Schemes
    ----------------------
    - Majority: allocentric if >= 50% Place, else egocentric
    - Ego_Presence: allocentric only if 100% Place
    - Ego_Exclusive: egocentric only if 0% Place (else allocentric)
    """
    # Majority scheme: >= 50% Place → allocentric
    majority = 'allocentric' if pct_place >= 50 else 'egocentric'

    # Ego_Presence scheme: only 100% Place → allocentric
    ego_presence = 'allocentric' if pct_place == 100 else 'egocentric'

    # Ego_Exclusive scheme: only 0% Place → egocentric
    ego_exclusive = 'egocentric' if pct_place == 0 else 'allocentric'

    return PreferenceClassification(
        majority=majority,
        ego_presence=ego_presence,
        ego_exclusive=ego_exclusive
    )


class PreferenceAggregator:
    """
    Aggregates preference data from multiple files and subjects.

    Expected input format: CSV with columns
    - ID: Subject identifier
    - MazeName: Environment/maze name
    - Preference: 'Place' or 'Response'
    """

    def __init__(self):
        self.preferences: List[pd.DataFrame] = []

    def add_preference_file(self, filepath: Path) -> None:
        """
        Add a preference file to the aggregation.

        Parameters
        ----------
        filepath : Path
            Path to preference CSV file
        """
        try:
            df = pd.read_csv(filepath)
            df.columns = df.columns.str.strip()

            # Validate required columns
            required = ['ID', 'Preference']
            missing = [c for c in required if c not in df.columns]
            if missing:
                logger.warning(
                    f"Skipping {filepath.name}: missing columns {missing}"
                )
                return

            self.preferences.append(df)
            logger.debug(f"Added preference file: {filepath.name}")

        except Exception as e:
            logger.warning(f"Could not load {filepath}: {e}")

    def _aggregate_subject(self, subject_id: str, df: pd.DataFrame) -> SubjectPreference:
        """
        Aggregate preferences for a single subject.

        Parameters
        ----------
        subject_id : str
            Subject identifier
        df : pd.DataFrame
            DataFrame filtered to this subject

        Returns
        -------
        SubjectPreference
            Aggregated preference data
        """
        # Count preference types (strip whitespace from values)
        n_environments = len(df)
        n_place = (df['Preference'].str.strip().str.lower() == 'place').sum()
        n_response = n_environments - n_place

        # Calculate percentages
        pct_place = (n_place / n_environments * 100) if n_environments > 0 else 0
        pct_response = 100 - pct_place

        # Apply classification
        classification = classify_preference(pct_place)

        return SubjectPreference(
            subject_id=subject_id,
            n_environments=n_environments,
            n_place=n_place,
            n_response=n_response,
            pct_place=pct_place,
            pct_response=pct_response,
            classification=classification
        )

    def aggregate(self) -> List[SubjectPreference]:
        """
        Aggregate preferences across all loaded files.

        Returns
        -------
        List[SubjectPreference]
            Aggregated preferences per subject
        """
        if not self.preferences:
            logger.warning("No preference files loaded")
            return []

        # Combine all preference data
        combined = pd.concat(self.preferences, ignore_index=True)

        # Strip whitespace from ID column
        combined['ID'] = combined['ID'].astype(str).str.strip()

        # Get unique subjects
        subjects = combined['ID'].unique()

        results = []
        for subject_id in subjects:
            subject_df = combined[combined['ID'] == subject_id]
            preference = self._aggregate_subject(subject_id, subject_df)
            results.append(preference)

        # Sort by subject ID
        results.sort(key=lambda p: p.subject_id)

        logger.info(f"Aggregated preferences for {len(results)} subjects")

        return results


def aggregate_preferences(
    preference_files: List[Path]
) -> pd.DataFrame:
    """
    Convenience function to aggregate preferences from multiple files.

    Parameters
    ----------
    preference_files : List[Path]
        List of paths to preference CSV files

    Returns
    -------
    pd.DataFrame
        Aggregated preference data with classification columns:
        - subject_id: Subject identifier
        - n_environments: Number of environments with preference data
        - n_place: Number of Place responses
        - n_response: Number of Response responses
        - pct_place: Percentage Place responses
        - pct_response: Percentage Response responses
        - majority: Classification under Majority scheme
        - ego_presence: Classification under Ego_Presence scheme
        - ego_exclusive: Classification under Ego_Exclusive scheme
    """
    aggregator = PreferenceAggregator()

    for filepath in preference_files:
        aggregator.add_preference_file(filepath)

    results = aggregator.aggregate()

    if not results:
        return pd.DataFrame()

    return pd.DataFrame([r.to_dict() for r in results])


def load_and_aggregate_preferences(data_dir: Path) -> pd.DataFrame:
    """
    Discover and aggregate all preference files in a directory.

    Searches recursively for files containing "Preferences" in the name.

    Parameters
    ----------
    data_dir : Path
        Root data directory to search

    Returns
    -------
    pd.DataFrame
        Aggregated preference data
    """
    # Find all preference files
    # Skip anything inside a folder starting with "_" (_excluded, _archive, ...)
    preference_files = [f for f in data_dir.rglob("*Preferences*.csv")
                        if not any(part.startswith("_") for part in f.relative_to(data_dir).parts[:-1])]

    if not preference_files:
        logger.warning(f"No preference files found in {data_dir}")
        return pd.DataFrame()

    logger.info(f"Found {len(preference_files)} preference files")

    return aggregate_preferences(preference_files)
