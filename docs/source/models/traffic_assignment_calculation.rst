.. |required| replace:: (**required**)

Traffic Assignment Calculation Model
====================================

The traffic assignment calculation model (``"traffic_assignment_calculation"``)
distributes origin-destination demand onto transport network links using
equilibrium traffic assignment algorithms.

The model uses the `Aequilibrae <https://www.aequilibrae.com/>`_ library for
traffic assignment computations.

Use cases include:

* Computing traffic flows on road networks
* Analyzing congestion patterns
* Estimating travel times under different demand scenarios
* Modeling freight flows on waterways and railways

How It Works
------------

1. Reads OD demand matrices from virtual node entities
2. Builds a network graph from transport segments
3. Assigns traffic using user equilibrium (UE) algorithm
4. Applies volume-delay functions (VDF) to model congestion
5. Publishes flow, travel time, and congestion metrics to segments

Volume-Delay Function
---------------------

The BPR (Bureau of Public Roads) volume-delay function is:

.. math::

    t = t_0 \cdot \left(1 + \alpha \cdot \left(\frac{V}{C}\right)^\beta\right)

Where:

- :math:`t_0` is the free-flow travel time
- :math:`V` is the traffic volume (in PCU)
- :math:`C` is the link capacity
- :math:`\alpha` and :math:`\beta` are calibration parameters

Supported Modalities
--------------------

+--------------------+-----------------------------------------------------------+
| Modality           | Description                                               |
+====================+===========================================================+
| ``roads``          | Standard vehicle traffic with congestion effects          |
+--------------------+-----------------------------------------------------------+
| ``waterways``      | Waterway traffic with lock waiting time included          |
+--------------------+-----------------------------------------------------------+
| ``tracks``         | Combined rail traffic (no congestion, alpha=0)            |
+--------------------+-----------------------------------------------------------+
| ``passenger_tracks`` | Passenger-only rail assignment                          |
+--------------------+-----------------------------------------------------------+
| ``cargo_tracks``   | Freight-only rail with cargo restriction support          |
+--------------------+-----------------------------------------------------------+

Configuration Options
---------------------

+---------------+---------+------------------------------------------------------+
| Option        | Type    | Description                                          |
+===============+=========+======================================================+
| modality      | string  | Transport mode (required, see table above)           |
+---------------+---------+------------------------------------------------------+
| dataset       | string  | Transport network dataset name (required)            |
+---------------+---------+------------------------------------------------------+
| vdf_alpha     | number  | VDF alpha parameter (default: 0.15 for roads)        |
+---------------+---------+------------------------------------------------------+
| vdf_beta      | number  | VDF beta parameter (default: 4.0)                    |
+---------------+---------+------------------------------------------------------+
| cargo_pcu     | number  | PCU factor for cargo vehicles (default: 2.0)         |
+---------------+---------+------------------------------------------------------+

Example Configuration
---------------------

Road traffic assignment:

.. code-block:: json

    {
        "name": "road_traffic_assignment",
        "type": "traffic_assignment_calculation",
        "modality": "roads",
        "dataset": "road_network",
        "vdf_alpha": 0.64,
        "vdf_beta": 4,
        "cargo_pcu": 2
    }

Railway cargo assignment:

.. code-block:: json

    {
        "name": "railway_cargo_traffic_assignment",
        "type": "traffic_assignment_calculation",
        "modality": "cargo_tracks",
        "dataset": "railway_network"
    }

Waterway traffic assignment:

.. code-block:: json

    {
        "name": "waterway_traffic_assignment",
        "type": "traffic_assignment_calculation",
        "modality": "waterways",
        "dataset": "waterway_network",
        "vdf_alpha": 0.64,
        "vdf_beta": 4,
        "cargo_pcu": 1
    }

Input Requirements
------------------

**Transport segments** must have:

* ``transport.max_speed``: Maximum speed on the link
* ``transport.capacity.hours``: Hourly capacity (vehicles)
* ``transport.layout`` (optional): Number of lanes/tracks

**Virtual nodes** must have:

* ``transport.passenger_demand``: Passenger OD matrix (CSR)
* ``transport.cargo_demand``: Cargo OD matrix (CSR)

Output Attributes
-----------------

+--------------------------------------+------------------------------------------+
| Attribute                            | Description                              |
+======================================+==========================================+
| ``transport.passenger_flow``         | Passenger flow (passengers/hour)         |
+--------------------------------------+------------------------------------------+
| ``transport.cargo_flow``             | Cargo flow (tons/hour)                   |
+--------------------------------------+------------------------------------------+
| ``transport.passenger_car_unit``     | Total flow in PCU                        |
+--------------------------------------+------------------------------------------+
| ``transport.volume_to_capacity_ratio`` | Congestion indicator (V/C)             |
+--------------------------------------+------------------------------------------+
| ``transport.delay_factor``           | Ratio of congested to free-flow time     |
+--------------------------------------+------------------------------------------+
| ``transport.average_time``           | Congested travel time (seconds)          |
+--------------------------------------+------------------------------------------+

Modality-Specific Behavior
--------------------------

Roads
-----

Standard BPR function with configurable parameters. Cargo vehicles are converted
to passenger car units (PCU) using the ``cargo_pcu`` factor.

Waterways
---------

Includes lock waiting time in free-flow calculation. Uses a modified VDF where
alpha varies by segment based on lock presence:

* Segments without locks: standard alpha
* Segments with locks: alpha = r / t_ff' where r = 344 minutes (waiting time)

Railways
--------

For freight (``cargo_tracks``): Uses capacity restrictions based on
``transport.cargo_allowed`` attribute. Segments with cargo_allowed=false get
minimal capacity to prevent routing.

For passengers (``passenger_tracks``): No cargo demand, passenger-only assignment.

Notes
-----

* The model recalculates assignments when demand or network attributes change
* Links with zero capacity get corrected output values to avoid division errors
* Travel time output uses a large correction value (1e9) for blocked links
* The graph is rebuilt when max_speed, capacity, or layout changes

Config Schema Reference
-----------------------

TrafficAssignmentConfig
^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``modality``: ``string`` Transport mode: ``"roads"``, ``"waterways"``, ``"tracks"``, ``"passenger_tracks"``, or ``"cargo_tracks"`` |required|
  | ``dataset``: ``string`` Transport network dataset name |required|
  | ``vdf_alpha``: ``number`` Volume-delay function alpha parameter (default: 0.15 for roads)
  | ``vdf_beta``: ``number`` Volume-delay function beta parameter (default: 4.0)
  | ``cargo_pcu``: ``number`` PCU factor for cargo vehicles (default: 2.0)
