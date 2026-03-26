Movici Drinking Water Model
===========================

A drinking water network simulation model for `Movici <https://movici.nl>`_,
powered by `WNTR <https://wntr.readthedocs.io/>`_ (Water Network Tool for
Resilience).

Features
--------

- Hydraulic simulation of water distribution networks
- Support for junctions, tanks, reservoirs, pipes, pumps, and valves
- Pressure-dependent demand (PDD) modelling
- Pause/restart simulation pattern for integrating external control changes
- CSR curve data for pump head curves and tank volume curves

Installation
------------

.. code-block:: bash

   pip install movici-drinking-water-model

The model registers itself as a Movici plugin automatically via entry points.

License
-------

Movici Public License
