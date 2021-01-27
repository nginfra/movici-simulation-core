from typing import Union, List, Optional, Tuple, cast

from model_engine import TimeStamp, Config, DataFetcher
from model_engine.base_model.base import BaseModelVDataManager
from model_engine.model_driver.data_handlers import DataHandlerType, DType
from .dataset import get_geometry_dataset_cls, OverlapDataset, GeometryDataset
from .overlap_status import OverlapStatus

ComponentPropertyTuple = Optional[Tuple[Optional[str], Optional[str]]]


class Model(BaseModelVDataManager):
    """
    Implementation of the time window status model
    """

    overlap_status: Union[OverlapStatus, None] = None
    type = "overlap_status"
    custom_variable_names = [
        "output_dataset",
        "from_entity_group",
        "from_geometry_type",
        "from_check_status_property",
        "to_entity_groups",
        "to_geometry_types",
        "to_check_status_properties",
        "distance_threshold",
        "display_name_template",
    ]

    def __init__(self, name: str, config: Config) -> None:
        super().__init__(name, config)
        self.data_handler_types = {}
        self.managed_datasets = {}
        self.netcdf_datasets = {}
        self.parse_config(self.custom_variable_names)

    def initialize_model(self, data_fetcher: DataFetcher) -> None:
        overlap_dataset = cast(
            OverlapDataset, self.datasets[self.custom_variables.get("output_dataset")[0]]
        )
        from_dataset = cast(
            GeometryDataset, self.datasets[self.custom_variables.get("from_entity_group")[0][0]]
        )
        to_datasets = []
        for dataset in self.custom_variables.get("to_entity_groups") or []:
            to_datasets.append(cast(GeometryDataset, self.datasets[dataset[0]]))

        self.overlap_status = OverlapStatus(
            from_dataset=from_dataset,
            to_datasets=to_datasets,
            overlap_dataset=overlap_dataset,
            logger=self.logger,
            distance_threshold=self.custom_variables.get("distance_threshold"),
            display_name_template=self.custom_variables.get("display_name_template"),
        )

    def update_model(self, time_stamp: TimeStamp) -> Optional[TimeStamp]:
        return self.overlap_status.update(time_stamp)

    def parse_config(self, custom_variable_names: Optional[List[str]] = None) -> None:
        """
        Parse scenario config
        Differs from base class in that we set the data_handler_types dataset_classes on the fly
        """
        scenario_config: Config = self.config
        self.check_config_version(scenario_config)
        self.set_custom_variables(custom_variable_names)
        self.parse_datasets(
            self.custom_variables.get("output_dataset")[0],
            self.custom_variables.get("from_entity_group")[0],
            self.custom_variables.get("from_geometry_type"),
            self.custom_variables.get("from_check_status_property"),
            self.custom_variables.get("to_entity_groups"),
            self.custom_variables.get("to_geometry_types"),
            self.custom_variables.get("to_check_status_properties"),
        )
        self.set_filters()

    def parse_datasets(
        self,
        output_dataset: str,
        from_entity_group: Tuple[str, str],
        from_geometry_type: str,
        from_check_status_property: ComponentPropertyTuple,
        to_entity_groups: List[Tuple[str, str]],
        to_geometry_types: List[str],
        to_check_status_properties: Optional[List[ComponentPropertyTuple]],
    ) -> None:
        self.data_handler_types = {output_dataset: DataHandlerType(dataset_cls=OverlapDataset)}
        self.managed_datasets = {output_dataset: output_dataset}
        self.netcdf_datasets = {}

        from_active_status_component, from_active_status_property = (
            from_check_status_property if from_check_status_property else (None, None)
        )

        self.parse_dataset(
            from_entity_group,
            from_geometry_type,
            from_active_status_component,
            from_active_status_property,
            "FromDataset",
        )

        if to_check_status_properties is None:
            to_check_status_properties = [(None, None)] * len(to_geometry_types)
        for i, elem in enumerate(to_check_status_properties):
            if elem is None:
                to_check_status_properties[i] = (None, None)

        if len(to_entity_groups) != len(to_geometry_types) or len(to_entity_groups) != len(
            to_check_status_properties
        ):
            raise IndexError(
                "Arrays to_entity_groups, to_geometry_types"
                " and to_check_status_properties must have the same lengths"
            )

        for entity_group, geometry_type, to_check_status_property in zip(
            to_entity_groups, to_geometry_types, to_check_status_properties
        ):
            self.parse_dataset(
                entity_group,
                geometry_type,
                to_check_status_property[0],
                to_check_status_property[1],
                "ToDataset",
            )

    def parse_dataset(
        self,
        entity_group: Tuple[str, str],
        geometry_type: str,
        active_status_component: Optional[str],
        active_status_property: Optional[str],
        dataset_name_prefix: str,
    ) -> None:
        dataset_name, entity_name = entity_group
        self.managed_datasets[dataset_name] = dataset_name
        self.data_handler_types[dataset_name] = DataHandlerType(
            dataset_cls=get_geometry_dataset_cls(
                f"{dataset_name_prefix}_{geometry_type}",
                entity_name=entity_name,
                geom_type=geometry_type,
                active_component=active_status_component,
                active_property=active_status_property,
            )
        )

    def read_managed_data(self, data_fetcher: DataFetcher) -> None:
        """
        Differs from base class in that we have to set the dataset_type into the dataset_cls
        """
        for dataset_name in self.managed_datasets.values():
            data_dtype, data_dict = data_fetcher.get(dataset_name)
            if data_dtype not in [DType.JSON, DType.MSGPACK]:
                raise ValueError(f"`{dataset_name}` not of type {DType.JSON} / {DType.MSGPACK}")
            dataset_cls = self.data_handler_types[dataset_name].dataset_cls
            dataset_cls.dataset_type = data_dict["type"]
            self.datasets[dataset_name] = dataset_cls(data_dict)
