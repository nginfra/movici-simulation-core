Area Aggregation Model
======================

.. currentmodule:: movici_simulation_core.models.area_aggregation

Overview
--------

The Area Aggregation model performs spatial aggregation of attributes from source geometries (points, lines, or polygons) to target polygon areas. This model is essential for analyzing spatial data by computing statistics like sum, average, min, max, or time-integrated values within defined geographical boundaries.

Common use cases include:

* Aggregating sensor measurements within districts or zones
* Computing total traffic flow through regions
* Calculating average pollution levels per neighborhood
* Summing population or economic indicators by administrative boundaries
* Time-integrated analysis for cumulative effects over periods

Key Features
------------

* **Multiple geometry support**: Aggregate from points, lines, or polygons
* **Various aggregation functions**: min, max, average, sum, integral (with time units)
* **Temporal integration**: Support for time-based integral calculations
* **Multiple aggregations**: Configure multiple source-to-target aggregations in one model
* **Efficient spatial indexing**: Uses movici-geo-query for fast spatial operations

Configuration Schema
--------------------

The model uses the following configuration structure:

.. code-block:: json

   {
     "name": "my_area_aggregation",
     "type": "area_aggregation",
     "target_entity_group": ["target_dataset", "target_polygons"],
     "output_interval": 3600,
     "aggregations": [
       {
         "source_entity_group": ["source_dataset", "source_entities"],
         "source_attribute": "measurement_value",
         "target_attribute": "aggregated_value",
         "function": "average",
         "source_geometry": "point"
       }
     ]
   }

Configuration Parameters
------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Parameter
     - Type
     - Description
   * - ``target_entity_group``
     - array[string, string]
     - **Required**. Target dataset and entity group name for aggregated results. Must be polygon entities.
   * - ``aggregations``
     - array[object]
     - **Required**. List of aggregation configurations. Each defines a source-to-target mapping.
   * - ``output_interval``
     - number or null
     - Optional. Time interval (seconds) for outputting results. If null, outputs every update.

Aggregation Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~

Each aggregation in the ``aggregations`` array has:

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Parameter
     - Type
     - Description
   * - ``source_entity_group``
     - array[string, string]
     - **Required**. Source dataset and entity group name [dataset_name, entity_name].
   * - ``source_attribute``
     - string
     - **Required**. Name of the attribute to aggregate from source entities.
   * - ``target_attribute``
     - string
     - **Required**. Name of the attribute to store aggregated results in target entities.
   * - ``function``
     - string
     - **Required**. Aggregation function. See supported functions below.
   * - ``source_geometry``
     - string
     - **Required**. Geometry type of source entities: "point", "line", or "polygon".

Supported Aggregation Functions
-------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Function
     - Description
   * - ``min``
     - Minimum value of all source entities within each target polygon
   * - ``max``
     - Maximum value of all source entities within each target polygon
   * - ``average``
     - Average (mean) value of all source entities within each target polygon
   * - ``sum``
     - Sum of all source entity values within each target polygon
   * - ``integral``
     - Time-integrated value (area under curve) in base time units
   * - ``integral_seconds``
     - Time-integrated value with result in value·seconds
   * - ``integral_minutes``
     - Time-integrated value with result in value·minutes
   * - ``integral_hours``
     - Time-integrated value with result in value·hours
   * - ``integral_days``
     - Time-integrated value with result in value·days

Data Requirements
-----------------

Input Requirements
~~~~~~~~~~~~~~~~~~

* **Target polygons**: Must exist in the specified target dataset with valid polygon geometries
* **Source entities**: Must have the specified geometry type and contain the source attribute
* **Spatial overlap**: Source entities must spatially intersect with target polygons for aggregation

Output Attributes
~~~~~~~~~~~~~~~~~

The model creates or updates the specified ``target_attribute`` in the target polygon entities with the aggregated values. The attribute type is always float/double.

Examples
--------

Example 1: Average Temperature by District
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Aggregate temperature sensor readings to compute average temperature per district:

.. code-block:: json

   {
     "name": "district_temperature",
     "type": "area_aggregation",
     "target_entity_group": ["administrative", "districts"],
     "aggregations": [
       {
         "source_entity_group": ["sensors", "temperature_sensors"],
         "source_attribute": "temperature",
         "target_attribute": "average_temperature",
         "function": "average",
         "source_geometry": "point"
       }
     ]
   }

Example 2: Total Traffic Flow Through Regions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sum traffic flow from road segments within each region:

.. code-block:: json

   {
     "name": "regional_traffic_flow",
     "type": "area_aggregation",
     "target_entity_group": ["regions", "analysis_zones"],
     "output_interval": 900,
     "aggregations": [
       {
         "source_entity_group": ["transport", "road_segments"],
         "source_attribute": "vehicle_flow",
         "target_attribute": "total_vehicle_flow",
         "function": "sum",
         "source_geometry": "line"
       },
       {
         "source_entity_group": ["transport", "road_segments"],
         "source_attribute": "vehicle_speed",
         "target_attribute": "average_speed",
         "function": "average",
         "source_geometry": "line"
       }
     ]
   }

Example 3: Cumulative Exposure Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Calculate time-integrated pollution exposure per neighborhood:

.. code-block:: json

   {
     "name": "pollution_exposure",
     "type": "area_aggregation",
     "target_entity_group": ["city", "neighborhoods"],
     "aggregations": [
       {
         "source_entity_group": ["environment", "pollution_zones"],
         "source_attribute": "pm25_concentration",
         "target_attribute": "cumulative_pm25_exposure",
         "function": "integral_hours",
         "source_geometry": "polygon"
       }
     ]
   }

Performance Considerations
--------------------------

* **Spatial indexing**: The model uses efficient spatial indexing for overlap detection
* **Large datasets**: For datasets with many source entities, consider the computational cost
* **Update frequency**: Use ``output_interval`` to control update frequency and reduce computation
* **Memory usage**: Aggregating from high-resolution grids may require significant memory

Best Practices
--------------

1. **Geometry alignment**: Ensure source and target geometries use the same coordinate reference system
2. **Attribute initialization**: Target attributes are automatically created if they don't exist
3. **Null handling**: Entities without the source attribute are skipped in aggregation
4. **Time integrals**: For integral functions, ensure consistent time steps in your simulation
5. **Multiple aggregations**: Group related aggregations in a single model instance for efficiency

Common Issues and Solutions
---------------------------

**Issue**: No aggregated values appearing
   * Check spatial overlap between source and target geometries
   * Verify source attribute exists and has non-null values
   * Ensure geometries are in the same CRS

**Issue**: Unexpected aggregation results
   * Verify the correct aggregation function is selected
   * Check for overlapping source geometries that might be double-counted
   * For averages, confirm the number of entities being averaged

**Issue**: Performance problems with large datasets
   * Use ``output_interval`` to reduce update frequency
   * Consider spatial partitioning of input data
   * Pre-filter source entities to relevant spatial extent

Integration with Other Models
-----------------------------

The Area Aggregation model works well with:

* **CSV Player**: Import time-series data for aggregation
* **NetCDF Player**: Aggregate gridded climate or environmental data
* **Traffic Assignment**: Aggregate traffic metrics by zones
* **Data Collector**: Store aggregated time-series results

See Also
--------

* :doc:`/creating_models/geospatial_queries` - Understanding spatial queries in Movici
* :doc:`/tutorials/data_preparation` - Preparing spatial data for aggregation
* :class:`~movici_simulation_core.models.area_aggregation.model.Model` - API reference