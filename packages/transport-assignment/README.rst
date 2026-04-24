Movici Transport Assignment Model
==================================

A traffic assignment simulation model for `Movici <https://movici.nl>`_,
powered by `Aequilibrae <https://aequilibrae.com/>`_.

Features
--------

- Traffic assignment on road, waterway, and railway networks
- Support for multiple modalities (road, waterway, track, passenger track, cargo track)
- Volume Delay Functions: BPR and Conical
- Assignment algorithms: bi-conjugate Frank-Wolfe, MSA, Frank-Wolfe, conjugate Frank-Wolfe, all-or-nothing
- Dynamic capacity and speed updates during simulation

Installation
------------

.. code-block:: bash

   pip install movici-transport-assignment-model

The model registers itself as a Movici plugin automatically via entry points.

License
-------

Movici Public License
