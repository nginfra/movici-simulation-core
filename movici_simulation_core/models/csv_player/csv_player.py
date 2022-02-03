from __future__ import annotations

import typing as t

import pandas as pd

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.data_tracker.attribute import PUB, AttributeObject, UniformAttribute
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.model_connector.init_data import FileType, InitDataHandler
from movici_simulation_core.models.common.csv_tape import CsvTape
from movici_simulation_core.utils.moment import Moment


class CSVPlayer(TrackedModel, name="csv_player"):
    targets: t.Dict[str, UniformAttribute]
    publishers: t.List[Publisher]
    csv_tape: CsvTape

    def setup(
        self, state: TrackedState, schema: AttributeSchema, init_data_handler: InitDataHandler, **_
    ):
        self.csv_tape = get_csv_tape(init_data_handler, self.config["csv_tape"][0])
        self.publishers = [
            Publisher(tape=self.csv_tape, parameter=param, target=target)
            for (param, target) in zip(
                self.config["csv_parameters"],
                get_publish_attributes(self.config, state=state, schema=schema),
            )
        ]

    def update(self, moment: Moment, **_) -> t.Optional[Moment]:
        self.csv_tape.proceed_to(moment)
        self.publish()
        return self.csv_tape.get_next_timestamp()

    def publish(self):
        for publisher in self.publishers:
            publisher.publish()


class Publisher:
    def __init__(self, tape: CsvTape, parameter: str, target: AttributeObject) -> None:
        self.tape = tape
        self.parameter = parameter
        self.target = target

    def publish(self):
        self.tape.assert_parameter(self.parameter)
        self.target[:] = self.tape.get_data(self.parameter)


def get_csv_tape(data_handler: InitDataHandler, name: str) -> CsvTape:
    _, data = data_handler.ensure_ftype(name, FileType.CSV)
    csv: pd.DataFrame = pd.read_csv(data)
    tape = CsvTape()
    tape.initialize(csv)
    tape.proceed_to(Moment(0))
    return tape


def get_publish_attributes(config: dict, schema: AttributeSchema, state: TrackedState):
    dataset, entity_group = config["entity_group"][0]
    targets = config["target_attributes"]
    yield from (
        state.register_attribute(
            dataset,
            entity_group,
            schema.get_spec(target, default_data_type=DataType(float)),
            flags=PUB,
        )
        for target in targets
    )
