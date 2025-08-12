Operational Status Model
========================

.. currentmodule:: movici_simulation_core.models.operational_status

Overview
--------

The Operational Status model determines the operational state of infrastructure entities based on environmental conditions, particularly focusing on flooding impacts. It analyzes how environmental hazards affect the functionality of transport networks, buildings, or other infrastructure by applying thresholds and spatial analysis.

This model is essential for:

* **Resilience analysis**: Understanding infrastructure vulnerability to environmental hazards
* **Risk assessment**: Identifying critical infrastructure at risk during extreme events
* **Emergency planning**: Supporting evacuation route planning and resource allocation
* **Climate adaptation**: Evaluating infrastructure performance under changing conditions
* **Real-time monitoring**: Updating operational status based on current environmental data

Key Features
------------

* **Multi-hazard support**: Extensible framework for different environmental hazards
* **Flooding analysis**: Built-in support for flood impact assessment
* **Spatial analysis**: Uses geometric queries to relate hazards to infrastructure
* **Threshold-based logic**: Configurable thresholds for operational state determination
* **Multiple geometries**: Works with points, lines, and polygons
* **Dynamic updates**: Continuously updates status based on changing conditions

Configuration Schema
--------------------

.. code-block:: json

   {
     "name": "infrastructure_status",
     "type": "operational_status",
     "entity_group": ["infrastructure", "road_segments"],
     "geometry": "line",
     "elevation_attribute": "elevation",
     "flooding": {
       "flooding_cells": ["flood_model", "grid_cells"],
       "flooding_points": ["flood_model", "water_points"],
       "flooding_threshold": 0.1
     }
   }

Configuration Parameters
------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Parameter
     - Type
     - Description
   * - ``entity_group``
     - array[string, string]
     - **Required**. Target infrastructure [dataset_name, entity_group_name]
   * - ``geometry``
     - string
     - **Required**. Geometry type: "point", "line", or "polygon"
   * - ``elevation_attribute``
     - string
     - **Optional**. Attribute name for entity elevation/height data
   * - ``flooding``
     - object
     - **Optional**. Flooding analysis configuration

Flooding Configuration
~~~~~~~~~~~~~~~~~~~~~~

The ``flooding`` object configures flood impact analysis:

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Parameter
     - Type
     - Description
   * - ``flooding_cells``
     - array[string, string]
     - **Required**. Grid cells with flood data [dataset_name, entity_group_name]
   * - ``flooding_points``
     - array[string, string]
     - **Required**. Point measurements [dataset_name, entity_group_name]
   * - ``flooding_threshold``
     - number
     - **Optional**. Water depth threshold (meters) for operational impact. Default varies by use case

Data Requirements
-----------------

Target Infrastructure
~~~~~~~~~~~~~~~~~~~~~

The target entities must have:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Description
   * - ``geometry``
     - Spatial geometry (points, lines, or polygons)
   * - ``elevation`` (optional)
     - Height/elevation above reference level (meters)

Flooding Data Sources
~~~~~~~~~~~~~~~~~~~~~

For flood analysis, the model requires:

**Flooding Cells** (grid-based flood data):

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Description
   * - ``geometry``
     - Grid cell polygons
   * - ``flooding.water_height``
     - Water surface elevation (meters above reference)
   * - ``flooding.water_depth``
     - Water depth above ground (meters)

**Flooding Points** (measurement points):

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Description
   * - ``geometry``
     - Point locations
   * - ``flooding.water_height``
     - Water surface elevation at point
   * - ``flooding.water_depth``
     - Water depth at point

Output Attributes
-----------------

The model publishes operational status indicators:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Attribute
     - Description
   * - ``operational_status``
     - Boolean indicating if entity is operational (True) or impacted (False)
   * - ``flooding_depth`` (optional)
     - Computed water depth affecting the entity (meters)
   * - ``flooding_height`` (optional)
     - Water surface elevation at entity location (meters)

Analysis Methods
----------------

Spatial Water Depth Calculation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The model determines water conditions at infrastructure locations using:

1. **Grid-based interpolation**: For entities overlapping flood grid cells
2. **Point-based queries**: Spatial queries to nearby flood measurement points
3. **Elevation adjustment**: Accounts for infrastructure elevation relative to ground
4. **Maximum depth selection**: Uses worst-case scenario when multiple sources available

Operational Status Determination
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Infrastructure is considered **non-operational** when:

* Water depth exceeds the configured ``flooding_threshold``
* No threshold specified: any measurable flooding impacts operations
* Spatial queries indicate entity is within flooded areas

Examples
--------

Example 1: Road Network Flood Impact
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Assess road segment operability during flooding:

.. code-block:: json

   {
     "name": "road_flood_status",
     "type": "operational_status",
     "entity_group": ["transport", "road_segments"],
     "geometry": "line",
     "elevation_attribute": "road_elevation",
     "flooding": {
       "flooding_cells": ["flood_simulation", "inundation_grid"],
       "flooding_points": ["sensors", "water_level_gauges"],
       "flooding_threshold": 0.15
     }
   }

This configuration:
   * Monitors road segments for flood impacts
   * Uses both grid-based flood simulation and sensor data
   * Considers roads non-operational when water depth exceeds 15cm
   * Accounts for road elevation in calculations

Example 2: Building Vulnerability Assessment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Evaluate building operational status:

.. code-block:: json

   {
     "name": "building_flood_risk",
     "type": "operational_status",
     "entity_group": ["infrastructure", "buildings"],
     "geometry": "polygon",
     "elevation_attribute": "floor_height",
     "flooding": {
       "flooding_cells": ["flood_model", "flood_grid"],
       "flooding_points": ["monitoring", "flood_sensors"],
       "flooding_threshold": 0.05
     }
   }

Example 3: Critical Infrastructure Monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Monitor hospitals and emergency services:

.. code-block:: json

   {
     "name": "critical_infrastructure",
     "type": "operational_status",
     "entity_group": ["emergency", "hospitals"],
     "geometry": "point",
     "flooding": {
       "flooding_cells": ["real_time_flood", "flood_cells"],
       "flooding_points": ["gauges", "river_stations"],
       "flooding_threshold": 0.02
     }
   }

Use Cases by Threshold
----------------------

Threshold Selection Guidelines
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Infrastructure Type
     - Typical Threshold
     - Rationale
   * - Road segments
     - 0.10 - 0.20m
     - Vehicle passage becomes dangerous
   * - Railways
     - 0.05 - 0.10m
     - Track stability and signaling issues
   * - Buildings (ground floor)
     - 0.02 - 0.05m
     - Equipment damage and safety concerns
   * - Bridges
     - varies
     - Depends on clearance and structural design
   * - Airports
     - 0.03 - 0.10m
     - Runway safety and aircraft operations

Temporal Considerations
-----------------------

Dynamic Status Updates
~~~~~~~~~~~~~~~~~~~~~

* Status updates automatically when flood conditions change
* Model recalculates spatial relationships at each time step
* Can handle both rapidly changing (flash floods) and slowly evolving situations

Event Duration Analysis
~~~~~~~~~~~~~~~~~~~~~~

* Tracks operational status over time
* Can identify infrastructure repeatedly affected by flooding
* Supports recovery time analysis when water levels recede

Performance Considerations
-------------------------

Spatial Query Optimization
~~~~~~~~~~~~~~~~~~~~~~~~~~

* Uses efficient spatial indexing for geometry intersections
* Performance scales with number of entities and flood data points
* Grid-based data generally faster than point-based queries

Memory Usage
~~~~~~~~~~~~

* Spatial indices require memory proportional to entity count
* Large flood grids may require significant memory
* Consider spatial extent when defining flood data coverage

Best Practices
--------------

1. **Threshold Calibration**: Use local knowledge and historical data to set appropriate thresholds
2. **Data Quality**: Ensure flood data and infrastructure elevations use consistent vertical reference systems
3. **Spatial Resolution**: Match flood data resolution to infrastructure analysis needs
4. **Validation**: Compare model results with historical flood impacts for calibration
5. **Update Frequency**: Consider computational cost vs. required temporal resolution

Common Issues and Solutions
---------------------------

**Issue**: All infrastructure shows as flooded or none shows as flooded
   * Check coordinate reference systems are consistent between datasets
   * Verify threshold values are appropriate for water depth units
   * Ensure spatial overlap between infrastructure and flood data

**Issue**: Inconsistent results between grid and point-based flood data
   * Check temporal alignment of different flood data sources
   * Verify elevation references are consistent
   * Consider data quality differences between sources

**Issue**: Performance problems with large datasets
   * Reduce spatial extent to area of interest
   * Use lower resolution flood grids if appropriate
   * Consider pre-filtering infrastructure to areas at risk

Integration with Other Models
-----------------------------

The Operational Status model works well with:

* **Traffic Assignment**: Update network capacity based on operational status
* **Corridor Analysis**: Account for flooded routes in corridor performance
* **Area Aggregation**: Aggregate operational statistics by administrative regions
* **Data Collector**: Store operational status time series for analysis

Future Extensions
-----------------

The modular design supports additional hazard modules:

* **Wind damage**: High wind speed impacts on infrastructure
* **Temperature effects**: Extreme heat/cold operational limits
* **Seismic impacts**: Earthquake damage assessment
* **Multi-hazard**: Combined effects of multiple environmental stressors

See Also
--------

* :doc:`/creating_models/geospatial_queries` - Understanding spatial analysis in Movici
* :doc:`/tutorials/data_preparation` - Preparing flood and infrastructure data
* :doc:`area_aggregation` - For aggregating operational statistics
* :class:`~movici_simulation_core.models.operational_status.operational_status.OperationalStatus` - API reference
