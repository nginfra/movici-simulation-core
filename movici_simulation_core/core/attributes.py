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

PointProperties_PositionX = AttributeSpec(
    "position_x", component="point_properties", data_type=DataType(float)
)
PointProperties_PositionY = AttributeSpec(
    "position_y", component="point_properties", data_type=DataType(float)
)
PointProperties_PositionZ = AttributeSpec(
    "position_z", component="point_properties", data_type=DataType(float)
)
ShapeProperties_Linestring2d = AttributeSpec(
    "linestring_2d", component="shape_properties", data_type=DataType(float, (2,), True)
)
ShapeProperties_Linestring3d = AttributeSpec(
    "linestring_3d", component="shape_properties", data_type=DataType(float, (3,), True)
)
ShapeProperties_Polygon = AttributeSpec(
    "polygon", component="shape_properties", data_type=DataType(float, (2,), True)
)
ShapeProperties_Area = AttributeSpec(
    "area", component="shape_properties", data_type=DataType(float)
)
LineProperties_FromNodeId = AttributeSpec(
    "from_node_id", component="line_properties", data_type=DataType(int)
)
LineProperties_ToNodeId = AttributeSpec(
    "to_node_id", component="line_properties", data_type=DataType(int)
)
LineProperties_Length = AttributeSpec(
    "length", component="line_properties", data_type=DataType(float)
)

ConnectionProperties_FromId = AttributeSpec(
    "from_id", component="connection_properties", data_type=DataType(int)
)
ConnectionProperties_FromIds = AttributeSpec(
    name="from_ids", component="connection_properties", data_type=DataType(int, (), True)
)
ConnectionProperties_ToId = AttributeSpec(
    "to_id", component="connection_properties", data_type=DataType(int)
)
ConnectionProperties_ToIds = AttributeSpec(
    name="to_ids", component="connection_properties", data_type=DataType(int, (), True)
)
ConnectionProperties_FromDataset = AttributeSpec(
    "from_dataset", component="connection_properties", data_type=DataType(str)
)
ConnectionProperties_ToDataset = AttributeSpec(
    "to_dataset", component="connection_properties", data_type=DataType(str)
)
ConnectionProperties_FromReference = AttributeSpec(
    "from_reference", component="connection_properties", data_type=DataType(str)
)
ConnectionProperties_ToReference = AttributeSpec(
    "to_reference", component="connection_properties", data_type=DataType(str)
)
ConnectionProperties_ToReferences = AttributeSpec(
    "to_references", component="connection_properties", data_type=DataType(str, (), True)
)
GlobalAttributes = attribute_plugin_from_dict(globals())
