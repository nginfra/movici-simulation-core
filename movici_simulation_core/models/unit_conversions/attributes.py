from movici_simulation_core.core.schema import PropertySpec, DataType

Transport_TotalOutwardCargoDemandVehicles = PropertySpec(
    name="transport.total_outward_cargo_demand_vehicles", data_type=DataType(float, (), False)
)
Transport_TotalInwardCargoDemandVehicles = PropertySpec(
    name="transport.total_inward_cargo_demand_vehicles", data_type=DataType(float, (), False)
)
Transport_TotalOutwardPassengerDemandVehicles = PropertySpec(
    name="transport.total_outward_passenger_demand_vehicles", data_type=DataType(float, (), False)
)
Transport_TotalInwardPassengerDemandVehicles = PropertySpec(
    name="transport.total_inward_passenger_demand_vehicles", data_type=DataType(float, (), False)
)
Transport_TotalOutwardCargoDemand = PropertySpec(
    name="transport.total_outward_cargo_demand", data_type=DataType(float, (), False)
)
Transport_TotalInwardCargoDemand = PropertySpec(
    name="transport.total_inward_cargo_demand", data_type=DataType(float, (), False)
)
Transport_TotalOutwardPassengerDemand = PropertySpec(
    name="transport.total_outward_passenger_demand", data_type=DataType(float, (), False)
)
Transport_TotalInwardPassengerDemand = PropertySpec(
    name="transport.total_inward_passenger_demand", data_type=DataType(float, (), False)
)
Transport_PassengerVehicleFlow = PropertySpec(
    name="transport.passenger_vehicle_flow", data_type=DataType(float, (), False)
)
Transport_CargoVehicleFlow = PropertySpec(
    name="transport.cargo_vehicle_flow", data_type=DataType(float, (), False)
)
Transport_PassengerFlow = PropertySpec(
    name="transport.passenger_flow", data_type=DataType(float, (), False)
)
Transport_CargoFlow = PropertySpec(
    name="transport.cargo_flow", data_type=DataType(float, (), False)
)
