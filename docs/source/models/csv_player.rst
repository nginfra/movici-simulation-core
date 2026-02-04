.. |required| replace:: (**required**)

CSV Player
==========

The CSV player model (``"csv_player"``) replays time-series data from CSV files
during a simulation, publishing parameter values to entity attributes at their
designated timestamps.

Use cases include:

* Injecting time-varying scenario parameters (e.g., growth factors, prices)
* Playing back measured data as model inputs
* Simulating external forcing functions

How It Works
------------

1. The CSV file is loaded and parsed at simulation setup
2. The ``time`` column defines when each row's values become active
3. At each timestamp, the model publishes column values to target attributes
4. Values remain constant until the next timestamp in the CSV

CSV File Format
---------------

The CSV file must have:

* A ``time`` column with timestamps in seconds since simulation start
* Additional columns for each parameter to be published

Example CSV::

    time,temperature,demand_factor
    0,15.0,1.0
    3600,18.0,1.2
    7200,22.0,1.5

Example Configuration
---------------------

.. code-block:: json

    {
        "name": "scenario_parameters",
        "type": "csv_player",
        "csv_tape": "scenario_parameters_csv",
        "entity_group": ["parameters", "global_entities"],
        "csv_parameters": [
            {
                "parameter": "demand_factor",
                "target_attribute": "scenario.demand_factor"
            },
            {
                "parameter": "temperature",
                "target_attribute": "weather.temperature"
            }
        ]
    }

Notes
-----

* All target entities receive the same value (the CSV provides a single value
  per parameter per timestamp)
* The model returns the next timestamp from the CSV, allowing the simulation
  to advance efficiently
* Parameter values are broadcast to all entities in the target entity group

Config Schema Reference
-----------------------

CSVPlayerConfig
^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``csv_tape``: ``string`` Name of the CSV dataset |required|
  | ``entity_group``: :ref:`CSVPlayerEntityGroup` |required|
  | ``csv_parameters``: :ref:`CSVPlayerParameters` |required|

.. _CSVPlayerEntityGroup:

CSVPlayerEntityGroup
^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``

.. _CSVPlayerParameters:

CSVPlayerParameters
^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`CSVPlayerParameter`
| ``minItems``: 1

.. _CSVPlayerParameter:

CSVPlayerParameter
^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``parameter``: ``string`` Column name in the CSV file |required|
  | ``target_attribute``: ``string`` Attribute name to publish the value to |required|
