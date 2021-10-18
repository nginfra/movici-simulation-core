from __future__ import annotations

from movici_simulation_core.core.schema import (
    PropertySpec,
    DataType,
    attribute_plugin_from_dict,
)

TrafficProperties_AverageTime = PropertySpec(
    "average_time", component="traffic_properties", data_type=DataType(float)
)
Transport_MaxSpeed = PropertySpec("transport.max_speed", data_type=DataType(float, (), False))
Transport_Capacity_Hours = PropertySpec(
    "transport.capacity.hours", data_type=DataType(float, (), False)
)
Transport_Layout = PropertySpec("transport.layout", data_type=DataType(int, (4,), False))

Transport_PassengerVehicleFlow = PropertySpec(
    "transport.passenger_vehicle_flow", data_type=DataType(float)
)
Transport_CargoVehicleFlow = PropertySpec(
    "transport.cargo_vehicle_flow", data_type=DataType(float)
)
Transport_DelayFactor = PropertySpec("transport.delay_factor", data_type=DataType(float))
Transport_VolumeToCapacityRatio = PropertySpec(
    "transport.volume_to_capacity_ratio", data_type=DataType(float)
)
Transport_PassengerCarUnit = PropertySpec(
    "transport.passenger_car_unit", data_type=DataType(float)
)
Transport_PassengerDemand = PropertySpec(
    "transport.passenger_demand", data_type=DataType(float, csr=True)
)
Transport_CargoDemand = PropertySpec("transport.cargo_demand", data_type=DataType(float, csr=True))
Transport_AdditionalTime = PropertySpec("transport.additional_time", data_type=DataType(float))

CommonAttributes = attribute_plugin_from_dict(globals())
