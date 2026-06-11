"""Urban drainage simulation model using pyswmm/SWMM.

This model simulates urban drainage (storm water and sewer) networks using the
EPA SWMM engine through pyswmm. It performs dynamic-wave hydraulic routing and
rainfall-runoff hydrology over subcatchments.

Unlike the WNTR-backed drinking-water model (which re-runs a full simulation per
update), this model keeps a single live SWMM :class:`~pyswmm.Simulation` open
and advances it forward to each Movici moment. Control inputs (rainfall, node
inflow and regulator settings) are applied to the live simulation *before*
advancing, because SWMM marches forward and cannot rewind.

.. note::
   Internal SWMM controls (rules / curves) are not used; control logic should be
   supplied externally through the regulator ``target_setting`` and node
   ``generated_inflow`` attributes (e.g. via the Movici Rules Model).
"""

from __future__ import annotations

import dataclasses
import logging
import pathlib
import typing as t

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import PUBLISH
from movici_simulation_core.core.moment import Moment, get_timeline_info
from movici_simulation_core.core.schema import attributes_from_dict
from movici_simulation_core.core.state import TrackedState

from . import attributes
from .dataset import (
    ConduitEntity,
    JunctionEntity,
    OrificeEntity,
    OutfallEntity,
    OutletEntity,
    PumpEntity,
    RainGageEntity,
    StorageEntity,
    SubcatchmentEntity,
    UrbanDrainageNetwork,
    WeirEntity,
)
from .simulation_wrapper import SimulationWrapper

_PACKAGE_DIR = pathlib.Path(__file__).parent


def _deep_merge(a: dict, b: dict) -> dict:
    """Deep-merge two dicts. Values in *b* take precedence."""
    result = dict(a)
    for key, value in b.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Model(TrackedModel, name="urban_drainage"):
    """Urban drainage (storm/sewer) network simulation model using SWMM.

    Simulates:

    - Dynamic-wave hydraulic routing through conduits, pumps, orifices,
      weirs and outlets
    - Rainfall-runoff hydrology over subcatchments driven by rain gages
    - Junctions, outfalls and storage units as network nodes

    Per-step results (depth, head, flooding, flow, runoff, ...) are published;
    rainfall, external inflow and regulator settings may be supplied as inputs.
    """

    __model_config_schema__ = _PACKAGE_DIR / "urban_drainage.json"

    @classmethod
    def get_schema_attributes(cls):
        """Return all AttributeSpecs used by this model."""
        return attributes_from_dict(vars(attributes))

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.network = SimulationWrapper()
        self.last_calculated: Moment | None = None
        self.dataset: UrbanDrainageNetwork | None = None
        self.dataset_name = self.config["dataset"]

        # Provisional cadence from config; the authoritative value is resolved in
        # initialize() from the options merged with the dataset general section, so
        # the Movici wake cadence and the SWMM REPORT/WET/DRY steps stay in sync.
        options = self.config.get("options", {})
        self.report_timestep: int = int(options.get("report_timestep", 300))
        self.next_time = Moment(self.report_timestep)

    def setup(self, state: TrackedState, logger: logging.Logger, **kwargs):
        """Register entity groups and wire up the simulation wrapper."""
        self.network.logger = logger
        self.dataset = self._register_dataset(state, self.dataset_name)

    @staticmethod
    def _register_dataset(state: TrackedState, dataset_name: str) -> UrbanDrainageNetwork:
        """Register all entity groups as optional so empty groups don't block init."""
        return UrbanDrainageNetwork(
            junctions=state.register_entity_group(dataset_name, JunctionEntity(optional=True)),
            outfalls=state.register_entity_group(dataset_name, OutfallEntity(optional=True)),
            storage=state.register_entity_group(dataset_name, StorageEntity(optional=True)),
            conduits=state.register_entity_group(dataset_name, ConduitEntity(optional=True)),
            pumps=state.register_entity_group(dataset_name, PumpEntity(optional=True)),
            orifices=state.register_entity_group(dataset_name, OrificeEntity(optional=True)),
            weirs=state.register_entity_group(dataset_name, WeirEntity(optional=True)),
            outlets=state.register_entity_group(dataset_name, OutletEntity(optional=True)),
            subcatchments=state.register_entity_group(
                dataset_name, SubcatchmentEntity(optional=True)
            ),
            raingages=state.register_entity_group(dataset_name, RainGageEntity(optional=True)),
        )

    def _ensure_pub_attributes_initialized(self):
        """Allocate arrays for all PUBLISH attributes that received no init data.

        PUB-only attributes don't receive data during init loading, but the
        framework checks their ``.changed`` property during ``generate_update``,
        including on empty entity groups.
        """
        for f in dataclasses.fields(self.dataset):
            entity = getattr(self.dataset, f.name)
            size = len(entity)
            for attr_name in entity.attributes:
                attr = getattr(entity, attr_name)
                if attr.flags & PUBLISH and not attr.has_data():
                    attr.initialize(size)

    def _get_options(self, state: TrackedState) -> dict:
        """Merge model-config options with the dataset general section options."""
        config_options = dict(self.config.get("options", {}))
        dataset_options = dict(state.general.get(self.dataset_name, {}))
        return _deep_merge(config_options, dataset_options)

    def initialize(self, state: TrackedState):
        """Validate the network, synthesise the ``.inp`` and open the simulation."""
        if self.dataset is None:
            raise RuntimeError("Model.setup() must be called before model.initialize()")

        for f in dataclasses.fields(self.dataset):
            getattr(self.dataset, f.name).is_ready()

        self._ensure_pub_attributes_initialized()
        # Resolve the cadence from the same merged options the engine uses, so the
        # Movici re-wake cadence matches the SWMM REPORT/WET/DRY steps.
        options = self._get_options(state)
        self.report_timestep = int(options.get("report_timestep", self.report_timestep))
        self.next_time = Moment(self.report_timestep)

        # Anchor the SWMM calendar to the Movici timeline so its timestamps line up
        # with the scenario's world time (rather than an arbitrary fixed epoch).
        timeline = get_timeline_info()
        start_datetime = None
        if timeline is not None:
            start_datetime = timeline.timestamp_to_datetime(0)
            if timeline.time_scale != int(timeline.time_scale):
                self.network.logger.warning(
                    "Non-integer time_scale %s: SWMM advances in whole seconds, so "
                    "fractional Movici moments are rounded down when stepping.",
                    timeline.time_scale,
                )
        self.network.configure_options(options, start_datetime=start_datetime)
        self.network.initialize(self.dataset)

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        """Advance the live simulation to *moment* and publish the results.

        Control inputs are applied to the live simulation before advancing,
        since SWMM marches forward and cannot rewind. When updated again at a
        timestep already simulated, there is nothing to do: the (late-arriving)
        control changes are read from the arrays on the next forward step.
        """
        if self.last_calculated is not None and self.last_calculated >= moment:
            return self.next_time

        # 1. Apply control inputs to the live simulation objects
        self.network.process_changes()
        # 2. Step the live simulation forward to the requested moment (no-op at t=0)
        self.network.advance_to(int(moment.seconds))
        # 3. Publish simulation results
        self.network.write_results()

        self.last_calculated = moment
        if moment >= self.next_time:
            self.next_time = Moment(self.next_time.timestamp + self.report_timestep)
        return self.next_time

    def shutdown(self, state: TrackedState):
        """Finalise and close the simulation."""
        if self.network:
            self.network.close()
