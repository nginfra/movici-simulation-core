Traffic Demand Calculation Model
=================================

The Traffic Demand Calculation model computes changes in transportation demand based on elasticity parameters, investment scenarios, and policy interventions. It uses both global and local elasticity factors to model how demand responds to changes in travel costs, times, and infrastructure investments.

Overview
--------

This model is essential for:

- Policy impact assessment on travel demand
- Investment scenario evaluation
- Demand elasticity modeling
- Origin-destination matrix updates
- Multi-modal demand shifts
- Regional and local demand effects
- Economic growth impact on mobility

The model implements sophisticated elasticity-based calculations that account for both system-wide (global) and location-specific (local) factors affecting travel demand.

Key Features
------------

- **Elasticity modeling**: Price and time elasticity of demand
- **Multi-scale parameters**: Global and local effect modeling
- **Investment impacts**: Infrastructure investment demand multipliers
- **Geometric mapping**: Nearest-neighbor and route-based local effects
- **CSV integration**: External parameter scenario management
- **OD matrix updates**: Direct manipulation of origin-destination demand

Mathematical Foundation
-----------------------

The demand calculation follows elasticity theory:

.. math::

    D_{new} = D_{base} \times \prod_i (1 + e_i \times \Delta p_i)

Where:

- ``D_{new}`` = Updated demand
- ``D_{base}`` = Base demand
- ``e_i`` = Elasticity for parameter i
- ``Δp_i`` = Relative change in parameter i

For combined global and local effects:

.. math::

    D_{final} = D_{base} \times G_{global} \times L_{local} \times I_{investment}

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "demand_calculator",
        "type": "traffic_demand_calculation",
        "demand_path": {
            "dataset": "transport_demand",
            "entity": "od_matrix",
            "attribute": "passenger_demand"
        },
        "global_parameters": {
            "fuel_price": -0.3,
            "gdp_growth": 0.8,
            "population": 1.0
        }
    }

Advanced Configuration
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "comprehensive_demand",
        "type": "traffic_demand_calculation",
        "demand_path": {
            "dataset": "multimodal_demand",
            "entity": "od_pairs",
            "attribute": "trip_demand"
        },
        "global_parameters": {
            "fuel_cost": -0.35,
            "travel_time": -0.6,
            "income_level": 0.9
        },
        "local_parameters": {
            "congestion_charge": {
                "elasticity": -0.4,
                "geometry": "nearest",
                "dataset": "zones",
                "entity_group": "charge_zones"
            },
            "transit_quality": {
                "elasticity": 0.5,
                "geometry": "route",
                "dataset": "transit",
                "entity_group": "transit_lines"
            }
        },
        "parameter_dataset": "scenario_parameters",
        "investment_multipliers": {
            "rail_expansion": 1.15,
            "highway_upgrade": 1.08,
            "bike_infrastructure": 1.25
        }
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
   * - ``demand_path``
     - object
     - Yes
     - OD matrix location specification
   * - ``demand_path.dataset``
     - string
     - Yes
     - Dataset containing OD matrix
   * - ``demand_path.entity``
     - string
     - Yes
     - Entity group with demand data
   * - ``demand_path.attribute``
     - string
     - Yes
     - Attribute containing demand values
   * - ``global_parameters``
     - object
     - No
     - Global elasticity parameters
   * - ``local_parameters``
     - object
     - No
     - Local elasticity configurations
   * - ``local_parameters.<name>``
     - object
     - No
     - Specific local parameter config
   * - ``local_parameters.<name>.elasticity``
     - float
     - Yes
     - Elasticity coefficient
   * - ``local_parameters.<name>.geometry``
     - string
     - Yes
     - "nearest" or "route"
   * - ``local_parameters.<name>.dataset``
     - string
     - Yes
     - Dataset for geometric mapping
   * - ``local_parameters.<name>.entity_group``
     - string
     - Yes
     - Entity group for mapping
   * - ``parameter_dataset``
     - string
     - No
     - CSV dataset with scenario values
   * - ``investment_multipliers``
     - object
     - No
     - Investment impact factors

Data Requirements
-----------------

Input Data
^^^^^^^^^^

**OD Demand Matrix:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - Demand attribute
     - CSR/array
     - Origin-destination demand values
   * - ``origin_id``
     - array[int]
     - Origin zone identifiers
   * - ``destination_id``
     - array[int]
     - Destination zone identifiers

**Parameter Dataset (CSV):**

.. code-block:: text

    parameter,value,change_percent
    fuel_price,2.50,15.0
    gdp_growth,3.2,2.5
    toll_rate,5.00,-10.0
    transit_fare,2.00,5.0

**Local Effect Geometries:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``geometry``
     - varies
     - Spatial geometry for mapping
   * - ``effect_value``
     - array[float]
     - Local parameter values

Output Data
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - Updated demand
     - CSR/array
     - Modified OD demand values
   * - ``total_demand_in``
     - array[float]
     - Total inward demand per zone
   * - ``total_demand_out``
     - array[float]
     - Total outward demand per zone
   * - ``demand_change_factor``
     - array[float]
     - Multiplicative change factors

Elasticity Parameters
---------------------

Common Global Parameters
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 20 30 30

   * - Parameter
     - Typical Range
     - Interpretation
     - Example Impact
   * - Fuel price
     - -0.2 to -0.5
     - Negative: higher price → less demand
     - 10% price ↑ → 3% demand ↓
   * - Travel time
     - -0.5 to -1.0
     - Strong negative elasticity
     - 20% time ↓ → 15% demand ↑
   * - Income/GDP
     - 0.5 to 1.2
     - Positive: growth → more travel
     - 5% GDP ↑ → 4% demand ↑
   * - Transit fare
     - -0.3 to -0.6
     - Mode-specific price sensitivity
     - 25% fare ↓ → 10% ridership ↑

Local Parameter Examples
^^^^^^^^^^^^^^^^^^^^^^^^

- **Congestion charging**: Zone-specific price effects
- **Parking costs**: Location-based demand suppression
- **Transit quality**: Route-specific attractiveness
- **Land use density**: Area-based trip generation

Examples
--------

Urban Congestion Pricing
^^^^^^^^^^^^^^^^^^^^^^^^

Modeling congestion charge impacts:

.. code-block:: json

    {
        "name": "congestion_pricing_analysis",
        "type": "traffic_demand_calculation",
        "demand_path": {
            "dataset": "city_transport",
            "entity": "od_flows",
            "attribute": "vehicle_trips"
        },
        "global_parameters": {
            "fuel_price": -0.3
        },
        "local_parameters": {
            "congestion_zone": {
                "elasticity": -0.5,
                "geometry": "nearest",
                "dataset": "pricing",
                "entity_group": "charge_zones"
            }
        }
    }

**Scenario Analysis:**

.. code-block:: python

    # Base demand: 1000 trips
    # Congestion charge: $10 (50% increase)
    # Elasticity: -0.5
    
    # Calculation:
    # Demand change = 1 + (-0.5 * 0.5) = 0.75
    # New demand = 1000 * 0.75 = 750 trips
    # 25% reduction in trips to charged zone

Multi-Modal Shift Analysis
^^^^^^^^^^^^^^^^^^^^^^^^^^

Evaluating mode shift from investments:

.. code-block:: json

    {
        "name": "mode_shift_calculation",
        "type": "traffic_demand_calculation",
        "demand_path": {
            "dataset": "modal_split",
            "entity": "od_matrix",
            "attribute": "car_trips"
        },
        "global_parameters": {
            "fuel_price": -0.35,
            "parking_cost": -0.25
        },
        "investment_multipliers": {
            "metro_expansion": 0.85,
            "bike_network": 0.92
        },
        "parameter_dataset": "policy_scenarios"
    }

Regional Growth Impact
^^^^^^^^^^^^^^^^^^^^^^

Economic growth effects on demand:

.. code-block:: json

    {
        "name": "economic_growth_demand",
        "type": "traffic_demand_calculation",
        "demand_path": {
            "dataset": "regional_transport",
            "entity": "inter_city_flows",
            "attribute": "passenger_demand"
        },
        "global_parameters": {
            "gdp_growth": 1.1,
            "population_growth": 0.8,
            "employment_rate": 0.6
        },
        "parameter_dataset": "economic_forecast"
    }

Algorithm Details
-----------------

The demand calculation process:

1. **Parameter Loading**:
   
   .. code-block:: python
   
       # Load scenario parameters from CSV
       parameters = load_csv_parameters(parameter_dataset)
       
       # Calculate parameter changes
       for param_name, base_value in parameters.items():
           change_factor = (new_value - base_value) / base_value

2. **Global Effect Calculation**:
   
   .. code-block:: python
   
       global_multiplier = 1.0
       for param, elasticity in global_parameters.items():
           change = get_parameter_change(param)
           global_multiplier *= (1 + elasticity * change)

3. **Local Effect Mapping**:
   
   .. code-block:: python
   
       # For each OD pair
       for origin, destination in od_pairs:
           local_multiplier = 1.0
           
           # Nearest geometry mapping
           if geometry_type == "nearest":
               affected_zone = find_nearest(origin, local_geometries)
               local_effect = get_local_effect(affected_zone)
           
           # Route-based mapping
           elif geometry_type == "route":
               route = get_route(origin, destination)
               local_effect = aggregate_route_effects(route)
           
           local_multiplier *= (1 + elasticity * local_effect)

4. **Demand Update**:
   
   .. code-block:: python
   
       new_demand = base_demand * global_multiplier * local_multiplier * investment_multiplier

Performance Considerations
--------------------------

Optimization Strategies
^^^^^^^^^^^^^^^^^^^^^^^

- Pre-compute geometric mappings
- Cache elasticity calculations
- Vectorize demand updates
- Use sparse matrices for OD data

Scalability
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - OD Pairs
     - Parameters
     - Processing Strategy
   * - < 10,000
     - < 10
     - Direct calculation
   * - 10,000-100,000
     - 10-50
     - Batch processing, vectorization
   * - > 100,000
     - > 50
     - Parallel processing, approximations

Best Practices
--------------

Elasticity Calibration
^^^^^^^^^^^^^^^^^^^^^^

- Use empirical data for elasticity values
- Consider temporal variations (short vs long-term)
- Account for mode-specific elasticities
- Validate with observed demand changes

Scenario Design
^^^^^^^^^^^^^^^

- Create consistent parameter sets
- Document assumptions clearly
- Consider parameter correlations
- Test sensitivity to elasticity values

Integration Planning
^^^^^^^^^^^^^^^^^^^^

- Coordinate with assignment models
- Ensure demand unit consistency
- Plan for iterative equilibrium
- Handle negative demand appropriately

Common Issues and Troubleshooting
----------------------------------

Unrealistic Demand Changes
^^^^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Demand changes seem excessive

**Solutions**:

- Review elasticity magnitudes
- Check parameter change calculations
- Verify base demand values
- Consider elasticity bounds

Geometric Mapping Errors
^^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Local effects not applied correctly

**Solutions**:

- Verify geometry datasets
- Check coordinate systems
- Validate nearest-neighbor logic
- Review route definitions

Negative Demand Values
^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Calculations produce negative demand

**Solutions**:

- Implement demand floors (minimum zero)
- Review elasticity combinations
- Check for extreme parameter changes
- Consider non-linear elasticity models

Integration with Other Models
-----------------------------

The Traffic Demand Calculation model works with:

- **Traffic Assignment Model**: Provides updated demand for assignment
- **Shortest Path Model**: Routes for local effect mapping
- **Unit Conversions Model**: Standardize demand units
- **Traffic KPI Model**: Evaluate demand change impacts

Advanced Features
-----------------

Non-Linear Elasticity
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def non_linear_elasticity(base_demand, price_change, elasticity):
        # Logarithmic elasticity model
        if price_change > 0:
            factor = (1 + price_change) ** elasticity
        else:
            factor = 1 / ((1 - price_change) ** (-elasticity))
        return base_demand * factor

Cross-Elasticity Effects
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Mode substitution elasticities
    cross_elasticity_matrix = {
        ("car", "transit"): 0.3,
        ("car", "bike"): 0.1,
        ("transit", "bike"): 0.2
    }
    
    def apply_cross_elasticity(demands, price_changes):
        for mode_from, mode_to in cross_elasticity_matrix:
            elasticity = cross_elasticity_matrix[(mode_from, mode_to)]
            shift = demands[mode_from] * elasticity * price_changes[mode_from]
            demands[mode_from] -= shift
            demands[mode_to] += shift

Time-Varying Elasticity
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def time_dependent_elasticity(base_elasticity, time_horizon):
        # Short-term vs long-term elasticity
        if time_horizon < 365:  # days
            return base_elasticity * 0.5  # Short-term
        elif time_horizon < 1825:  # 5 years
            return base_elasticity * 0.8  # Medium-term
        else:
            return base_elasticity  # Long-term

See Also
--------

- :doc:`traffic_assignment` - For demand assignment to networks
- :doc:`traffic_kpi` - For demand-based KPI calculation
- :doc:`unit_conversions` - For demand unit standardization
- :doc:`shortest_path` - For route-based local effects

API Reference
-------------

- :class:`movici_simulation_core.models.traffic_demand_calculation.TrafficDemandCalculationModel`
- :mod:`movici_simulation_core.models.traffic_demand_calculation.global_contributors`
- :mod:`movici_simulation_core.models.traffic_demand_calculation.local_contributors`