.. |required| replace:: (**required**)

Generalized Journey Time Model
==============================

The generalized journey time model (``"generalized_journey_time"``) calculates
the perceived travel time for railway passengers, accounting for in-vehicle
time, waiting time, and crowdedness effects.

Use cases include:

* Evaluating passenger experience on rail networks
* Modeling mode choice based on service quality
* Analyzing the impact of frequency and capacity changes

How It Works
------------

The generalized journey time (GJT) represents the total "cost" of a journey
from a passenger's perspective. It includes:

1. **In-vehicle time**: Actual travel time on the train
2. **Waiting time**: Expected wait based on service frequency
3. **Crowdedness penalty**: Discomfort from traveling in crowded trains

The GJT formula is:

.. math::

    GJT = w \\cdot TT + \\frac{f}{2 \\cdot freq}

Where:

* :math:`w` is the crowdedness factor (increases with load factor)
* :math:`TT` is the in-vehicle travel time from shortest path calculation
* :math:`f` is the waiting time penalty factor (default: 1.5)
* :math:`freq` is the train frequency (trains per hour)

Crowdedness Factor
------------------

The crowdedness factor :math:`w` is calculated based on the passenger load
factor (ratio of passengers to capacity). As trains become more crowded,
passengers perceive the journey time as longer.

Configuration Options
---------------------

+--------------------+---------+--------------------------------------------------+
| Option             | Type    | Description                                      |
+====================+=========+==================================================+
| transport_segments | array   | ``[dataset_name, entity_group_name]`` for tracks |
+--------------------+---------+--------------------------------------------------+
| travel_time        | string  | Attribute name for travel time input (optional)  |
+--------------------+---------+--------------------------------------------------+

Example Configuration
---------------------

.. code-block:: json

    {
        "name": "railway_gjt",
        "type": "generalized_journey_time",
        "transport_segments": ["railway_network", "track_segment_entities"],
        "travel_time": "transport.passenger_average_time"
    }

Input Requirements
------------------

**Track segments** must have:

* Travel time attribute (configurable)
* ``transport.passenger_flow``: Current passenger flow

**Virtual nodes** must have:

* ``transport.passenger_vehicle_frequency``: Train frequency
* ``transport.passenger_vehicle_capacity``: Train capacity

Output Attributes
-----------------

+--------------------------------------+----------------------------------------+
| Attribute                            | Description                            |
+======================================+========================================+
| ``transport.generalized_journey_time`` | GJT matrix (CSR) for all OD pairs    |
+--------------------------------------+----------------------------------------+

Notes
-----

* GJT is calculated as a matrix for all origin-destination pairs
* If no trains run on a route (frequency = 0), GJT is set to 0
* The model uses shortest path algorithms to find routes
* Crowdedness is based on travel-time-weighted average passenger flow

Config Schema Reference
-----------------------

GJTConfig
^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``transport_segments``: :ref:`GJTEntityGroup` |required|
  | ``travel_time``: ``string`` Attribute name for travel time input

.. _GJTEntityGroup:

GJTEntityGroup
^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``
