"""
Outcome measures calculation for Y-Maze behavioral analysis.

Calculates behavioral metrics at three levels:
- Trial-level: Individual trial outcomes
- Environment-level: Aggregated outcomes per environment
- Task-level: Aggregated outcomes per subject/run

Also provides group-level aggregation across all subjects.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrialOutcome:
    """Outcome measures for a single trial."""
    subject_id: str
    environment: str
    trial_num: int
    trial_type: str  # 'np' or 'p'
    duration: float
    start_time: float
    end_time: float

    def to_dict(self) -> Dict:
        """Convert to dictionary for DataFrame creation."""
        return {
            'subject_id': self.subject_id,
            'environment': self.environment,
            'trial_num': self.trial_num,
            'trial_type': self.trial_type,
            'duration': self.duration,
            'start_time': self.start_time,
            'end_time': self.end_time
        }


@dataclass
class EnvironmentOutcome:
    """Outcome measures for a single environment."""
    subject_id: str
    environment: str
    n_np_trials: int  # Number of non-probe trials
    total_time: float
    avg_np_duration: float
    probe_duration: Optional[float]  # None if no probe
    has_probe: bool

    def to_dict(self) -> Dict:
        """Convert to dictionary for DataFrame creation."""
        return {
            'subject_id': self.subject_id,
            'environment': self.environment,
            'n_np_trials': self.n_np_trials,
            'total_time': self.total_time,
            'avg_np_duration': self.avg_np_duration,
            'probe_duration': self.probe_duration,
            'has_probe': self.has_probe
        }


@dataclass
class TaskOutcome:
    """Outcome measures for a complete task (subject/run)."""
    subject_id: str
    run_suffix: Optional[str]
    n_environments: int
    n_complete_environments: int  # Environments with probe trials
    total_time: float
    total_np_trials: int
    total_probe_trials: int
    avg_np_per_environment: float
    avg_env_duration: float
    avg_np_duration: float
    avg_probe_duration: Optional[float]  # None if no probes

    def to_dict(self) -> Dict:
        """Convert to dictionary for DataFrame creation."""
        return {
            'subject_id': self.subject_id,
            'run_suffix': self.run_suffix,
            'n_environments': self.n_environments,
            'n_complete_environments': self.n_complete_environments,
            'total_time': self.total_time,
            'total_np_trials': self.total_np_trials,
            'total_probe_trials': self.total_probe_trials,
            'avg_np_per_environment': self.avg_np_per_environment,
            'avg_env_duration': self.avg_env_duration,
            'avg_np_duration': self.avg_np_duration,
            'avg_probe_duration': self.avg_probe_duration
        }


@dataclass
class OutcomeMeasures:
    """Complete outcome measures for a subject at all levels."""
    subject_id: str
    run_suffix: Optional[str]
    trial_outcomes: List[TrialOutcome]
    env_outcomes: List[EnvironmentOutcome]
    task_outcome: TaskOutcome

    def trial_outcomes_to_dataframe(self) -> pd.DataFrame:
        """Convert trial outcomes to DataFrame."""
        if not self.trial_outcomes:
            return pd.DataFrame()
        return pd.DataFrame([t.to_dict() for t in self.trial_outcomes])

    def env_outcomes_to_dataframe(self) -> pd.DataFrame:
        """Convert environment outcomes to DataFrame."""
        if not self.env_outcomes:
            return pd.DataFrame()
        return pd.DataFrame([e.to_dict() for e in self.env_outcomes])

    def task_outcome_to_dataframe(self) -> pd.DataFrame:
        """Convert task outcome to DataFrame (single row)."""
        return pd.DataFrame([self.task_outcome.to_dict()])


class OutcomeCalculator:
    """
    Calculates outcome measures from timing data.

    Takes TimingData from the processing pipeline and computes
    behavioral metrics at trial, environment, and task levels.

    Parameters
    ----------
    subject_id : str
        Subject identifier
    run_suffix : Optional[str]
        Run identifier (e.g., "C" or "S")
    """

    def __init__(self, subject_id: str, run_suffix: Optional[str] = None):
        self.subject_id = subject_id
        self.run_suffix = run_suffix

    def _classify_trial_type(self, trial_type: str) -> str:
        """
        Classify trial type as 'np' (non-probe) or 'p' (probe).

        Parameters
        ----------
        trial_type : str
            Original trial type (e.g., 'np1', 'np2', 'p')

        Returns
        -------
        str
            Simplified type: 'np' or 'p'
        """
        if trial_type == 'p':
            return 'p'
        return 'np'

    def _calculate_trial_outcomes(self, trials) -> List[TrialOutcome]:
        """
        Calculate trial-level outcomes.

        Parameters
        ----------
        trials : List[Trial]
            Trial objects from TimingData

        Returns
        -------
        List[TrialOutcome]
            Trial-level outcome measures
        """
        outcomes = []

        for trial in trials:
            outcome = TrialOutcome(
                subject_id=self.subject_id,
                environment=trial.environment,
                trial_num=trial.trial_num,
                trial_type=self._classify_trial_type(trial.trial_type),
                duration=trial.duration,
                start_time=trial.start,
                end_time=trial.end
            )
            outcomes.append(outcome)

        return outcomes

    def _calculate_env_outcomes(
        self,
        trial_outcomes: List[TrialOutcome]
    ) -> List[EnvironmentOutcome]:
        """
        Calculate environment-level outcomes from trial outcomes.

        Parameters
        ----------
        trial_outcomes : List[TrialOutcome]
            Trial-level outcome measures

        Returns
        -------
        List[EnvironmentOutcome]
            Environment-level outcome measures
        """
        # Group trials by environment
        env_trials = defaultdict(list)
        for trial in trial_outcomes:
            env_trials[trial.environment].append(trial)

        outcomes = []

        for env, trials in env_trials.items():
            # Separate non-probe and probe trials
            np_trials = [t for t in trials if t.trial_type == 'np']
            probe_trials = [t for t in trials if t.trial_type == 'p']

            # Calculate metrics
            n_np_trials = len(np_trials)
            has_probe = len(probe_trials) > 0

            # Total time = last trial end - first trial start
            all_trials_sorted = sorted(trials, key=lambda t: t.start_time)
            total_time = (
                all_trials_sorted[-1].end_time - all_trials_sorted[0].start_time
                if all_trials_sorted else 0.0
            )

            # Average non-probe duration
            avg_np_duration = (
                np.mean([t.duration for t in np_trials])
                if np_trials else 0.0
            )

            # Probe duration
            probe_duration = (
                probe_trials[0].duration if probe_trials else None
            )

            outcome = EnvironmentOutcome(
                subject_id=self.subject_id,
                environment=env,
                n_np_trials=n_np_trials,
                total_time=total_time,
                avg_np_duration=avg_np_duration,
                probe_duration=probe_duration,
                has_probe=has_probe
            )
            outcomes.append(outcome)

        # Sort by environment name
        outcomes.sort(key=lambda o: o.environment)

        return outcomes

    def _calculate_task_outcome(
        self,
        trial_outcomes: List[TrialOutcome],
        env_outcomes: List[EnvironmentOutcome]
    ) -> TaskOutcome:
        """
        Calculate task-level outcomes from trial and environment outcomes.

        Parameters
        ----------
        trial_outcomes : List[TrialOutcome]
            Trial-level outcome measures
        env_outcomes : List[EnvironmentOutcome]
            Environment-level outcome measures

        Returns
        -------
        TaskOutcome
            Task-level outcome measures
        """
        # Count environments
        n_environments = len(env_outcomes)
        n_complete = sum(1 for e in env_outcomes if e.has_probe)

        # Total time across all trials
        if trial_outcomes:
            sorted_trials = sorted(trial_outcomes, key=lambda t: t.start_time)
            total_time = sorted_trials[-1].end_time - sorted_trials[0].start_time
        else:
            total_time = 0.0

        # Count trials
        np_trials = [t for t in trial_outcomes if t.trial_type == 'np']
        probe_trials = [t for t in trial_outcomes if t.trial_type == 'p']

        total_np_trials = len(np_trials)
        total_probe_trials = len(probe_trials)

        # Average calculations
        avg_np_per_env = (
            total_np_trials / n_environments
            if n_environments > 0 else 0.0
        )

        avg_env_duration = (
            np.mean([e.total_time for e in env_outcomes])
            if env_outcomes else 0.0
        )

        avg_np_duration = (
            np.mean([t.duration for t in np_trials])
            if np_trials else 0.0
        )

        avg_probe_duration = (
            np.mean([t.duration for t in probe_trials])
            if probe_trials else None
        )

        return TaskOutcome(
            subject_id=self.subject_id,
            run_suffix=self.run_suffix,
            n_environments=n_environments,
            n_complete_environments=n_complete,
            total_time=total_time,
            total_np_trials=total_np_trials,
            total_probe_trials=total_probe_trials,
            avg_np_per_environment=avg_np_per_env,
            avg_env_duration=avg_env_duration,
            avg_np_duration=avg_np_duration,
            avg_probe_duration=avg_probe_duration
        )

    def calculate(self, timing_data) -> OutcomeMeasures:
        """
        Calculate all outcome measures from timing data.

        Parameters
        ----------
        timing_data : TimingData
            Timing data from the processing pipeline

        Returns
        -------
        OutcomeMeasures
            Complete outcome measures at all levels
        """
        # Calculate at each level
        trial_outcomes = self._calculate_trial_outcomes(timing_data.trials)
        env_outcomes = self._calculate_env_outcomes(trial_outcomes)
        task_outcome = self._calculate_task_outcome(trial_outcomes, env_outcomes)

        logger.info(
            f"Calculated outcomes for {self.subject_id}: "
            f"{len(trial_outcomes)} trials, {len(env_outcomes)} environments"
        )

        return OutcomeMeasures(
            subject_id=self.subject_id,
            run_suffix=self.run_suffix,
            trial_outcomes=trial_outcomes,
            env_outcomes=env_outcomes,
            task_outcome=task_outcome
        )


def calculate_outcome_measures(
    timing_data,
    subject_id: str,
    run_suffix: Optional[str] = None
) -> OutcomeMeasures:
    """
    Convenience function to calculate outcome measures.

    Parameters
    ----------
    timing_data : TimingData
        Timing data from the processing pipeline
    subject_id : str
        Subject identifier
    run_suffix : Optional[str]
        Run identifier (e.g., "C" or "S")

    Returns
    -------
    OutcomeMeasures
        Complete outcome measures at all levels
    """
    calculator = OutcomeCalculator(subject_id, run_suffix)
    return calculator.calculate(timing_data)


def aggregate_task_outcomes(
    all_outcomes: List[OutcomeMeasures]
) -> pd.DataFrame:
    """
    Aggregate task-level outcomes across all subjects.

    Parameters
    ----------
    all_outcomes : List[OutcomeMeasures]
        Outcome measures from all subjects

    Returns
    -------
    pd.DataFrame
        Aggregated task-level outcomes (one row per subject/run)
    """
    if not all_outcomes:
        return pd.DataFrame()

    rows = [om.task_outcome.to_dict() for om in all_outcomes]
    df = pd.DataFrame(rows)

    # Sort by subject_id and run_suffix
    df = df.sort_values(['subject_id', 'run_suffix']).reset_index(drop=True)

    logger.info(f"Aggregated task outcomes for {len(all_outcomes)} subject/runs")

    return df
