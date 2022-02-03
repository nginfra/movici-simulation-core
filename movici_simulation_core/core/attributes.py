from __future__ import annotations

from movici_simulation_core.core.schema import (
    AttributeSpec,
    DataType,
    attribute_plugin_from_dict,
)

Id = AttributeSpec("id", data_type=DataType(int))
Reference = AttributeSpec("reference", data_type=DataType(str))
Labels = AttributeSpec("labels", data_type=DataType(int, csr=True))
DisplayName = AttributeSpec("display_name", data_type=DataType(str))

Geometry_X = AttributeSpec("geometry.x", data_type=DataType(float))
Geometry_Y = AttributeSpec("geometry.y", data_type=DataType(float))
Geometry_Z = AttributeSpec("geometry.z", data_type=DataType(float))
Geometry_Linestring2d = AttributeSpec(
    "geometry.linestring_2d", data_type=DataType(float, (2,), True)
)
Geometry_Linestring3d = AttributeSpec(
    "geometry.linestring_3d", data_type=DataType(float, (3,), True)
)
Geometry_Polygon = AttributeSpec("geometry.polygon", data_type=DataType(float, (2,), True))
Shape_Area = AttributeSpec("shape.area", data_type=DataType(float))
Topology_FromNodeId = AttributeSpec("topology.from_node_id", data_type=DataType(int))
Topology_ToNodeId = AttributeSpec("topology.to_node_id", data_type=DataType(int))
Shape_Length = AttributeSpec("shape.length", data_type=DataType(float))

Connection_FromId = AttributeSpec("connection.from_id", data_type=DataType(int))
Connection_FromIds = AttributeSpec(name="connection.from_ids", data_type=DataType(int, (), True))
Connection_ToId = AttributeSpec("connection.to_id", data_type=DataType(int))
Connection_ToIds = AttributeSpec(name="connection.to_ids", data_type=DataType(int, (), True))
Connection_FromDataset = AttributeSpec("connection.from_dataset", data_type=DataType(str))
Connection_ToDataset = AttributeSpec("connection.to_dataset", data_type=DataType(str))
Connection_FromReference = AttributeSpec("connection.from_reference", data_type=DataType(str))
Connection_ToReference = AttributeSpec("connection.to_reference", data_type=DataType(str))
Connection_ToReferences = AttributeSpec(
    "connection.to_references", data_type=DataType(str, (), True)
)
GlobalAttributes = attribute_plugin_from_dict(globals())
