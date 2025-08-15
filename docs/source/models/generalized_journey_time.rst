Generalized Journey Time Model
===============================

The Generalized Journey Time (GJT) model calculates comprehensive travel times for railway passengers by incorporating crowdedness effects, waiting times, and comfort factors. It extends basic travel time calculations to account for passenger experience quality, making it essential for realistic public transport planning and optimization.

Overview
--------

The GJT model addresses the reality that passenger journey experience involves more than just travel time. It incorporates:

- **Crowdedness penalties**: Increased perceived time due to overcrowding
- **Waiting time**: Average waiting time based on service frequency
- **Comfort factors**: Multipliers based on passenger load factors
- **Network effects**: Integration with shortest path calculations

This model is particularly valuable for:

- Public transport route planning
- Service frequency optimization
- Capacity planning decisions
- Passenger flow analysis
- Multi-modal journey planning

Key Features
------------

- **Crowdedness modeling**: Linear regression-based crowdedness factors
- **Load factor analysis**: Capacity-aware journey time adjustments
- **Network integration**: Works with shortest path algorithms
- **CSR matrix output**: Efficient storage of journey time matrices
- **Dynamic updates**: Responds to changing passenger flows and frequencies

Mathematical Foundation
-----------------------

The generalized journey time is calculated using:

.. math::

    GJT = w \times TT + \frac{f}{2 \times freq}

Where:

- ``GJT`` = Generalized Journey Time
- ``w`` = Crowdedness weight factor (based on load factor)
- ``TT`` = Base travel time
- ``f`` = Fixed waiting time factor
- ``freq`` = Service frequency

The crowdedness weight ``w`` is determined by:

.. math::

    w = \begin{cases}
    1.0 & \text{if } LF \leq 0.4 \\
    0.95 + 0.28 \times LF & \text{if } 0.4 < LF \leq 1.0 \\
    1.23 + 1.6 \times (LF - 1.0) & \text{if } LF > 1.0
    \end{cases}

Where ``LF`` = Load Factor (passengers/capacity)

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "rail_gjt",
        "type": "generalized_journey_time",
        "transport_segments": {
            "dataset": "railway_network",
            "entity_group": "rail_segments"
        },
        "travel_time": {
            "property": "transport.travel_time"
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
   * - ``transport_segments``
     - object
     - Yes
     - Transport network configuration
   * - ``transport_segments.dataset``
     - string
     - Yes
     - Name of the dataset containing transport segments
   * - ``transport_segments.entity_group``
     - string
     - Yes
     - Entity group containing transport segments
   * - ``travel_time``
     - object
     - Yes
     - Travel time attribute configuration
   * - ``travel_time.property``
     - string
     - Yes
     - Attribute containing base travel times

Data Requirements
-----------------

Input Data
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``transport.travel_time``
     - array[float]
     - Base travel time for each segment (seconds)
   * - ``transport.passenger_flow``
     - array[float]
     - Number of passengers per segment
   * - ``transport.train_frequency``
     - array[float]
     - Service frequency (trains per hour)
   * - ``transport.train_capacity``
     - array[float]
     - Maximum passenger capacity per train
   * - ``transport.from_node_id``
     - array[int]
     - Origin node for each segment
   * - ``transport.to_node_id``
     - array[int]
     - Destination node for each segment

Output Data
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``transport.gjt_matrix``
     - CSR matrix
     - Generalized journey times between all node pairs
   * - ``transport.crowdedness_factor``
     - array[float]
     - Calculated crowdedness weight for each segment
   * - ``transport.load_factor``
     - array[float]
     - Passenger load factor (flow/capacity)

Examples
--------

Urban Rail Network
^^^^^^^^^^^^^^^^^^

Configuration for city metro system with crowding analysis:

.. code-block:: json

    {
        "name": "metro_gjt",
        "type": "generalized_journey_time",
        "transport_segments": {
            "dataset": "metro_network",
            "entity_group": "metro_lines"
        },
        "travel_time": {
            "property": "schedule.segment_time"
        }
    }

**Sample Data Structure:**

.. code-block:: python

    # Input attributes
    {
        "schedule.segment_time": [120, 180, 150, 90],  # seconds
        "passenger.hourly_flow": [5000, 4500, 3000, 6000],
        "service.trains_per_hour": [12, 10, 10, 15],
        "vehicle.capacity": [800, 800, 600, 1000]
    }

    # Output: GJT considering crowding
    # Segment 1: LF = 5000/(12*800) = 0.52 → w = 1.096
    # GJT = 1.096 * 120 + 60/(2*12) = 131.5 + 2.5 = 134 seconds

Regional Rail Network
^^^^^^^^^^^^^^^^^^^^^

Configuration for intercity rail with comfort considerations:

.. code-block:: json

    {
        "name": "intercity_gjt",
        "type": "generalized_journey_time",
        "transport_segments": {
            "dataset": "national_rail",
            "entity_group": "rail_corridors"
        },
        "travel_time": {
            "property": "timetable.travel_duration"
        }
    }

Multi-Modal Integration
^^^^^^^^^^^^^^^^^^^^^^^

Configuration for integrated transport planning:

.. code-block:: json

    {
        "name": "multimodal_gjt",
        "type": "generalized_journey_time",
        "transport_segments": {
            "dataset": "integrated_network",
            "entity_group": "rail_segments"
        },
        "travel_time": {
            "property": "multimodal.segment_time"
        }
    }

Algorithm Details
-----------------

The GJT calculation follows these steps:

1. **Load Factor Calculation**:

   .. code-block:: python

       load_factor = passenger_flow / (train_frequency * train_capacity)

2. **Crowdedness Weight Determination**:

   - Uses piecewise linear function based on research data
   - Three regimes: comfortable (LF ≤ 0.4), moderate (0.4 < LF ≤ 1.0), overcrowded (LF > 1.0)

3. **Journey Time Calculation**:

   - Apply crowdedness weight to base travel time
   - Add average waiting time component
   - Store results in CSR matrix format for efficient path finding

4. **Network Integration**:

   - Build graph from segment connectivity
   - Calculate shortest paths using GJT weights
   - Support both single-source and all-pairs calculations

Performance Considerations
--------------------------

Memory Optimization
^^^^^^^^^^^^^^^^^^^

- CSR matrices reduce memory for sparse networks
- Cache frequently accessed journey times
- Use appropriate data types (float32 vs float64)

Computation Efficiency
^^^^^^^^^^^^^^^^^^^^^^

- Batch process load factor calculations
- Update only affected segments when flows change
- Use incremental shortest path algorithms where possible

Scalability Guidelines
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Network Size
     - Memory Usage
     - Recommendations
   * - < 1,000 segments
     - < 100 MB
     - Full matrix computation feasible
   * - 1,000 - 10,000 segments
     - 100 MB - 1 GB
     - Use CSR matrices, selective updates
   * - > 10,000 segments
     - > 1 GB
     - Implement hierarchical computation, zone-based processing

Best Practices
--------------

Data Quality
^^^^^^^^^^^^

- Ensure accurate passenger flow measurements
- Validate train capacity specifications
- Use consistent time units (typically seconds)
- Regular calibration with real-world data

Model Calibration
^^^^^^^^^^^^^^^^^

- Adjust crowdedness regression parameters based on local preferences
- Validate waiting time assumptions with schedule data
- Consider peak vs off-peak parameter variations
- Account for different vehicle types (local vs express)

Integration Strategies
^^^^^^^^^^^^^^^^^^^^^^

- Combine with demand models for flow predictions
- Link to assignment models for equilibrium analysis
- Connect to visualization for bottleneck identification
- Use with timetable optimization tools

Common Issues and Troubleshooting
----------------------------------

Unrealistic Journey Times
^^^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Calculated GJT values seem too high or low

**Solutions**:

- Verify unit consistency (seconds vs minutes)
- Check passenger flow and capacity values
- Validate frequency data (trains per hour)
- Review crowdedness weight parameters

Network Connectivity Issues
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Shortest paths not found between certain nodes

**Solutions**:

- Verify from_node_id and to_node_id connectivity
- Check for isolated network components
- Ensure bidirectional segments where appropriate
- Validate node ID consistency

Performance Degradation
^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Slow computation for large networks

**Solutions**:

- Implement zone-based processing
- Use approximate algorithms for non-critical pairs
- Cache frequently requested routes
- Consider parallel processing for independent calculations

Integration with Other Models
-----------------------------

The GJT model integrates effectively with:

- **Shortest Path Model**: Uses GJT as edge weights for realistic routing
- **Traffic Assignment Model**: Provides passenger flow inputs
- **Traffic Demand Model**: Supplies OD demand for flow calculation
- **Data Collector Model**: Stores GJT matrices for analysis

Future Extensions
-----------------

Potential enhancements include:

- Time-dependent GJT with peak/off-peak variations
- Multi-class passengers with different comfort preferences
- Real-time updates based on actual crowding data
- Integration with fare systems for generalized cost
- Weather and incident impact factors

See Also
--------

- :doc:`shortest_path` - For network path calculations
- :doc:`traffic_assignment` - For passenger flow equilibrium
- :doc:`traffic_demand_calculation` - For demand modeling
- :doc:`corridor` - For corridor-level analysis

API Reference
-------------

- :class:`movici_simulation_core.models.generalized_journey_time.GJTModel`
- :mod:`movici_simulation_core.models.generalized_journey_time.crowdedness`
