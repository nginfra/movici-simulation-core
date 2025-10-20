from .results import (
    ResultDataset,
    ReversibleUpdate,
    SimulationResults,
    TimeProgressingState,
    UpdateStream,
    merge_updates,
)

# SQLite support (optional - requires sqlalchemy)
try:
    from .sqlite_results import (
        SQLiteSimulationResults,
        detect_results_format,
        get_simulation_results,
    )

    __all__ = [
        "SimulationResults",
        "ResultDataset",
        "TimeProgressingState",
        "ReversibleUpdate",
        "UpdateStream",
        "merge_updates",
        "SQLiteSimulationResults",
        "detect_results_format",
        "get_simulation_results",
    ]
except ImportError:
    # SQLite support not available (sqlalchemy not installed)
    __all__ = [
        "SimulationResults",
        "ResultDataset",
        "TimeProgressingState",
        "ReversibleUpdate",
        "UpdateStream",
        "merge_updates",
    ]
