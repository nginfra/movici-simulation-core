from typing import Type, Optional, cast

from model_engine.dataset_manager import Property
from model_engine.dataset_manager.dataset_handler import DataSet, DataEntityHandler
import model_engine.dataset_manager.property_definition as pd
from model_engine.dataset_manager.property_definition import ConnectionProperties, Reference


class TimeWindowStatusEntity(DataEntityHandler):
    entity_group_name: str = None
    init = True
    calc = True
    reference: Property = Reference(init=True)
    time_window_status: Property = None


class TimeWindowEntity(DataEntityHandler):
    entity_group_name: str = None
    init = True
    calc = False
    time_window_begin: Property = None
    time_window_end: Property = None
    time_window_status: Property = None
    connection_to_dataset = ConnectionProperties.ToDataset(init=True)
    connection_to_references = ConnectionProperties.ToReferences(init=True)


def get_status_entity_cls(
    entity_name: str,
    status_property: str,
    status_component: Optional[str] = None,
) -> Type[TimeWindowStatusEntity]:

    return cast(
        Type[TimeWindowStatusEntity],
        type(
            entity_name,
            (TimeWindowStatusEntity,),
            {
                "entity_group_name": entity_name,
                "time_window_status": get_dynamic_property(status_property, status_component)(
                    pub=True
                ),
            },
        ),
    )


def get_status_dataset_cls(
    class_name: str,
    entity_name: str,
    status_property: str,
    status_component: Optional[str] = None,
) -> Type[DataSet]:
    entity_cls = get_status_entity_cls(entity_name, status_property, status_component)

    return cast(
        Type[DataSet],
        type(
            class_name,
            (DataSet,),
            {"dataset_type": "", "data_entity_types": [entity_cls]},
        ),
    )


def get_time_window_entity_cls(
    entity_name: str,
    time_window_begin_property: str,
    time_window_end_property: str,
    time_window_begin_component: Optional[str] = None,
    time_window_end_component: Optional[str] = None,
    status_property: str = None,
    status_component: Optional[str] = None,
) -> Type[TimeWindowEntity]:

    return cast(
        Type[TimeWindowEntity],
        type(
            entity_name,
            (TimeWindowEntity,),
            {
                "entity_group_name": entity_name,
                "time_window_begin": get_dynamic_property(
                    time_window_begin_property, time_window_begin_component
                )(init=True),
                "time_window_end": get_dynamic_property(
                    time_window_end_property, time_window_end_component
                )(init=True),
                "time_window_status": get_dynamic_property(status_property, status_component)(
                    pub=True
                ),
            },
        ),
    )


def get_time_window_dataset_cls(
    class_name: str,
    entity_name: str,
    time_window_begin_property: str,
    time_window_end_property: str,
    time_window_begin_component: Optional[str] = None,
    time_window_end_component: Optional[str] = None,
    status_property: str = None,
    status_component: Optional[str] = None,
) -> Type[DataSet]:
    entity_cls = get_time_window_entity_cls(
        entity_name,
        time_window_begin_property,
        time_window_end_property,
        time_window_begin_component,
        time_window_end_component,
        status_property,
        status_component,
    )

    return cast(
        Type[DataSet],
        type(class_name, (DataSet,), {"dataset_type": "", "data_entity_types": [entity_cls]}),
    )


def get_field_name(property_name: str) -> str:
    return property_name.replace("_", " ").title().replace(" ", "").replace(".", "_")


def get_dynamic_property(
    property_name: str, component_name: Optional[str] = None
) -> Type[Property]:

    root_obj = pd
    if component_name is not None:
        root_obj = getattr(root_obj, get_field_name(component_name))

    property_class_name = get_field_name(property_name)
    return getattr(root_obj, property_class_name)
