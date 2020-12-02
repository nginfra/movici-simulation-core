from typing import Union, List, Optional, Tuple

from model_engine import TimeStamp, Config, DataFetcher
from model_engine.base_model.base import BaseModelVDataManager
from model_engine.dataset_manager.dataset_handler import DataSet
from model_engine.model_driver.data_handlers import DataHandlerType, DType

from .time_window_status import TimeWindowStatus
from .dataset import (
    get_time_window_dataset_cls,
    get_status_dataset_cls,
)


class Model(BaseModelVDataManager):
    """
    Implementation of the time window status model
    """

    time_window_status: Union[TimeWindowStatus, None] = None
    type = "time_window_status"
    custom_variable_names = [
        "time_window_dataset",
        "status_datasets",
        "time_window_begin",
        "time_window_end",
        "time_window_status",
    ]

    def __init__(self, name: str, config: Config) -> None:
        super().__init__(name, config)
        self.parse_config(self.custom_variable_names)

    def initialize_model(self, data_fetcher: DataFetcher) -> None:
        window_dataset_name, _ = self.custom_variables.get("time_window_dataset")[0]
        status_datasets: List[DataSet] = []
        for ds_name, ds in self.datasets.items():
            if ds_name != window_dataset_name:
                status_datasets.append(ds)
        time_window_dataset: DataSet = self.datasets.get(window_dataset_name)
        self.time_window_status = TimeWindowStatus(
            time_window_dataset,
            status_datasets,
            self.logger,
            self.config.REFERENCE_TIME,
            self.config.TIME_SCALE,
        )

    def update_model(self, time_stamp: TimeStamp) -> Optional[TimeStamp]:
        return self.time_window_status.update(time_stamp)

    def parse_config(self, custom_variable_names: Optional[List[str]] = None) -> None:
        """
        Parse scenario config
        Differs from base class in that we set the data_handler_types dataset_classes on the fly
        """
        scenario_config: Config = self.config
        self.check_config_version(scenario_config)
        self.set_custom_variables(custom_variable_names)
        self.parse_status_datasets(self.custom_variables.get("status_datasets"))
        self.parse_time_window_dataset()
        self.set_filters()

    def parse_status_datasets(self, datasets: List[Tuple[str, str]]) -> None:
        self.data_handler_types = {}
        self.managed_datasets = {}
        self.netcdf_datasets = {}
        time_window_status_component, time_window_status_property = self.custom_variables.get(
            "time_window_status"
        )
        for i, (dataset_name, entity_name) in enumerate(datasets):
            self.managed_datasets[dataset_name] = dataset_name
            self.data_handler_types[dataset_name] = DataHandlerType(
                dataset_cls=get_status_dataset_cls(
                    f"StatusDataset{i}",
                    entity_name=entity_name,
                    status_property=time_window_status_property,
                    status_component=time_window_status_component,
                )
            )

    def parse_time_window_dataset(self) -> None:
        dataset_name, entity_name = self.custom_variables.get("time_window_dataset")[0]
        time_window_begin_component, time_window_begin_property = self.custom_variables.get(
            "time_window_begin"
        )
        time_window_end_component, time_window_end_property = self.custom_variables.get(
            "time_window_end"
        )
        self.managed_datasets[dataset_name] = dataset_name
        self.data_handler_types[dataset_name] = DataHandlerType(
            dataset_cls=get_time_window_dataset_cls(
                "TimeWindowDataset",
                entity_name=entity_name,
                time_window_begin_property=time_window_begin_property,
                time_window_end_property=time_window_end_property,
                time_window_begin_component=time_window_begin_component,
                time_window_end_component=time_window_end_component,
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
