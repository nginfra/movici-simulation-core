Shortest Path Model
===================

The Shortest Path model computes optimal routes through transport networks using configurable cost factors and calculation methods. It supports both single-source and all-pairs shortest path computations, with options for sum-based or weighted average calculations along paths.

Overview
--------

This model is fundamental for:

- Route optimization in transport networks
- Travel time calculations
- Cost-distance analysis
- Network accessibility studies
- Service area determination
- Multi-criteria path finding

The model integrates with network graphs and can handle various edge weight attributes, making it versatile for different transportation modes and analysis scenarios.

Key Features
------------

- **Flexible cost factors**: Any numeric attribute as edge weight
- **Multiple calculation types**: Sum and weighted average operations
- **Single-source paths**: From specific origins to all destinations
- **All-pairs computation**: Complete origin-destination matrices
- **CSR matrix output**: Efficient storage for sparse networks
- **Dynamic updates**: Respond to changing network conditions

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "network_shortest_paths",
        "type": "shortest_path",
        "transport_segments": {
            "dataset": "road_network",
            "entity_group": "road_segments"
        },
        "cost_factor": "travel_time",
        "calculations": [
            {
                "name": "travel_time_matrix",
                "type": "sum",
                "input": "travel_time",
                "output": "shortest_travel_time"
            }
        ]
    }

Advanced Configuration
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "multimodal_routing",
        "type": "shortest_path",
        "transport_segments": {
            "dataset": "transport_network",
            "entity_group": "network_links"
        },
        "cost_factor": "generalized_cost",
        "no_update_shortest_path": false,
        "calculations": [
            {
                "name": "cost_paths",
                "type": "sum",
                "input": "monetary_cost",
                "output": "total_cost",
                "output_type": "csr"
            },
            {
                "name": "emission_paths",
                "type": "weighted_average",
                "input": "co2_emissions",
                "weight": "segment_length",
                "output": "average_emissions",
                "output_type": "uniform"
            }
        ]
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
     - Network dataset configuration
   * - ``transport_segments.dataset``
     - string
     - Yes
     - Dataset containing network segments
   * - ``transport_segments.entity_group``
     - string
     - Yes
     - Entity group with network links
   * - ``cost_factor``
     - string
     - Yes
     - Attribute name for path cost calculation
   * - ``calculations``
     - array
     - Yes
     - List of calculation configurations
   * - ``calculations[].name``
     - string
     - Yes
     - Unique name for calculation
   * - ``calculations[].type``
     - string
     - Yes
     - "sum" or "weighted_average"
   * - ``calculations[].input``
     - string
     - Yes
     - Input attribute for calculation
   * - ``calculations[].output``
     - string
     - Yes
     - Output attribute name
   * - ``calculations[].weight``
     - string
     - No
     - Weight attribute (for weighted_average)
   * - ``calculations[].output_type``
     - string
     - No
     - "uniform" or "csr" (default: "uniform")
   * - ``calculations[].entity_id``
     - integer
     - No
     - Single source entity ID
   * - ``calculations[].entity_ref``
     - string
     - No
     - Reference attribute for single source
   * - ``no_update_shortest_path``
     - boolean
     - No
     - Skip path updates if true

Data Requirements
-----------------

Input Data
^^^^^^^^^^

**Network Segments:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``id``
     - array[int]
     - Unique segment identifier
   * - ``from_node_id``
     - array[int]
     - Origin node of segment
   * - ``to_node_id``
     - array[int]
     - Destination node of segment
   * - Cost factor attribute
     - array[float]
     - Edge weight for shortest path
   * - Calculation inputs
     - array[float]
     - Attributes for sum/average calculations
   * - Weight attributes
     - array[float]
     - Weights for weighted averages

Output Data
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - Calculation outputs
     - array or CSR
     - Results of path calculations
   * - ``shortest_path_tree``
     - dict
     - Path tree structure (internal)
   * - ``path_costs``
     - array[float]
     - Minimum costs to each node

Calculation Types
-----------------

Sum Calculation
^^^^^^^^^^^^^^^

Accumulates values along the shortest path:

.. code-block:: python

    # For path: A -> B -> C -> D
    # Input values: [10, 15, 8]
    # Output: 10 + 15 + 8 = 33

Applications:

- Total travel time
- Cumulative distance
- Total monetary cost
- Aggregate emissions

Weighted Average Calculation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Computes weighted average along the path:

.. code-block:: python

    # For path: A -> B -> C -> D
    # Input values: [50, 60, 40]
    # Weights: [100, 200, 150]
    # Output: (50*100 + 60*200 + 40*150) / (100 + 200 + 150)
    #       = 23000 / 450 = 51.11

Applications:

- Average speed
- Mean congestion level
- Average emission rate
- Weighted service quality

Examples
--------

Road Network Travel Times
^^^^^^^^^^^^^^^^^^^^^^^^^

Computing travel time matrices:

.. code-block:: json

    {
        "name": "road_travel_times",
        "type": "shortest_path",
        "transport_segments": {
            "dataset": "city_roads",
            "entity_group": "road_links"
        },
        "cost_factor": "free_flow_time",
        "calculations": [
            {
                "name": "morning_peak",
                "type": "sum",
                "input": "peak_travel_time",
                "output": "morning_shortest_time",
                "output_type": "csr"
            },
            {
                "name": "off_peak",
                "type": "sum",
                "input": "free_flow_time",
                "output": "offpeak_shortest_time",
                "output_type": "csr"
            }
        ]
    }

Public Transit Routing
^^^^^^^^^^^^^^^^^^^^^^

Multi-criteria transit path finding:

.. code-block:: json

    {
        "name": "transit_routing",
        "type": "shortest_path",
        "transport_segments": {
            "dataset": "transit_network",
            "entity_group": "transit_links"
        },
        "cost_factor": "generalized_journey_time",
        "calculations": [
            {
                "name": "fare_calculation",
                "type": "sum",
                "input": "segment_fare",
                "output": "total_fare"
            },
            {
                "name": "comfort_score",
                "type": "weighted_average",
                "input": "comfort_rating",
                "weight": "segment_time",
                "output": "average_comfort"
            }
        ]
    }

Emergency Service Coverage
^^^^^^^^^^^^^^^^^^^^^^^^^^

Single-source shortest paths from emergency facilities:

.. code-block:: json

    {
        "name": "ambulance_response",
        "type": "shortest_path",
        "transport_segments": {
            "dataset": "emergency_network",
            "entity_group": "road_segments"
        },
        "cost_factor": "emergency_travel_time",
        "calculations": [
            {
                "name": "hospital_a_coverage",
                "type": "sum",
                "input": "emergency_travel_time",
                "output": "response_time_hospital_a",
                "entity_id": 42
            },
            {
                "name": "hospital_b_coverage",
                "type": "sum",
                "input": "emergency_travel_time",
                "output": "response_time_hospital_b",
                "entity_ref": "hospital_b_node"
            }
        ]
    }

Algorithm Details
-----------------

The model uses graph algorithms for shortest path computation:

1. **Network Graph Construction**:

   .. code-block:: python

       # Build directed graph from segments
       for segment in segments:
           graph.add_edge(
               from_node=segment.from_node_id,
               to_node=segment.to_node_id,
               weight=segment.cost_factor
           )

2. **Shortest Path Computation**:

   - **Single-source**: Dijkstra's algorithm
   - **All-pairs**: Floyd-Warshall or repeated Dijkstra
   - Optimizations for sparse networks

3. **Path Value Calculation**:

   - Trace paths through predecessor tree
   - Accumulate values based on calculation type
   - Store results in specified format

4. **Output Format**:

   - **Uniform**: Dense array for all nodes
   - **CSR**: Compressed sparse row for efficiency

Performance Considerations
--------------------------

Algorithm Selection
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Network Size
     - Density
     - Recommended Algorithm
   * - < 1,000 nodes
     - Any
     - Floyd-Warshall for all-pairs
   * - 1,000-10,000 nodes
     - Sparse
     - Dijkstra with heap
   * - > 10,000 nodes
     - Sparse
     - A* with heuristics

Memory Optimization
^^^^^^^^^^^^^^^^^^^

- Use CSR format for sparse results
- Process in batches for large all-pairs
- Cache frequently requested paths
- Clear intermediate structures

Computation Optimization
^^^^^^^^^^^^^^^^^^^^^^^^

- Pre-compute static shortest paths
- Use bidirectional search for point-to-point
- Implement contraction hierarchies for large networks
- Parallelize independent source computations

Best Practices
--------------

Network Preparation
^^^^^^^^^^^^^^^^^^^

- Ensure network connectivity
- Validate node ID consistency
- Check for negative edge weights
- Remove duplicate edges

Cost Factor Selection
^^^^^^^^^^^^^^^^^^^^^

- Use appropriate units (time, distance, cost)
- Consider multi-criteria costs
- Account for turn penalties if needed
- Validate cost factor ranges

Calculation Design
^^^^^^^^^^^^^^^^^^

- Choose appropriate calculation types
- Use CSR for sparse OD matrices
- Batch similar calculations
- Document output interpretations

Common Issues and Troubleshooting
----------------------------------

Infinite Path Costs
^^^^^^^^^^^^^^^^^^^

**Issue**: Some destinations show infinite cost

**Solutions**:

- Check network connectivity
- Verify all segments have valid costs
- Ensure bidirectional links where needed
- Look for isolated network components

Unexpected Path Results
^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Paths don't match expected routes

**Solutions**:

- Verify cost factor values
- Check for data type issues (int vs float)
- Review network topology
- Validate edge directions

Memory Exhaustion
^^^^^^^^^^^^^^^^^

**Issue**: Out of memory for all-pairs calculation

**Solutions**:

- Use CSR output format
- Process in geographic chunks
- Reduce precision if appropriate
- Consider approximate algorithms

Integration with Other Models
-----------------------------

The Shortest Path model integrates with:

- **Generalized Journey Time Model**: Provides realistic path costs
- **Traffic Assignment Model**: Uses paths for flow distribution
- **Corridor Model**: Analyzes paths within corridors
- **Data Collector Model**: Stores path matrices

Advanced Features
-----------------

Multi-Modal Networks
^^^^^^^^^^^^^^^^^^^^

- Handle mode transfer penalties
- Support time-dependent costs
- Implement schedule-based routing

Dynamic Shortest Paths
^^^^^^^^^^^^^^^^^^^^^^

- Update paths with changing conditions
- Incremental path recalculation
- Real-time route guidance

Constrained Routing
^^^^^^^^^^^^^^^^^^^

- Vehicle type restrictions
- Time window constraints
- Capacity-limited paths

See Also
--------

- :doc:`generalized_journey_time` - For realistic travel costs
- :doc:`traffic_assignment` - For network flow distribution
- :doc:`corridor` - For corridor-based analysis
- :doc:`data_collector` - For storing path results

API Reference
-------------

- :class:`movici_simulation_core.models.shortest_path.ShortestPathModel`
