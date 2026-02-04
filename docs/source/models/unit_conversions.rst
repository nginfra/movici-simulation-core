.. |required| replace:: (**required**)

Unit Conversions Model
======================

The unit conversions model (``"unit_conversions"``) transforms vehicle counts
into cargo tonnage and passenger numbers using time-varying coefficients.

Reference: Asgarpour, S., Konstantinos, K., Hartmann, A., and Neef, R. (2021).
Modeling interdependent infrastructures under future scenarios. Work in Progress.

Use cases include:

* Converting cargo vehicle flows to tonnage
* Converting passenger vehicle flows to passenger counts
* Applying scenario-dependent fleet composition

How It Works
------------

1. Reads conversion coefficients from a CSV parameter file
2. For cargo: multiplies vehicle count by load capacity, share, and load factor
3. For passengers: multiplies vehicle count by occupancy and share
4. Updates output attributes with converted values

The conversion formulas differ by modality:

**Roads (cargo)**::

    tons = vehicles * effective_load_factor * (
        load_capacity_truck_medium * share_truck_medium +
        load_capacity_tractor_light * share_tractor_light +
        load_capacity_tractor_heavy * share_tractor_heavy
    )

**Roads (passengers)**::

    passengers = vehicles * load_capacity_passenger_car * share_passenger_car

**Waterways (cargo)**::

    tons = vehicles * effective_load_factor * (
        load_capacity_rhc * share_rhc +
        load_capacity_lr * share_lr
    )

Configuration Options
---------------------

+--------------------+---------+------------------------------------------------+
| Option             | Type    | Description                                    |
+====================+=========+================================================+
| parameters_dataset | string  | CSV dataset with conversion coefficients       |
+--------------------+---------+------------------------------------------------+
| conversions        | array   | List of conversion specifications              |
+--------------------+---------+------------------------------------------------+

Conversion Specification
------------------------

Each conversion entry has:

+--------------+---------+------------------------------------------------------+
| Option       | Type    | Description                                          |
+==============+=========+======================================================+
| class        | string  | ``"flow"`` for segment flows, ``"od"`` for OD pairs  |
+--------------+---------+------------------------------------------------------+
| modality     | string  | ``"roads"`` or ``"waterways"``                       |
+--------------+---------+------------------------------------------------------+
| entity_group | array   | ``[dataset_name, entity_group_name]``                |
+--------------+---------+------------------------------------------------------+

Example Configuration
---------------------

.. code-block:: json

    {
        "name": "road_unit_conversion",
        "type": "unit_conversions",
        "parameters_dataset": "traffic_kpi_coefficients_diesel",
        "conversions": [
            {
                "class": "flow",
                "modality": "roads",
                "entity_group": ["road_network", "road_segment_entities"]
            },
            {
                "class": "od",
                "modality": "roads",
                "entity_group": ["road_network", "virtual_node_entities"]
            }
        ]
    }

Required Coefficients
---------------------

The CSV parameter file must contain these columns:

**For roads:**

* ``road_effective_load_factor``
* ``load_capacity_truck_medium``, ``share_truck_medium``
* ``load_capacity_tractor_light``, ``share_tractor_light``
* ``load_capacity_tractor_heavy``, ``share_tractor_heavy``
* ``load_capacity_passenger_car``, ``share_passenger_car``

**For waterways:**

* ``waterway_effective_load_factor``
* ``load_capacity_rhc``, ``share_rhc``
* ``load_capacity_lr``, ``share_lr``

Config Schema Reference
-----------------------

UnitConversionsConfig
^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``parameters_dataset``: ``string`` CSV dataset name with conversion coefficients |required|
  | ``conversions``: :ref:`UnitConversions` |required|

.. _UnitConversions:

UnitConversions
^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`UnitConversion`
| ``minItems``: 1

.. _UnitConversion:

UnitConversion
^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``class``: ``string`` Conversion class: ``"flow"`` or ``"od"`` |required|
  | ``modality``: ``string`` Transport mode: ``"roads"`` or ``"waterways"`` |required|
  | ``entity_group``: :ref:`UnitConversionsEntityGroup` |required|

.. _UnitConversionsEntityGroup:

UnitConversionsEntityGroup
^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``
