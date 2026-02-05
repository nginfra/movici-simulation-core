.. |required| replace:: (**required**)

Operational Status Model
========================

The operational status model (``"operational_status"``) calculates the impact
of external hazards on infrastructure entities. Currently supports flooding
impact calculation.

Use cases include:

* Calculating water depth at infrastructure locations during floods
* Determining which assets are affected by flood events
* Providing input for cascading failure models

How It Works
------------

**Flooding Module:**

1. Maps flooding grid cells to target entity locations using spatial queries
2. For each entity, finds overlapping grid cells
3. Calculates water depth as maximum water height minus entity elevation
4. Publishes water depth to target entities

For line and polygon entities, the model considers the elevation at each
vertex and takes the maximum water depth across all points.

Configuration Options
---------------------

+--------------+---------+----------------------------------------------------------+
| Option       | Type    | Description                                              |
+==============+=========+==========================================================+
| entity_group | array   | ``[dataset_name, entity_group_name]`` for targets        |
+--------------+---------+----------------------------------------------------------+
| geometry     | string  | Target geometry: ``"point"``, ``"line"``, ``"polygon"``  |
+--------------+---------+----------------------------------------------------------+
| flooding     | object  | Flooding module configuration (optional)                 |
+--------------+---------+----------------------------------------------------------+

Flooding Configuration
----------------------

+------------------+---------+--------------------------------------------------+
| Option           | Type    | Description                                      |
+==================+=========+==================================================+
| flooding_cells   | array   | ``[dataset_name, entity_group_name]`` for cells  |
+------------------+---------+--------------------------------------------------+
| flooding_points  | array   | ``[dataset_name, entity_group_name]`` for points |
+------------------+---------+--------------------------------------------------+

Note: ``flooding_cells`` and ``flooding_points`` must be in the same dataset.

Example Configuration
---------------------

.. code-block:: json

    {
        "name": "road_flooding_status",
        "type": "operational_status",
        "entity_group": ["road_network", "road_segment_entities"],
        "geometry": "line",
        "flooding": {
            "flooding_cells": ["flooding_grid", "grid_cell_entities"],
            "flooding_points": ["flooding_grid", "grid_point_entities"]
        }
    }

Input Requirements
------------------

**Target entities** must have:

* 3D geometry (x, y, z coordinates) for elevation

**Flooding grid** must have:

* ``flooding.water_height`` attribute on grid cells

Output Attributes
-----------------

+---------------------------+---------------------------------------------------+
| Attribute                 | Description                                       |
+===========================+===================================================+
| ``flooding.water_depth``  | Water depth above entity surface (meters)         |
+---------------------------+---------------------------------------------------+

Notes
-----

* Water depth is calculated as: ``max(water_height - elevation, 0)``
* For entities below the water surface, depth is positive
* Entities above the water surface have depth of 0
* The model uses the maximum water height from all overlapping grid cells

Config Schema Reference
-----------------------

OperationalStatusConfig
^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``entity_group``: :ref:`OperationalStatusEntityGroup` |required|
  | ``geometry``: ``string`` Target geometry type: ``"point"``, ``"line"``, or ``"polygon"`` |required|
  | ``flooding``: :ref:`OperationalStatusFlooding` Flooding module configuration

.. _OperationalStatusEntityGroup:

OperationalStatusEntityGroup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``

.. _OperationalStatusFlooding:

OperationalStatusFlooding
^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``flooding_cells``: :ref:`OperationalStatusEntityGroup` Entity group for flood grid cells |required|
  | ``flooding_points``: :ref:`OperationalStatusEntityGroup` Entity group for flood grid points |required|
