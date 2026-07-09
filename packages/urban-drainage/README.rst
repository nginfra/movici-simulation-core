Movici Urban Drainage Model
===========================

An urban drainage (storm water and sewer) network simulation model for
`Movici <https://movici.nl>`_, powered by `pyswmm <https://www.pyswmm.org/>`_
which wraps the EPA `SWMM <https://www.epa.gov/water-research/storm-water-management-model-swmm>`_
hydrology and hydraulic engine.

Features
--------

- Dynamic-wave hydraulic routing of drainage networks using SWMM via pyswmm
- Rainfall-runoff hydrology over subcatchments driven by rain gages
- Support for junctions, outfalls, storage units, conduits, pumps,
  orifices, weirs, and outlets
- Depth, head, flooding, flow, Froude number, and runoff output per network element
- External control of pumps, orifices and weirs through their settings

Installation
------------

.. code-block:: bash

   pip install movici-urban-drainage-model

The model registers itself as a Movici plugin automatically via entry points.

License
-------

Movici Public License
