.. |required| replace:: (**required**)

Time Window Status Model
========================

The time window status model (``"time_window_status"``) sets boolean status
attributes on target entities based on time windows defined in source entities.

Use cases include:

* Activating/deactivating entities during scheduled maintenance periods
* Modeling operational schedules (e.g., business hours, shift schedules)
* Triggering events based on calendar-defined time windows

How It Works
------------

1. Source entities define time windows using begin and end timestamp attributes
   (as ISO 8601 formatted strings)
2. Target entities have a boolean status attribute
3. When the simulation time enters a time window, the status becomes ``true``
4. When the simulation time exits a time window, the status becomes ``false``

If a source entity has connections to multiple target entities (via reference
matching), all connected entities are updated simultaneously.

Configuration Options
---------------------

+-------------------+---------+---------------------------------------------------+
| Option            | Type    | Description                                       |
+===================+=========+===================================================+
| source            | array   | ``[dataset_name, entity_group_name]`` for source  |
|                   |         | entities with time window definitions (required)  |
+-------------------+---------+---------------------------------------------------+
| time_window_begin | string  | Attribute name for window start time (required)   |
+-------------------+---------+---------------------------------------------------+
| time_window_end   | string  | Attribute name for window end time (required)     |
+-------------------+---------+---------------------------------------------------+
| targets           | array   | List of target configurations (required)          |
+-------------------+---------+---------------------------------------------------+

Target Configuration
--------------------

Each target in the ``targets`` array has the following options:

+-------------------+---------+---------------------------------------------------+
| Option            | Type    | Description                                       |
+===================+=========+===================================================+
| entity_group      | array   | ``[dataset_name, entity_group_name]`` for target  |
+-------------------+---------+---------------------------------------------------+
| attribute         | string  | Boolean attribute to set on target entities       |
+-------------------+---------+---------------------------------------------------+

Example Configuration
---------------------

.. code-block:: json

    {
        "name": "maintenance_scheduler",
        "type": "time_window_status",
        "source": ["maintenance_schedule", "schedule_entities"],
        "time_window_begin": "schedule.begin_time",
        "time_window_end": "schedule.end_time",
        "targets": [
            {
                "entity_group": ["road_network", "road_segment_entities"],
                "attribute": "operational.maintenance_active"
            },
            {
                "entity_group": ["railway_network", "track_segment_entities"],
                "attribute": "operational.maintenance_active"
            }
        ]
    }

Notes
-----

* Time window begin/end values should be ISO 8601 formatted strings
  (e.g., ``"2024-01-15T08:00:00"``).

* Source entities can reference target entities using the
  ``connection.to_dataset`` and ``connection.to_references`` attributes.

* Multiple overlapping time windows affecting the same entity are handled
  correctly - the status remains ``true`` as long as at least one window
  is active.

Config Schema Reference
-----------------------

TimeWindowStatusConfig
^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``source``: :ref:`TimeWindowEntityGroup` |required|
  | ``time_window_begin``: ``string`` Attribute name for window start time |required|
  | ``time_window_end``: ``string`` Attribute name for window end time |required|
  | ``targets``: :ref:`TimeWindowTargets` |required|

.. _TimeWindowEntityGroup:

TimeWindowEntityGroup
^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``

.. _TimeWindowTargets:

TimeWindowTargets
^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`TimeWindowTarget`
| ``minItems``: 1

.. _TimeWindowTarget:

TimeWindowTarget
^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``entity_group``: :ref:`TimeWindowEntityGroup` |required|
  | ``attribute``: ``string`` Boolean attribute to set on target entities |required|
