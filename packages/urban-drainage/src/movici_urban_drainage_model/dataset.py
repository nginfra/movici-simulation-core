"""Entity definitions for urban drainage (storm/sewer) simulation.

Entity groups map the SWMM object model onto Movici geometry entities:

- nodes (junctions, outfalls, storage units) are :class:`PointEntity`
- links (conduits, pumps, orifices, weirs, outlets) are :class:`LinkEntity`
  and route between their ``from_node_id`` / ``to_node_id``
- subcatchments are :class:`PolygonEntity`
- rain gages are :class:`PointEntity`

Static SWMM parameters (needed to build the model) are ``INIT``; optional
parameters and runtime control inputs are ``OPT``; per-step simulation results
are ``PUB``.

.. note::
   Dividers are not modelled: SWMM treats them as ordinary junctions under
   dynamic-wave routing. Coordinates (``geometry.x/y``) are used to write the
   SWMM ``[COORDINATES]`` section; they do not affect the simulation results.
"""

import dataclasses

from movici_simulation_core.attributes import Shape_Length
from movici_simulation_core.core.attribute import INIT, OPT, PUB, field
from movici_simulation_core.models.common.entity_groups import (
    LinkEntity,
    PointEntity,
    PolygonEntity,
)

from .attributes import (
    UrbanDrainage_Area,
    UrbanDrainage_Barrels,
    UrbanDrainage_Conductivity,
    UrbanDrainage_CrestHeight,
    UrbanDrainage_CrossSectionGeometry,
    UrbanDrainage_CrossSectionShape,
    UrbanDrainage_CurrentSetting,
    UrbanDrainage_CurveNumber,
    UrbanDrainage_DecayConstant,
    UrbanDrainage_DischargeCoefficient,
    UrbanDrainage_DryTime,
    UrbanDrainage_EvaporationLoss,
    UrbanDrainage_FixedStage,
    UrbanDrainage_FlapGate,
    UrbanDrainage_Flooding,
    UrbanDrainage_Flow,
    UrbanDrainage_FlowDepth,
    UrbanDrainage_FlowVolume,
    UrbanDrainage_FroudeNumber,
    UrbanDrainage_GeneratedInflow,
    UrbanDrainage_HydraulicHead,
    UrbanDrainage_InfiltrationLoss,
    UrbanDrainage_InitialDeficit,
    UrbanDrainage_InitialDepth,
    UrbanDrainage_InitialFlow,
    UrbanDrainage_InletOffset,
    UrbanDrainage_InvertElevation,
    UrbanDrainage_LateralInflow,
    UrbanDrainage_MaxDepth,
    UrbanDrainage_MaxInfiltrationRate,
    UrbanDrainage_MinInfiltrationRate,
    UrbanDrainage_NImperv,
    UrbanDrainage_NPerv,
    UrbanDrainage_OrificeShape,
    UrbanDrainage_OrificeType,
    UrbanDrainage_OutfallType,
    UrbanDrainage_OutletNodeId,
    UrbanDrainage_OutletOffset,
    UrbanDrainage_OutletRatingType,
    UrbanDrainage_PctZero,
    UrbanDrainage_PercentImpervious,
    UrbanDrainage_PondedArea,
    UrbanDrainage_PumpCurve,
    UrbanDrainage_PumpCurveType,
    UrbanDrainage_Rainfall,
    UrbanDrainage_RainfallFormat,
    UrbanDrainage_RainfallIntensity,
    UrbanDrainage_RainfallInterval,
    UrbanDrainage_RainGageId,
    UrbanDrainage_RatingCoefficient,
    UrbanDrainage_RatingCurve,
    UrbanDrainage_RatingExponent,
    UrbanDrainage_Roughness,
    UrbanDrainage_Runoff,
    UrbanDrainage_Runon,
    UrbanDrainage_ShutoffDepth,
    UrbanDrainage_SImperv,
    UrbanDrainage_Slope,
    UrbanDrainage_SnowDepth,
    UrbanDrainage_SPerv,
    UrbanDrainage_StartupDepth,
    UrbanDrainage_StorageCoefficient,
    UrbanDrainage_StorageConstant,
    UrbanDrainage_StorageCurve,
    UrbanDrainage_StorageExponent,
    UrbanDrainage_StoredVolume,
    UrbanDrainage_SuctionHead,
    UrbanDrainage_SurchargeDepth,
    UrbanDrainage_TargetSetting,
    UrbanDrainage_TotalInflow,
    UrbanDrainage_TotalOutflow,
    UrbanDrainage_WaterDepth,
    UrbanDrainage_WeirType,
    UrbanDrainage_Width,
)


class DrainageNodeEntity(PointEntity):
    """Base class for drainage network nodes with common output attributes.

    Keeps ``geometry.x`` / ``geometry.y`` (used to write SWMM ``[COORDINATES]``)
    and drops the elevation / reference attributes that the model does not need.
    """

    __exclude__ = ["z", "reference"]

    # PUBLISH outputs shared by all node types
    water_depth = field(UrbanDrainage_WaterDepth, flags=PUB)
    hydraulic_head = field(UrbanDrainage_HydraulicHead, flags=PUB)
    flooding = field(UrbanDrainage_Flooding, flags=PUB)
    total_inflow = field(UrbanDrainage_TotalInflow, flags=PUB)
    total_outflow = field(UrbanDrainage_TotalOutflow, flags=PUB)
    lateral_inflow = field(UrbanDrainage_LateralInflow, flags=PUB)
    stored_volume = field(UrbanDrainage_StoredVolume, flags=PUB)

    # Optional external inflow injected each step (coupling / dry-weather flow)
    generated_inflow = field(UrbanDrainage_GeneratedInflow, flags=OPT)


class DrainageLinkEntity(LinkEntity):
    """Base class for drainage network links with common output attributes.

    Links route between ``from_node_id`` / ``to_node_id`` (inherited, ``INIT``);
    the line geometry is not needed by the simulation.
    """

    __exclude__ = ["reference", "_linestring2d", "_linestring3d"]

    # PUBLISH outputs shared by all link types
    flow = field(UrbanDrainage_Flow, flags=PUB)
    flow_depth = field(UrbanDrainage_FlowDepth, flags=PUB)
    flow_volume = field(UrbanDrainage_FlowVolume, flags=PUB)
    froude_number = field(UrbanDrainage_FroudeNumber, flags=PUB)
    current_setting = field(UrbanDrainage_CurrentSetting, flags=PUB)

    # Optional control input (regulator opening / pump speed, fraction 0..1)
    target_setting = field(UrbanDrainage_TargetSetting, flags=OPT)

    def is_ready(self):
        return True


# ---------------------------------------------------------------------------
# Node entity groups
# ---------------------------------------------------------------------------


class JunctionEntity(DrainageNodeEntity):
    """Drainage junctions: manholes / pipe connection nodes."""

    __entity_name__ = "drainage_junction_entities"

    invert_elevation = field(UrbanDrainage_InvertElevation, flags=INIT)

    max_depth = field(UrbanDrainage_MaxDepth, flags=OPT)
    initial_depth = field(UrbanDrainage_InitialDepth, flags=OPT)
    surcharge_depth = field(UrbanDrainage_SurchargeDepth, flags=OPT)
    ponded_area = field(UrbanDrainage_PondedArea, flags=OPT)


class OutfallEntity(DrainageNodeEntity):
    """Drainage outfalls: terminal nodes with a boundary stage condition."""

    __entity_name__ = "drainage_outfall_entities"

    invert_elevation = field(UrbanDrainage_InvertElevation, flags=INIT)
    outfall_type = field(UrbanDrainage_OutfallType, flags=INIT)

    fixed_stage = field(UrbanDrainage_FixedStage, flags=OPT)
    flap_gate = field(UrbanDrainage_FlapGate, flags=OPT)


class StorageEntity(DrainageNodeEntity):
    """Drainage storage units: ponds / basins / tanks with a stage-area curve.

    The storage geometry is defined either functionally
    (``area = constant + coefficient * depth ^ exponent``) or by a tabular
    ``storage_curve`` of (depth, surface_area) points.
    """

    __entity_name__ = "drainage_storage_entities"

    invert_elevation = field(UrbanDrainage_InvertElevation, flags=INIT)
    max_depth = field(UrbanDrainage_MaxDepth, flags=INIT)

    storage_constant = field(UrbanDrainage_StorageConstant, flags=OPT)
    storage_coefficient = field(UrbanDrainage_StorageCoefficient, flags=OPT)
    storage_exponent = field(UrbanDrainage_StorageExponent, flags=OPT)
    storage_curve = field(UrbanDrainage_StorageCurve, flags=OPT)
    initial_depth = field(UrbanDrainage_InitialDepth, flags=OPT)
    surcharge_depth = field(UrbanDrainage_SurchargeDepth, flags=OPT)
    ponded_area = field(UrbanDrainage_PondedArea, flags=OPT)


# ---------------------------------------------------------------------------
# Link entity groups
# ---------------------------------------------------------------------------


class ConduitEntity(DrainageLinkEntity):
    """Drainage conduits: pipes and channels carrying gravity flow."""

    __entity_name__ = "drainage_conduit_entities"

    length = field(Shape_Length, flags=INIT)
    roughness = field(UrbanDrainage_Roughness, flags=INIT)
    cross_section_shape = field(UrbanDrainage_CrossSectionShape, flags=INIT)
    cross_section_geometry = field(UrbanDrainage_CrossSectionGeometry, flags=INIT)

    barrels = field(UrbanDrainage_Barrels, flags=OPT)
    inlet_offset = field(UrbanDrainage_InletOffset, flags=OPT)
    outlet_offset = field(UrbanDrainage_OutletOffset, flags=OPT)
    initial_flow = field(UrbanDrainage_InitialFlow, flags=OPT)


class PumpEntity(DrainageLinkEntity):
    """Drainage pumps: lift water from the inlet node to the outlet node.

    With no ``pump_curve`` (or an ``IDEAL`` ``pump_curve_type``) the pump passes
    its inlet inflow directly. Otherwise the curve defines the pump behaviour.
    """

    __entity_name__ = "drainage_pump_entities"

    pump_curve_type = field(UrbanDrainage_PumpCurveType, flags=OPT)
    pump_curve = field(UrbanDrainage_PumpCurve, flags=OPT)
    startup_depth = field(UrbanDrainage_StartupDepth, flags=OPT)
    shutoff_depth = field(UrbanDrainage_ShutoffDepth, flags=OPT)


class OrificeEntity(DrainageLinkEntity):
    """Drainage orifices: openings (side or bottom) regulating flow.

    ``cross_section_geometry`` carries the opening dimensions (Geom1 = height,
    Geom2 = width for rectangular orifices; Geom1 = diameter for circular).
    """

    __entity_name__ = "drainage_orifice_entities"

    orifice_type = field(UrbanDrainage_OrificeType, flags=INIT)
    orifice_shape = field(UrbanDrainage_OrificeShape, flags=INIT)
    cross_section_geometry = field(UrbanDrainage_CrossSectionGeometry, flags=INIT)
    discharge_coefficient = field(UrbanDrainage_DischargeCoefficient, flags=INIT)

    crest_height = field(UrbanDrainage_CrestHeight, flags=OPT)
    flap_gate = field(UrbanDrainage_FlapGate, flags=OPT)


class WeirEntity(DrainageLinkEntity):
    """Drainage weirs: crested structures regulating overflow.

    ``cross_section_geometry`` carries the opening dimensions (Geom1 = height,
    Geom2 = length, Geom3 = side slope for trapezoidal/v-notch weirs).
    """

    __entity_name__ = "drainage_weir_entities"

    weir_type = field(UrbanDrainage_WeirType, flags=INIT)
    cross_section_geometry = field(UrbanDrainage_CrossSectionGeometry, flags=INIT)
    discharge_coefficient = field(UrbanDrainage_DischargeCoefficient, flags=INIT)

    crest_height = field(UrbanDrainage_CrestHeight, flags=OPT)
    flap_gate = field(UrbanDrainage_FlapGate, flags=OPT)


class OutletEntity(DrainageLinkEntity):
    """Drainage outlets: flow-control links with a head/depth-discharge rating.

    Rating is either functional (``flow = coefficient * x ^ exponent``) or a
    tabular ``rating_curve`` of (head_or_depth, flow) points, selected by
    ``outlet_rating_type``.
    """

    __entity_name__ = "drainage_outlet_entities"

    outlet_rating_type = field(UrbanDrainage_OutletRatingType, flags=INIT)

    crest_height = field(UrbanDrainage_CrestHeight, flags=OPT)
    rating_coefficient = field(UrbanDrainage_RatingCoefficient, flags=OPT)
    rating_exponent = field(UrbanDrainage_RatingExponent, flags=OPT)
    rating_curve = field(UrbanDrainage_RatingCurve, flags=OPT)
    flap_gate = field(UrbanDrainage_FlapGate, flags=OPT)


# ---------------------------------------------------------------------------
# Hydrology entity groups
# ---------------------------------------------------------------------------


class SubcatchmentEntity(PolygonEntity):
    """Drainage subcatchments: surfaces generating runoff from rainfall.

    Runoff is routed to ``outlet_node_id`` and driven by the rain gage
    referenced through ``raingage_id``. The polygon geometry is optional and
    used for display only, so readiness does not depend on it.
    """

    __entity_name__ = "drainage_subcatchment_entities"
    __exclude__ = ["reference"]

    # INIT static inputs
    area = field(UrbanDrainage_Area, flags=INIT)
    width = field(UrbanDrainage_Width, flags=INIT)
    percent_impervious = field(UrbanDrainage_PercentImpervious, flags=INIT)
    slope = field(UrbanDrainage_Slope, flags=INIT)
    outlet_node_id = field(UrbanDrainage_OutletNodeId, flags=INIT)
    raingage_id = field(UrbanDrainage_RainGageId, flags=INIT)

    # OPT subarea routing parameters
    n_imperv = field(UrbanDrainage_NImperv, flags=OPT)
    n_perv = field(UrbanDrainage_NPerv, flags=OPT)
    s_imperv = field(UrbanDrainage_SImperv, flags=OPT)
    s_perv = field(UrbanDrainage_SPerv, flags=OPT)
    pct_zero = field(UrbanDrainage_PctZero, flags=OPT)

    # OPT infiltration parameters; the active subset depends on the configured
    # infiltration model (Horton / Green-Ampt / Curve Number).
    max_infiltration_rate = field(UrbanDrainage_MaxInfiltrationRate, flags=OPT)
    min_infiltration_rate = field(UrbanDrainage_MinInfiltrationRate, flags=OPT)
    decay_constant = field(UrbanDrainage_DecayConstant, flags=OPT)
    dry_time = field(UrbanDrainage_DryTime, flags=OPT)
    suction_head = field(UrbanDrainage_SuctionHead, flags=OPT)
    conductivity = field(UrbanDrainage_Conductivity, flags=OPT)
    initial_deficit = field(UrbanDrainage_InitialDeficit, flags=OPT)
    curve_number = field(UrbanDrainage_CurveNumber, flags=OPT)

    # PUBLISH outputs
    rainfall = field(UrbanDrainage_Rainfall, flags=PUB)
    runoff = field(UrbanDrainage_Runoff, flags=PUB)
    runon = field(UrbanDrainage_Runon, flags=PUB)
    infiltration_loss = field(UrbanDrainage_InfiltrationLoss, flags=PUB)
    evaporation_loss = field(UrbanDrainage_EvaporationLoss, flags=PUB)
    snow_depth = field(UrbanDrainage_SnowDepth, flags=PUB)

    def is_ready(self):
        return (
            self.area.is_initialized()
            and self.width.is_initialized()
            and self.percent_impervious.is_initialized()
            and self.slope.is_initialized()
        )


class RainGageEntity(PointEntity):
    """Drainage rain gages: rainfall sources for subcatchments.

    Rainfall may be driven at runtime by another model publishing
    ``rainfall_intensity`` (applied via SWMM ``RainGage.total_precip``).
    """

    __entity_name__ = "drainage_raingage_entities"
    __exclude__ = ["z", "reference"]

    rainfall_format = field(UrbanDrainage_RainfallFormat, flags=OPT)
    rainfall_interval = field(UrbanDrainage_RainfallInterval, flags=OPT)

    # Optional runtime rainfall override
    rainfall_intensity = field(UrbanDrainage_RainfallIntensity, flags=OPT)

    # PUBLISH output
    rainfall = field(UrbanDrainage_Rainfall, flags=PUB)


@dataclasses.dataclass
class UrbanDrainageNetwork:
    junctions: JunctionEntity
    outfalls: OutfallEntity
    storage: StorageEntity
    conduits: ConduitEntity
    pumps: PumpEntity
    orifices: OrificeEntity
    weirs: WeirEntity
    outlets: OutletEntity
    subcatchments: SubcatchmentEntity
    raingages: RainGageEntity
