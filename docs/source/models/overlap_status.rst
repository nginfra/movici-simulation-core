Overlap Status Model
====================

The Overlap Status model detects and tracks geometric overlaps between different infrastructure entities, monitoring their active status over time. It provides essential spatial relationship analysis for scenarios involving infrastructure interactions, conflict detection, and impact assessment.

Overview
--------

This model identifies where infrastructure entities geometrically overlap or are within proximity of each other. It's crucial for:

- Flood impact assessment on infrastructure
- Construction conflict detection
- Service area coverage analysis
- Infrastructure interdependency mapping
- Environmental impact zones
- Safety buffer zone monitoring

The model supports multiple geometry types and can handle complex spatial relationships with configurable distance thresholds.

Key Features
------------

- **Multi-geometry support**: Points, lines, and polygons
- **Distance-based detection**: Configurable proximity thresholds
- **Status tracking**: Monitor overlap activation conditions
- **Batch processing**: Handle multiple target entity groups
- **Dynamic updates**: Real-time overlap status changes
- **Connection mapping**: Track relationships between overlapping entities

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "flood_infrastructure_overlap",
        "type": "overlap_status",
        "output_dataset": "infrastructure_overlaps",
        "source": {
            "dataset": "flooding",
            "entity_group": "flood_areas",
            "geometry_type": "polygon"
        },
        "targets": [
            {
                "dataset": "infrastructure",
                "entity_group": "roads",
                "geometry_type": "line"
            },
            {
                "dataset": "infrastructure",
                "entity_group": "buildings",
                "geometry_type": "polygon"
            }
        ]
    }

Advanced Configuration
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "construction_overlap_detector",
        "type": "overlap_status",
        "output_dataset": "construction_conflicts",
        "distance_threshold": 50.0,
        "display_name_template": "Overlap: {source} - {target}",
        "source": {
            "dataset": "projects",
            "entity_group": "construction_zones",
            "geometry_type": "polygon",
            "status_property": "construction.active"
        },
        "targets": [
            {
                "dataset": "utilities",
                "entity_group": "power_lines",
                "geometry_type": "line",
                "status_property": "operational.status"
            },
            {
                "dataset": "utilities",
                "entity_group": "gas_pipelines",
                "geometry_type": "line",
                "status_property": "pipeline.active"
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
   * - ``output_dataset``
     - string
     - Yes
     - Dataset name for storing overlap results
   * - ``source``
     - object
     - Yes
     - Source entity configuration
   * - ``source.dataset``
     - string
     - Yes
     - Dataset containing source entities
   * - ``source.entity_group``
     - string
     - Yes
     - Entity group name for source
   * - ``source.geometry_type``
     - string
     - Yes
     - Geometry type: "point", "line", or "polygon"
   * - ``source.status_property``
     - string
     - No
     - Optional status attribute for conditional overlaps
   * - ``targets``
     - array
     - Yes
     - List of target entity configurations
   * - ``targets[].dataset``
     - string
     - Yes
     - Dataset containing target entities
   * - ``targets[].entity_group``
     - string
     - Yes
     - Entity group name for target
   * - ``targets[].geometry_type``
     - string
     - Yes
     - Geometry type: "point", "line", or "polygon"
   * - ``targets[].status_property``
     - string
     - No
     - Optional status attribute for conditional overlaps
   * - ``distance_threshold``
     - float
     - No
     - Maximum distance for overlap detection (meters)
   * - ``display_name_template``
     - string
     - No
     - Template for overlap display names

Data Requirements
-----------------

Input Data
^^^^^^^^^^

**Source Entities:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``geometry``
     - varies
     - Spatial geometry (point/line/polygon)
   * - ``id``
     - array[int]
     - Unique identifier for each entity
   * - Status property
     - array[bool]
     - Optional activation status

**Target Entities:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``geometry``
     - varies
     - Spatial geometry (point/line/polygon)
   * - ``id``
     - array[int]
     - Unique identifier for each entity
   * - Status property
     - array[bool]
     - Optional activation status

Output Data
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``overlap.active``
     - array[bool]
     - Whether overlap is currently active
   * - ``overlap.source_id``
     - array[int]
     - ID of source entity in overlap
   * - ``overlap.target_id``
     - array[int]
     - ID of target entity in overlap
   * - ``overlap.distance``
     - array[float]
     - Distance between entities (if applicable)
   * - ``overlap.intersection_area``
     - array[float]
     - Area of intersection for polygons

Geometry Overlap Rules
----------------------

The model uses specific rules for different geometry combinations:

.. list-table:: Overlap Detection Rules
   :header-rows: 1
   :widths: 20 20 60

   * - Source Type
     - Target Type
     - Overlap Condition
   * - Point
     - Point
     - Distance ≤ threshold
   * - Point
     - Line
     - Point within buffer distance of line
   * - Point
     - Polygon
     - Point inside polygon or within buffer
   * - Line
     - Line
     - Lines intersect or within threshold
   * - Line
     - Polygon
     - Line intersects or contained in polygon
   * - Polygon
     - Polygon
     - Polygons intersect or overlap

Examples
--------

Flood Impact Detection
^^^^^^^^^^^^^^^^^^^^^^

Detecting infrastructure affected by flooding:

.. code-block:: json

    {
        "name": "flood_impact_detector",
        "type": "overlap_status",
        "output_dataset": "flood_impacts",
        "source": {
            "dataset": "hydrology",
            "entity_group": "flood_zones",
            "geometry_type": "polygon",
            "status_property": "flood.depth_above_threshold"
        },
        "targets": [
            {
                "dataset": "transport",
                "entity_group": "road_segments",
                "geometry_type": "line"
            },
            {
                "dataset": "buildings",
                "entity_group": "critical_facilities",
                "geometry_type": "polygon"
            },
            {
                "dataset": "utilities",
                "entity_group": "substations",
                "geometry_type": "point"
            }
        ]
    }

Construction Safety Zones
^^^^^^^^^^^^^^^^^^^^^^^^^

Monitoring safety buffer zones around construction:

.. code-block:: json

    {
        "name": "construction_safety",
        "type": "overlap_status",
        "output_dataset": "safety_violations",
        "distance_threshold": 100.0,
        "source": {
            "dataset": "construction",
            "entity_group": "active_sites",
            "geometry_type": "polygon",
            "status_property": "site.is_active"
        },
        "targets": [
            {
                "dataset": "public",
                "entity_group": "schools",
                "geometry_type": "polygon"
            },
            {
                "dataset": "public",
                "entity_group": "hospitals",
                "geometry_type": "polygon"
            }
        ]
    }

Service Coverage Analysis
^^^^^^^^^^^^^^^^^^^^^^^^^

Analyzing emergency service coverage:

.. code-block:: json

    {
        "name": "emergency_coverage",
        "type": "overlap_status",
        "output_dataset": "coverage_analysis",
        "distance_threshold": 5000.0,
        "source": {
            "dataset": "emergency",
            "entity_group": "fire_stations",
            "geometry_type": "point"
        },
        "targets": [
            {
                "dataset": "urban",
                "entity_group": "residential_areas",
                "geometry_type": "polygon"
            },
            {
                "dataset": "urban",
                "entity_group": "commercial_zones",
                "geometry_type": "polygon"
            }
        ]
    }

Algorithm Details
-----------------

The overlap detection process:

1. **Geometry Preparation**:

   - Load source and target geometries
   - Create spatial indices for efficient lookup
   - Apply buffer zones if distance threshold specified

2. **Overlap Detection**:

   .. code-block:: python

       for source_entity in source_entities:
           for target_entity in target_entities:
               if geometries_overlap(source_entity, target_entity, threshold):
                   create_overlap_record(source_entity, target_entity)

3. **Status Evaluation**:

   - Check optional status properties
   - Overlap is active if:
     - No status properties defined, OR
     - Both source and target status properties are True

4. **Connection Mapping**:

   - Create bidirectional mappings
   - Store relationship metadata
   - Update connection indices

Performance Considerations
--------------------------

Optimization Strategies
^^^^^^^^^^^^^^^^^^^^^^^

- Use spatial indexing (R-tree) for large datasets
- Pre-filter entities by bounding boxes
- Implement distance-based early rejection
- Cache frequently accessed geometries

Scalability Guidelines
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Entity Count
     - Processing Time
     - Recommendations
   * - < 1,000
     - < 1 second
     - Brute force acceptable
   * - 1,000 - 10,000
     - 1-10 seconds
     - Use spatial indexing
   * - > 10,000
     - > 10 seconds
     - Implement tiling, parallel processing

Memory Management
^^^^^^^^^^^^^^^^^

- Stream large geometries instead of loading all
- Use simplified geometries for initial filtering
- Implement level-of-detail for complex polygons
- Clear intermediate results regularly

Best Practices
--------------

Geometry Preparation
^^^^^^^^^^^^^^^^^^^^

- Ensure consistent coordinate reference systems
- Validate geometry integrity before processing
- Simplify complex geometries where appropriate
- Use appropriate precision for coordinates

Threshold Selection
^^^^^^^^^^^^^^^^^^^

- Consider real-world impact distances
- Account for data precision limitations
- Test sensitivity to threshold changes
- Document threshold justification

Status Property Design
^^^^^^^^^^^^^^^^^^^^^^^

- Use clear boolean conditions
- Ensure status updates are timely
- Consider composite status conditions
- Document status property semantics

Common Issues and Troubleshooting
----------------------------------

No Overlaps Detected
^^^^^^^^^^^^^^^^^^^^

**Issue**: Expected overlaps not found

**Solutions**:

- Verify coordinate reference systems match
- Check distance threshold is appropriate
- Ensure geometries are valid (no self-intersections)
- Confirm entity groups contain data

Performance Degradation
^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Slow processing for large datasets

**Solutions**:

- Implement spatial indexing
- Reduce geometry complexity
- Process in geographic tiles
- Use parallel processing

Memory Overflow
^^^^^^^^^^^^^^^

**Issue**: Out of memory with many overlaps

**Solutions**:

- Process in batches
- Stream results to disk
- Limit overlap detection radius
- Use more selective status properties

Integration with Other Models
-----------------------------

The Overlap Status model integrates with:

- **Opportunities Model**: Provides overlap data for opportunity analysis
- **Operational Status Model**: Determines infrastructure functionality
- **Time Window Status Model**: Combines spatial and temporal conditions
- **Data Collector Model**: Stores overlap history

See Also
--------

- :doc:`opportunities` - For economic impact of overlaps
- :doc:`operational_status` - For infrastructure status determination
- :doc:`time_window_status` - For temporal overlap conditions
- :doc:`data_collector` - For overlap history storage

API Reference
-------------

- :class:`movici_simulation_core.models.overlap_status.OverlapStatusModel`
- :mod:`movici_simulation_core.models.overlap_status.dataset`
- :mod:`movici_simulation_core.models.overlap_status.overlap_status`
