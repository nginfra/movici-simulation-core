.. _rules-model:

Rules Model
===========

The rules model is a generic model that can update certain attributes of certain entities based
on other attributes or the simulation time (either as time since the beginning of the simulation,
or a wall clock time) 

Rules
#####

Rules are constructed to update the value of a specific entity in a specific dataset. This target
entity is described by the ``"to_dataset"``, ``to_entity_group``, and either a ``"to_id"`` or 
``"to_reference"`` key. Based on a condition described in the ``"if"`` key, the target entity is
updated: the attribute in the ``"output"`` is given the value in the ``"value"`` key. The
condition in the ``"if"`` key can be one of the following:

- a single expression describing an attribute from a source entity. This source entity is described
  by the ``"from_dataset"``, ``from_entity_group`` and either the ``"from_id"`` or
  ``"from_reference"`` keys.
- an expression involving a special variable: ``<simtime>`` or ``<clocktime>``. These variables 
  represent the simulation time since the beginning of the simulation, or the time of the day
  inside the simulation
- a dictionary containing a ``"or"`` or ``"and"`` holding one or more conditions in an array.

Rules can be defined in the model config, but in some cases it can be preferable to place them in 
a dataset of type ``"rules"``. See the example dataset below.

Example rules dataset
---------------------

.. codeblock:: json
 
  {
    "name": "water_network_rules",
    "type": "rules",
    "format": "unstructured",
    "data": {
      "defaults": {
        "from_dataset": "a dataset",
        "to_dataset": "another dataset",
        "from_entity_group": "some_entities",
        "to_entity_group": "to_entities",
      },
      "rules": [
        {
          "if": "<simtime> == 34h",
          "to_reference": "some pump",
          "output": "water.pump_speed",
          "value": 1.2
        },
        {
          "if": "<simtime> == 34s",
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
          "to_id": 12,
          "if": "drinking_water.level >= 23",
          "to_reference": "some pipe",
          "output": "operational.status",
          "value": false,
          "else_value": true
        },
        {
          "from_id": 43,
          "to_id": 12,
          "if": {
            "and": [
              "clocktime >= 23:00",
              "clocktime < 6:00",
              {
                "or": ["drinking_water.level < 90", "diameter > 89"]
              }
            ]
          },
          "to_reference": "some pipe",
          "output": "operational.status",
          "value": false
        }
      ]
    }
  }

Notes
#####

- if a given reference is not unique in the dataset, we should raise an error
- while reference and id should/must be unique in a dataset, we currently do not have a way to
  use the TrackedModel to find the required id/reference *somewhere* in the dataset, we must
  provide an entity group.
- If a value in the condition is undefined, we should stop processing the rule

Possible future work
####################

- support not just a wall clock time, but a ISO datestring
- Migrate away from TrackedModel, and use SimpleModel instead so that we can do our own init data
  retrieval. Or design a nice api in TrackedModel to achieve finding ids/references without
  defining the entity group
