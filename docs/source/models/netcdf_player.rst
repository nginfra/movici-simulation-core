.. |required| replace:: (**required**)


NetCDFPlayer Model
===================================================================================================

The ``NetCDFPlayerModel`` can read a (specifically organized) netCDF file and write variables 
inside this netCDF to attributes in an entity group. The netCDF file must adhere to the following
specification:

* There must be a ``time`` variable with a number of timestamps. The timestamps represent the number 
  of seconds sinces ``t=0``
* There must be at least one other variable which has the length of ``time`` as the first dimension
  and the length of the number of (target) entities as the second dimension
* the variable data must be either 32 bit or 64 bit floating points


After initialization the ``NetCDFPlayerModel`` reads the netCDF data and writes the source variable
data per timestamp on the target attribute. The variable data is assigned to the target attribute
on an "index" basis, not on an "id" basis.

Example Configuration
---------------------------------------------------------------------------------------------------

.. code-block:: 
  
  {
    "name": "my_player",
    "type": "netcdf_player",
    "netcdf_tape": "some_netcdf_tape",
    "entity_group": ["target_dataset", "target_entities"],
    "attributes": [
      {
        "source": "source_var",
        "target": "target.attribute"
      }
    ]
  }

NetCDFPlayer Model Config Schema Reference
---------------------------------------------------------------------------------------------------

DatasetCreatorConfig
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``netcdf_tape``: ``string`` the name of a NetCDF tape dataset |required|
  | ``entity_group``: :ref:`NetCDFPlayerEntityGroup` |required|
  | ``attributes``: :ref:`NetCDFPlayerAttributes` |required|


.. _NetCDFPlayerEntityGroup:

NetCDFPlayerEntityGroup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``

A Tuple-array of two strings representing the target entity group: ["target_dataset", "target_entity_group"]

.. _NetCDFPlayerAttributes:

NetCDFPlayerAttributes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: :ref:`NetCDFPlayerAttribute`
| ``minItems``: 1

.. _NetCDFPlayerAttribute:

NetCDFPlayerAttribute
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``source``: ``string`` The variable name in the source (``netcdf_tape``) |required|
  | ``target``: ``string`` The attribute name in the target entity group |required|

