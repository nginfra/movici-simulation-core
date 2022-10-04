
.. _movici-geometries:

Geometries
============

Movici supports three kind of geometries for geospatial entities: ``points``, ``lines`` and
``polgyons``. These geometries are very similar to the GeoJSON features ``Point``, ``LineString``
and ``Polygon``:

+-----------+------------+--------------------------------+--------------------------------------+
| Movici    | GeoJSON    | Associated attributes          | Remarks                              |
+===========+============+================================+======================================+
| Point     | Point      | ``geometry.x`` ``geometry.y``  | ``geometry.z`` attribute is optional |
|           |            | ``geometry.z``                 |                                      |
+-----------+------------+--------------------------------+--------------------------------------+
| Line      | LineString | ``geometry.linestring_2d``     |  ``2d``/ ``3d`` depends on existence |
|           |            | ``geometry.linestring_3d``     |  of elevation component              |
+-----------+------------+--------------------------------+--------------------------------------+
| Polygon   | Polygon    | ``geometry.polygon``           | Supports only outer polygons.        |
|           |            | ``geometry.polygon_2d``        | ``2d``/ ``3d`` depends on existence  |
|           |            | ``geometry.polygon_3d``        | of elevation component.              |
|           |            |                                | ``geometry.polygon`` is implicitly   |
|           |            |                                | 2d.  Polygons must be closed loops.  |
+-----------+------------+--------------------------------+--------------------------------------+



