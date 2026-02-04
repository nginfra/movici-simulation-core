.. |required| replace:: (**required**)

UDF Model
=========

The UDF (User-Defined Function) model (``"udf"``) allows defining custom
mathematical expressions to compute derived attributes from input attributes.

Use cases include:

* Computing derived metrics from simulation outputs
* Applying transformations or corrections to attribute values
* Implementing custom business logic without writing model code
* Relaxation algorithms for iterative calculations

How It Works
------------

1. Input attributes are registered and mapped to variable names
2. Mathematical expressions are parsed and compiled
3. On each update, expressions are evaluated using current attribute values
4. Results are published to output attributes

Expression Syntax
-----------------

Expressions support:

* Arithmetic operators: ``+``, ``-``, ``*``, ``/``
* Comparison operators: ``==``, ``!=``, ``<``, ``>``, ``<=``, ``>=``
* Parentheses for grouping: ``(a + b) * c``
* Built-in functions (see below)

Built-in Functions
------------------

+---------------+-----------------------------------------------------------+
| Function      | Description                                               |
+===============+===========================================================+
| ``sum(x)``    | Row-wise sum for CSR attributes, or sum along all axes    |
+---------------+-----------------------------------------------------------+
| ``min(...)``  | Element-wise minimum of multiple arrays/values            |
+---------------+-----------------------------------------------------------+
| ``max(...)``  | Element-wise maximum of multiple arrays/values            |
+---------------+-----------------------------------------------------------+
| ``default(x,  | Replace undefined values in ``x`` with ``default_val``    |
| default_val)``|                                                           |
+---------------+-----------------------------------------------------------+
| ``if(cond,    | Conditional: returns ``if_true`` where condition is true, |
| if_true,      | ``if_false`` otherwise                                    |
| if_false)``   |                                                           |
+---------------+-----------------------------------------------------------+

Example Configuration
---------------------

Combine domestic and international cargo demand:

.. code-block:: json

    {
        "name": "railway_combined_cargo_demand",
        "type": "udf",
        "entity_group": ["railway_network", "virtual_node_entities"],
        "inputs": {
            "domestic": "transport.domestic_cargo_demand",
            "intl": "transport.international_cargo_demand"
        },
        "functions": [
            {
                "expression": "domestic + intl",
                "output": "transport.cargo_demand"
            }
        ]
    }

Relaxation algorithm with default values:

.. code-block:: json

    {
        "name": "railway_cargo_relaxation",
        "type": "udf",
        "entity_group": ["railway_network", "track_segment_entities"],
        "inputs": {
            "incoming": "transport.cargo_average_time",
            "outgoing": "transport.cargo_average_time.star"
        },
        "functions": [
            {
                "expression": "default(outgoing, incoming) * 0.5 + incoming * 0.5",
                "output": "transport.cargo_average_time.star"
            }
        ]
    }

Conditional expression:

.. code-block:: json

    {
        "name": "capacity_check",
        "type": "udf",
        "entity_group": ["road_network", "road_segment_entities"],
        "inputs": {
            "flow": "transport.passenger_car_unit",
            "capacity": "transport.capacity"
        },
        "functions": [
            {
                "expression": "if(flow > capacity, 1, 0)",
                "output": "transport.is_congested"
            }
        ]
    }

Config Schema Reference
-----------------------

UDFConfig
^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``entity_group``: :ref:`UDFEntityGroup` |required|
  | ``inputs``: ``object`` Map of variable names to attribute names |required|
  | ``functions``: :ref:`UDFFunctions` |required|
  | ``optional``: ``array`` List of optional input variable names

.. _UDFEntityGroup:

UDFEntityGroup
^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``

.. _UDFFunctions:

UDFFunctions
^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`UDFFunction`
| ``minItems``: 1

.. _UDFFunction:

UDFFunction
^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``expression``: ``string`` Mathematical expression using input variable names |required|
  | ``output``: ``string`` Target attribute name for the computed result |required|
