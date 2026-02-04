.. |required| replace:: (**required**)

Area Aggregation Model
======================

The area aggregation model (``"area_aggregation"``) aggregates attribute values
from source entities (points, lines, or polygons) to target polygon areas.

Use cases include:

* Aggregating traffic flows from road segments to municipality boundaries
* Computing maximum emissions within administrative areas
* Calculating cumulative metrics over time within geographic regions

Aggregation Functions
---------------------

The model supports the following aggregation functions:

**Instantaneous functions**

* ``min`` - Minimum value of source entities within each target area
* ``max`` - Maximum value of source entities within each target area
* ``average`` - Weighted average of source values (weights based on entity overlap)
* ``sum`` - Weighted sum of source values

**Time-integral functions**

* ``integral`` / ``integral_seconds`` - Cumulative sum over time (in seconds)
* ``integral_minutes`` - Cumulative sum over time (in minutes)
* ``integral_hours`` - Cumulative sum over time (in hours)
* ``integral_days`` - Cumulative sum over time (in days)

Source Geometries
-----------------

The model determines which source entities fall within each target polygon based
on the ``source_geometry`` setting:

* ``point`` - Point entities are matched if they fall within the target polygon
* ``line`` - Line entities are matched if they intersect the target polygon
* ``polygon`` - Polygon entities are matched if they intersect the target polygon

When a source entity overlaps multiple target polygons, its contribution is
weighted proportionally.

Configuration Options
---------------------

+--------------------+---------+-------------------------------------------------------+
| Option             | Type    | Description                                           |
+====================+=========+=======================================================+
| target_entity_group| array   | ``[dataset_name, entity_group_name]`` for target      |
|                    |         | polygons (required)                                   |
+--------------------+---------+-------------------------------------------------------+
| aggregations       | array   | List of aggregation configurations (required)         |
+--------------------+---------+-------------------------------------------------------+
| output_interval    | number  | Interval in seconds between outputs (optional)        |
+--------------------+---------+-------------------------------------------------------+

Aggregation Configuration
-------------------------

Each aggregation in the ``aggregations`` array has the following options:

+--------------------+---------+-------------------------------------------------------+
| Option             | Type    | Description                                           |
+====================+=========+=======================================================+
| source_entity_group| array   | ``[dataset_name, entity_group_name]`` for source      |
|                    |         | entities                                              |
+--------------------+---------+-------------------------------------------------------+
| source_attribute   | string  | Attribute to aggregate from source entities           |
+--------------------+---------+-------------------------------------------------------+
| target_attribute   | string  | Attribute to store aggregated values                  |
+--------------------+---------+-------------------------------------------------------+
| function           | string  | Aggregation function (see above)                      |
+--------------------+---------+-------------------------------------------------------+
| source_geometry    | string  | Source geometry type: ``"point"``, ``"line"``, or     |
|                    |         | ``"polygon"``                                         |
+--------------------+---------+-------------------------------------------------------+

Example Configurations
----------------------

Aggregating traffic flows to municipalities:

.. code-block:: json

    {
        "name": "railway_municipalities_aggregation",
        "type": "area_aggregation",
        "target_entity_group": ["municipalities_area_set", "area_entities"],
        "aggregations": [
            {
                "function": "max",
                "source_geometry": "line",
                "source_attribute": "transport.cargo_flow",
                "target_attribute": "transport.cargo_flow.railways",
                "source_entity_group": ["railway_network", "track_segment_entities"]
            },
            {
                "function": "integral_hours",
                "source_geometry": "line",
                "source_attribute": "transport.energy_consumption.hours",
                "target_attribute": "transport.cumulative_energy",
                "source_entity_group": ["railway_network", "track_segment_entities"]
            }
        ]
    }

Multiple source datasets to single target:

.. code-block:: json

    {
        "name": "road_aggregation",
        "type": "area_aggregation",
        "target_entity_group": ["municipalities_area_set", "area_entities"],
        "aggregations": [
            {
                "source_entity_group": ["road_network", "road_segment_entities"],
                "source_attribute": "transport.passenger_vehicle_flow",
                "target_attribute": "transport.passenger_vehicle_flow",
                "function": "max",
                "source_geometry": "line"
            },
            {
                "source_entity_group": ["road_network", "road_segment_entities"],
                "source_attribute": "transport.cargo_vehicle_flow",
                "target_attribute": "transport.cargo_vehicle_flow",
                "function": "max",
                "source_geometry": "line"
            }
        ]
    }

Notes
-----

* When a source entity overlaps multiple target polygons, its contribution is
  split proportionally between the overlapping targets.

* Time-integral functions accumulate values over the simulation duration. The
  target attribute is initialized to zero and updated incrementally.

* The ``output_interval`` option can be used to control how frequently the
  model produces outputs, which can reduce storage requirements for
  time-integral calculations.

Config Schema Reference
-----------------------

AreaAggregationConfig
^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``target_entity_group``: :ref:`AreaAggregationEntityGroup` |required|
  | ``aggregations``: :ref:`Aggregations` |required|
  | ``output_interval``: ``number`` Interval in seconds between outputs

.. _AreaAggregationEntityGroup:

AreaAggregationEntityGroup
^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``

.. _Aggregations:

Aggregations
^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`Aggregation`
| ``minItems``: 1

.. _Aggregation:

Aggregation
^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``source_entity_group``: :ref:`AreaAggregationEntityGroup` |required|
  | ``source_attribute``: ``string`` Attribute to aggregate from source entities |required|
  | ``target_attribute``: ``string`` Attribute to store aggregated values |required|
  | ``function``: ``string`` Aggregation function: ``"min"``, ``"max"``, ``"average"``, ``"sum"``, ``"integral"``, ``"integral_seconds"``, ``"integral_minutes"``, ``"integral_hours"``, or ``"integral_days"`` |required|
  | ``source_geometry``: ``string`` Source geometry type: ``"point"``, ``"line"``, or ``"polygon"`` |required|
