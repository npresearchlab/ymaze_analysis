"""
Processing modules for Y-Maze behavioral analysis.
"""

from .teleport_detection import (
    TeleportDetector,
    TeleportEvent,
    detect_teleportations,
    get_teleport_summary
)

from .trial_labeling import (
    TrialLabeler,
    LabelingSummary,
    label_trials
)

from .timing_extraction import (
    TimestampExtractor,
    TimingData,
    Trial,
    extract_timing,
    trials_to_dict_list
)

__all__ = [
    # Teleport detection
    'TeleportDetector',
    'TeleportEvent', 
    'detect_teleportations',
    'get_teleport_summary',
    # Trial labeling
    'TrialLabeler',
    'LabelingSummary',
    'label_trials',
    # Timing extraction
    'TimestampExtractor',
    'TimingData',
    'Trial',
    'extract_timing',
    'trials_to_dict_list'
]
