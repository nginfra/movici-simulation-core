.. |required| replace:: (**required**)

NetCDF Player
=============

The NetCDF player model (``"netcdf_player"``) replays multi-dimensional time-series
data from NetCDF files during a simulation, publishing variable values to entity
attributes at their designated timestamps.

Use cases include:

* Playing back pre-computed flooding data (water heights over time)
* Injecting spatial time-series datasets from external models
* Replaying meteorological or environmental data

How It Works
------------

1. The NetCDF file is loaded at simulation setup
2. The ``time`` variable defines when each data slice becomes active
3. At each timestamp, the model publishes variable values to target attributes
4. Values are assigned by index position (not by entity ID)

NetCDF File Format
------------------

The NetCDF file must adhere to the following specification:

* A ``time`` variable with timestamps (seconds since simulation start)
* Additional variables with dimensions ``[time, entities]``
* Variable data must be 32-bit or 64-bit floating point

Example Configuration
---------------------

.. code-block:: json

    {
        "name": "flooding_player",
        "type": "netcdf_player",
        "netcdf_tape": "flooding_data_netcdf",
        "entity_group": ["flooding_grid", "grid_cell_entities"],
        "attributes": [
            {
                "source": "water_height",
                "target": "flooding.water_height"
            }
        ]
    }

Notes
-----

* Variable data is assigned to entities by index position, not by entity ID
* The model closes the NetCDF file handle on shutdown
* Multiple attributes can be mapped from the same NetCDF file
* The model returns the next timestamp from the NetCDF, allowing the simulation
  to advance efficiently

Config Schema Reference
-----------------------

NetCDFPlayerConfig
^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``netcdf_tape``: ``string`` Name of the NetCDF tape dataset |required|
  | ``entity_group``: :ref:`NetCDFPlayerEntityGroup` |required|
  | ``attributes``: :ref:`NetCDFPlayerAttributes` |required|

.. _NetCDFPlayerEntityGroup:

NetCDFPlayerEntityGroup
^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``

.. _NetCDFPlayerAttributes:

NetCDFPlayerAttributes
^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`NetCDFPlayerAttribute`
| ``minItems``: 1

.. _NetCDFPlayerAttribute:

NetCDFPlayerAttribute
^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``source``: ``string`` Variable name in the NetCDF file |required|
  | ``target``: ``string`` Attribute name to publish the value to |required|

