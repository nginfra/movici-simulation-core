Movici Power Grid Model
=======================

A power grid simulation model for `Movici <https://movici.nl>`_,
powered by `power-grid-model <https://power-grid-model.readthedocs.io/>`_.

Features
--------

- Power flow analysis (Newton-Raphson, linear, iterative current)
- State estimation with voltage, power, and current sensors
- Short circuit analysis
- Support for nodes, lines, cables, transformers, loads, generators, sources, shunts
- Automatic tap changer regulation

Installation
------------

.. code-block:: bash

   pip install movici-power-grid-model

The model registers itself as a Movici plugin automatically via entry points.

License
-------

Movici Public License
