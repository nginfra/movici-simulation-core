from .results import (
    ResultDataset,
    ReversibleUpdate,
    SimulationResults,
    TimeProgressingState,
    UpdateStream,
    merge_updates,
)

__all__ = [
    "SimulationResults",
    "ResultDataset",
    "TimeProgressingState",
    "ReversibleUpdate",
    "UpdateStream",
    "merge_updates",
]

# SQLite support (optional - requires sqlalchemy)
try:
    from .sqlite_results import (
        SQLiteSimulationResults,
        detect_results_format,
        get_simulation_results,
    )

    __all__.extend(
        [
            SQLiteSimulationResults.__name__,
            detect_results_format.__name__,
            get_simulation_results.__name__,
        ]
    )
except ImportError:
    pass
