.. |required| replace:: (**required**)

Traffic Demand Calculation Model
================================

The traffic demand calculation model (``"traffic_demand_calculation"``) estimates
how transport demand evolves over time based on global scenario parameters and
local spatial factors.

Reference: Asgarpour, S., Konstantinos, K., Hartmann, A., and Neef, R. (2021).
Modeling interdependent infrastructures under future scenarios. Work in Progress.

Use cases include:

* Forecasting transport demand under different economic scenarios
* Modeling modal shift based on travel time changes
* Analyzing demand sensitivity to infrastructure investments

How It Works
------------

The model modifies origin-destination (OD) demand matrices using elasticity-based
multipliers that respond to changes in:

1. **Global parameters**: Economy-wide factors (GDP, energy prices) that affect
   all OD pairs uniformly
2. **Local parameters**: Spatially-varying factors (travel times, accessibility)
   that affect specific OD pairs based on their location or route

Global Effects
--------------

For each global parameter, the demand multiplier is:

.. math::

    F = \left(\frac{P_n}{P_{n-1}}\right)^{2\eta}

Where:

- :math:`P_n` is the parameter value at current timestep
- :math:`P_{n-1}` is the parameter value at previous timestep
- :math:`\eta` is the elasticity (positive = demand increases with parameter)

The exponent is doubled because global parameters affect both origin and
destination equally (symmetric effect).

Local Effects
-------------

For local parameters, two mapping types are supported:

**Nearest mapping** (``mapping_type: "nearest"``):
  Uses attribute values from the nearest entity to each demand node.
  Suitable for population density, job counts, or other zone-based metrics.

**Route mapping** (``mapping_type: "route"``):
  Calculates shortest paths between OD pairs and aggregates attribute values
  along the route. Suitable for travel time or generalized cost effects.

Configuration Options
---------------------

+--------------------------------+---------+-------------------------------------------+
| Option                         | Type    | Description                               |
+================================+=========+===========================================+
| demand_path                    | array   | ``[dataset, entity_group, attribute]``    |
+--------------------------------+---------+-------------------------------------------+
| parameter_dataset              | string  | CSV dataset with scenario parameters      |
+--------------------------------+---------+-------------------------------------------+
| global_parameters              | array   | List of global parameter configurations   |
+--------------------------------+---------+-------------------------------------------+
| local_parameters               | array   | List of local parameter configurations    |
+--------------------------------+---------+-------------------------------------------+
| scenario_multipliers           | array   | Direct multiplier parameter names         |
+--------------------------------+---------+-------------------------------------------+
| investment_multipliers         | array   | Time-triggered demand multipliers         |
+--------------------------------+---------+-------------------------------------------+
| total_inward_demand_attribute  | string  | Output attribute for column sums          |
+--------------------------------+---------+-------------------------------------------+
| total_outward_demand_attribute | string  | Output attribute for row sums             |
+--------------------------------+---------+-------------------------------------------+
| max_iterations                 | integer | Maximum updates per timestep              |
+--------------------------------+---------+-------------------------------------------+
| rtol, atol                     | number  | Convergence tolerances                    |
+--------------------------------+---------+-------------------------------------------+

Global Parameter Configuration
------------------------------

+---------------+---------+------------------------------------------------------+
| Option        | Type    | Description                                          |
+===============+=========+======================================================+
| name          | string  | Column name in the parameter CSV                     |
+---------------+---------+------------------------------------------------------+
| elasticity    | number  | Demand elasticity with respect to this parameter     |
+---------------+---------+------------------------------------------------------+

Local Parameter Configuration
-----------------------------

+----------------+---------+--------------------------------------------------------+
| Option         | Type    | Description                                            |
+================+=========+========================================================+
| attribute_path | array   | ``[dataset, entity_group, attribute]``                 |
+----------------+---------+--------------------------------------------------------+
| geometry       | string  | ``"point"``, ``"line"``, or ``"polygon"``              |
+----------------+---------+--------------------------------------------------------+
| elasticity     | number  | Demand elasticity for this parameter                   |
+----------------+---------+--------------------------------------------------------+
| mapping_type   | string  | ``"nearest"`` or ``"route"`` (default: ``"nearest"``)  |
+----------------+---------+--------------------------------------------------------+

Example Configuration
---------------------

Road cargo demand with global and local effects:

.. code-block:: json

    {
        "name": "road_domestic_cargo_demand_estimation",
        "type": "traffic_demand_calculation",
        "demand_path": [
            "road_network",
            "virtual_node_entities",
            "transport.domestic_cargo_demand"
        ],
        "parameter_dataset": "scenario_parameters",
        "total_inward_demand_attribute": "transport.total_inward_domestic_cargo_demand_vehicles",
        "max_iterations": 100,
        "global_parameters": [
            {"name": "consumer_energy_price", "elasticity": -0.035},
            {"name": "gdp", "elasticity": 0.285},
            {"name": "share_service_sector_gdp", "elasticity": -0.4}
        ],
        "local_parameters": [
            {
                "geometry": "line",
                "elasticity": -0.1,
                "mapping_type": "route",
                "attribute_path": [
                    "road_network",
                    "road_segment_entities",
                    "transport.average_time.star"
                ]
            },
            {
                "geometry": "line",
                "elasticity": 0.086,
                "mapping_type": "route",
                "attribute_path": [
                    "waterway_network",
                    "waterway_segment_entities",
                    "transport.average_time.star"
                ]
            }
        ]
    }

Passenger demand with population and job count effects:

.. code-block:: json

    {
        "name": "railway_passenger_demand_estimation",
        "type": "traffic_demand_calculation",
        "demand_path": [
            "railway_network",
            "virtual_node_entities",
            "transport.passenger_demand"
        ],
        "parameter_dataset": "scenario_parameters",
        "local_parameters": [
            {
                "geometry": "polygon",
                "elasticity": 0.29,
                "mapping_type": "nearest",
                "attribute_path": [
                    "municipalities_area_set",
                    "area_entities",
                    "jobs.count.index"
                ]
            },
            {
                "geometry": "polygon",
                "elasticity": 1.38,
                "mapping_type": "nearest",
                "attribute_path": [
                    "municipalities_area_set",
                    "area_entities",
                    "people.count.index"
                ]
            },
            {
                "geometry": "point",
                "elasticity": -1.51,
                "mapping_type": "nearest",
                "attribute_path": [
                    "railway_network",
                    "virtual_node_entities",
                    "transport.generalized_journey_time.star"
                ]
            }
        ]
    }

Notes
-----

* The model uses CSR (Compressed Sparse Row) format for efficient OD matrix operations
* Investment multipliers allow modeling discrete events (e.g., new infrastructure opening)
* Negative elasticity means demand decreases as the parameter increases
* Cross-elasticities (e.g., road demand vs. rail travel time) enable modal competition

Config Schema Reference
-----------------------

TrafficDemandConfig
^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``demand_path``: :ref:`DemandPath` |required|
  | ``parameter_dataset``: ``string`` CSV dataset with scenario parameters |required|
  | ``global_parameters``: :ref:`GlobalParameters` List of global parameter configurations
  | ``local_parameters``: :ref:`LocalParameters` List of local parameter configurations
  | ``scenario_multipliers``: ``array`` Direct multiplier parameter names (array of strings)
  | ``investment_multipliers``: ``array`` Time-triggered demand multipliers
  | ``total_inward_demand_attribute``: ``string`` Output attribute for column sums
  | ``total_outward_demand_attribute``: ``string`` Output attribute for row sums
  | ``max_iterations``: ``integer`` Maximum updates per timestep
  | ``rtol``: ``number`` Relative convergence tolerance
  | ``atol``: ``number`` Absolute convergence tolerance

.. _DemandPath:

DemandPath
^^^^^^^^^^

| ``type``: ``array``

A tuple of three strings: ``[dataset_name, entity_group_name, attribute_name]``

.. _GlobalParameters:

GlobalParameters
^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`GlobalParameter`

.. _GlobalParameter:

GlobalParameter
^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``name``: ``string`` Column name in the parameter CSV |required|
  | ``elasticity``: ``number`` Demand elasticity with respect to this parameter |required|

.. _LocalParameters:

LocalParameters
^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`LocalParameter`

.. _LocalParameter:

LocalParameter
^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``attribute_path``: :ref:`DemandPath` |required|
  | ``geometry``: ``string`` Source geometry: ``"point"``, ``"line"``, or ``"polygon"`` |required|
  | ``elasticity``: ``number`` Demand elasticity for this parameter |required|
  | ``mapping_type``: ``string`` Mapping method: ``"nearest"`` or ``"route"`` (default: ``"nearest"``)
