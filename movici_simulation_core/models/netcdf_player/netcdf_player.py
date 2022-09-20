from __future__ import annotations

import typing as t

import netCDF4
import numpy as np

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import PUB, AttributeObject
from movici_simulation_core.core.moment import Moment, TimelineInfo
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.model_connector.init_data import FileType, InitDataHandler
from movici_simulation_core.models.common.csv_tape import BaseTapefile
from movici_simulation_core.validate import ensure_valid_config


class NetCDFPlayer(TrackedModel, name="netcdf_player"):
    publishers: t.List[Publisher]
    netcdf_tape: NetCDFTape

    def __init__(self, model_config: dict):
        model_config = ensure_valid_config(
            model_config,
            "1",
            {
                "1": {
                    "schema": MODEL_CONFIG_SCHEMA_PATH,
                },
            },
        )
        super().__init__(model_config)

    def setup(
        self, state: TrackedState, schema: AttributeSchema, init_data_handler: InitDataHandler, **_
    ):
        self.netcdf_tape = get_netcdf_tape(init_data_handler, self.config["netcdf_tape"])
        self.publishers = [
            Publisher(
                tape=self.netcdf_tape,
                parameter=param["source"],
                target=get_publish_attribute(
                    param["target"],
                    self.config["entity_group"],
                    schema=schema,
                    state=state,
                ),
            )
            for param in self.config["attributes"]
        ]

    def update(self, moment: Moment, **_) -> t.Optional[Moment]:
        self.netcdf_tape.proceed_to(moment)
        self.publish()
        return self.netcdf_tape.get_next_timestamp()

    def publish(self):
        for publisher in self.publishers:
            publisher.publish()

    def shutdown(self, **_):
        if self.netcdf_tape:
            self.netcdf_tape.close()


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/netcdf_player.json"


class Publisher:
    def __init__(self, tape: NetCDFTape, parameter: str, target: AttributeObject) -> None:
        self.tape = tape
        self.parameter = parameter
        self.target = target

    def publish(self):
        self.tape.assert_variable(self.parameter)
        self.target[:] = self.tape.get_data(self.parameter)


def get_netcdf_tape(data_handler: InitDataHandler, name: str) -> NetCDFTape:
    _, file = data_handler.ensure_ftype(name, FileType.NETCDF)
    nc = netCDF4.Dataset(file)

    tape = NetCDFTape()
    tape.initialize(nc)
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


class NetCDFTape(BaseTapefile):
    time_var = "time"

    def __init__(self, timeline_info: t.Optional[TimelineInfo] = None) -> None:
        super().__init__(timeline_info)
        self.netcdf: t.Optional[netCDF4.Dataset] = None
        self.data: t.Dict[str, np.ndarray] = {}

    def initialize(self, netcdf: netCDF4.Dataset):
        timeline = np.asarray(netcdf.variables[self.time_var])
        self.netcdf = netcdf
        self.set_timeline(timeline)

    def assert_variable(self, var_name):
        if var_name not in self.netcdf.variables:
            raise ValueError(f"Variable {var_name} not found in supplied netcdf")

    def get_data(self, key):
        try:
            data = self.data[key]
        except KeyError:
            self.data[key] = data = self.netcdf.variables[key]

        return data[self.current_pos]

    def close(self):
        if self.netcdf:
            self.netcdf.close()
