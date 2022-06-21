from __future__ import annotations

import typing as t

import pandas as pd

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import PUB, AttributeObject, UniformAttribute
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.model_connector.init_data import FileType, InitDataHandler
from movici_simulation_core.models.common.csv_tape import CsvTape
from movici_simulation_core.validate import ensure_valid_config


class CSVPlayer(TrackedModel, name="csv_player"):
    targets: t.Dict[str, UniformAttribute]
    publishers: t.List[Publisher]
    csv_tape: CsvTape

    def __init__(self, model_config: dict):
        model_config = ensure_valid_config(
            model_config,
            "2",
            {
                "1": {"schema": MODEL_CONFIG_SCHEMA_LEGACY_PATH},
                "2": {"schema": MODEL_CONFIG_SCHEMA_PATH, "convert_from": {"1": convert_v1_v2}},
            },
        )
        super().__init__(model_config)

    def setup(
        self, state: TrackedState, schema: AttributeSchema, init_data_handler: InitDataHandler, **_
    ):
        self.csv_tape = get_csv_tape(init_data_handler, self.config["csv_tape"])
        self.publishers = [
            Publisher(
                tape=self.csv_tape,
                parameter=param["parameter"],
                target=get_publish_attribute(
                    param["target_attribute"],
                    self.config["entity_group"],
                    schema=schema,
                    state=state,
                ),
            )
            for param in self.config["csv_parameters"]
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


def get_publish_attribute(
    attr: str, target_entity_group: t.Tuple[str, str], schema: AttributeSchema, state: TrackedState
):
    dataset, entity_group = target_entity_group
    return state.register_attribute(
        dataset,
        entity_group,
        schema.get_spec(attr, default_data_type=DataType(float)),
        flags=PUB,
    )


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/csv_player.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/csv_player.json"


def convert_v1_v2(config):
    return {
        "csv_tape": config["csv_tape"][0],
        "entity_group": config["entity_group"][0],
        "csv_parameters": [
            {
                "parameter": config["csv_parameters"][i],
                "target_attribute": config["target_attributes"][i][1],
            }
            for i in range(len(config["csv_parameters"]))
        ],
    }
