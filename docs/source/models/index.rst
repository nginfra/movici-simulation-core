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

Analysis and Aggregation Models  
-------------------------------

.. toctree::
   :maxdepth: 1

   area_aggregation
   corridor
   operational_status

Transport and Traffic Models
----------------------------

.. toctree::  
   :maxdepth: 1

   traffic_assignment

Model Categories
================

**Data Input Models** load external data into simulations:
   * :doc:`csv_player` - Time-series data from CSV files
   * :doc:`netcdf_player` - Gridded spatiotemporal data from NetCDF files

**Data Output Models** capture and store simulation results:
   * :doc:`data_collector` - Saves simulation state data for analysis

**Spatial Analysis Models** perform geospatial computations:
   * :doc:`area_aggregation` - Aggregates attributes within spatial boundaries  
   * :doc:`operational_status` - Determines infrastructure operational state based on environmental conditions

**Transport Models** analyze movement and networks:
   * :doc:`corridor` - Analyzes transport corridors and route performance
   * :doc:`traffic_assignment` - Assigns traffic flows to network routes

**Status and Monitoring Models** track entity states:
   * :doc:`operational_status` - Infrastructure functionality under environmental stress

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
   * - :doc:`netcdf_player`
     - Gridded data input
     - Multi-dimensional arrays, temporal interpolation
   * - :doc:`operational_status`
     - Infrastructure status monitoring
     - Flood analysis, threshold-based, spatial queries
   * - :doc:`traffic_assignment`
     - Traffic flow modeling
     - Equilibrium assignment, capacity constraints
