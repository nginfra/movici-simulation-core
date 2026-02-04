.. |required| replace:: (**required**)

Shortest Path Model
===================

The shortest path model (``"shortest_path"``) computes aggregated values along
shortest paths between nodes in a transport network. It can calculate either
the sum or weighted average of link attributes along each shortest path.

Use cases include:

* Computing travel distances or times between origin-destination pairs
* Calculating accessibility metrics
* Aggregating lane lengths along routes

Calculation Types
-----------------

The model supports two calculation types:

**sum**
    Sums the input attribute values along the shortest path. For example,
    summing ``shape.length`` gives the total path distance.

**weighted_average**
    Computes a weighted average of the input attribute along the path,
    where the weights are determined by the ``cost_factor`` attribute.

Output Modes
------------

**All-pairs (default)**
    When no single source is specified, the model outputs an N×N CSR matrix
    where element (i,j) contains the aggregated value from node i to node j.

**Single-source**
    When ``single_source_entity_id`` or ``single_source_entity_reference`` is
    specified, the model outputs a 1D array with values from the source node
    to all other nodes.

Dataset Requirements
--------------------

The model expects a transport network dataset with the following entity groups:

* ``virtual_node_entities`` - Origin/destination nodes
* ``virtual_link_entities`` - Connections between virtual and transport nodes
* ``transport_node_entities`` - Internal network nodes
* Transport segment entities (e.g., ``road_segment_entities``, ``track_segment_entities``,
  ``waterway_segment_entities``)

Configuration Options
---------------------

+-------------------------------+---------+---------------------------------------------------+
| Option                        | Type    | Description                                       |
+===============================+=========+===================================================+
| transport_segments            | array   | ``[dataset_name, entity_group_name]`` (required)  |
+-------------------------------+---------+---------------------------------------------------+
| cost_factor                   | string  | Attribute used as edge weights for pathfinding    |
|                               |         | (required)                                        |
+-------------------------------+---------+---------------------------------------------------+
| calculations                  | array   | List of calculations to perform (required)        |
+-------------------------------+---------+---------------------------------------------------+
| no_update_shortest_path       | boolean | If true, paths are computed once at initialization|
|                               |         | and reused for all updates (default: false)       |
+-------------------------------+---------+---------------------------------------------------+

Calculation Configuration
-------------------------

Each calculation in the ``calculations`` array has the following options:

+-------------------------------+---------+---------------------------------------------------+
| Option                        | Type    | Description                                       |
+===============================+=========+===================================================+
| type                          | string  | ``"sum"`` or ``"weighted_average"``               |
+-------------------------------+---------+---------------------------------------------------+
| input                         | string  | Source attribute to aggregate along paths         |
+-------------------------------+---------+---------------------------------------------------+
| output                        | string  | Target attribute for results                      |
+-------------------------------+---------+---------------------------------------------------+
| single_source_entity_id       | integer | Entity ID for single-source mode (optional)       |
+-------------------------------+---------+---------------------------------------------------+
| single_source_entity_reference| string  | Entity reference for single-source mode (optional)|
+-------------------------------+---------+---------------------------------------------------+

Example Configurations
----------------------

Road network path length calculation (all-pairs):

.. code-block:: json

    {
        "name": "road_length_shortest_path",
        "type": "shortest_path",
        "no_update_shortest_path": false,
        "transport_segments": ["road_network", "road_segment_entities"],
        "cost_factor": "transport.average_time",
        "calculations": [
            {
                "type": "sum",
                "input": "shape.length",
                "output": "transport.shortest_path_length"
            }
        ]
    }

Railway cargo path length:

.. code-block:: json

    {
        "name": "railway_cargo_shortest_path",
        "type": "shortest_path",
        "no_update_shortest_path": false,
        "transport_segments": ["railway_network", "track_segment_entities"],
        "cost_factor": "transport.cargo_average_time",
        "calculations": [
            {
                "type": "sum",
                "input": "shape.length",
                "output": "transport.cargo_shortest_path_length"
            }
        ]
    }

Lane length calculation with static paths:

.. code-block:: json

    {
        "name": "road_lane_length_shortest_path",
        "type": "shortest_path",
        "no_update_shortest_path": true,
        "transport_segments": ["road_network", "road_segment_entities"],
        "cost_factor": "transport.average_time",
        "calculations": [
            {
                "type": "sum",
                "input": "transport.lane_length",
                "output": "transport.shortest_path_lane_length"
            }
        ]
    }

Single-source accessibility calculation:

.. code-block:: json

    {
        "name": "accessibility_from_center",
        "type": "shortest_path",
        "transport_segments": ["road_network", "road_segment_entities"],
        "cost_factor": "transport.average_time",
        "calculations": [
            {
                "type": "sum",
                "input": "transport.average_time",
                "output": "transport.average_time",
                "single_source_entity_reference": "7777"
            }
        ]
    }

Notes
-----

* When a path does not exist between two nodes, the output uses the special
  value defined in the dataset's ``general.special`` section.

* The ``no_update_shortest_path`` option is useful when paths remain constant
  but the input attribute values change over time. This avoids recomputing
  paths on every update, improving performance.

* Multiple calculations can be performed in a single model instance, sharing
  the same network and pathfinding results.

Config Schema Reference
-----------------------

ShortestPathConfig
^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``transport_segments``: :ref:`ShortestPathEntityGroup` |required|
  | ``cost_factor``: ``string`` Attribute used as edge weights for pathfinding |required|
  | ``calculations``: :ref:`ShortestPathCalculations` |required|
  | ``no_update_shortest_path``: ``boolean`` If true, paths computed once and reused (default: false)

.. _ShortestPathEntityGroup:

ShortestPathEntityGroup
^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``

.. _ShortestPathCalculations:

ShortestPathCalculations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`ShortestPathCalculation`
| ``minItems``: 1

.. _ShortestPathCalculation:

ShortestPathCalculation
^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``type``: ``string`` Calculation type: ``"sum"`` or ``"weighted_average"`` |required|
  | ``input``: ``string`` Source attribute to aggregate along paths |required|
  | ``output``: ``string`` Target attribute for results |required|
  | ``single_source_entity_id``: ``integer`` Entity ID for single-source mode
  | ``single_source_entity_reference``: ``string`` Entity reference for single-source mode
