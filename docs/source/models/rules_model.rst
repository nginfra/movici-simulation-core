.. |required| replace:: (**required**)

.. _rules-model:

Rules Model
===========

The rules model (``"rules"``) updates entity attributes based on conditional
expressions evaluated at each simulation timestep. Conditions can reference
simulation time, clock time, or source entity attributes.

Use cases include:

* Activating or deactivating pumps/valves at specific times
* Setting control outputs based on sensor thresholds
* Implementing time-of-day schedules for infrastructure operations
* Triggering alarms when attribute values cross limits

How It Works
------------

1. Rules are loaded from the model config and/or a rules dataset at setup
2. Source and target entities are resolved by ID or reference
3. At each update, every rule's condition is evaluated
4. When a condition is true, the target attribute is set to ``value``
5. When a condition is false and ``else_value`` is provided, the target
   attribute is set to ``else_value``; otherwise the attribute is left unchanged
6. If the condition references source attributes that have not yet received
   data, the rule is skipped entirely

Condition Syntax
----------------

The ``"if"`` key contains a string expression. Both sides of a comparison can
be an attribute name, a literal value, or a time variable.

**Comparison types:**

* Simulation time: ``"<simtime> >= 1h"``, ``"<simtime> == 1d5h30m"``
* Clock time: ``"<clocktime> == 12:00"``, ``"<clocktime> >= 08:30:00"``
* Attribute vs literal: ``"level >= 23"``, ``"status == true"``
* Attribute vs attribute: ``"level > threshold"``, ``"a.x > b.y"``
* Literal on left: ``"23 >= level"``

**Comparison operators:** ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``

**Duration values** support units ``s`` (seconds), ``m`` (minutes), ``h``
(hours), ``d`` (days), and can be combined: ``"1d5h30m10s"``.

**Clock times** use ``HH:MM`` or ``HH:MM:SS`` format.

**Boolean operators** combine multiple comparisons:

+-----------------+----------------------------------------------------+
| Operator        | Example                                            |
+=================+====================================================+
| ``AND`` / ``&&``| ``"level >= 10 && level <= 20"``                   |
+-----------------+----------------------------------------------------+
| ``OR`` / ``||`` | ``"level < 10 || level > 90"``                     |
+-----------------+----------------------------------------------------+
| ``NOT`` / ``!`` | ``"NOT status == true"``                           |
+-----------------+----------------------------------------------------+
| Parentheses     | ``"(level < 10 || level > 90) && status == true"`` |
+-----------------+----------------------------------------------------+

Spaces between tokens are optional: ``"level>=23"`` is equivalent to
``"level >= 23"``.

Attribute values must be scalars (``int``, ``float``, or ``bool``).

Source and Target Entities
--------------------------

Each rule identifies a target entity using ``"to_dataset"`` and either
``"to_id"`` or ``"to_reference"``. When the condition references attributes,
the source entity must be specified using ``"from_dataset"`` and either
``"from_id"`` or ``"from_reference"``.

These fields can be provided per-rule or as defaults at the top level.

During setup, the model resolves entity IDs and references to their entity
groups and indices within the dataset. If a referenced entity cannot be found,
setup raises an error.

Example Configuration
---------------------

Inline rules in model config:

.. code-block:: json

    {
        "name": "water_control_rules",
        "type": "rules",
        "defaults": {
            "from_dataset": "sensors",
            "to_dataset": "actuators"
        },
        "rules": [
            {
                "if": "<simtime> >= 1h",
                "from_id": 1,
                "to_id": 10,
                "output": "control.active",
                "value": true,
                "else_value": false
            },
            {
                "if": "sensor.level >= 23",
                "from_id": 1,
                "to_id": 10,
                "output": "control.pump_speed",
                "value": 1.5,
                "else_value": 0.0
            },
            {
                "if": "sensor.level > sensor.threshold",
                "from_id": 2,
                "to_id": 20,
                "output": "control.valve_open",
                "value": true,
                "else_value": false
            }
        ]
    }

Example Rules Dataset
---------------------

Rules can also be loaded from a separate dataset of type ``"rules"``:

.. code-block:: json

    {
        "name": "water_network_rules",
        "type": "rules",
        "format": "unstructured",
        "data": {
            "defaults": {
                "from_dataset": "a dataset",
                "to_dataset": "another dataset"
            },
            "rules": [
                {
                    "if": "<simtime> == 34h",
                    "to_reference": "some pump",
                    "output": "water.pump_speed",
                    "value": 1.2
                },
                {
                    "if": "<clocktime> == 12:00",
                    "to_reference": "some pipe",
                    "output": "operational.status",
                    "value": false
                },
                {
                    "from_dataset": "overridden dataset",
                    "from_reference": "some tank",
                    "to_reference": "some pipe",
                    "if": "drinking_water.level >= 23",
                    "output": "operational.status",
                    "value": false,
                    "else_value": true
                }
            ]
        }
    }

When both config and dataset specify rules, they are merged (config defaults
take precedence over dataset defaults).

Notes
-----

* Each rule targets a single entity; other entities in the same group are
  unaffected
* Rules are evaluated in order; later rules can overwrite earlier ones for
  the same output attribute
* Time-only conditions (``<simtime>``, ``<clocktime>``) do not require
  ``from_dataset``/``from_id``/``from_reference``

Config Schema Reference
-----------------------

RulesConfig
^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``rules_dataset``: ``string`` Name of a rules dataset to load rules from
  | ``defaults``: :ref:`RulesDefaults` Default source/target datasets
  | ``rules``: :ref:`RulesList` Inline rules

.. _RulesDefaults:

RulesDefaults
^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``from_dataset``: ``string`` Default source dataset for rules
  | ``to_dataset``: ``string`` Default target dataset for rules

.. _RulesList:

RulesList
^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`RuleItem`

.. _RuleItem:

RuleItem
^^^^^^^^

| ``type``: ``object``
| One of ``to_id`` or ``to_reference`` is required.

``properties``:
  | ``if``: ``string`` Condition expression |required|
  | ``output``: ``string`` Target attribute name |required|
  | ``value``: Value to set when condition is true |required|
  | ``else_value``: Value to set when condition is false
  | ``from_dataset``: ``string`` Source dataset (overrides default)
  | ``from_id``: ``integer`` Source entity ID
  | ``from_reference``: ``string`` Source entity reference
  | ``to_dataset``: ``string`` Target dataset (overrides default)
  | ``to_id``: ``integer`` Target entity ID
  | ``to_reference``: ``string`` Target entity reference
