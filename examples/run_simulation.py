import sys
import tempfile
import typing as t
from pathlib import Path

import numpy as np

from movici_simulation_core import (
    PUB,
    SUB,
    AttributeSpec,
    DataType,
    EntityInitDataFormat,
    Moment,
    Simulation,
    TimelineInfo,
    TrackedModel,
    TrackedState,
)


class DummyModel(TrackedModel):
    def __init__(self, config):
        super().__init__(config)
        self.mode = config["mode"]

    def setup(self, state: TrackedState, **_):
        mode = PUB if self.mode == "pub" else SUB
        self.attr = state.register_attribute(
            "dataset", "entity", AttributeSpec("attr", DataType(float, (), False)), flags=mode
        )

    def initialize(self, state: TrackedState):
        state.receive_update(
            {
                "dataset": {
                    "entity": {"id": {"data": np.array([1])}, "attr": {"data": np.array([0.0])}}
                }
            },
            is_initial=True,
        )

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        if self.attr.flags & PUB:
            self.attr[0] = 1.0
        else:
            (Path(tempfile.tempdir) / "test.json").write_bytes(
                EntityInitDataFormat().dumps(state.to_dict())
            )

        return None

    @classmethod
    def install(cls, sim: Simulation):
        sim.register_model_type("dummy", cls)


def setup_manually():
    sim = Simulation()

    sim.add_model("dummy_1", DummyModel({"mode": "pub"}))
    sim.add_model("dummy_2", DummyModel, {"mode": "sub"})  # defer instantiation to subprocess

    sim.set_timeline_info(TimelineInfo(reference=0, time_scale=1, start_time=0))
    return sim


def setup_from_config():
    sim = Simulation()
    sim.use(DummyModel)
    sim.configure(
        {
            "simulation_info": {
                "type": "time_oriented",
                "start_time": 0,
                "reference_time": 1,
                "duration": 1,
                "time_scale": 2,
            },
            "models": [
                {"name": "dummy_1", "type": "dummy", "mode": "sub"},
                {"name": "dummy_2", "type": "dummy", "mode": "pub"},
            ],
        }
    )
    return sim


if __name__ == "__main__":
    sim = setup_manually()
    sys.exit(sim.run())
