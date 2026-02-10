.. |required| replace:: (**required**)

Overlap Status Model
====================

The overlap status model (``"overlap_status"``) detects spatial proximity
between source and target infrastructure entities and publishes overlap records.

Use cases include:

* Detecting when infrastructure assets are within a specified distance
* Creating input for coordination analysis (see :doc:`opportunities`)
* Monitoring spatial relationships between different infrastructure types

How It Works
------------

1. At initialization, calculates distances between source and target entities
2. Entity pairs within the distance threshold are identified
3. Overlap records are published to a dedicated output dataset
4. Status updates track when overlaps become active/inactive

Configuration Options
---------------------

+----------------------+---------+--------------------------------------------------+
| Option               | Type    | Description                                      |
+======================+=========+==================================================+
| output_dataset       | string  | Dataset name for overlap records (required)      |
+----------------------+---------+--------------------------------------------------+
| source               | object  | Source entity configuration (required)           |
+----------------------+---------+--------------------------------------------------+
| targets              | array   | List of target configurations (required)         |
+----------------------+---------+--------------------------------------------------+
| distance_threshold   | number  | Maximum distance for overlap detection (meters)  |
+----------------------+---------+--------------------------------------------------+
| display_name_template| string  | Template for overlap display names               |
+----------------------+---------+--------------------------------------------------+

Source and Target Configuration
-------------------------------

Each source/target configuration has:

+-------------------+---------+--------------------------------------------------+
| Option            | Type    | Description                                      |
+===================+=========+==================================================+
| entity_group      | array   | ``[dataset_name, entity_group_name]``            |
+-------------------+---------+--------------------------------------------------+
| geometry          | string  | ``"point"``, ``"line"``, or ``"polygon"``        |
+-------------------+---------+--------------------------------------------------+
| status_attribute  | string  | Boolean attribute for active status (optional)   |
+-------------------+---------+--------------------------------------------------+

Example Configuration
---------------------

Detect overlaps between roads and cables:

.. code-block:: json

    {
        "name": "road_cable_overlaps",
        "type": "overlap_status",
        "output_dataset": "road_cable_overlap_records",
        "distance_threshold": 10.0,
        "source": {
            "entity_group": ["road_network", "road_segment_entities"],
            "geometry": "line",
            "status_attribute": "maintenance.excavation_active"
        },
        "targets": [
            {
                "entity_group": ["cable_network", "cable_segment_entities"],
                "geometry": "line",
                "status_attribute": "maintenance.replacement_planned"
            }
        ]
    }

Output Dataset
--------------

The model publishes overlap records with the following attributes:

+--------------------------------+---------------------------------------------------+
| Attribute                      | Description                                       |
+================================+===================================================+
| ``overlap.active``             | Boolean indicating if overlap is currently active |
+--------------------------------+---------------------------------------------------+
| ``connection.from_dataset``    | Source entity dataset name                        |
+--------------------------------+---------------------------------------------------+
| ``connection.from_id``         | Source entity ID                                  |
+--------------------------------+---------------------------------------------------+
| ``connection.to_dataset``      | Target entity dataset name                        |
+--------------------------------+---------------------------------------------------+
| ``connection.to_id``           | Target entity ID                                  |
+--------------------------------+---------------------------------------------------+

Status Attributes
-----------------

If ``status_attribute`` is specified:

* An overlap becomes **active** when both source and target status attributes
  are true (or when one is true and the other has no status attribute)
* The overlap is **inactive** when either status is false

If no status attributes are specified, overlaps are considered active based
solely on spatial proximity.

Config Schema Reference
-----------------------

OverlapStatusConfig
^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``output_dataset``: ``string`` Dataset name for overlap records |required|
  | ``source``: :ref:`OverlapEntityConfig` Source entity configuration |required|
  | ``targets``: :ref:`OverlapTargets` List of target configurations |required|
  | ``distance_threshold``: ``number`` Maximum distance for overlap detection (meters)
  | ``display_name_template``: ``string`` Template for overlap display names

.. _OverlapEntityConfig:

OverlapEntityConfig
^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``entity_group``: :ref:`OverlapEntityGroup` |required|
  | ``geometry``: ``string`` Geometry type: ``"point"``, ``"line"``, or ``"polygon"`` |required|
  | ``status_attribute``: ``string`` Boolean attribute for active status

.. _OverlapTargets:

OverlapTargets
^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`OverlapEntityConfig`
| ``minItems``: 1

.. _OverlapEntityGroup:

OverlapEntityGroup
^^^^^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``
