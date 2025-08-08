Unit Conversions Model
======================

The Unit Conversions model transforms vehicle flow and origin-destination (OD) data into passenger and cargo quantities using modal-specific conversion coefficients. It standardizes different measurement units across transportation systems and converts between vehicle counts, passenger numbers, and cargo tonnages.

Overview
--------

This model is essential for:

- Converting vehicle flows to passenger/cargo volumes
- Standardizing measurement units across modes
- Capacity planning and analysis
- Multi-modal comparison
- Load factor calculations
- Transportation demand quantification
- Infrastructure sizing

The model uses CSV-based coefficient tables to handle different vehicle types, load factors, and modal characteristics.

Key Features
------------

- **Multi-modal support**: Roads and waterways conversions
- **Flexible coefficients**: CSV-based conversion parameters
- **OD and flow data**: Handles both origin-destination matrices and flow data
- **Vehicle differentiation**: Separate passenger and cargo coefficients
- **Load factor modeling**: Capacity utilization considerations
- **Batch processing**: Efficient handling of large datasets

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "vehicle_to_passengers",
        "type": "unit_conversions",
        "conversions": [
            {
                "conversion_type": "flow",
                "source_dataset": "traffic_flows",
                "source_entity_group": "road_segments",
                "source_property": "vehicle_count",
                "target_property": "passenger_count"
            }
        ],
        "parameters_dataset": "conversion_coefficients"
    }

Advanced Configuration
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "multimodal_conversions",
        "type": "unit_conversions",
        "conversions": [
            {
                "conversion_type": "flow",
                "modality": "roads",
                "source_dataset": "road_traffic",
                "source_entity_group": "road_links",
                "source_property": "vehicles_per_hour",
                "target_property": "passengers_per_hour"
            },
            {
                "conversion_type": "od",
                "modality": "roads",
                "source_dataset": "car_demand",
                "source_entity_group": "od_matrix",
                "source_property": "car_trips",
                "target_property": "car_passengers"
            },
            {
                "conversion_type": "flow",
                "modality": "waterways",
                "source_dataset": "shipping",
                "source_entity_group": "shipping_lanes",
                "source_property": "vessel_count",
                "target_property": "cargo_tons"
            }
        ],
        "parameters_dataset": "modal_coefficients"
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
   * - ``conversions``
     - array
     - Yes
     - List of conversion configurations
   * - ``conversions[].conversion_type``
     - string
     - Yes
     - "flow" or "od" (origin-destination)
   * - ``conversions[].modality``
     - string
     - No
     - "roads" or "waterways" (default: "roads")
   * - ``conversions[].source_dataset``
     - string
     - Yes
     - Dataset containing source data
   * - ``conversions[].source_entity_group``
     - string
     - Yes
     - Entity group with source data
   * - ``conversions[].source_property``
     - string
     - Yes
     - Source attribute to convert
   * - ``conversions[].target_property``
     - string
     - Yes
     - Output attribute for converted values
   * - ``parameters_dataset``
     - string
     - Yes
     - CSV dataset with conversion coefficients

Data Requirements
-----------------

Input Data
^^^^^^^^^^

**Source Data:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - Source property
     - array[float]
     - Vehicle counts or flows to convert
   * - ``modality`` (optional)
     - array[string]
     - Transport mode identifier

**Parameters Dataset (CSV):**

.. code-block:: text

    modality,vehicle_type,passengers_per_vehicle,cargo_per_vehicle,load_factor
    roads,car,1.5,0.0,0.6
    roads,bus,40.0,0.0,0.3
    roads,truck,1.2,15.0,0.8
    waterways,cargo_ship,20.0,5000.0,0.7
    waterways,passenger_ferry,200.0,50.0,0.5

Output Data
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - Target property
     - array[float]
     - Converted passenger/cargo values
   * - Conversion factors
     - array[float]
     - Applied conversion coefficients

Conversion Methods
------------------

Vehicle to Passenger Conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Basic conversion
    passengers = vehicles * passengers_per_vehicle * load_factor
    
    # Example: 100 cars with 1.5 passengers/car at 60% load factor
    # passengers = 100 * 1.5 * 0.6 = 90 passengers

Vehicle to Cargo Conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Cargo conversion
    cargo_tons = vehicles * cargo_per_vehicle * load_factor
    
    # Example: 50 trucks with 15 tons capacity at 80% load factor
    # cargo_tons = 50 * 15 * 0.8 = 600 tons

OD Matrix Conversion
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # OD conversions preserve matrix structure
    for origin in origins:
        for destination in destinations:
            od_passengers[origin][destination] = (
                od_vehicles[origin][destination] * 
                passengers_per_vehicle * 
                load_factor
            )

Examples
--------

Road Traffic Conversion
^^^^^^^^^^^^^^^^^^^^^^^

Converting vehicle counts to passengers and cargo:

.. code-block:: json

    {
        "name": "road_conversions",
        "type": "unit_conversions",
        "conversions": [
            {
                "conversion_type": "flow",
                "modality": "roads",
                "source_dataset": "traffic_counts",
                "source_entity_group": "count_stations",
                "source_property": "hourly_vehicles",
                "target_property": "hourly_passengers"
            },
            {
                "conversion_type": "flow",
                "modality": "roads",
                "source_dataset": "freight_flows",
                "source_entity_group": "truck_routes",
                "source_property": "truck_count",
                "target_property": "cargo_tons"
            }
        ],
        "parameters_dataset": "vehicle_occupancy"
    }

**Sample Calculation:**

.. code-block:: python

    # Input data
    traffic_count = {
        "hourly_vehicles": [500, 800, 1200],  # vehicles/hour
        "vehicle_mix": "mixed_urban"
    }
    
    # Coefficients (weighted average)
    coefficients = {
        "car": {"share": 0.8, "passengers": 1.4, "load_factor": 0.6},
        "bus": {"share": 0.05, "passengers": 40, "load_factor": 0.3},
        "truck": {"share": 0.15, "passengers": 1.2, "load_factor": 1.0}
    }
    
    # Weighted conversion factor
    factor = (0.8 * 1.4 * 0.6 + 0.05 * 40 * 0.3 + 0.15 * 1.2 * 1.0)
    #       = (0.672 + 0.6 + 0.18) = 1.452
    
    # Result
    passengers = [500 * 1.452, 800 * 1.452, 1200 * 1.452]
    #          = [726, 1162, 1742] passengers/hour

Maritime Cargo Conversion
^^^^^^^^^^^^^^^^^^^^^^^^^

Converting vessel counts to cargo capacity:

.. code-block:: json

    {
        "name": "port_cargo_conversion",
        "type": "unit_conversions",
        "conversions": [
            {
                "conversion_type": "flow",
                "modality": "waterways",
                "source_dataset": "port_operations",
                "source_entity_group": "berths",
                "source_property": "vessel_arrivals",
                "target_property": "cargo_handled_tons"
            }
        ],
        "parameters_dataset": "vessel_capacities"
    }

OD Matrix Transformation
^^^^^^^^^^^^^^^^^^^^^^^^

Converting trip matrices between units:

.. code-block:: json

    {
        "name": "od_conversion",
        "type": "unit_conversions",
        "conversions": [
            {
                "conversion_type": "od",
                "modality": "roads",
                "source_dataset": "demand_model",
                "source_entity_group": "car_demand",
                "source_property": "vehicle_trips",
                "target_property": "person_trips"
            }
        ],
        "parameters_dataset": "occupancy_rates"
    }

Coefficient Management
----------------------

Vehicle Type Categories
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table:: Road Vehicle Coefficients
   :header-rows: 1
   :widths: 20 20 20 20 20

   * - Vehicle Type
     - Passengers/Veh
     - Cargo (tons)
     - Typical Load Factor
     - Usage Context
   * - Passenger car
     - 1.2-1.6
     - 0
     - 0.5-0.7
     - Urban/suburban
   * - Taxi
     - 2.0
     - 0
     - 0.5
     - City centers
   * - Bus (city)
     - 40-60
     - 0
     - 0.2-0.4
     - Urban transit
   * - Bus (intercity)
     - 50-80
     - 0
     - 0.6-0.8
     - Long distance
   * - Light truck
     - 1.2
     - 2-5
     - 0.7-0.9
     - Delivery
   * - Heavy truck
     - 1.0
     - 15-40
     - 0.7-0.9
     - Freight

Waterway Coefficients
^^^^^^^^^^^^^^^^^^^^^

.. list-table:: Waterway Vehicle Coefficients
   :header-rows: 1
   :widths: 25 20 20 35

   * - Vessel Type
     - Passengers
     - Cargo (tons)
     - Typical Applications
   * - Cargo ship
     - 20-30
     - 2000-20000
     - Container, bulk freight
   * - Passenger ferry
     - 100-500
     - 50-200
     - Urban water transport
   * - Barge
     - 2-5
     - 500-3000
     - River freight
   * - Cruise ship
     - 2000-6000
     - 500
     - Tourism

Performance Considerations
--------------------------

Optimization Strategies
^^^^^^^^^^^^^^^^^^^^^^^

- Pre-compute coefficient lookups
- Cache conversion factors
- Vectorize array operations
- Batch similar conversions

Scalability
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Data Size
     - Processing Time
     - Recommendations
   * - < 10,000 values
     - < 0.1 seconds
     - Direct processing
   * - 10,000-100,000
     - 0.1-1 seconds
     - Vectorized operations
   * - > 100,000
     - > 1 second
     - Parallel processing

Best Practices
--------------

Coefficient Selection
^^^^^^^^^^^^^^^^^^^^^

- Use local occupancy surveys
- Consider time-of-day variations
- Account for seasonal changes
- Validate with observed data

Data Validation
^^^^^^^^^^^^^^^

- Check for reasonable output ranges
- Validate coefficient magnitudes
- Ensure unit consistency
- Test with known cases

.. code-block:: python

    # Validation checks
    assert all(passengers >= 0), "Negative passenger counts"
    assert all(cargo >= 0), "Negative cargo values"
    assert max(passengers) < reasonable_upper_bound
    
    # Unit consistency
    if source_unit == "vehicles/hour" and target_unit == "passengers/hour":
        assert conversion_factor > 0.5  # Minimum occupancy
        assert conversion_factor < 100   # Maximum reasonable

Integration Planning
^^^^^^^^^^^^^^^^^^^^

- Coordinate with demand models
- Align with capacity calculations
- Consider multi-step conversions
- Document conversion chains

Common Issues and Troubleshooting
----------------------------------

Zero Output Values
^^^^^^^^^^^^^^^^^^

**Issue**: All converted values are zero

**Solutions**:

- Verify source data is non-zero
- Check coefficient dataset loading
- Ensure modality matching
- Validate load factors > 0

Unrealistic Conversions
^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Output values seem too high/low

**Solutions**:

- Review coefficient magnitudes
- Check load factor assumptions
- Verify vehicle type mapping
- Compare with benchmark data

Missing Coefficients
^^^^^^^^^^^^^^^^^^^^

**Issue**: Some conversions fail due to missing parameters

**Solutions**:

- Complete coefficient CSV file
- Add default coefficients
- Implement fallback values
- Use regional averages

Integration with Other Models
-----------------------------

The Unit Conversions model integrates with:

- **Traffic Assignment Model**: Standardize demand units
- **Traffic KPI Model**: Convert for emission calculations  
- **Traffic Demand Model**: Normalize demand inputs
- **Data Collector Model**: Store converted values

Advanced Features
-----------------

Time-Varying Coefficients
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def get_time_coefficient(hour_of_day, base_coefficient):
        # Peak hour adjustments
        if 7 <= hour_of_day <= 9:
            return base_coefficient * 0.8  # Lower occupancy
        elif 17 <= hour_of_day <= 19:
            return base_coefficient * 0.9  # Commuter traffic
        else:
            return base_coefficient

Vehicle Mix Adjustments
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def apply_vehicle_mix(total_vehicles, vehicle_mix_percentages):
        converted_values = 0
        for vehicle_type, percentage in vehicle_mix_percentages.items():
            vehicle_count = total_vehicles * percentage
            coefficient = get_coefficient(vehicle_type)
            converted_values += vehicle_count * coefficient
        return converted_values

Seasonal Adjustments
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    seasonal_factors = {
        "spring": 1.0,
        "summer": 1.2,  # Tourism peak
        "autumn": 1.0,
        "winter": 0.8   # Reduced travel
    }
    
    def seasonal_conversion(base_value, season):
        return base_value * seasonal_factors[season]

Quality Control
---------------

Validation Methods
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def validate_conversions(input_data, output_data, coefficients):
        # Range checks
        assert all(output >= 0 for output in output_data)
        
        # Ratio checks
        ratios = [out/inp for out, inp in zip(output_data, input_data) if inp > 0]
        assert min(ratios) >= 0.1, "Suspiciously low conversion"
        assert max(ratios) <= 200, "Suspiciously high conversion"
        
        # Coefficient validation
        assert all(coef > 0 for coef in coefficients.values())

Comparison with Benchmarks
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Compare with known benchmarks
    benchmark_occupancy = {"urban": 1.4, "suburban": 1.6, "highway": 1.8}
    
    calculated_occupancy = sum(passengers) / sum(vehicles)
    expected = benchmark_occupancy[area_type]
    
    assert abs(calculated_occupancy - expected) / expected < 0.2  # 20% tolerance

See Also
--------

- :doc:`traffic_assignment` - For demand standardization
- :doc:`traffic_kpi` - For emission factor inputs
- :doc:`traffic_demand_calculation` - For demand normalization
- :doc:`data_collector` - For storing converted data

API Reference
-------------

- :class:`movici_simulation_core.models.unit_conversions.UnitConversionsModel`
- :mod:`movici_simulation_core.models.unit_conversions.attributes`
- :mod:`movici_simulation_core.models.unit_conversions.entities`