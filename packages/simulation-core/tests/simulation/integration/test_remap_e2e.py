"""End-to-end integration test: two emitter models conflict on the same attribute, a
combiner solver helper takes ownership, the orchestrator sends REMAPs, the simulation
runs and produces the combined canonical value. See issue #127."""

from __future__ import annotations

import json
import logging

import pytest

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import PUB
from movici_simulation_core.core.moment import TimelineInfo
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.models.combiner import Combiner
from movici_simulation_core.models.data_collector.data_collector import DataCollector
from movici_simulation_core.simulation import Simulation
from movici_simulation_core.testing.helpers import list_dir


class _Emitter(TrackedModel):
    """A minimal TrackedModel that publishes a constant value to a single attribute on
    every update. Used only by the REMAP e2e test."""

    def setup(self, state: TrackedState, schema: AttributeSchema, **_):
        attribute = self.config["attribute"]
        spec = schema.get_spec(attribute["name"], default_data_type=DataType(float))
        self._attr = state.register_attribute(
            attribute["dataset"], attribute["entity_group"], spec, flags=PUB
        )
        self._value = float(self.config["value"])
        self._emitted = False

    def initialize(self, state: TrackedState):
        return

    def update(self, state: TrackedState, **_):
        if self._emitted:
            return None
        self._attr.array[:] = self._value
        self._emitted = True
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

    # Look at what the data collector wrote. We expect:
    # (a) at least one snapshot of cargo_demand under the canonical name
    # (b) NO :i-suffixed attribute names in the saved output (wildcard filter skips them)
    saved_files = list_dir(storage_dir)
    assert saved_files, "data collector wrote nothing"
    saved = [
        json.loads(storage_dir.joinpath(name).read_text())
        for name in saved_files
        if name.endswith(".json")
    ]
    flattened_attrs: set[str] = set()
    for snapshot in saved:
        if not isinstance(snapshot, dict):
            continue
        for entity_groups in snapshot.values():
            if not isinstance(entity_groups, dict):
                continue
            for attrs in entity_groups.values():
                if isinstance(attrs, dict):
                    flattened_attrs.update(attrs.keys())
    assert "cargo_demand" in flattened_attrs
    assert not any(name.endswith(":i") for name in flattened_attrs), (
        f"internal :i variants leaked to data collector: {flattened_attrs}"
    )

    # Verify the mean was actually computed (10.0 + 30.0) / 2 = 20.0.
    found_combined = False
    for snapshot in saved:
        if not isinstance(snapshot, dict):
            continue
        eg = (snapshot.get("the_dataset") or {}).get("the_entities") or {}
        if "cargo_demand" not in eg:
            continue
        values = eg["cargo_demand"]
        # The DataCollector's snapshot may serialise as {"data": [...]} or as a bare list.
        if isinstance(values, dict):
            values = values.get("data", [])
        if values and all(abs(v - 20.0) < 1e-9 for v in values):
            found_combined = True
            break
    assert found_combined, f"expected mean(10, 30) == 20.0 in canonical output, saw: {saved}"

    # Suppress an "unused" warning on the logger import — kept available in case the test
    # is extended to assert on orchestrator log lines.
    logging.getLogger("movici").debug("REMAP e2e test completed")
