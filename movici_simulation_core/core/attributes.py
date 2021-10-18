from __future__ import annotations

from movici_simulation_core.core.schema import (
    PropertySpec,
    DataType,
    attribute_plugin_from_dict,
)

Id = PropertySpec("id", data_type=DataType(int))
Reference = PropertySpec("reference", data_type=DataType(str))
Labels = PropertySpec("labels", data_type=DataType(int, csr=True))
DisplayName = PropertySpec("display_name", data_type=DataType(str))

PointProperties_PositionX = PropertySpec(
    "position_x", component="point_properties", data_type=DataType(float)
)
PointProperties_PositionY = PropertySpec(
    "position_y", component="point_properties", data_type=DataType(float)
)
PointProperties_PositionZ = PropertySpec(
    "position_z", component="point_properties", data_type=DataType(float)
)
ShapeProperties_Linestring2d = PropertySpec(
    "linestring_2d", component="shape_properties", data_type=DataType(float, (2,), True)
)
ShapeProperties_Linestring3d = PropertySpec(
    "linestring_3d", component="shape_properties", data_type=DataType(float, (3,), True)
)
ShapeProperties_Polygon = PropertySpec(
    "polygon", component="shape_properties", data_type=DataType(float, (2,), True)
)
ShapeProperties_Area = PropertySpec(
    "area", component="shape_properties", data_type=DataType(float)
)
LineProperties_FromNodeId = PropertySpec(
    "from_node_id", component="line_properties", data_type=DataType(int)
)
LineProperties_ToNodeId = PropertySpec(
    "to_node_id", component="line_properties", data_type=DataType(int)
)
LineProperties_Length = PropertySpec(
    "length", component="line_properties", data_type=DataType(float)
)

ConnectionProperties_FromId = PropertySpec(
    "from_id", component="connection_properties", data_type=DataType(int)
)
ConnectionProperties_FromIds = PropertySpec(
    name="from_ids", component="connection_properties", data_type=DataType(int, (), True)
)
ConnectionProperties_ToId = PropertySpec(
    "to_id", component="connection_properties", data_type=DataType(int)
)
ConnectionProperties_ToIds = PropertySpec(
    name="to_ids", component="connection_properties", data_type=DataType(int, (), True)
)
ConnectionProperties_FromDataset = PropertySpec(
    "from_dataset", component="connection_properties", data_type=DataType(str)
)
ConnectionProperties_ToDataset = PropertySpec(
    "to_dataset", component="connection_properties", data_type=DataType(str)
)
ConnectionProperties_FromReference = PropertySpec(
    "from_reference", component="connection_properties", data_type=DataType(str)
)
ConnectionProperties_ToReference = PropertySpec(
    "to_reference", component="connection_properties", data_type=DataType(str)
)
ConnectionProperties_ToReferences = PropertySpec(
    "to_references", component="connection_properties", data_type=DataType(str, (), True)
)
GlobalAttributes = attribute_plugin_from_dict(globals())
