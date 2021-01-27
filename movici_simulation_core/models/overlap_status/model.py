from typing import Union, List, Optional, Tuple, cast

from model_engine import TimeStamp, Config, DataFetcher
from model_engine.base_model.base import BaseModelVDataManager
from model_engine.model_driver.data_handlers import DataHandlerType, DType
from .dataset import get_geometry_dataset_cls, OverlapDataset, GeometryDataset
from .overlap_status import OverlapStatus


class Model(BaseModelVDataManager):
    """
    Implementation of the time window status model
    """

    overlap_status: Union[OverlapStatus, None] = None
    type = "overlap_status"
    custom_variable_names = [
        "output_dataset",
        "from_dataset",
        "from_dataset_geometry",
        "to_points_datasets",
        "to_lines_datasets",
        "to_polygons_datasets",
        "check_overlapping_from",
        "check_overlapping_to",
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
            GeometryDataset, self.datasets[self.custom_variables.get("from_dataset")[0][0]]
        )
        to_datasets = []
        for datasets in ["to_points_datasets", "to_lines_datasets", "to_polygons_datasets"]:
            for dataset in self.custom_variables.get(datasets) or []:
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
            self.custom_variables.get("from_dataset")[0],
            self.custom_variables.get("from_dataset_geometry"),
            self.custom_variables.get("to_points_datasets") or [],
            self.custom_variables.get("to_lines_datasets") or [],
            self.custom_variables.get("to_polygons_datasets") or [],
        )
        self.set_filters()

    def parse_datasets(
        self,
        output_dataset: str,
        from_dataset: Tuple[str, str],
        from_dataset_geometry: str,
        to_points_datasets: List[Tuple[str, str]],
        to_lines_datasets: List[Tuple[str, str]],
        to_polygons_datasets: List[Tuple[str, str]],
    ) -> None:
        self.data_handler_types = {output_dataset: DataHandlerType(dataset_cls=OverlapDataset)}
        self.managed_datasets = {output_dataset: output_dataset}
        self.netcdf_datasets = {}

        from_component_property = self.custom_variables.get("check_overlapping_from")
        from_active_status_component, from_active_status_property = (
            from_component_property if from_component_property else (None, None)
        )

        self.parse_from_dataset(
            from_dataset,
            from_dataset_geometry,
            from_active_status_component,
            from_active_status_property,
        )

        to_component_property = self.custom_variables.get("check_overlapping_to")

        to_active_status_component, to_active_status_property = (
            to_component_property if to_component_property else (None, None)
        )
        self.parse_to_datasets(
            to_points_datasets,
            to_lines_datasets,
            to_polygons_datasets,
            to_active_status_component,
            to_active_status_property,
        )

    def parse_from_dataset(
        self,
        from_dataset: Tuple[str, str],
        from_dataset_geometry: str,
        active_status_component: Optional[str],
        active_status_property: str,
    ) -> None:
        dataset_name, entity_name = from_dataset
        self.managed_datasets[dataset_name] = dataset_name
        self.data_handler_types[dataset_name] = DataHandlerType(
            dataset_cls=get_geometry_dataset_cls(
                f"FromDataset_{from_dataset_geometry}",
                entity_name=entity_name,
                geom_type=from_dataset_geometry,
                active_component=active_status_component,
                active_property=active_status_property,
            )
        )

    def parse_to_datasets(
        self,
        to_points_datasets: List[Tuple[str, str]],
        to_lines_datasets: List[Tuple[str, str]],
        to_polygons_datasets: List[Tuple[str, str]],
        active_status_component: Optional[str],
        active_status_property: str,
    ) -> None:
        for geometry_type, datasets in [
            ("lines", to_lines_datasets),
            ("points", to_points_datasets),
            ("polygons", to_polygons_datasets),
        ]:
            for i, (dataset_name, entity_name) in enumerate(datasets):
                self.managed_datasets[dataset_name] = dataset_name
                self.data_handler_types[dataset_name] = DataHandlerType(
                    dataset_cls=get_geometry_dataset_cls(
                        f"ToDataset_{geometry_type}{i}",
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
