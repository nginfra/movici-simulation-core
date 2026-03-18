from movici_simulation_core.core.schema import AttributeSpec, DataType

TrafficProperties_AverageTime = AttributeSpec(
    name="transport.average_time", data_type=DataType(float, (), False)
)
Transport_VolumeToCapacityRatio = AttributeSpec(
    name="transport.volume_to_capacity_ratio", data_type=DataType(float, (), False)
)
Transport_DelayFactor = AttributeSpec(
    name="transport.delay_factor", data_type=DataType(float, (), False)
)
Transport_PassengerVehicleFlow = AttributeSpec(
    name="transport.passenger_vehicle_flow", data_type=DataType(float, (), False)
)
Transport_CargoVehicleFlow = AttributeSpec(
    name="transport.cargo_vehicle_flow", data_type=DataType(float, (), False)
)
Transport_PassengerCarUnit = AttributeSpec(
    name="transport.passenger_car_unit", data_type=DataType(float, (), False)
)
Transport_Co2Emission_Hours = AttributeSpec(
    name="transport.co2_emission.hours", data_type=DataType(float, (), False)
)
Transport_NoxEmission_Hours = AttributeSpec(
    name="transport.nox_emission.hours", data_type=DataType(float, (), False)
)
Transport_EnergyConsumption_Hours = AttributeSpec(
    name="transport.energy_consumption.hours", data_type=DataType(float, (), False)
)
Transport_PassengerDemand = AttributeSpec(
    name="transport.passenger_demand", data_type=DataType(float, (), True)
)
Transport_CargoDemand = AttributeSpec(
    name="transport.cargo_demand", data_type=DataType(float, (), True)
)
