.. |required| replace:: (**required**)

Corridor Model
==============

The corridor model (``"corridor"``) aggregates transport key performance indicators
(KPIs) along predefined routes connecting origin and destination nodes.

Use cases include:

* Monitoring freight flows along major transport corridors
* Calculating environmental impacts for strategic routes
* Comparing congestion levels across different corridors

How It Works
------------

1. Corridor definitions specify origin and destination node sets
2. For each origin-destination pair, the shortest path is computed
3. KPIs are aggregated along the path, weighted by demand
4. Results are published to the corridor entity attributes

Computed metrics include:

* **Passenger and cargo flow**: Total flow through the corridor
* **Passenger car units (PCU)**: Standardized vehicle equivalent
* **CO2 and NOx emissions**: Weighted by corridor demand share
* **Energy consumption**: Total energy used along the route
* **Travel time**: Demand-weighted average travel time
* **Delay factor**: Maximum ratio of actual to free-flow travel time
* **Volume-to-capacity ratio**: Maximum congestion indicator

Configuration Options
---------------------

+---------------------------+---------+------------------------------------------------+
| Option                    | Type    | Description                                    |
+===========================+=========+================================================+
| corridors                 | string  | Dataset name for corridor definitions          |
+---------------------------+---------+------------------------------------------------+
| modality                  | string  | ``"roads"``, ``"waterways"``, or ``"tracks"``  |
+---------------------------+---------+------------------------------------------------+
| dataset                   | string  | Transport network dataset name                 |
+---------------------------+---------+------------------------------------------------+
| cargo_pcu                 | number  | PCU factor for cargo vehicles (default: 2.0)   |
+---------------------------+---------+------------------------------------------------+
| publish_corridor_geometry | bool    | Publish computed route geometry                |
+---------------------------+---------+------------------------------------------------+

Corridor Dataset Requirements
-----------------------------

The corridor dataset must contain entities with:

* ``connection.from_node_ids``: CSR array of origin node IDs
* ``connection.to_node_ids``: CSR array of destination node IDs

Example Configuration
---------------------

.. code-block:: json

    {
        "name": "road_corridors",
        "type": "corridor",
        "corridors": "corridor_definitions",
        "modality": "roads",
        "dataset": "road_network",
        "cargo_pcu": 2.0,
        "publish_corridor_geometry": true
    }

Output Attributes
-----------------

The model publishes the following attributes to corridor entities:

+-----------------------------------+--------------------------------------------+
| Attribute                         | Description                                |
+===================================+============================================+
| ``transport.passenger_flow``      | Total passengers through corridor          |
+-----------------------------------+--------------------------------------------+
| ``transport.cargo_flow``          | Total cargo (tons) through corridor        |
+-----------------------------------+--------------------------------------------+
| ``transport.passenger_car_unit``  | PCU equivalent of all traffic              |
+-----------------------------------+--------------------------------------------+
| ``transport.travel_time``         | Demand-weighted average travel time        |
+-----------------------------------+--------------------------------------------+
| ``transport.co2_emission``        | CO2 emissions (proportional to demand)     |
+-----------------------------------+--------------------------------------------+
| ``transport.nox_emission``        | NOx emissions (proportional to demand)     |
+-----------------------------------+--------------------------------------------+
| ``transport.energy_consumption``  | Energy consumption (proportional to demand)|
+-----------------------------------+--------------------------------------------+
| ``transport.delay_factor``        | Maximum delay factor on route              |
+-----------------------------------+--------------------------------------------+
| ``transport.max_volume_to_capacity`` | Maximum V/C ratio on route              |
+-----------------------------------+--------------------------------------------+

Config Schema Reference
-----------------------

CorridorConfig
^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``corridors``: ``string`` Dataset name containing corridor definitions |required|
  | ``modality``: ``string`` Transport mode: ``"roads"``, ``"waterways"``, or ``"tracks"`` |required|
  | ``dataset``: ``string`` Transport network dataset name |required|
  | ``cargo_pcu``: ``number`` PCU factor for cargo vehicles (default: 2.0)
  | ``publish_corridor_geometry``: ``boolean`` Whether to publish computed route geometry
