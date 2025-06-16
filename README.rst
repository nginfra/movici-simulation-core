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

External System Dependencies
############################

**mod_spatialite**

The traffic assignment model (``traffic_assignment_calculation``) uses ``aequilibrae`` which
requires the ``mod_spatialite`` SQLite extension to be installed on your system.

* **Linux (Debian/Ubuntu)**: ``sudo apt-get install libsqlite3-mod-spatialite``
* **Linux (Fedora/RHEL)**: ``sudo dnf install sqlite-mod_spatialite``
* **macOS**: ``brew install spatialite-tools``
* **Windows**: Follow the `official installation guide <https://faims2-documentation.readthedocs.io/en/latest/Installing+Spatialite+on+Windows/>`_

Python and Dependency Version Support
######################################

**Python Support:** Movici Simulation Core supports Python 3.8 through 3.12.

**Current Default (NumPy 1.x):** For full compatibility including traffic assignment with aequilibrae:
- numpy (>=1.26.0, <2.0.0)
- numba (>=0.58.0)
- pandas (>=2.0.0)
- aequilibrae (>=1.4.0) - latest version

**NumPy 2.0+ Support:** This package core is fully compatible with NumPy 2.0+, but requires environment-specific setup. For NumPy 2.0+ compatibility without traffic assignment models, use::

  pip install movici-simulation-core -r requirements-numpy2.txt

**Note:** We recommend NumPy 1.x for production use to ensure full ecosystem compatibility, especially for traffic assignment functionality.
