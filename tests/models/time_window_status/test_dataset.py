from model_engine.dataset_manager.property_definition import (
    OperationStatusProperties,
    Maintenance_WindowBegin_Date,
    Maintenance_WindowEnd_Date,
)

from movici_simulation_core.models.time_window_status.dataset import (
    get_dynamic_property,
    get_status_dataset_cls,
    get_time_window_dataset_cls,
)


class TestDynamicProperty:
    def test_can_get_property(self):
        prop = get_dynamic_property("maintenance.window_begin.date")
        assert prop == Maintenance_WindowBegin_Date

    def test_can_get_property_with_component(self):
        prop = get_dynamic_property("is_working_properly", "operation_status_properties")
        assert prop == OperationStatusProperties.IsWorkingProperly


class TestDatasetClass:
    def test_can_get_status_dataset(self):
        prop = get_status_dataset_cls(
            "TestDataset",
            entity_name="test_entity",
            status_property="is_working_properly",
            status_component="operation_status_properties",
        )
        assert isinstance(
            prop.data_entity_types_dict["test_entity"].time_window_status,
            OperationStatusProperties.IsWorkingProperly,
        )

    def test_can_get_time_window_dataset(self):
        prop = get_time_window_dataset_cls(
            "TestDataset",
            entity_name="maintenance_job_entities",
            time_window_begin_property="maintenance.window_begin.date",
            time_window_end_property="maintenance.window_end.date",
            status_property="is_working_properly",
            status_component="operation_status_properties",
        )
        assert isinstance(
            prop.data_entity_types_dict["maintenance_job_entities"].time_window_begin,
            Maintenance_WindowBegin_Date,
        )
        assert isinstance(
            prop.data_entity_types_dict["maintenance_job_entities"].time_window_end,
            Maintenance_WindowEnd_Date,
        )
