Model Library
===============

This section provides comprehensive documentation for all available models in movici-simulation-core. Each model serves specific simulation purposes, from data input/output to complex analysis and computation.

Data Input/Output Models
------------------------

.. toctree::
   :maxdepth: 1

   csv_player
   netcdf_player
   data_collector
   tape_player

Analysis and Aggregation Models
-------------------------------

.. toctree::
   :maxdepth: 1

   area_aggregation
   corridor
   operational_status
   overlap_status
   opportunities

Transport and Traffic Models
----------------------------

.. toctree::
   :maxdepth: 1

   traffic_assignment
   traffic_demand_calculation
   traffic_kpi
   generalized_journey_time
   shortest_path
   unit_conversions

Utility and Support Models
---------------------------

.. toctree::
   :maxdepth: 1

   udf_model
   time_window_status
   evacuation_point_resolution

Model Categories
================

**Data Input Models** load external data into simulations:
   * :doc:`csv_player` - Time-series data from CSV files
   * :doc:`netcdf_player` - Gridded spatiotemporal data from NetCDF files
   * :doc:`tape_player` - Replay recorded simulation data from JSON/MessagePack files

**Data Output Models** capture and store simulation results:
   * :doc:`data_collector` - Saves simulation state data for analysis

**Spatial Analysis Models** perform geospatial computations:
   * :doc:`area_aggregation` - Aggregates attributes within spatial boundaries
   * :doc:`operational_status` - Determines infrastructure operational state based on environmental conditions
   * :doc:`overlap_status` - Detects geometric overlaps between infrastructure entities
   * :doc:`opportunities` - Analyzes economic opportunities and costs from overlapping projects

**Transport and Traffic Models** analyze movement and networks:
   * :doc:`corridor` - Analyzes transport corridors and route performance
   * :doc:`traffic_assignment` - Assigns traffic flows to network routes
   * :doc:`traffic_demand_calculation` - Calculates demand changes based on elasticity parameters
   * :doc:`traffic_kpi` - Computes transportation KPIs (emissions, energy consumption)
   * :doc:`generalized_journey_time` - Calculates realistic travel times with crowdedness effects
   * :doc:`shortest_path` - Computes optimal routes through transport networks
   * :doc:`unit_conversions` - Converts between vehicle counts, passengers, and cargo

**Status and Monitoring Models** track entity states:
   * :doc:`operational_status` - Infrastructure functionality under environmental stress
   * :doc:`time_window_status` - Time-based activation/deactivation of entity states

**Utility Models** provide general-purpose functionality:
   * :doc:`udf_model` - User-defined mathematical functions and calculations
   * :doc:`evacuation_point_resolution` - Maps road segments to evacuation points

Quick Reference
===============

.. list-table:: Model Overview
   :header-rows: 1
   :widths: 20 25 55

   * - Model
     - Primary Use Case
     - Key Features
   * - :doc:`area_aggregation`
     - Spatial data aggregation
     - Multiple functions, geometry support, time integration
   * - :doc:`corridor`
     - Transport route analysis
     - Shortest paths, demand integration, multi-modal
   * - :doc:`csv_player`
     - Time-series data input
     - Automatic timing, multiple parameters, step functions
   * - :doc:`data_collector`
     - Simulation result capture
     - Selective filtering, concurrent I/O, multiple formats
   * - :doc:`evacuation_point_resolution`
     - Emergency evacuation planning
     - ID-based mapping, CSR arrays, batch processing
   * - :doc:`generalized_journey_time`
     - Realistic travel time calculation
     - Crowdedness modeling, load factors, network integration
   * - :doc:`netcdf_player`
     - Gridded data input
     - Multi-dimensional arrays, temporal interpolation
   * - :doc:`opportunities`
     - Economic opportunity analysis
     - Cost calculation, overlap integration, investment impacts
   * - :doc:`operational_status`
     - Infrastructure status monitoring
     - Flood analysis, threshold-based, spatial queries
   * - :doc:`overlap_status`
     - Geometric overlap detection
     - Multi-geometry support, distance thresholds, status tracking
   * - :doc:`shortest_path`
     - Network route optimization
     - Multiple calculation types, CSR matrices, dynamic updates
   * - :doc:`tape_player`
     - Recorded data playback
     - JSON/MessagePack support, time synchronization, dynamic attributes
   * - :doc:`time_window_status`
     - Time-based status management
     - Flexible time formats, multi-target updates, timeline awareness
   * - :doc:`traffic_assignment`
     - Traffic flow modeling
     - Equilibrium assignment, capacity constraints
   * - :doc:`traffic_demand_calculation`
     - Demand elasticity modeling
     - Global/local parameters, investment impacts, OD matrix updates
   * - :doc:`traffic_kpi`
     - Transportation impact assessment
     - Multi-modal emissions, scenario modeling, coefficient management
   * - :doc:`udf_model`
     - Custom mathematical calculations
     - Expression compiler, array operations, conditional logic
   * - :doc:`unit_conversions`
     - Unit standardization
     - Multi-modal support, coefficient management, load factors
