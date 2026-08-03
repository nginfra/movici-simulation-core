"""Attribute specifications for urban drainage (storm/sewer) simulation using pyswmm/SWMM.

Attribute naming follows the Movici documentation convention:

- ``urban_drainage.*`` : urban-drainage / SWMM specific attributes
- ``shape.length`` : conduit length (reused from movici core)

Enum-typed attributes store an integer index into a dataset-defined enum (the
``general.enum`` section of the dataset). The integer maps to a SWMM keyword
string (e.g. ``"CIRCULAR"``) which the simulation wrapper feeds to SWMM. The
expected keyword values for each enum are documented next to its declaration.
"""

from __future__ import annotations

from movici_simulation_core.core import DataType
from movici_simulation_core.core.schema import AttributeSpec, attribute_plugin_from_dict

# =============================================================================
# Node outputs (PUBLISH) - shared by every node type
# =============================================================================
# water_depth is PUB|OPT: it is published every step and, when supplied as input,
# also seeds the initial water depth at t=0 (there is no separate initial_depth).
UrbanDrainage_WaterDepth = AttributeSpec("urban_drainage.water_depth", data_type=DataType(float))
UrbanDrainage_HydraulicHead = AttributeSpec(
    "urban_drainage.hydraulic_head", data_type=DataType(float)
)
UrbanDrainage_FloodingRate = AttributeSpec(
    "urban_drainage.flooding_rate", data_type=DataType(float)
)
UrbanDrainage_TotalInflow = AttributeSpec("urban_drainage.total_inflow", data_type=DataType(float))
UrbanDrainage_TotalOutflow = AttributeSpec(
    "urban_drainage.total_outflow", data_type=DataType(float)
)
UrbanDrainage_LateralInflow = AttributeSpec(
    "urban_drainage.lateral_inflow", data_type=DataType(float)
)
UrbanDrainage_StoredVolume = AttributeSpec(
    "urban_drainage.stored_volume", data_type=DataType(float)
)

# =============================================================================
# Node static inputs
# =============================================================================
# Elevation of the node invert - the bottom (lowest point) of the manhole, basin
# or outfall - in the dataset's vertical units (metres for metric flow units).
# Water depth is measured upward from here, and head = invert_elevation + depth.
UrbanDrainage_InvertElevation = AttributeSpec(
    "urban_drainage.invert_elevation", data_type=DataType(float)
)
UrbanDrainage_MaxDepth = AttributeSpec("urban_drainage.max_depth", data_type=DataType(float))
UrbanDrainage_SurchargeDepth = AttributeSpec(
    "urban_drainage.surcharge_depth", data_type=DataType(float)
)
UrbanDrainage_PondedArea = AttributeSpec("urban_drainage.ponded_area", data_type=DataType(float))

# Externally imposed node inflow (e.g. dry-weather flow or coupling from another
# model), applied each step via pyswmm ``Node.generated_inflow``.
UrbanDrainage_GeneratedInflow = AttributeSpec(
    "urban_drainage.generated_inflow", data_type=DataType(float)
)

# =============================================================================
# Outfall attributes
# =============================================================================
# Outfall type: index into enum "outfall_type" with keywords
# FREE / NORMAL / FIXED / TIDAL / TIMESERIES
UrbanDrainage_OutfallType = AttributeSpec(
    "urban_drainage.outfall_type", data_type=DataType(int), enum_name="outfall_type"
)
UrbanDrainage_FixedStage = AttributeSpec("urban_drainage.fixed_stage", data_type=DataType(float))
UrbanDrainage_FlapGate = AttributeSpec("urban_drainage.flap_gate", data_type=DataType(bool))

# =============================================================================
# Storage attributes
# =============================================================================
# Storage shape: index into enum "storage_geometry" with keywords
# FUNCTIONAL / TABULAR / CYLINDRICAL / CONICAL / PARABOLIC / PYRAMIDAL.
# When set it is authoritative; when unset the shape is inferred from which of the
# attributes below are set (a ``storage_curve`` -> TABULAR, otherwise FUNCTIONAL).
# NOTE: SWMM's keyword is PARABOLIC (not PARABOLOID, which the engine rejects).
UrbanDrainage_StorageGeometry = AttributeSpec(
    "urban_drainage.storage_geometry", data_type=DataType(int), enum_name="storage_geometry"
)
# Functional storage: area = constant + coefficient * depth ^ exponent
UrbanDrainage_StorageConstant = AttributeSpec(
    "urban_drainage.storage_constant", data_type=DataType(float)
)
UrbanDrainage_StorageCoefficient = AttributeSpec(
    "urban_drainage.storage_coefficient", data_type=DataType(float)
)
UrbanDrainage_StorageExponent = AttributeSpec(
    "urban_drainage.storage_exponent", data_type=DataType(float)
)
# Tabular storage: CSR array of (depth, surface_area) points
UrbanDrainage_StorageCurve = AttributeSpec(
    "urban_drainage.storage_curve", data_type=DataType(float, (2,), csr=True)
)
# Geometric storage (CYLINDRICAL/CONICAL/PARABOLIC/PYRAMIDAL): the SWMM L, W, Z
# parameters. Their meaning depends on the shape (per the SWMM [STORAGE] format):
#  - CYLINDRICAL: L=major axis, W=minor axis, Z unused
#  - CONICAL / PYRAMIDAL: L=base major, W=base minor, Z=side slope (run/rise)
#  - PARABOLIC: L=major axis at full height, W=minor axis at full height, Z=full height (>0)
UrbanDrainage_StorageGeometryParameters = AttributeSpec(
    "urban_drainage.storage_geometry_parameters", data_type=DataType(float, (3,))
)

# =============================================================================
# Link outputs (PUBLISH) - shared by every link type
# =============================================================================
# flow:        volumetric flow RATE through the link (e.g. m3/s for CMS units)
# flow_depth:  water depth inside the conduit/regulator (m)
# flow_volume: VOLUME of water currently stored in the link (m3)
# flow is PUB|OPT: it is published every step and, when supplied as input, seeds the
# conduit's initial flow at t=0 (there is no separate initial_flow).
UrbanDrainage_Flow = AttributeSpec("urban_drainage.flow", data_type=DataType(float))
UrbanDrainage_FlowDepth = AttributeSpec("urban_drainage.flow_depth", data_type=DataType(float))
UrbanDrainage_FlowVolume = AttributeSpec("urban_drainage.flow_volume", data_type=DataType(float))
UrbanDrainage_FroudeNumber = AttributeSpec(
    "urban_drainage.froude_number", data_type=DataType(float)
)
# The actual (applied) control setting reported by SWMM each step (0..1 for
# regulators, typically 1.0 for conduits).
UrbanDrainage_CurrentSetting = AttributeSpec(
    "urban_drainage.current_setting", data_type=DataType(float)
)

# =============================================================================
# Link control input (SUBSCRIBE)
# =============================================================================
# Target control setting for regulators (pump speed / orifice / weir opening as
# a fraction 0..1), applied each step via pyswmm ``Link.target_setting``.
UrbanDrainage_TargetSetting = AttributeSpec(
    "urban_drainage.target_setting", data_type=DataType(float)
)

# =============================================================================
# Conduit attributes
# =============================================================================
UrbanDrainage_Roughness = AttributeSpec("urban_drainage.roughness", data_type=DataType(float))
# Cross-section shape: index into enum "xsection_shape". Common keywords:
# CIRCULAR / FORCE_MAIN / FILLED_CIRCULAR / RECT_CLOSED / RECT_OPEN /
# TRAPEZOIDAL / TRIANGULAR / PARABOLIC / RECT_TRIANGULAR / RECT_ROUND /
# DUMMY (full list per SWMM [XSECTIONS]).
UrbanDrainage_CrossSectionShape = AttributeSpec(
    "urban_drainage.cross_section_shape", data_type=DataType(int), enum_name="xsection_shape"
)
# Cross-section geometry parameters Geom1..Geom4 (meaning depends on shape;
# for CIRCULAR, Geom1 is the diameter).
UrbanDrainage_CrossSectionGeometry = AttributeSpec(
    "urban_drainage.cross_section_geometry", data_type=DataType(float, (4,))
)
UrbanDrainage_Barrels = AttributeSpec("urban_drainage.barrels", data_type=DataType(int))
# Height of the conduit ends above their node inverts (named for the from/to nodes).
UrbanDrainage_FromOffset = AttributeSpec("urban_drainage.from_offset", data_type=DataType(float))
UrbanDrainage_ToOffset = AttributeSpec("urban_drainage.to_offset", data_type=DataType(float))

# =============================================================================
# Regulator (orifice / weir / outlet) shared geometry
# =============================================================================
# Height of the crest/opening above the inlet-node invert (the regulator offset).
UrbanDrainage_CrestHeight = AttributeSpec("urban_drainage.crest_height", data_type=DataType(float))
UrbanDrainage_DischargeCoefficient = AttributeSpec(
    "urban_drainage.discharge_coefficient", data_type=DataType(float)
)

# =============================================================================
# Pump attributes
# =============================================================================
# Pump curve type: index into enum "pump_curve_type" -> PUMP1..PUMP4 / IDEAL
# (the SWMM [CURVES] pump-curve keywords). When IDEAL (or no pump_curve provided)
# the pump passes its inlet inflow.
UrbanDrainage_PumpCurveType = AttributeSpec(
    "urban_drainage.pump_curve_type", data_type=DataType(int), enum_name="pump_curve_type"
)
# Pump curve as a CSR array of (x, y) points (meaning depends on pump type).
UrbanDrainage_PumpCurve = AttributeSpec(
    "urban_drainage.pump_curve", data_type=DataType(float, (2,), csr=True)
)
UrbanDrainage_StartupDepth = AttributeSpec(
    "urban_drainage.startup_depth", data_type=DataType(float)
)
UrbanDrainage_ShutoffDepth = AttributeSpec(
    "urban_drainage.shutoff_depth", data_type=DataType(float)
)

# =============================================================================
# Orifice attributes
# =============================================================================
# Orifice type: index into enum "orifice_type" -> SIDE / BOTTOM
UrbanDrainage_OrificeType = AttributeSpec(
    "urban_drainage.orifice_type", data_type=DataType(int), enum_name="orifice_type"
)
# Orifice shape: index into enum "orifice_shape" -> CIRCULAR / RECT_CLOSED
UrbanDrainage_OrificeShape = AttributeSpec(
    "urban_drainage.orifice_shape", data_type=DataType(int), enum_name="orifice_shape"
)

# =============================================================================
# Weir attributes
# =============================================================================
# Weir type: index into enum "weir_type" ->
# TRANSVERSE / SIDEFLOW / V-NOTCH / TRAPEZOIDAL / ROADWAY
UrbanDrainage_WeirType = AttributeSpec(
    "urban_drainage.weir_type", data_type=DataType(int), enum_name="weir_type"
)

# =============================================================================
# Outlet attributes
# =============================================================================
# Outlet rating type: index into enum "outlet_rating_type" ->
# FUNCTIONAL/HEAD / FUNCTIONAL/DEPTH / TABULAR/HEAD / TABULAR/DEPTH
UrbanDrainage_OutletRatingType = AttributeSpec(
    "urban_drainage.outlet_rating_type", data_type=DataType(int), enum_name="outlet_rating_type"
)
UrbanDrainage_RatingCoefficient = AttributeSpec(
    "urban_drainage.rating_coefficient", data_type=DataType(float)
)
UrbanDrainage_RatingExponent = AttributeSpec(
    "urban_drainage.rating_exponent", data_type=DataType(float)
)
# Tabular outlet rating curve as CSR array of (head_or_depth, flow) points.
UrbanDrainage_RatingCurve = AttributeSpec(
    "urban_drainage.rating_curve", data_type=DataType(float, (2,), csr=True)
)

# =============================================================================
# Subcatchment attributes
# =============================================================================
UrbanDrainage_Area = AttributeSpec("urban_drainage.area", data_type=DataType(float))
UrbanDrainage_Width = AttributeSpec("urban_drainage.width", data_type=DataType(float))
UrbanDrainage_PercentImpervious = AttributeSpec(
    "urban_drainage.percent_impervious", data_type=DataType(float)
)
UrbanDrainage_Slope = AttributeSpec("urban_drainage.slope", data_type=DataType(float))
# Movici id of the node this subcatchment drains to.
UrbanDrainage_OutletNodeId = AttributeSpec(
    "urban_drainage.outlet_node_id", data_type=DataType(int)
)
# Movici id of the rain gage driving this subcatchment's rainfall.
UrbanDrainage_RainGageId = AttributeSpec("urban_drainage.raingage_id", data_type=DataType(int))
# Subarea routing parameters (Manning n and depression storage).
UrbanDrainage_NImperv = AttributeSpec("urban_drainage.n_imperv", data_type=DataType(float))
UrbanDrainage_NPerv = AttributeSpec("urban_drainage.n_perv", data_type=DataType(float))
UrbanDrainage_SImperv = AttributeSpec("urban_drainage.s_imperv", data_type=DataType(float))
UrbanDrainage_SPerv = AttributeSpec("urban_drainage.s_perv", data_type=DataType(float))
UrbanDrainage_PctZero = AttributeSpec("urban_drainage.pct_zero", data_type=DataType(float))
# Infiltration parameters. Each subcatchment's infiltration model is resolved from
# these (see the wrapper): an ``infiltration_model_override`` in the model config
# forces one model for all subcatchments; otherwise the model is inferred from which
# family of attributes is set, falling back to the dataset's
# ``infiltration_model_default`` (general section) and finally HORTON. Each family
# reads a different subset:
#  - HORTON / MODIFIED_HORTON: max/min_infiltration_rate, decay_constant, dry_time
#  - GREEN_AMPT / MODIFIED_GREEN_AMPT: suction_head, conductivity, initial_deficit
#  - CURVE_NUMBER: curve_number, conductivity, dry_time
UrbanDrainage_MaxInfiltrationRate = AttributeSpec(
    "urban_drainage.max_infiltration_rate", data_type=DataType(float)
)
UrbanDrainage_MinInfiltrationRate = AttributeSpec(
    "urban_drainage.min_infiltration_rate", data_type=DataType(float)
)
UrbanDrainage_DecayConstant = AttributeSpec(
    "urban_drainage.decay_constant", data_type=DataType(float)
)
UrbanDrainage_DryTime = AttributeSpec("urban_drainage.dry_time", data_type=DataType(float))
UrbanDrainage_SuctionHead = AttributeSpec("urban_drainage.suction_head", data_type=DataType(float))
UrbanDrainage_Conductivity = AttributeSpec(
    "urban_drainage.conductivity", data_type=DataType(float)
)
UrbanDrainage_InitialDeficit = AttributeSpec(
    "urban_drainage.initial_deficit", data_type=DataType(float)
)
UrbanDrainage_CurveNumber = AttributeSpec("urban_drainage.curve_number", data_type=DataType(float))

# Subcatchment outputs (PUBLISH)
UrbanDrainage_Rainfall = AttributeSpec("urban_drainage.rainfall", data_type=DataType(float))
UrbanDrainage_Runoff = AttributeSpec("urban_drainage.runoff", data_type=DataType(float))
UrbanDrainage_InfiltrationLoss = AttributeSpec(
    "urban_drainage.infiltration_loss", data_type=DataType(float)
)
UrbanDrainage_EvaporationLoss = AttributeSpec(
    "urban_drainage.evaporation_loss", data_type=DataType(float)
)

# =============================================================================
# Rain gage attributes
# =============================================================================
# Externally imposed rainfall intensity, applied each step via
# pyswmm ``RainGage.total_precip``. Rainfall is driven at runtime (by other models),
# so there is no time-series format/interval to configure.
UrbanDrainage_RainfallIntensity = AttributeSpec(
    "urban_drainage.rainfall_intensity", data_type=DataType(float)
)

# =============================================================================
# Register all attributes as a plugin
# =============================================================================
UrbanDrainageAttributes = attribute_plugin_from_dict(globals())
