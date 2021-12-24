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

PointProperties_PositionX = AttributeSpec("geometry.x", data_type=DataType(float))
PointProperties_PositionY = AttributeSpec("geometry.y", data_type=DataType(float))
PointProperties_PositionZ = AttributeSpec("geometry.z", data_type=DataType(float))
ShapeProperties_Linestring2d = AttributeSpec(
    "geometry.linestring_2d", data_type=DataType(float, (2,), True)
)
ShapeProperties_Linestring3d = AttributeSpec(
    "geometry.linestring_3d", data_type=DataType(float, (3,), True)
)
ShapeProperties_Polygon = AttributeSpec("geometry.polygon", data_type=DataType(float, (2,), True))
ShapeProperties_Area = AttributeSpec("shape.area", data_type=DataType(float))
LineProperties_FromNodeId = AttributeSpec("topology.from_node_id", data_type=DataType(int))
LineProperties_ToNodeId = AttributeSpec("topology.to_node_id", data_type=DataType(int))
LineProperties_Length = AttributeSpec("shape.length", data_type=DataType(float))

ConnectionProperties_FromId = AttributeSpec("connection.from_id", data_type=DataType(int))
ConnectionProperties_FromIds = AttributeSpec(
    name="connection.from_ids", data_type=DataType(int, (), True)
)
ConnectionProperties_ToId = AttributeSpec("connection.to_id", data_type=DataType(int))
ConnectionProperties_ToIds = AttributeSpec(
    name="connection.to_ids", data_type=DataType(int, (), True)
)
ConnectionProperties_FromDataset = AttributeSpec(
    "connection.from_dataset", data_type=DataType(str)
)
ConnectionProperties_ToDataset = AttributeSpec("connection.to_dataset", data_type=DataType(str))
ConnectionProperties_FromReference = AttributeSpec(
    "connection.from_reference", data_type=DataType(str)
)
ConnectionProperties_ToReference = AttributeSpec(
    "connection.to_reference", data_type=DataType(str)
)
ConnectionProperties_ToReferences = AttributeSpec(
    "connection.to_references", data_type=DataType(str, (), True)
)
GlobalAttributes = attribute_plugin_from_dict(globals())
