from movici_simulation_core.core.schema import AttributeSpec, DataType

Transport_TotalOutwardCargoDemandVehicles = AttributeSpec(
    name="transport.total_outward_cargo_demand_vehicles", data_type=DataType(float, (), False)
)
Transport_TotalInwardCargoDemandVehicles = AttributeSpec(
    name="transport.total_inward_cargo_demand_vehicles", data_type=DataType(float, (), False)
)
Transport_TotalOutwardPassengerDemandVehicles = AttributeSpec(
    name="transport.total_outward_passenger_demand_vehicles", data_type=DataType(float, (), False)
)
Transport_TotalInwardPassengerDemandVehicles = AttributeSpec(
    name="transport.total_inward_passenger_demand_vehicles", data_type=DataType(float, (), False)
)
Transport_TotalOutwardCargoDemand = AttributeSpec(
    name="transport.total_outward_cargo_demand", data_type=DataType(float, (), False)
)
Transport_TotalInwardCargoDemand = AttributeSpec(
    name="transport.total_inward_cargo_demand", data_type=DataType(float, (), False)
)
Transport_TotalOutwardPassengerDemand = AttributeSpec(
    name="transport.total_outward_passenger_demand", data_type=DataType(float, (), False)
)
Transport_TotalInwardPassengerDemand = AttributeSpec(
    name="transport.total_inward_passenger_demand", data_type=DataType(float, (), False)
)
Transport_PassengerVehicleFlow = AttributeSpec(
    name="transport.passenger_vehicle_flow", data_type=DataType(float, (), False)
)
Transport_CargoVehicleFlow = AttributeSpec(
    name="transport.cargo_vehicle_flow", data_type=DataType(float, (), False)
)
Transport_PassengerFlow = AttributeSpec(
    name="transport.passenger_flow", data_type=DataType(float, (), False)
)
Transport_CargoFlow = AttributeSpec(
    name="transport.cargo_flow", data_type=DataType(float, (), False)
)
