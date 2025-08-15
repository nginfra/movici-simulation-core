Corridor Model
==============

.. currentmodule:: movici_simulation_core.models.corridor

Overview
--------

The Corridor model analyzes transport corridors by computing shortest paths between origin-destination pairs and aggregating travel characteristics along these routes. It connects transport networks with demand patterns to provide corridor-level performance metrics essential for transport planning and analysis.

A transport corridor represents a collection of routes between multiple origin and destination nodes, characterized by:

* **Multiple O-D pairs**: Each corridor can contain many origin-destination combinations
* **Shortest path routing**: Uses network analysis to find optimal routes
* **Demand aggregation**: Combines passenger and cargo demands with configurable conversion factors
* **Performance metrics**: Calculates travel times, distances, and demand flows

Key Features
------------

* **Multi-modal support**: Compatible with road, waterway, and rail networks
* **Dynamic routing**: Recalculates paths when travel times change
* **Demand integration**: Handles both passenger and cargo demands with PCU conversion
* **Corridor aggregation**: Provides aggregate metrics across all O-D pairs in a corridor
* **Geometry publishing**: Optional corridor route geometry output for visualization
* **AequilibraE integration**: Uses professional transport planning algorithms

Common Use Cases
----------------

* **Corridor performance analysis**: Monitor key transport routes
* **Infrastructure impact assessment**: Evaluate effects of network changes
* **Demand flow analysis**: Track passenger and cargo movements
* **Route optimization**: Identify bottlenecks and improvement opportunities
* **Multi-modal planning**: Compare performance across transport modes

Configuration Schema
--------------------

.. code-block:: json

   {
     "name": "my_corridor_analysis",
     "type": "corridor",
     "corridors": "corridor_definitions",
     "modality": "roads",
     "dataset": "transport_network",
     "cargo_pcu": 2.0,
     "publish_corridor_geometry": false
   }

Configuration Parameters
------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Parameter
     - Type
     - Description
   * - ``corridors``
     - string
     - **Required**. Dataset name containing corridor definitions with O-D pairs
   * - ``modality``
     - string
     - **Optional**. Transport mode: "roads", "waterways", or "tracks". Default: "roads"
   * - ``dataset``
     - string
     - **Optional**. Transport network dataset name. If not specified, uses modality-based default
   * - ``cargo_pcu``
     - number
     - **Optional**. Passenger Car Unit (PCU) conversion factor for cargo. Default: 2.0
   * - ``publish_corridor_geometry``
     - boolean
     - **Optional**. Whether to output corridor route geometries. Default: false

Data Requirements
-----------------

Corridor Definitions
~~~~~~~~~~~~~~~~~~~~

The corridors dataset must contain:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Description
   * - ``id``
     - Unique corridor identifiers
   * - ``from_nodes``
     - CSR array of origin node IDs for each corridor
   * - ``to_nodes``
     - CSR array of destination node IDs for each corridor

Transport Network
~~~~~~~~~~~~~~~~~

Required network attributes:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Description
   * - Road segments: ``travel_time``
     - Current travel time in seconds (input)
   * - Road nodes: ``geometry``
     - Node coordinates for routing

Demand Data
~~~~~~~~~~~

Required demand node attributes:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Description
   * - ``passenger_demand``
     - CSR matrix of passenger trips between demand nodes
   * - ``cargo_demand``
     - CSR matrix of cargo shipments between demand nodes

Output Attributes
-----------------

The model publishes corridor-level metrics:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Attribute
     - Description
   * - ``average_travel_time``
     - Mean travel time across all O-D pairs in corridor (seconds)
   * - ``total_passenger_demand``
     - Sum of passenger demands in corridor
   * - ``total_cargo_demand``
     - Sum of cargo demands in corridor
   * - ``total_pcu_demand``
     - Total demand in Passenger Car Units (PCU)
   * - ``total_distance``
     - Sum of route distances in corridor (meters)
   * - ``geometry`` (optional)
     - Corridor route geometry for visualization

Examples
--------

Example 1: Highway Corridor Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Analyze major highway corridor with passenger and freight traffic:

.. code-block:: json

   {
     "name": "highway_corridor",
     "type": "corridor",
     "corridors": "major_highways",
     "modality": "roads",
     "dataset": "road_network",
     "cargo_pcu": 2.5,
     "publish_corridor_geometry": true
   }

This configuration:
   * Analyzes highway corridors defined in "major_highways" dataset
   * Uses road network routing
   * Converts cargo to passenger equivalents using factor 2.5
   * Outputs route geometries for visualization

Example 2: Rail Corridor Performance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Monitor rail corridor efficiency:

.. code-block:: json

   {
     "name": "rail_corridor_monitor",
     "type": "corridor",
     "corridors": "rail_corridors",
     "modality": "tracks",
     "dataset": "railway_network",
     "cargo_pcu": 1.5
   }

Example 3: Waterway Freight Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Analyze cargo flows along waterway corridors:

.. code-block:: json

   {
     "name": "waterway_freight",
     "type": "corridor",
     "corridors": "shipping_routes",
     "modality": "waterways",
     "dataset": "waterway_network",
     "cargo_pcu": 10.0,
     "publish_corridor_geometry": false
   }

Corridor Definition Examples
----------------------------

Simple Corridor
~~~~~~~~~~~~~~~

CSV format for corridor definitions:

.. code-block:: text

   id,from_nodes,to_nodes
   corridor_1,"[101,102]","[201,202]"
   corridor_2,"[103]","[203,204,205]"

This defines:
   * Corridor 1: Routes from nodes 101,102 to nodes 201,202 (4 O-D pairs)
   * Corridor 2: Routes from node 103 to nodes 203,204,205 (3 O-D pairs)

Complex Multi-Point Corridor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   id,from_nodes,to_nodes
   major_highway,"[1001,1002,1003]","[2001,2002,2003,2004]"

This creates a corridor with 12 O-D pairs (3×4) representing a major highway with multiple access points.

Performance Metrics
-------------------

Travel Time Calculation
~~~~~~~~~~~~~~~~~~~~~~~

* Uses current ``travel_time`` from transport segments
* Recalculates paths when travel times change
* Averages travel times across all viable O-D pairs

Demand Aggregation
~~~~~~~~~~~~~~~~~~

* **Total PCU Demand** = (Cargo Demand × ``cargo_pcu``) + Passenger Demand
* Sums all O-D pair demands within each corridor
* Accounts for both directions of travel

Distance Calculation
~~~~~~~~~~~~~~~~~~~~

* Sums segment lengths along shortest paths
* Uses network topology for accurate distances
* Accounts for route deviations from straight-line distance

Best Practices
--------------

1. **Corridor Design**: Define corridors that align with real transport patterns
2. **Node Selection**: Choose representative O-D nodes that capture main flows
3. **PCU Factors**: Use appropriate cargo-to-passenger conversion factors for your context
4. **Network Quality**: Ensure transport network has realistic travel times and connectivity
5. **Demand Data**: Provide realistic demand matrices that reflect actual travel patterns

Performance Considerations
--------------------------

* **Path Calculation**: Routing complexity increases with number of O-D pairs
* **Network Size**: Large networks require more computation time
* **Update Frequency**: Recalculation occurs when travel times change
* **Memory Usage**: Corridor geometries can be memory-intensive for complex routes

Algorithm Details
-----------------

The model uses these computational steps:

1. **Network Preparation**: Build routing graph from transport network
2. **Path Finding**: Calculate shortest paths for each O-D pair using AequilibraE
3. **Route Analysis**: Extract travel times, distances, and geometries
4. **Demand Integration**: Apply demand data and PCU conversion factors
5. **Aggregation**: Compute corridor-level summary statistics

Common Issues and Solutions
---------------------------

**Issue**: "Nodes X-Y doesn't have a valid path between them"
   * Check network connectivity between origin and destination nodes
   * Verify node IDs exist in the transport network
   * Ensure transport network allows travel in required direction

**Issue**: Unexpected travel times or distances
   * Verify transport network ``travel_time`` attributes are realistic
   * Check for network topology errors (isolated segments, wrong connections)
   * Validate corridor O-D node selections

**Issue**: Memory issues with large corridors
   * Disable ``publish_corridor_geometry`` for large networks
   * Consider splitting large corridors into smaller segments
   * Monitor system memory during complex corridor analysis

Integration with Other Models
-----------------------------

The Corridor model integrates well with:

* **Traffic Assignment**: Use assignment results to update corridor travel times
* **Data Collector**: Store corridor performance time series
* **Area Aggregation**: Aggregate corridor metrics to administrative regions
* **CSV Player**: Inject time-varying demand data

See Also
--------

* :doc:`traffic_assignment` - For network-wide traffic analysis
* :doc:`/creating_models/geospatial_queries` - Understanding network routing
* :doc:`/tutorials/data_preparation` - Preparing network and demand data
* :class:`~movici_simulation_core.models.corridor.model.Model` - API reference
