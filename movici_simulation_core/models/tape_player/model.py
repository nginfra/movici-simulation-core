import dataclasses
import typing as t

import msgpack
import orjson as json

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import PUB
from movici_simulation_core.core.data_format import load_from_json
from movici_simulation_core.core.moment import Moment, get_timeline_info
from movici_simulation_core.core.schema import (
    AttributeSchema,
    AttributeSpec,
    DataType,
    infer_data_type_from_array,
)
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.model_connector.init_data import FileType, InitDataHandler
from movici_simulation_core.models.common.time_series import TimeSeries
from movici_simulation_core.validate import ensure_valid_config


class Model(TrackedModel, name="tape_player"):

    timeline: t.Optional[TimeSeries[dict]] = None

    def __init__(self, model_config: dict):
        model_config = ensure_valid_config(
            model_config,
            "1",
            {
                "1": {"schema": MODEL_CONFIG_SCHEMA_PATH},
            },
        )
        super().__init__(model_config)
        self.pub_attributes: t.Set[AttributeInfo] = set()

    def setup(
        self, state: TrackedState, schema: AttributeSchema, init_data_handler: InitDataHandler, **_
    ):
        self.timeline = TimeSeries()
        tapes = self.config.get("tabular", [])
        if not isinstance(tapes, (list, tuple)):
            tapes = [tapes]
        for tape_name in tapes:
            ftype, tapefile_path = init_data_handler.get(tape_name)
            if tapefile_path is None:
                raise ValueError(f"Tapefile dataset {tape_name} not found!")
            if ftype == FileType.JSON:
                tapefile = json.loads(tapefile_path.read_bytes())
            elif ftype == FileType.MSGPACK:
                tapefile = msgpack.unpackb(tapefile_path.read_bytes())
            else:
                raise TypeError(f"Invalid data type for tabular data '{tape_name}: {ftype.name}")

            self.process_tape(tapefile, schema)

        for info in self.pub_attributes:
            state.register_attribute(info.dataset, info.entity_group, info.spec, flags=PUB)
        self.timeline.sort()

    def initialize(self, state: TrackedState):
        pass

    def process_tape(self, tapefile: dict, schema):
        data_section = tapefile["data"]
        dataset_name = data_section["tabular_data_name"]
        timeline_info = get_timeline_info()
        for seconds, json_data in zip(data_section["time_series"], data_section["data_series"]):
            timestamp = timeline_info.seconds_to_timestamp(seconds)
            numpy_data = load_from_json(
                {dataset_name: json_data}, schema, cache_inferred_attributes=True
            )

            self.timeline.append((timestamp, numpy_data))
            self.pub_attributes.update(iter_attribute_info(numpy_data, exclude=("id",)))

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        for _, upd in self.timeline.pop_until(moment.timestamp):
            state.receive_update(upd)
        return self.timeline.next_time


@dataclasses.dataclass(frozen=True)
class AttributeInfo:
    dataset: str
    entity_group: str
    name: str
    data_type: DataType

    @property
    def spec(self):
        return AttributeSpec(self.name, self.data_type)


def iter_attribute_info(data: dict, dataset=None, entity_group=None, exclude=()):
    for key, val in data.items():
        if dataset is None:
            yield from iter_attribute_info(val, dataset=key, exclude=exclude)
        elif entity_group is None:
            yield from iter_attribute_info(val, dataset, entity_group=key, exclude=exclude)
        elif key not in exclude:
            yield AttributeInfo(dataset, entity_group, key, infer_data_type_from_array(val))


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/tape_player.json"
