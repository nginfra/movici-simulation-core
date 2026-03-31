Movici Drinking Water Model
===========================

A drinking water network simulation model for `Movici <https://movici.nl>`_,
powered by `WNTR <https://wntr.readthedocs.io/>`_ (Water Network Tool for
Resilience).

Features
--------

- Hydraulic simulation of water distribution networks using WNTR
- Demand-driven (DDA) and pressure-dependent demand (PDA) analysis
- Support for junctions, tanks, reservoirs, pipes, pumps, and valves
- Pressure, head, flow, velocity, and demand output per network element

Installation
------------

.. code-block:: bash

   pip install movici-drinking-water-model

The model registers itself as a Movici plugin automatically via entry points.

License
-------

Movici Public License
