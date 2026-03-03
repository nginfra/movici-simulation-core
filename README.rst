Movici
======

Copyright 2025ff NGinfra

Movici is a set of tools and software for performing simulations on geospatial entities.

Movici Simulation Core
----------------------

Movici Simulation Core is the main package needed to run Movici simulations. It contains

* Simulation core for running simulations
* Pre-processing tools for preparing data to be used in simulations
* Post-processing tools for performing analyses on simulation results
* A number of (domain) models to quickly start setting up simulations

Installation
############

.. code-block::

  pip install movici-simulation-core


Installing Models
#################

Some models require additional libraries to be installed. Most of these can be installed using the
``models`` extras (``pip install movici-simulation-core[models]``). However, there are some
exceptions


traffic_assignment_calculation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The traffic assignment model uses ``aequilibrae`` to perform it's traffic assignment. This library
requires the ``mod_spatialite`` sqlite extension. On Debian based Linux (eg. Ubuntu) this can
be done using ``apt-get install libsqlite3-mod-spatialite``. On Windows, please follow the
`official installation guide <https://faims2-documentation.readthedocs.io/en/latest/Installing+Spatialite+on+Windows/>`_


Development
-----------

This project uses `uv <https://docs.astral.sh/uv/>`_ as the project management tool. In order to
start development on Movici, please install uv first using your favorite install method.

Then you can install this package and all its dependencies using uv:

.. code-block::

  uv sync --all-groups

  # optional: activate the virtual environment
  source .venv/bin/activate

This project uses `uv workspaces <https://docs.astral.sh/uv/concepts/projects/workspaces/>`_ to
manage multiple packages. The workspace packages can be found in `packages/`. Currently the
following packages are included:

* ``movici-simulation-core`` (``/packages/simulation-core``)

pre-commit
##########

To install the pre-commit hooks, please first install pre-commit using your favorite installer,
eg: `pipx` or `uv tool`.

Then install the precommit hooks by running

.. code-block::

  pre-commit install
