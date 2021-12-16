from __future__ import annotations

from movici_simulation_core.core.schema import (
    AttributeSpec,
    DataType,
    attribute_plugin_from_dict,
)

TrafficProperties_AverageTime = AttributeSpec(
    "average_time", component="traffic_properties", data_type=DataType(float)
)
Transport_MaxSpeed = AttributeSpec("transport.max_speed", data_type=DataType(float, (), False))
Transport_Capacity_Hours = AttributeSpec(
    "transport.capacity.hours", data_type=DataType(float, (), False)
)
Transport_Layout = AttributeSpec("transport.layout", data_type=DataType(int, (4,), False))

Transport_PassengerVehicleFlow = AttributeSpec(
    "transport.passenger_vehicle_flow", data_type=DataType(float)
)
Transport_CargoVehicleFlow = AttributeSpec(
    "transport.cargo_vehicle_flow", data_type=DataType(float)
)
Transport_DelayFactor = AttributeSpec("transport.delay_factor", data_type=DataType(float))
Transport_VolumeToCapacityRatio = AttributeSpec(
    "transport.volume_to_capacity_ratio", data_type=DataType(float)
)
Transport_PassengerCarUnit = AttributeSpec(
    "transport.passenger_car_unit", data_type=DataType(float)
)
Transport_PassengerDemand = AttributeSpec(
    "transport.passenger_demand", data_type=DataType(float, csr=True)
)
Transport_CargoDemand = AttributeSpec(
    "transport.cargo_demand", data_type=DataType(float, csr=True)
)
Transport_AdditionalTime = AttributeSpec("transport.additional_time", data_type=DataType(float))

CommonAttributes = attribute_plugin_from_dict(globals())
