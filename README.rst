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

On Windows and Linux
#####################

.. code-block::

  pip install movici-simulation-core


On MacOS
##########

Due to some dependencies, the installation on MacOS is a bit more involved. Please follow the instructions below.

**Pre-requisites:**
- Python 3.11 or higher (Lower versions produce conflicts wtith OpenMP at runtime.)
- Homebrew package manager (https://brew.sh/)

1. On a terminal. Install spatialite as bollows:

..  code-block::bash

    brew update
    brew install spatialite-tools
    brew install libspatialite


2. Install the `llvm`` compiler suite:

.. code-block::bash

  brew install llvm

3. Set the following environment variables to use the ``llvm`` C and C++ compilers:

.. code-block::bash

  export CC=/opt/homebrew/opt/llvm/bin/clang
  export CXX=/opt/homebrew/opt/llvm/bin/clang++

4. Update the ``DYLD_LIBRARY_PATH`` to include ``libspatialite``.

.. code-block::bash

  export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH

5. Clone ``aequilibrae`` repository and install it from source.

.. code-block::bash

  git clone https://github.com/AequilibraE/aequilibrae.git
  cd aequilibrae
  pip install .

6. Finally, install ``movici-simulation-core`` from source.

.. code-block::bash

  git clone https://github.com/nginfra/movici-simulation-core.git
  pip install .


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
- On MacOS, this can be done using Homebrew as described in the installation instructions above.

Development
-----------

If you want to develop on this package, you can following the same steps above depending of your operating system with one exception, **install** ``movici-simulation-core`` **package in editable mode.** This allows you to make changes to the code and have them reflected immediately without needing to reinstall the package.


On Windows Linux
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

To install the pre-commit hooks, first install ``pre-commit`` using your favorite installer, eg: `pipx` or `uv tool`. Then, install the precommit hooks by running 

.. code-block::

  pre-commit install

