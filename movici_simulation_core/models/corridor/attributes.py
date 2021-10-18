from movici_simulation_core.core.schema import PropertySpec, DataType

TrafficProperties_AverageTime = PropertySpec(
    name="average_time", component="traffic_properties", data_type=DataType(float, (), False)
)
Transport_VolumeToCapacityRatio = PropertySpec(
    name="transport.volume_to_capacity_ratio", data_type=DataType(float, (), False)
)
Transport_DelayFactor = PropertySpec(
    name="transport.delay_factor", data_type=DataType(float, (), False)
)
Transport_PassengerVehicleFlow = PropertySpec(
    name="transport.passenger_vehicle_flow", data_type=DataType(float, (), False)
)
Transport_CargoVehicleFlow = PropertySpec(
    name="transport.cargo_vehicle_flow", data_type=DataType(float, (), False)
)
Transport_PassengerCarUnit = PropertySpec(
    name="transport.passenger_car_unit", data_type=DataType(float, (), False)
)
Transport_Co2Emission_Hours = PropertySpec(
    name="transport.co2_emission.hours", data_type=DataType(float, (), False)
)
Transport_NoxEmission_Hours = PropertySpec(
    name="transport.nox_emission.hours", data_type=DataType(float, (), False)
)
Transport_EnergyConsumption_Hours = PropertySpec(
    name="transport.energy_consumption.hours", data_type=DataType(float, (), False)
)
Transport_PassengerDemand = PropertySpec(
    name="transport.passenger_demand", data_type=DataType(float, (), True)
)
Transport_CargoDemand = PropertySpec(
    name="transport.cargo_demand", data_type=DataType(float, (), True)
)
