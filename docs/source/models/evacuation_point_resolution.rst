.. |required| replace:: (**required**)

Evacuation Point Resolution Model
==================================

The evacuation point resolution model (``"evacuation_point_resolution"``)
assigns evacuation point identifiers to road segments based on routing data.

Use cases include:

* Tracking which evacuation destination each road segment routes to
* Visualizing evacuation routes during emergency simulations
* Analyzing evacuation zone coverage

How It Works
------------

1. At initialization, creates a mapping from road IDs to evacuation point labels
2. During simulation, monitors the "last ID" attribute on road segments
3. When a road segment's last ID changes, looks up the corresponding
   evacuation point
4. Publishes the evacuation point ID to the road segment

The "last ID" represents the final road in an evacuation route, which indicates
which evacuation point the route leads to.

Configuration Options
---------------------

+-------------------+---------+----------------------------------------------------+
| Option            | Type    | Description                                        |
+===================+=========+====================================================+
| dataset           | string  | Dataset containing evacuation points and roads     |
+-------------------+---------+----------------------------------------------------+
| evacuation_points | object  | Evacuation point configuration (optional)          |
+-------------------+---------+----------------------------------------------------+
| road_segments     | object  | Road segment configuration (optional)              |
+-------------------+---------+----------------------------------------------------+

Evacuation Points Configuration
-------------------------------

+---------------+---------+------------------------------------------------------+
| Option        | Type    | Description                                          |
+===============+=========+======================================================+
| entity_group  | string  | Entity group name (default: ``evacuation_point_entities``)|
+---------------+---------+------------------------------------------------------+
| attribute     | string  | Label attribute (default: ``id``)                    |
+---------------+---------+------------------------------------------------------+

Road Segments Configuration
---------------------------

+---------------+---------+------------------------------------------------------+
| Option        | Type    | Description                                          |
+===============+=========+======================================================+
| entity_group  | string  | Entity group name (default: ``road_segment_entities``)|
+---------------+---------+------------------------------------------------------+
| attribute     | string  | Output attribute (default: ``evacuation.evacuation_point_id``)|
+---------------+---------+------------------------------------------------------+

Example Configuration
---------------------

Basic configuration with defaults:

.. code-block:: json

    {
        "name": "evacuation_routing",
        "type": "evacuation_point_resolution",
        "dataset": "road_network"
    }

Custom configuration:

.. code-block:: json

    {
        "name": "evacuation_routing",
        "type": "evacuation_point_resolution",
        "dataset": "road_network",
        "evacuation_points": {
            "entity_group": "evacuation_point_entities",
            "attribute": "evacuation.point_label"
        },
        "road_segments": {
            "entity_group": "road_segment_entities",
            "attribute": "evacuation.destination_id"
        }
    }

Input Requirements
------------------

**Evacuation points** must have:

* ``evacuation.road_ids``: CSR array mapping points to their road IDs

**Road segments** must have:

* ``evacuation.last_id``: Updated by evacuation routing model

Output Attributes
-----------------

+----------------------------------+-----------------------------------------------+
| Attribute                        | Description                                   |
+==================================+===============================================+
| ``evacuation.evacuation_point_id``| ID of the evacuation point this road routes to|
+----------------------------------+-----------------------------------------------+

Notes
-----

* The model expects evacuation points to define which roads belong to them
  via the ``evacuation.road_ids`` attribute
* Special values in ``last_id`` are preserved in the output
* Undefined ``last_id`` values are not processed

Config Schema Reference
-----------------------

EvacuationPointResolutionConfig
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``dataset``: ``string`` Dataset name containing evacuation points and roads |required|
  | ``evacuation_points``: :ref:`EvacuationPointsConfig` Evacuation point configuration
  | ``road_segments``: :ref:`RoadSegmentsConfig` Road segment configuration

.. _EvacuationPointsConfig:

EvacuationPointsConfig
^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``entity_group``: ``string`` Entity group name (default: ``evacuation_point_entities``)
  | ``attribute``: ``string`` Label attribute (default: ``id``)

.. _RoadSegmentsConfig:

RoadSegmentsConfig
^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``entity_group``: ``string`` Entity group name (default: ``road_segment_entities``)
  | ``attribute``: ``string`` Output attribute (default: ``evacuation.evacuation_point_id``)
