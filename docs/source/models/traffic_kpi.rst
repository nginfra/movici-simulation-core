.. |required| replace:: (**required**)

Traffic KPI Model
=================

The traffic KPI model (``"traffic_kpi"``) calculates environmental key
performance indicators (CO2 emissions, NOx emissions, energy consumption)
for transport segments based on traffic flows.

Reference: Asgarpour, S., Konstantinos, K., Hartmann, A., and Neef, R. (2021).
Modeling interdependent infrastructures under future scenarios. Work in Progress.

Use cases include:

* Calculating emissions from road, rail, and waterway traffic
* Comparing environmental impacts across fuel types
* Modeling emission reduction scenarios

How It Works
------------

1. Reads emission and consumption factors from a coefficients CSV file
2. For each segment, calculates KPIs based on flow, length, and factors
3. Supports different fuel types (diesel, electricity, hydrogen, petrol)
4. Optionally applies scenario multipliers for sensitivity analysis

The calculation formula for each KPI::

    KPI = flow * length * coefficient * scenario_multiplier

Where ``coefficient`` is the product of emission factor, fleet share, and
(for cargo) load capacity and effective load factor.

Configuration Options
---------------------

+-------------------------------+---------+-------------------------------------------+
| Option                        | Type    | Description                               |
+===============================+=========+===========================================+
| modality                      | string  | ``"roads"``, ``"tracks"``, or ``"waterways"``|
+-------------------------------+---------+-------------------------------------------+
| dataset                       | string  | Transport network dataset name            |
+-------------------------------+---------+-------------------------------------------+
| coefficients_dataset          | string  | CSV with emission/consumption factors     |
+-------------------------------+---------+-------------------------------------------+
| scenario_parameters_dataset   | string  | Optional CSV with scenario multipliers    |
+-------------------------------+---------+-------------------------------------------+
| cargo_scenario_parameters     | array   | Column names for cargo multipliers        |
+-------------------------------+---------+-------------------------------------------+
| passenger_scenario_parameters | array   | Column names for passenger multipliers    |
+-------------------------------+---------+-------------------------------------------+
| energy_consumption_attribute  | string  | Output attribute (default:                |
|                               |         | ``transport.energy_consumption.hours``)   |
+-------------------------------+---------+-------------------------------------------+
| co2_emission_attribute        | string  | Output attribute (default:                |
|                               |         | ``transport.co2_emission.hours``)         |
+-------------------------------+---------+-------------------------------------------+
| nox_emission_attribute        | string  | Output attribute (default:                |
|                               |         | ``transport.nox_emission.hours``)         |
+-------------------------------+---------+-------------------------------------------+

Example Configuration
---------------------

Basic configuration for road network:

.. code-block:: json

    {
        "name": "road_kpi_diesel",
        "type": "traffic_kpi",
        "modality": "roads",
        "dataset": "road_network",
        "coefficients_dataset": "traffic_kpi_coefficients_diesel"
    }

Configuration with scenario parameters:

.. code-block:: json

    {
        "name": "road_kpi_electricity",
        "type": "traffic_kpi",
        "modality": "roads",
        "dataset": "road_network",
        "coefficients_dataset": "traffic_kpi_coefficients_electricity",
        "scenario_parameters_dataset": "infraconomy_interpolated",
        "passenger_scenario_parameters": ["electricity_share_passenger_road"],
        "cargo_scenario_parameters": ["electricity_share_freight_road"],
        "co2_emission_attribute": "transport.co2_emission_electricity.hours",
        "nox_emission_attribute": "transport.nox_emission_electricity.hours",
        "energy_consumption_attribute": "transport.energy_consumption_electricity.hours"
    }

Coefficients CSV Format
-----------------------

The coefficients CSV must contain columns for:

**Roads:**

* Carbon emission factors: ``cef_f_truck_medium``, ``cef_f_tractor_light``,
  ``cef_f_tractor_heavy``, ``cef_p_passenger_car``
* NOx emission factors: ``nef_f_*`` (same suffixes)
* Energy consumption factors: ``ecf_f_*``, ``ecf_p_*``
* Fleet shares and load capacities

**Tracks:**

* Factors for: ``train_medium_length``, ``ic``, ``st``
* ``passenger_train_capacity``

**Waterways:**

* Factors for: ``rhc`` (Rhine-Herne-Canal), ``lr`` (Large Rhine)

Config Schema Reference
-----------------------

TrafficKPIConfig
^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``modality``: ``string`` Transport mode: ``"roads"``, ``"tracks"``, or ``"waterways"`` |required|
  | ``dataset``: ``string`` Transport network dataset name |required|
  | ``coefficients_dataset``: ``string`` CSV dataset with emission/consumption factors |required|
  | ``scenario_parameters_dataset``: ``string`` Optional CSV with scenario multipliers
  | ``cargo_scenario_parameters``: ``array`` Column names for cargo multipliers (array of strings)
  | ``passenger_scenario_parameters``: ``array`` Column names for passenger multipliers (array of strings)
  | ``energy_consumption_attribute``: ``string`` Output attribute (default: ``transport.energy_consumption.hours``)
  | ``co2_emission_attribute``: ``string`` Output attribute (default: ``transport.co2_emission.hours``)
  | ``nox_emission_attribute``: ``string`` Output attribute (default: ``transport.nox_emission.hours``)
