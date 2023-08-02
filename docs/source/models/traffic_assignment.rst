
.. |required| replace:: (**required**)

Traffic Assignment Model
---------------------------------------------------------------------------------------------------

The traffic assignment model (``'traffic_assignment'``) can be used to calculate traffic flows on
a transport network dataset. Internally it uses `Aequilibrae <https://aequilibrae.com>`_ to
calculate traffic flows. The model merely acts as a wrapper.

Dataset requirements
^^^^^^^^^^^^^^^^^^^^
The traffic assignement model expects a dataset with a certain set of entity groups and attributes.

**virtual_node_entities**. These are the incoming and outgoing nodes of the network and contain the
 origin destination matrices. The OD-matrices must be a CSR-type ``float`` matrix attribute. Every
 value represents the outgoing demand (in vehicles/hour) from the row's virtual node to the virtual
 node matching the column. Two OD-matrix attributes are supported:

 * ``transport.passenger_demand``
 * ``transport.cargo_demand``

**virtual_link_entities**. These connect ``virtual_node_entities`` to ``transport_node_entities`` using
 the ``connection.from_node_id`` and ``connection.to_node_id`` attributes

**transport_node_entities**. these are nodes in the network and connect transport segments to
 other transport segmenets and to virtual links

The transport segments entity type depends on the modality the model operates. These can be either

* **road_segment_entities** for roads
* **waterway_segment_entities** for waterways
* **track_segment_entities** for railway tracks

Supported attributes for the transport segments are:

* ``transport.capacity``
* ``transport.layout`` (a 4-tuple indicating number of lanes an directionality: [forward lanes, reverse lanes, bidirectional lanes, unknown directionality lanes])
* ``transport.max_speed``


Modalities
----------
The traffic assignment model can operate in different modes, depending on the modality. They are
as following

Roads
^^^^^
For ``roads``, the model supports both passenger demand and cargo demand. Model parameters that can
be tweaked are ``vdf_alpha``, ``vdf_beta`` and ``cargo_pcu``. ``vdf_alpha`` and ``vdf_beta`` in the
`volume delay function <http://aequilibrae.com/python/latest/modeling_with_aequilibrae/modeling_concepts/assignment_mechanics.html#volume-delay-function>`_
the volume on the road is calculated by combining the passenger vehicle volume and the cargo
vehicle volume for which the cargo vehicle volume has a weight equal to the ``cargo_pcu`` parameter.


Other modalities
^^^^^^^^^^^^^^^^

Other modalities are ``waterways``, ``cargo_tracks`` and ``passenger_tracks``. These will be explained
further in the future

Example Configuration
---------------------------------------------------------------------------------------------------

.. code-block::

  {
    "name": "road_traffic_assignment",
    "type": "traffic_assignment",
    "dataset": "some_road_network",
    "modality": "roads"
    "vdf_beta": 0.64,
    "vdf_alpha": 4.0,
    "cargo_pcu": 1.9
  }

Traffic Assigment Model Config Schema Reference
---------------------------------------------------------------------------------------------------

TrafficAssignmentConfig
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``dataset``: ``string`` the name of a transport network dataset |required|
  | ``modality``: ``string`` one of `waterways`, `cargo_tracks` or `passenger_tracks` |required|
  | ``vdf_alpha``: ``number`` the alpha parameter of the volume delay function (default: ``4.0``)
  | ``vdf_beta``: ``number`` the beta parameter of the volume delay function (default: ``0.64``)
  | ``cargo_pcu``: ``number`` the weight factor of a cargo vehicle (truck) on the volume (default: ``1.9``)

