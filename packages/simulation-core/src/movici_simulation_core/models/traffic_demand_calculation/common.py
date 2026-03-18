from __future__ import annotations

import logging
import typing as t
from collections import defaultdict

import numpy as np
from movici_geo_query.geo_query import GeoQuery, QueryResult
from movici_geo_query.geometry import Geometry

from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.models.common.csv_tape import CsvTape
from movici_simulation_core.settings import Settings


class DemandEstimation:
    def __init__(
        self,
        global_params: t.Sequence[GlobalContributor] = (),
        local_params: t.Sequence[LocalContributor] = (),
    ):
        self.global_params = global_params
        self.local_params = local_params

    def setup(
        self,
        *,
        state: TrackedState,
        settings: Settings,
        schema: AttributeSchema,
        logger: logging.Logger,
    ):
        for param in self.local_params:
            param.setup(state=state, settings=settings, schema=schema, logger=logger)

    def initialize(self, mapper: LocalMapper):
        for param in self.local_params:
            param.initialize(mapper)

    def update(
        self, matrix: np.ndarray, force_update: bool = False, *, moment: Moment
    ) -> np.ndarray:
        global_factor = 1
        for param in self.global_params:
            if param.has_changes():
                global_factor = param.update_factor(global_factor, moment=moment)

        for param in self.local_params:
            matrix = param.update_demand(matrix, force_update, moment=moment)

        return global_factor * matrix

    def close(self):
        for param in self.local_params:
            param.close()


class Contributor:
    pass


class GlobalContributor(Contributor):
    def __init__(self, parameter: str, csv_tape: CsvTape):
        self.parameter = parameter
        self.csv_tape = csv_tape

    def update_factor(self, factor: float, *, moment: Moment) -> float:
        raise NotImplementedError

    def get_value(self):
        return self.csv_tape[self.parameter]

    def has_changes(self):
        return self.csv_tape.has_update()


class LocalContributor(Contributor):
    def setup(
        self,
        *,
        state: TrackedState,
        settings: Settings,
        schema: AttributeSchema,
        logger: logging.Logger,
    ):
        pass

    def initialize(self, mapper: LocalMapper):
        pass

    def has_changes(self):
        raise NotImplementedError

    def update_demand(self, matrix: np.ndarray, force_update: bool = False, *, moment: Moment):
        raise NotImplementedError

    def close(self):
        pass


class LocalMapper:
    def __init__(self, demand_geometry: Geometry):
        self.geometry = demand_geometry
        self.mappings: t.Dict[EntityGroup, QueryResult] = ArgDefaultDict(
            lambda e: GeoQuery(e.get_geometry()).nearest_to(demand_geometry)
        )

    def get_nearest(self, target_entities) -> np.ndarray:
        """
        The resulting array length matches the demand entities, the values match indices in the
        target entity group
        """
        return self.mappings[target_entities].indices


class ArgDefaultDict(defaultdict):
    default_factory: t.Callable[[object], object]

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError((key,))
        self[key] = value = self.default_factory(key)
        return value
