Movici Simulation Core
======================

Copyright 2026 NGinfra

Movici is a set of tools and software for performing simulations on geospatial entities. 

Movici Simulation Core is the main package needed to run Movici simulations. It contains
  
* Simulation core for running simulations
* Pre-processing tools for preparing data to be used in simulations
* Post-processing tools for performing analyses on simulation results
* A number of (domain) models to quickly start setting up simulations


Installation
------------

On Windows and Linux
#####################

.. code-block::

  pip install movici-simulation-core


On MacOS
##########

Python must be installed via `Homebrew <https://brew.sh/>`_  to support Spatialite.

**Pre-requisites:**

- `Homebrew <https://brew.sh/>`_ package manager 
- Python 3.11 or higher installed via Homebrew (Lower versions will raise conflicts with OpenMP, a requirement of Aequilibrae)

1. On a terminal. Install the spatialite library as follows:
  
.. code-block:: bash

    brew update
    brew install libspatialite

2. Install ``movici-simulation-core`` to your Homebrew Python environment (below instructions assume Python 3.12):

.. code-block:: bash

  python3.12 -m pip install movici-simulation-core

Installing Models
-----------------

Some models require additional libraries to be installed. Most of these can be installed using the
``models`` extras (``pip install movici-simulation-core[models]``). However, there are some 
exceptions:

Traffic Assignment Calculation
##############################

The traffic assignment model uses ``aequilibrae`` to perform traffic assignment. This library
requires the ``mod_spatialite`` sqlite extension. 

- On Debian based Linux (eg. Ubuntu) this can be done using ``apt-get install libsqlite3-mod-spatialite``. 
- On Windows, please follow the 
`official installation guide <https://faims2-documentation.readthedocs.io/en/latest/Installing+Spatialite+on+Windows/>`_
- On MacOS, this can be done using the ``llvm`` compiler. Please follow the instructions below:

  1. Install the ``llvm`` compiler suite. This is requiered to build ``Aequilibrae`` with OpenMP support. On a terminal, run:

  .. code-block:: bash

    brew install llvm 

  2. Set the following environment variables to point ``pip`` to use the ``llvm`` compiler and libraries:  

  .. code-block:: bash

    export CC=/opt/homebrew/opt/llvm/bin/clang
    export CXX=/opt/homebrew/opt/llvm/bin/clang++
    export LDFLAGS="-L/opt/homebrew/opt/llvm/lib"
    export CPPFLAGS="-I/opt/homebrew/opt/llvm/include"

  3. Install the movici models with the following command:

  .. code-block:: bash

    pip install movici-simulation-core[models]


Development
-----------

If you want to develop on this package, you can following the same steps above depending of your operating system with one exception, **install** ``movici-simulation-core`` **package in editable mode.** This allows you to make changes to the code and have them reflected immediately without needing to reinstall the package.


On Windows and Linux
#####################

.. code-block:: bash

  git clone https://github.com/nginfra/movici-simulation-core.git
  pip install -e .[dev,models]

On MacOS
#####################

.. code-block:: bash

  # After installing dependencies and configuring environment variables, the final step should be:

  git clone https://github.com/nginfra/movici-simulation-core.git
  pip install -e .[dev,models]


Using Pre-commit Hooks
######################

To install the pre-commit hooks, first install ``pre-commit`` using your favorite installer, eg: ``pipx`` or ``uv tool``. Then, install the precommit hooks by running 

.. code-block::

  pre-commit install

