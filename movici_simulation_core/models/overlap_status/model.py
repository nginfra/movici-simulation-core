import typing as t

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core import DataType
from movici_simulation_core.core.attribute import OPT
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, AttributeSpec, attributes_from_dict
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.validate import ensure_valid_config

from ..common.model_util import try_get_geometry_type
from . import dataset as ds
from .overlap_status import OverlapStatus


class Model(TrackedModel, name="overlap_status"):
    """
    Implementation of the overlap status model
    """

    overlap_status: t.Union[OverlapStatus, None] = None

    def __init__(self, model_config):
        model_config = ensure_valid_config(
            model_config,
            "2",
            {
                "1": {"schema": MODEL_CONFIG_SCHEMA_LEGACY_PATH},
                "2": {"schema": MODEL_CONFIG_SCHEMA_PATH, "convert_from": {"1": convert_v1_v2}},
            },
        )
        super().__init__(model_config)

    def setup(self, state: TrackedState, schema, **_):
        self.parse_config(state, schema)

    def initialize(self, state: TrackedState) -> None:
        if not self.overlap_status.is_ready():
            raise NotReady
        self.overlap_status.resolve_connections()

    def update(self, state: TrackedState, moment: Moment):
        self.overlap_status.update()

    def parse_config(self, state: TrackedState, schema: AttributeSchema) -> None:
        config = self.config
        overlap_entity = state.register_entity_group(config["output_dataset"], ds.OverlapEntity())
        target_entities = []
        to_check_attributes = []
        for target in config["targets"]:
            ds_name, entity_name = target["entity_group"]
            geometry = target["geometry"]
            attr = target.get("status_attribute")
            target_entities.append(
                state.register_entity_group(
                    dataset_name=ds_name, entity=try_get_geometry_type(geometry)(name=entity_name)
                )
            )
            if attr is None:
                to_check_attributes.append(None)
            else:
                to_spec = schema.get_spec(attr, default_data_type=DataType(bool))
                self.ensure_uniform_attribute(ds_name, entity_name, to_spec)
                to_check_attributes.append(
                    state.register_attribute(
                        dataset_name=ds_name, entity_name=entity_name, spec=to_spec, flags=OPT
                    )
                )
        source = config["source"]
        from_ds_name, from_entity_name = source["entity_group"]
        from_geometry = try_get_geometry_type(source["geometry"])
        from_attr = source.get("status_attribute")

        from_entity = state.register_entity_group(
            dataset_name=from_ds_name, entity=from_geometry(name=from_entity_name)
        )
        if from_attr is None:
            from_check_attribute = None
        else:
            from_spec = schema.get_spec(from_attr, default_data_type=DataType(bool))
            self.ensure_uniform_attribute(from_ds_name, from_entity_name, from_spec)
            from_check_attribute = state.register_attribute(
                dataset_name=from_ds_name, entity_name=from_entity_name, spec=from_spec, flags=OPT
            )

        self.overlap_status = OverlapStatus(
            from_entity=from_entity,
            from_check_attribute=from_check_attribute,
            to_entities=target_entities,
            to_check_attributes=to_check_attributes,
            overlap_entity=overlap_entity,
            distance_threshold=config.get("distance_threshold"),
            display_name_template=config.get("display_name_template"),
        )

    @staticmethod
    def ensure_uniform_attribute(ds, entity, spec: AttributeSpec):
        if spec.data_type.py_type == str:
            raise ValueError(f"Attribute {ds}/{entity}/{spec.name} can't have string type")
        if spec.data_type.csr is True:
            raise ValueError(f"attribute {ds}/{entity}/{spec.name} should be of uniform data type")
        if len(spec.data_type.unit_shape):
            raise ValueError(f"attribute {ds}/{entity}/{spec.name} should be one-dimensional")

    @classmethod
    def get_schema_attributes(cls) -> t.Iterable[AttributeSpec]:
        return attributes_from_dict(vars(ds))


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/overlap_status.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/overlap_status.json"


def convert_v1_v2(config):
    rv = {
        "output_dataset": config["output_dataset"][0],
        "source": {
            "entity_group": config["from_entity_group"][0],
            "geometry": config["from_geometry_type"],
        },
    }
    if "from_check_status_property" in config:
        rv["source"]["status_attribute"] = config["from_check_status_property"][1]

    for key in ("distance_threshold", "display_name_template"):
        if key in config:
            rv[key] = config[key]

    targets = []
    for i in range(len(config["to_entity_groups"])):
        tgt = {
            "entity_group": config["to_entity_groups"][i],
            "geometry": config["to_geometry_types"][i],
        }
        if "to_check_status_properties" in config:
            comp_prop = config["to_check_status_properties"][i]
            attr = comp_prop if comp_prop is None else comp_prop[1]
            tgt["status_attribute"] = attr
        targets.append(tgt)
    rv["targets"] = targets

    return rv
