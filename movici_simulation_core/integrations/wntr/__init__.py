"""WNTR integration for Movici water network simulation.

This package provides the interface between Movici's entity-based data model
and WNTR's water network simulation engine. Controls are handled externally
by the Movici Rules Model rather than internally by WNTR.
"""

from .collections import (
    JunctionCollection,
    PipeCollection,
    PumpCollection,
    ReservoirCollection,
    SimulationResults,
    TankCollection,
    ValveCollection,
)
from .id_mapper import IdMapper
from .network_wrapper import NetworkWrapper
from .pattern_manager import PatternManager

__all__ = [
    "NetworkWrapper",
    "IdMapper",
    "PatternManager",
    "JunctionCollection",
    "TankCollection",
    "ReservoirCollection",
    "PipeCollection",
    "PumpCollection",
    "ValveCollection",
    "SimulationResults",
]
