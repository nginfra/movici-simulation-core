Installation
==============

.. warning::
    ``movici-simulation-core`` and its associated libraries are currently not yet publicly 
    available for installation. Contact ``movici[-at-]nginfra.nl`` to request a copy

.. _installation_linux:

Linux
---------------

``movici-simulation-core`` can be installed using pip:

.. code-block::

  pip install movici-simulation-core

This installs ``movici-simulation-core`` and its core requirements with which you can get started to
create your own models and setup simulations. Some models that that are included with 
``movici-simulation-core`` require extra requirements that can be installed separately:

.. code-block::

  pip install movici-simulation-core[models]

The models that require these extra requirements are

* ``area_aggregation``
* ``overlap_status``
* ``traffic_demand_calculation``
* ``traffic_assignment_calculation``


Windows
---------------

Unfortunately, Windows is currently not yet 100% supported. ``movici_simulation_core``
can easily be installed using pip, but there are no compiled binaries yet for 
the spatial mapping tool ``movici-geo-query``, which is a dependency for many models.
Compiling ``movici-geo-query`` yourself requires an up to date version of 
`Boost Geometry <https://www.boost.org/users/download/>`_ and ``MSVC`` as a C compiler.

Until Windows is fully supported, it is recommended to run Movici inside 
:abbr:`WSL (Windows Subsystem for Linux)`. Follow the installation instructuctions for
:ref:`Linux<installation_linux>` for how to install Movici under WSL
