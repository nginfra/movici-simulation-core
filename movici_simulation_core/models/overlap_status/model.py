import typing as t

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core import DataType
from movici_simulation_core.core.schema import AttributeSchema, AttributeSpec, attributes_from_dict
from movici_simulation_core.data_tracker.attribute import OPT
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.utils.moment import Moment

from . import dataset as ds
from .overlap_status import OverlapStatus
from ..common.model_util import try_get_geometry_type


class Model(TrackedModel, name="overlap_status"):
    """
    Implementation of the overlap status model
    """

    overlap_status: t.Union[OverlapStatus, None] = None

    def setup(self, state: TrackedState, schema, **_):
        self.check_input_lengths()
        self.parse_config(state, schema)

    def check_input_lengths(self):
        config = self.config
        keys = [
            "to_entity_groups",
            "to_geometry_types",
        ]
        if "to_check_status_properties" in config:
            keys.append("to_check_status_properties")
        if any(len(config[key]) != len(config[keys[0]]) for key in keys[1:]):
            raise IndexError(f"Arrays {[key for key in keys]} must have the same lengths")

    def initialize(self, state: TrackedState) -> None:
        if not self.overlap_status.is_ready():
            raise NotReady
        self.overlap_status.resolve_connections()

    def update(self, state: TrackedState, moment: Moment):
        self.overlap_status.update()

    def parse_config(self, state: TrackedState, schema: AttributeSchema) -> None:
        config = self.config
        overlap_entity = state.register_entity_group(
            config["output_dataset"][0], ds.OverlapEntity()
        )
        to_entities = []
        to_check_attributes = []
        for (ds_name, entity_name), attr, geometry in zip(
            config["to_entity_groups"],
            config.get("to_check_status_properties", [None] * len(config["to_entity_groups"])),
            config["to_geometry_types"],
        ):
            to_entities.append(
                state.register_entity_group(
                    dataset_name=ds_name, entity=try_get_geometry_type(geometry)(name=entity_name)
                )
            )
            if attr is None or attr == (None, None):
                to_check_attributes.append(None)
            else:
                to_spec = schema.get_spec(attr, default_data_type=DataType(bool))
                self.ensure_uniform_attribute(ds_name, entity_name, to_spec)
                to_check_attributes.append(
                    state.register_attribute(
                        dataset_name=ds_name, entity_name=entity_name, spec=to_spec, flags=OPT
                    )
                )

        from_ds_name, from_entity_name = config["from_entity_group"][0]
        from_geometry = try_get_geometry_type(config["from_geometry_type"])
        from_attr = config.get("from_check_status_property")
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
            to_entities=to_entities,
            to_check_attributes=to_check_attributes,
            overlap_entity=overlap_entity,
            distance_threshold=config.get("distance_threshold"),
            display_name_template=config.get("display_name_template"),
        )

    @staticmethod
    def ensure_uniform_attribute(ds, entity, spec: AttributeSpec):
        if spec.data_type.py_type == str:
            raise ValueError(f"Attribute {ds}/{entity}/{spec.full_name} can't have string type")
        if spec.data_type.csr is True:
            raise ValueError(
                f"attribute {ds}/{entity}/{spec.full_name} should be of uniform data type"
            )
        if len(spec.data_type.unit_shape):
            raise ValueError(f"attribute {ds}/{entity}/{spec.full_name} should be one-dimensional")

    @classmethod
    def get_schema_attributes(cls) -> t.Iterable[AttributeSpec]:
        return attributes_from_dict(vars(ds))
