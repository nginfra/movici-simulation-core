Evacuation Point Resolution Model
==================================

The Evacuation Point Resolution model maps road segments to designated evacuation points during emergency scenarios. It resolves the assignment of evacuation points to road infrastructure by matching road segment IDs with evacuation point road IDs, enabling efficient evacuation route planning and analysis.

Overview
--------

This model is essential for emergency management simulations where you need to:

- Assign evacuation points to road segments
- Map evacuation routes to safe zones
- Analyze evacuation point coverage
- Identify unassigned road segments

The model uses Compressed Sparse Row (CSR) arrays for efficient storage and processing of road-to-evacuation-point mappings, making it suitable for large-scale urban evacuation scenarios.

Key Features
------------

- **ID-based mapping**: Matches road segment IDs with evacuation point road IDs
- **Label resolution**: Assigns evacuation point labels to corresponding road segments
- **Efficient storage**: Uses CSR arrays for memory-efficient road ID storage
- **Special value handling**: Manages undefined assignments with configurable special values
- **Batch processing**: Processes all mappings in a single update cycle

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "evacuation_resolver",
        "type": "evacuation_point_resolution",
        "dataset": "infrastructure",
        "evacuation_points": {
            "entity_group": "evacuation_points",
            "property": "evacuation.point_label"
        },
        "road_segments": {
            "entity_group": "road_segments",
            "property": "evacuation.point_id"
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
   * - ``dataset``
     - string
     - Yes
     - Name of the dataset containing evacuation and road data
   * - ``evacuation_points``
     - object
     - Yes
     - Configuration for evacuation point entities
   * - ``evacuation_points.entity_group``
     - string
     - Yes
     - Entity group containing evacuation points
   * - ``evacuation_points.property``
     - string
     - Yes
     - Attribute containing evacuation point labels
   * - ``road_segments``
     - object
     - Yes
     - Configuration for road segment entities
   * - ``road_segments.entity_group``
     - string
     - Yes
     - Entity group containing road segments
   * - ``road_segments.property``
     - string
     - Yes
     - Output attribute for evacuation point assignments

Data Requirements
-----------------

Input Data
^^^^^^^^^^

**Evacuation Points Entity Group:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``evacuation.road_ids``
     - CSR array
     - IDs of road segments associated with each evacuation point
   * - ``evacuation.point_label``
     - array[int]
     - Unique label/ID for each evacuation point

**Road Segments Entity Group:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``id``
     - array[int]
     - Unique identifier for each road segment

Output Data
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``evacuation.point_id``
     - array[int]
     - Assigned evacuation point ID for each road segment
   * - Special value (-9999)
     - int
     - Indicates unassigned road segments

Examples
--------

Urban Evacuation Scenario
^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration for city-wide evacuation planning:

.. code-block:: json

    {
        "name": "city_evacuation",
        "type": "evacuation_point_resolution",
        "dataset": "city_infrastructure",
        "evacuation_points": {
            "entity_group": "evacuation_shelters",
            "property": "shelter.id"
        },
        "road_segments": {
            "entity_group": "city_roads",
            "property": "assigned.shelter_id"
        }
    }

Multi-Zone Evacuation
^^^^^^^^^^^^^^^^^^^^^^

Configuration for regional evacuation with multiple zones:

.. code-block:: json

    {
        "name": "regional_evacuation",
        "type": "evacuation_point_resolution",
        "dataset": "regional_network",
        "evacuation_points": {
            "entity_group": "safe_zones",
            "property": "zone.identifier"
        },
        "road_segments": {
            "entity_group": "highways",
            "property": "evacuation.zone_assignment"
        }
    }

Coastal Evacuation Routes
^^^^^^^^^^^^^^^^^^^^^^^^^

Configuration for tsunami evacuation planning:

.. code-block:: json

    {
        "name": "tsunami_evacuation",
        "type": "evacuation_point_resolution",
        "dataset": "coastal_infrastructure",
        "evacuation_points": {
            "entity_group": "high_ground_points",
            "property": "elevation.point_id"
        },
        "road_segments": {
            "entity_group": "coastal_roads",
            "property": "evacuation.high_ground_id"
        }
    }

Algorithm Details
-----------------

The model performs the following steps:

1. **Load evacuation point data**: Retrieves road IDs and labels from evacuation points
2. **Create mapping dictionary**: Builds a mapping from road IDs to evacuation point labels
3. **Process road segments**: For each road segment:

   - Check if segment ID exists in the mapping
   - Assign corresponding evacuation point label if found
   - Assign special value (-9999) if no mapping exists

4. **Update attributes**: Write assignments to the specified road segment attribute

The CSR array structure allows efficient storage of variable-length road ID lists per evacuation point, minimizing memory usage for sparse assignments.

Best Practices
--------------

Data Preparation
^^^^^^^^^^^^^^^^

- Ensure all road segment IDs are unique and consistent
- Verify evacuation point road ID arrays are properly formatted as CSR
- Use meaningful evacuation point labels for easier analysis
- Consider geographic proximity when assigning road IDs to evacuation points

Performance Optimization
^^^^^^^^^^^^^^^^^^^^^^^^

- Pre-process road ID assignments to minimize lookup operations
- Use appropriate data types for IDs (int32 vs int64 based on range)
- Batch multiple evacuation scenarios in separate model instances
- Consider spatial indexing for large road networks

Integration Guidelines
^^^^^^^^^^^^^^^^^^^^^^

- Combine with shortest path models for route optimization
- Use with traffic assignment models for capacity analysis
- Integrate with time window models for phased evacuations
- Connect to visualization tools for evacuation coverage maps

Common Issues and Troubleshooting
----------------------------------

No Assignments Found
^^^^^^^^^^^^^^^^^^^^

**Issue**: All road segments receive the special value (-9999)

**Solutions**:

- Verify road IDs in evacuation points match road segment IDs exactly
- Check data type compatibility between ID attributes
- Ensure CSR array is properly formatted with correct indices

Partial Coverage
^^^^^^^^^^^^^^^^

**Issue**: Some road segments remain unassigned despite evacuation points

**Solutions**:

- Review evacuation point road ID arrays for completeness
- Check for disconnected road network segments
- Verify all evacuation points have associated road IDs
- Consider increasing evacuation point coverage area

Memory Issues
^^^^^^^^^^^^^

**Issue**: Large memory consumption with extensive road networks

**Solutions**:

- Optimize CSR array compression
- Process regions separately if possible
- Use appropriate integer types for IDs
- Consider hierarchical evacuation point assignment

Integration with Other Models
-----------------------------

The Evacuation Point Resolution model works well with:

- **Shortest Path Model**: Calculate optimal evacuation routes from assigned points
- **Traffic Assignment Model**: Analyze evacuation traffic flow and bottlenecks
- **Time Window Status Model**: Implement phased evacuation schedules
- **Operational Status Model**: Account for infrastructure damage affecting routes

See Also
--------

- :doc:`shortest_path` - For evacuation route calculation
- :doc:`traffic_assignment` - For evacuation traffic analysis
- :doc:`time_window_status` - For evacuation scheduling
- :doc:`operational_status` - For infrastructure availability

API Reference
-------------

- :class:`movici_simulation_core.models.evacuation_point_resolution.EvacuationPointResolutionModel`
