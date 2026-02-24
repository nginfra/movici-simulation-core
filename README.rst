Movici Simulation Core
======================

Copyright 2020ff NGinfra

Movici is a set of tools and software for performing simulations geospatial entities. 

Movici Simulation Core is the main package needed to run Movici simulations. It contains
  
* Simulation core for running simulations
* Pre-processing tools for preparing data to be used in simulations
* Post-processing tools for performing analyses on simulation results
* A number of (domain) models to quickly start setting up simulations


Installation
------------

.. code-block::

  pip install movici-simulation-core


Installing Models
-----------------

Some models require additional libraries to be installed. Most of these can be installed using the
``models`` extras (``pip install movici-simulation-core[models]``). However, there are some 
exceptions


traffic_assignment_calculation
##############################

The traffic assignment model uses ``aequilibrae`` to perform it's traffic assignment. This library
requires the ``mod_spatialite`` sqlite extension. On Debian based Linux (eg. Ubuntu) this can
be done using ``apt-get install libsqlite3-mod-spatialite``. On Windows, please follow the 
`official installation guide <https://faims2-documentation.readthedocs.io/en/latest/Installing+Spatialite+on+Windows/>`_


Development
-----------

Install this package in editable mode and include all depenencies:

.. code-block::

  pip install -e .[dev,models]

pre-commit
##########

To install the pre-commit hooks, please first install pre-commit using your favorite installer, eg: `pipx` or `uv tool`.

then install the precommit hooks by running 

.. code-block::

  pre-commit install

