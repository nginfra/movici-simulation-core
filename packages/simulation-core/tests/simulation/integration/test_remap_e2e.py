"""End-to-end integration test: two emitter models conflict on the same attribute, a
combiner solver helper takes ownership, the orchestrator sends REMAPs, the simulation
runs and produces the combined canonical value. See issue #127."""

from __future__ import annotations

import json

import pytest

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import PUB
from movici_simulation_core.core.moment import TimelineInfo
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.models.combiner import Combiner
from movici_simulation_core.models.data_collector.data_collector import DataCollector
from movici_simulation_core.simulation import Simulation


class _Emitter(TrackedModel):
    """A minimal TrackedModel that publishes a constant value to a single attribute on
    every update. The change tracking in TrackedState makes sure the value is only
    actually published once. Used only by the REMAP e2e test."""

    def setup(self, state: TrackedState, schema: AttributeSchema, **_):
        attribute = self.config["attribute"]
        spec = schema.get_spec(attribute["name"], default_data_type=DataType(float))
        self._attr = state.register_attribute(
            attribute["dataset"], attribute["entity_group"], spec, flags=PUB
        )
        self._value = float(self.config["value"])

    def initialize(self, state: TrackedState):
        return

    def update(self, state: TrackedState, **_):
        self._attr.array[:] = self._value
        return None


@pytest.fixture
def data_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("init_data")


@pytest.fixture
def storage_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("storage")


@pytest.fixture
def init_data(data_dir):
    payload = {
        "name": "the_dataset",
        "data": {
            "the_entities": {"id": [1, 2, 3]},
        },
    }
    data_dir.joinpath("the_dataset.json").write_text(json.dumps(payload))


def test_combiner_resolves_conflict_and_produces_canonical(data_dir, storage_dir, init_data):
    sim = Simulation(data_dir=data_dir, storage_dir=storage_dir, debug=True, distributed=False)
    sim.add_model(
        "demand_a",
        _Emitter(
            {
                "name": "demand_a",
                "type": "_emitter",
                "attribute": {
                    "dataset": "the_dataset",
                    "entity_group": "the_entities",
                    "name": "cargo_demand",
                },
                "value": 10.0,
            }
        ),
    )
    sim.add_model(
        "demand_b",
        _Emitter(
            {
                "name": "demand_b",
                "type": "_emitter",
                "attribute": {
                    "dataset": "the_dataset",
                    "entity_group": "the_entities",
                    "name": "cargo_demand",
                },
                "value": 30.0,
            }
        ),
    )
    sim.add_model(
        "combiner",
        Combiner(
            {
                "name": "combiner",
                "type": "combiner",
                "attribute": {
                    "dataset": "the_dataset",
                    "entity_group": "the_entities",
                    "name": "cargo_demand",
                },
                "method": "mean",
            }
        ),
    )
    sim.add_model("data_collector", DataCollector, {})
    sim.set_timeline_info(TimelineInfo(0, 1, 0, duration=1))
    exit_code = sim.run()
    assert exit_code == 0

    # The data collector must have written exactly one update file: the combiner's
    # canonical output. The emitters' updates are dropped entirely — the wildcard filter
    # strips their :i variants, leaving nothing to record — which also proves that no
    # internal variant leaked to the data collector.
    assert [f.name for f in sorted(storage_dir.iterdir())] == ["t0_0_the_dataset.json"]
    saved = json.loads(storage_dir.joinpath("t0_0_the_dataset.json").read_text())
    assert saved == {
        "the_dataset": {
            "the_entities": {
                "id": [1, 2, 3],
                # mean(10.0, 30.0)
                "cargo_demand": [20.0, 20.0, 20.0],
            }
        }
    }


class _BrokenCombiner(Combiner):
    """A combiner whose remap() callback raises, used to prove that a solver-helper
    failure during the REMAP round terminates the simulation. See issue #127."""

    def remap(self, payload):
        raise RuntimeError("intentional failure in remap")


def test_solver_helper_remap_failure_terminates_simulation(data_dir, storage_dir, init_data):
    # If a solver helper raises while handling its REMAP, the simulation must terminate
    # (non-zero exit) rather than hang or silently proceed with an unresolved conflict.
    # Confirmed with the issue author: a remap() failure is fatal, like any model failure.
    attribute = {
        "dataset": "the_dataset",
        "entity_group": "the_entities",
        "name": "cargo_demand",
    }
    sim = Simulation(data_dir=data_dir, storage_dir=storage_dir, debug=True, distributed=False)
    sim.add_model(
        "demand_a",
        _Emitter({"name": "demand_a", "type": "_emitter", "attribute": attribute, "value": 10.0}),
    )
    sim.add_model(
        "demand_b",
        _Emitter({"name": "demand_b", "type": "_emitter", "attribute": attribute, "value": 30.0}),
    )
    sim.add_model(
        "combiner",
        _BrokenCombiner(
            {"name": "combiner", "type": "combiner", "attribute": attribute, "method": "mean"}
        ),
    )
    sim.set_timeline_info(TimelineInfo(0, 1, 0, duration=1))
    exit_code = sim.run()
    assert exit_code != 0
