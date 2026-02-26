
.. _movici-common-attributes:

Common Attributes
=================

While it is up to a model/scenario developer to define domain-specific attributes. Some attributes
are already defined in the system. The following tabel gives an overview of these attributes:

.. list-table::
  :widths: 10 20 20 50
  :header-rows: 1

  * - Attribute
    - Data type [*]_
    - Unit
    - Description
  * - ``id``
    - ``int``
    - \-
    - Entity identifier, must be unique within a dataset

  * - ``display_name``
    - ``str``
    - \-
    - An attribute to provide a human readable name for an entity

  * - ``reference``
    - ``str``
    - \-
    - An attribute that can be used to provide a (unique) asset id

  * - ``labels``
    - ``int`` , ``csr``
    - \-
    - Assign 0 or more labels to an entity, uses the ``label`` enum

  * - ``geometry.x``
    - ``float``
    - ``m`` or ``deg`` depending on CRS
    - X component of a Point geometry
  * - ``geometry.y``
    - ``float``
    - ``m`` or ``deg`` depending on CRS
    - Y component of a Point geometry
  * - ``geometry.z``
    - ``float``
    - ``m``
    - Z component of a Point geometry
  * - ``geometry.linestring_2d``
    - ``float``, ``(2,)`` , ``csr``
    - ``m`` or ``deg`` depending on CRS
    - Geometry of a 2D LineString
  * - ``geometry.linestring_3d``
    - ``float``, ``(3,)`` , ``csr``
    - ``m`` or ``deg`` depending on CRS
    - Geometry of a 3D LineString
  * - ``geometry.polygon_2d``
    - ``float``, ``(2,)`` , ``csr``
    - ``m`` or ``deg`` depending on CRS
    - Geometry of a 2D (closed) Polygon
  * - ``geometry.polygon_3d``
    - ``float``, ``(3,)`` , ``csr``
    - ``m`` or ``deg`` depending on CRS
    - Geometry of a 3D (closed) Polygon
  * - ``geometry.polygon``
    - ``float``, ``(2,)`` , ``csr``
    - ``m`` or ``deg`` depending on CRS
    - Legacy geometry attribute, equivalent to ``geometry.polygon_2d``
  * - ``grid.grid_points``
    - ``int``, ``csr``
    - \-
    - Used in grid-type datasets where every entity represents a grid cell. Values refer to the
      ``id`` of entities that form the vertices for each grid cell. Those entities are expected to
      have a point geometry (``geometry.x`` and ``geometry.y``)

  * - ``topology.from_node_id``
    - ``int``
    - \-
    - Used in network-type datasets to connect edges to nodes. The value refers to the ``id`` of
      an entity that acts as a node. Marks the beginning of a (directional) edge.
  * - ``topology.to_node_id``
    - ``int``
    - \-
    - Used in network-type datasets to connect edges to nodes. The value refers to the ``id`` of
      an entity that acts as a node. Marks the end of a (directional) edge.
  * - ``shape.area``
    - ``float``
    - ``m``
    - Area of a Polygon
  * - ``shape.length``
    - ``float``
    - ``m``
    - length of a LineString
  * - ``connection.from_id``
    - ``int``
    - \-

    - Arbitrary reference that connects this entity to an entity that may reside in a different
      dataset. See also ``connection.from_dataset``
  * - ``connection.from_ids``
    - ``int`` , ``csr``
    - \-

    - Arbitrary reference that connects this entity to zero or more entities that may reside in a
      different dataset. See also ``connection.from_dataset``. All connected entities must reside
      in the same dataset
  * - ``connection.to_id``
    - ``int``
    - \-

    - Arbitrary reference that connects this entity to an entity that may reside in a different
      dataset. See also ``connection.to_dataset``
  * - ``connection.to_ids``
    - ``int`` , ``csr``
    - \-

    - Arbitrary reference that connects this entity to zero or more entities that may reside in a
      different dataset. See also ``connection.to_dataset``. All connected entities must reside
      in the same dataset
  * - ``connection.from_dataset``
    - ``str``
    - \-

    - a reference to a dataset in which the ``from`` connected entities reside. May be the same
      dataset as the connecting entity's, or a different one. Can also be used without an
      accompanying ``from_id`` / ``from_reference`` attribute, in which case a model may create
      a connection itself based on proximity using the ``movici-geo-query`` spatial indexing tools
  * - ``connection.to_dataset``
    - ``str``
    - \-

    - a reference to a dataset in which the ``to`` connected entities reside. May be the same
      dataset as the connecting entity's, or a different one. Can also be used without an
      accompanying ``from_id`` / ``from_reference`` attribute, in which case a model may create
      a connection itself based on proximity using the ``movici-geo-query`` spatial indexing tools
  * - ``connection.from_reference``
    - ``str``
    - \-

    - Arbitrary reference that connects this entity to an entity that may reside in a different
      dataset. See also ``connection.from_dataset``. The connection is defined based on the
      ``reference`` field of the connected entity. This may be used as an alternative as
      ``connection.from_id`` in case the connected entity's ``id`` attribute is not known
      beforehand.
  * - ``connection.from_references``
    - ``str`` , ``csr``
    - \-

    - Arbitrary reference that connects this entity to zero or more entities that may reside in a
      different dataset. See also ``connection.from_dataset``. All connected entities must reside
      in the same dataset. The connection is defined based on the ``reference`` field of the
      connected entity. This may be used as an alternative as ``connection.from_ids`` in case
      the connected entities' ``id`` atttributes are not known beforehand.
  * - ``connection.to_reference``
    - ``str``
    - \-

    - Arbitrary reference that connects this entity to an entity that may reside in a different
      dataset. See also ``connection.to_dataset``. The connection is defined based on the
      ``reference`` field of the connected entity. This may be used as an alternative as
      ``connection.to_id`` in case the connected entity's ``id`` attribute is not known
      beforehand.
  * - ``connection.to_references``
    - ``str`` , ``csr``
    - \-

    - Arbitrary reference that connects this entity to zero or more entities that may reside in a
      different dataset. See also ``connection.to_dataset``. All connected entities must reside
      in the same dataset. The connection is defined based on the ``reference`` field of the
      connected entity. This may be used as an alternative as ``connection.to_ids`` in case
      the connected entities' ``id`` atttributes are not known beforehand.

.. [*] See :ref:`movici-data-format-data-types` for an explanation of the data types

These attributes can all be imported from :mod:`movici_simulation_core.core.attributes`
