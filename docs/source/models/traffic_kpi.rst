Traffic KPI Model
=================

The Traffic KPI model calculates key performance indicators for transportation systems, including energy consumption, CO2 emissions, and NOx emissions. It uses mode-specific emission coefficients and traffic flow data to compute environmental impacts across different transport modalities (roads, railways, waterways).

Overview
--------

This model is crucial for:

- Environmental impact assessment
- Emission inventory calculations
- Energy consumption monitoring
- Sustainability reporting
- Policy impact evaluation
- Multi-modal emission comparison
- Climate change mitigation planning

The model applies vehicle-specific or mode-specific emission factors to traffic flows, accounting for different vehicle types, fuel types, and operational conditions.

Key Features
------------

- **Multi-modal support**: Roads, railways, and waterways
- **Flexible coefficients**: CSV-based emission factor management
- **Scenario modeling**: Parameter multipliers for policy scenarios
- **Vehicle differentiation**: Separate passenger and freight calculations
- **Hourly emissions**: Time-based emission rates
- **Distance-based calculations**: Per-kilometer emission factors

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "road_emissions",
        "type": "traffic_kpi",
        "dataset": "road_network",
        "modality": "roads",
        "coefficients_dataset": "emission_factors",
        "energy": "energy_consumption",
        "co2": "co2_emissions",
        "nox": "nox_emissions"
    }

Advanced Configuration
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "multimodal_kpi",
        "type": "traffic_kpi",
        "dataset": "transport_network",
        "modality": "roads",
        "coefficients_dataset": "emission_coefficients",
        "scenario_parameters_dataset": "policy_scenarios",
        "energy": "energy.consumption_kwh",
        "co2": "emissions.co2_tons",
        "nox": "emissions.nox_kg",
        "pm": "emissions.particulate_matter",
        "noise": "impact.noise_level"
    }

Configuration Schema
^^^^^^^^^^^^^^^^^^^^

.. list-table:: Configuration Parameters
   :header-rows: 1
   :widths: 20 15 15 50

   * - Parameter
     - Type
     - Required
     - Description
   * - ``dataset``
     - string
     - Yes
     - Transport network dataset
   * - ``modality``
     - string
     - Yes
     - Transport mode: "roads", "tracks", or "waterways"
   * - ``coefficients_dataset``
     - string
     - Yes
     - CSV dataset with emission coefficients
   * - ``scenario_parameters_dataset``
     - string
     - No
     - CSV dataset with scenario multipliers
   * - ``energy``
     - string
     - No
     - Output attribute for energy consumption
   * - ``co2``
     - string
     - No
     - Output attribute for CO2 emissions
   * - ``nox``
     - string
     - No
     - Output attribute for NOx emissions
   * - Additional KPIs
     - string
     - No
     - Custom output attributes for other indicators

Data Requirements
-----------------

Input Data
^^^^^^^^^^

**Transport Network:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``passenger_flow``
     - array[float]
     - Passenger vehicles or passengers per hour
   * - ``cargo_flow``
     - array[float]
     - Freight vehicles or cargo tons per hour
   * - ``segment_length``
     - array[float]
     - Length of transport segments (km)
   * - ``vehicle_type``
     - array[int]
     - Vehicle category identifier (optional)

**Coefficients Dataset (CSV):**

.. code-block:: text

    vehicle_type,fuel_type,energy_kwh_km,co2_g_km,nox_g_km,load_factor
    passenger_car,petrol,0.65,120,0.5,1.5
    passenger_car,diesel,0.55,110,0.8,1.5
    passenger_car,electric,0.20,0,0,1.5
    bus,diesel,2.5,850,12.0,40
    truck,diesel,3.2,950,15.0,15
    train,electric,15.0,0,0,500
    ship,diesel,50.0,3200,80.0,5000

**Scenario Parameters (CSV):**

.. code-block:: text

    parameter,multiplier,description
    electric_share,1.5,50% increase in electric vehicles
    efficiency_improvement,0.85,15% efficiency gain
    modal_shift,0.9,10% shift to public transport

Output Data
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - Energy consumption
     - array[float]
     - Energy use per hour (kWh/h)
   * - CO2 emissions
     - array[float]
     - CO2 emissions per hour (tons/h)
   * - NOx emissions
     - array[float]
     - NOx emissions per hour (kg/h)
   * - Total emissions
     - float
     - Network-wide emission totals

Emission Calculation Methods
-----------------------------

Road Transport
^^^^^^^^^^^^^^

.. code-block:: python

    # Per segment calculation
    energy = (passenger_flow * passenger_energy_factor + 
              cargo_flow * cargo_energy_factor) * segment_length
    
    co2 = (passenger_flow * passenger_co2_factor + 
           cargo_flow * cargo_co2_factor) * segment_length
    
    nox = (passenger_flow * passenger_nox_factor + 
           cargo_flow * cargo_nox_factor) * segment_length

Rail Transport
^^^^^^^^^^^^^^

.. code-block:: python

    # Capacity-based calculation
    train_count = max(passenger_flow / train_capacity,
                     cargo_flow / freight_capacity)
    
    energy = train_count * train_energy_factor * segment_length
    co2 = train_count * train_co2_factor * segment_length
    nox = train_count * train_nox_factor * segment_length

Waterway Transport
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Tonnage-based calculation
    vessel_count = cargo_flow / vessel_capacity
    
    energy = vessel_count * vessel_energy_factor * segment_length
    co2 = vessel_count * vessel_co2_factor * segment_length
    nox = vessel_count * vessel_nox_factor * segment_length

Examples
--------

Urban Road Network KPIs
^^^^^^^^^^^^^^^^^^^^^^^

Calculating emissions for city traffic:

.. code-block:: json

    {
        "name": "city_road_emissions",
        "type": "traffic_kpi",
        "dataset": "urban_roads",
        "modality": "roads",
        "coefficients_dataset": "urban_emission_factors",
        "energy": "hourly_energy_mwh",
        "co2": "hourly_co2_tons",
        "nox": "hourly_nox_kg",
        "pm10": "hourly_pm10_kg"
    }

**Sample Calculation:**

.. code-block:: python

    # Input data for one road segment
    segment = {
        "passenger_flow": 1000,  # vehicles/hour
        "cargo_flow": 100,       # trucks/hour
        "segment_length": 5      # km
    }
    
    # Emission factors from CSV
    factors = {
        "passenger": {"co2": 120, "nox": 0.5},  # g/km
        "cargo": {"co2": 950, "nox": 15.0}      # g/km
    }
    
    # Calculation
    co2_emissions = (1000 * 120 + 100 * 950) * 5 / 1000000  # tons/h
    # = (120000 + 95000) * 5 / 1000000
    # = 1.075 tons CO2/hour

Railway Network Assessment
^^^^^^^^^^^^^^^^^^^^^^^^^^

Environmental impact of rail transport:

.. code-block:: json

    {
        "name": "rail_environmental_kpi",
        "type": "traffic_kpi",
        "dataset": "national_rail",
        "modality": "tracks",
        "coefficients_dataset": "rail_coefficients",
        "scenario_parameters_dataset": "electrification_scenario",
        "energy": "traction_energy_mwh",
        "co2": "co2_emissions_tons"
    }

Maritime Emissions Monitoring
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Port and shipping lane emissions:

.. code-block:: json

    {
        "name": "port_emissions",
        "type": "traffic_kpi",
        "dataset": "shipping_routes",
        "modality": "waterways",
        "coefficients_dataset": "vessel_emissions",
        "energy": "fuel_consumption_tons",
        "co2": "maritime_co2",
        "nox": "maritime_nox",
        "sox": "maritime_sox"
    }

Coefficient Management
----------------------

Vehicle Categories
^^^^^^^^^^^^^^^^^^

.. list-table:: Road Vehicle Types
   :header-rows: 1
   :widths: 20 20 20 20 20

   * - Category
     - Energy (kWh/km)
     - CO2 (g/km)
     - NOx (g/km)
     - Load Factor
   * - Passenger car
     - 0.5-0.7
     - 100-150
     - 0.3-0.8
     - 1.5
   * - Electric car
     - 0.15-0.25
     - 0
     - 0
     - 1.5
   * - Bus
     - 2.0-3.0
     - 800-1000
     - 10-15
     - 40
   * - Heavy truck
     - 3.0-4.0
     - 900-1200
     - 15-20
     - 15

Scenario Multipliers
^^^^^^^^^^^^^^^^^^^^

Apply policy scenario effects:

.. code-block:: python

    # Base emissions
    base_co2 = calculate_base_emissions()
    
    # Apply scenario multipliers
    scenario_multipliers = {
        "technology_improvement": 0.85,  # 15% reduction
        "fleet_electrification": 0.70,   # 30% reduction
        "traffic_management": 0.95       # 5% reduction
    }
    
    adjusted_co2 = base_co2
    for multiplier in scenario_multipliers.values():
        adjusted_co2 *= multiplier

Performance Considerations
--------------------------

Optimization Strategies
^^^^^^^^^^^^^^^^^^^^^^^

- Pre-compute coefficient lookups
- Vectorize emission calculations
- Cache frequently used factors
- Batch process by vehicle type

Scalability
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Network Size
     - Calculation Time
     - Optimization
   * - < 1,000 segments
     - < 0.1 seconds
     - Direct calculation
   * - 1,000-10,000
     - 0.1-1 seconds
     - Vectorized operations
   * - > 10,000
     - > 1 second
     - Parallel processing

Best Practices
--------------

Coefficient Validation
^^^^^^^^^^^^^^^^^^^^^^

- Use official emission databases (HBEFA, COPERT)
- Account for local fuel quality
- Consider fleet age distribution
- Update factors regularly

Scenario Design
^^^^^^^^^^^^^^^

- Define clear baseline year
- Document assumption changes
- Consider technology trajectories
- Account for policy interactions

Results Interpretation
^^^^^^^^^^^^^^^^^^^^^^

- Report confidence intervals
- Compare with inventory data
- Validate against measurements
- Document methodology clearly

Common Issues and Troubleshooting
----------------------------------

Zero Emissions Output
^^^^^^^^^^^^^^^^^^^^^

**Issue**: All KPIs show zero values

**Solutions**:

- Verify flow data is non-zero
- Check coefficient dataset loaded
- Ensure modality matches network type
- Validate segment lengths

Unrealistic Values
^^^^^^^^^^^^^^^^^^

**Issue**: Emission values seem too high/low

**Solutions**:

- Review unit consistency (g vs kg vs tons)
- Check coefficient magnitudes
- Verify flow units (vehicles vs passengers)
- Validate load factors

Missing Coefficients
^^^^^^^^^^^^^^^^^^^^

**Issue**: Some vehicle types have no factors

**Solutions**:

- Complete coefficient CSV file
- Add default factors for unknown types
- Implement factor interpolation
- Use conservative estimates

Integration with Other Models
-----------------------------

The Traffic KPI model integrates with:

- **Traffic Assignment Model**: Provides flow data
- **Traffic Demand Model**: Links demand to emissions
- **Unit Conversions Model**: Standardizes units
- **Data Collector Model**: Stores KPI time series

Advanced Features
-----------------

Time-Varying Emissions
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def time_dependent_emissions(flow, hour_of_day):
        # Peak hour emission factors
        if 7 <= hour_of_day <= 9 or 17 <= hour_of_day <= 19:
            congestion_factor = 1.2  # 20% higher in congestion
        else:
            congestion_factor = 1.0
        
        return base_emissions * congestion_factor

Temperature Effects
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def temperature_adjusted_emissions(base_emissions, temperature):
        # Cold start penalties
        if temperature < 0:
            cold_factor = 1.3
        elif temperature < 10:
            cold_factor = 1.1
        else:
            cold_factor = 1.0
        
        return base_emissions * cold_factor

Fleet Composition
^^^^^^^^^^^^^^^^^

.. code-block:: python

    def fleet_weighted_emissions(flow, fleet_composition):
        total_emissions = 0
        for vehicle_type, percentage in fleet_composition.items():
            type_flow = flow * percentage
            type_emissions = type_flow * emission_factors[vehicle_type]
            total_emissions += type_emissions
        return total_emissions

See Also
--------

- :doc:`traffic_assignment` - For traffic flow inputs
- :doc:`traffic_demand_calculation` - For demand scenarios
- :doc:`unit_conversions` - For unit standardization
- :doc:`data_collector` - For KPI time series storage

API Reference
-------------

- :class:`movici_simulation_core.models.traffic_kpi.TrafficKPIModel`
- :mod:`movici_simulation_core.models.traffic_kpi.coefficients_tape`
- :mod:`movici_simulation_core.models.traffic_kpi.entities`