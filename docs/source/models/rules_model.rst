.. _rules-model:

Rules Model
===========

The rules model is a generic model that can update certain attributes of certain entities based
on other attributes or the simulation time (either as time since the beginning of the simulation,
or a wall clock time) 

Rules
#####

Rules are constructed to update the value of a specific entity in a specific dataset. This target
entity is described by the ``"to_dataset"``, and either a ``"to_id"`` or 
``"to_reference"`` key. Based on a condition described in the ``"if"`` key, the target entity is
updated: the attribute in the ``"output"`` is given the value in the ``"value"`` key. The
``"if"`` key describes the condition or set of conditions that must be met to set the value. This can contain:
* one or more comparisons of attributes in the source entity
* an expression involving a special variable: ``<simtime>`` or ``<clocktime>``. These variables 
  represent the simulation time since the beginning of the simulation, or the time of the day
  inside the simulation
 * Boolean expressions are supported (see below)
Rules can be defined in the model config, but in some cases it can be preferable to place them in 
a dataset of type ``"rules"``. See the example dataset below.

Example rules dataset
---------------------

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
- An id must (and a reference should) be unique in a dataset. We just need to find which entity
  group it belongs to before we can register it to the :class:`TrackedState`. We can do the
  registration in two stages. In the first stage in :meth:`TrackedModel.setup` we retrieve the to
  and from datasets ourselves, and process them. We find the entity groups that our ids/references
  belong to (if we can't find them, we give a warning (or perhaps throw an error?)). We can now
  register those entity groups to the :class:`TrackedState` and continue business as usual.
- If a value in the condition is undefined, we should stop processing the rule

Possible future work
####################

- support not just a wall clock time, but a ISO datestring
