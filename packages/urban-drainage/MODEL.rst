Urban Drainage Model
====================

Domain
------

The urban drainage model simulates **storm water and sewer drainage networks** -
how rainfall becomes runoff, how that runoff (plus any sanitary / dry-weather
inflow) is routed through pipes, pumps, weirs, orifices and storage basins, and
where it floods or discharges. It wraps the EPA `Storm Water Management Model
(SWMM) <https://www.epa.gov/water-research/storm-water-management-model-swmm>`_
engine through `pyswmm <https://www.pyswmm.org/>`_, and is the drainage
counterpart to the WNTR-backed drinking-water model.

Features
--------

- **Hydrology** - rainfall-runoff over subcatchments, with selectable
  infiltration (Horton, Modified Horton, Green-Ampt, Modified Green-Ampt or
  Curve Number).
- **Hydraulics** - dynamic-wave routing through conduits, pumps, orifices,
  weirs and outlets, between junction / outfall / storage nodes.
- **External control** - rainfall, point inflows and regulator settings can be
  driven at runtime by other models (e.g. the Rules model), enabling real-time
  control studies.
- **Outputs** - per-element depth, head, flooding, flow, Froude number, runoff
  and stored volume.

Model characteristics
---------------------

- **Time scale.** The model is time-stepped. Movici calls ``update(moment)`` at
  a configurable ``report_timestep`` cadence (default 300 s); internally SWMM
  routes at a finer ``hydraulic_timestep`` (default 60 s). A single live SWMM
  simulation is kept open across the whole run and advanced forward to each
  Movici moment - SWMM is forward-only and cannot rewind.
- **Steady state.** There is no steady-state mode; the model always integrates
  forward in time. At ``t=0`` it reports the initial conditions without stepping.
- **Calendar.** SWMM timestamps are anchored to the Movici timeline reference,
  so the engine's clock matches the scenario's world time.
- **Control latency.** Control inputs are applied to the live engine *before*
  each forward step, so a value supplied at time *t* governs the step from *t*
  onward (a one-step latency, as in real-time control).

Entities and attributes
-----------------------

Each SWMM object type maps to a Movici entity group. Static parameters needed to
build the network are ``INIT`` (required); optional parameters and runtime
control inputs are ``OPT``; per-step results are ``PUB`` (published). Units follow
the configured ``flow_units`` (metric ``CMS`` by default: metres, m³/s, mm/hr).
See the SWMM5 Reference Manual for the underlying definitions.

Nodes (``PointEntity``)
~~~~~~~~~~~~~~~~~~~~~~~~~

``drainage_junction_entities``, ``drainage_outfall_entities``,
``drainage_storage_entities``.

Shared inputs/outputs (``invert_elevation`` INIT; ``generated_inflow`` OPT input;
``water_depth``/``hydraulic_head``/``flooding``/``total_inflow``/``total_outflow``/
``lateral_inflow``/``stored_volume`` published). Junctions add ``max_depth`` and
ponding options; outfalls add ``outfall_type`` (+ ``fixed_stage``); storage adds
either functional coefficients (``storage_constant``/``coefficient``/``exponent``)
or a tabular ``storage_curve`` - the shape is inferred from which is present.

============================  ====  =====================================================
Attribute                     Flag  Meaning (units)
============================  ====  =====================================================
urban_drainage.invert_elevation  INIT  Node bottom elevation (m)
urban_drainage.generated_inflow  OPT   Externally imposed point inflow (m³/s)
urban_drainage.water_depth       PUB   Water depth above the invert (m)
urban_drainage.hydraulic_head    PUB   Hydraulic head = invert + depth (m)
urban_drainage.flooding          PUB   Surface flooding / overflow rate (m³/s)
urban_drainage.total_inflow      PUB   Total inflow to the node (m³/s)
urban_drainage.total_outflow     PUB   Total outflow from the node (m³/s)
urban_drainage.lateral_inflow    PUB   External + runoff inflow (m³/s)
urban_drainage.stored_volume     PUB   Water volume held at the node (m³)
============================  ====  =====================================================

Links (``LinkEntity``, routed between ``from_node_id`` / ``to_node_id``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``drainage_conduit_entities`` (``length``, ``roughness``, ``cross_section_shape``
+ ``cross_section_geometry``), ``drainage_pump_entities`` (``pump_curve`` /
``pump_curve_type``), ``drainage_orifice_entities``, ``drainage_weir_entities``,
``drainage_outlet_entities``. All links publish ``flow`` (rate, m³/s),
``flow_depth`` (m), ``flow_volume`` (m³), ``froude_number`` and
``current_setting``; all accept an optional ``target_setting`` (0-1) control.

Hydrology
~~~~~~~~~

``drainage_subcatchment_entities`` (``PolygonEntity``) - ``area``, ``width``,
``percent_impervious``, ``slope``, plus ``outlet_node_id`` / ``raingage_id`` links
and the infiltration parameters; publishes ``rainfall``, ``runoff``, ``runon``,
``infiltration_loss``, ``evaporation_loss``, ``snow_depth``.
``drainage_raingage_entities`` (``PointEntity``) - accepts a runtime
``rainfall_intensity`` (mm/hr) and publishes ``rainfall``.

How it works
-----------

1. On ``initialize`` the Movici dataset is synthesised into a transient SWMM
   ``.inp`` file and a live ``Simulation`` is opened.
2. Each ``update(moment)`` applies the current control inputs to the live SWMM
   objects, advances the simulation forward to that moment, and reads the
   per-element results back into the published attributes.
3. SWMM solves the **dynamic-wave** form of the Saint-Venant equations for
   conduit routing, with rainfall-runoff and infiltration on the subcatchments.

Network characteristics: looped and branched networks, backwater, surcharging
and pressurised flow are all supported by the dynamic-wave solver.

Scope and limitations
--------------------

- **Dividers** are not modelled (under dynamic-wave routing SWMM treats them as
  ordinary junctions).
- Link **velocity** is not published (the runtime engine exposes no usable
  per-link velocity); the Froude number is published instead.
- Outfalls support ``FREE`` / ``NORMAL`` / ``FIXED`` boundaries; ``TIDAL`` and
  ``TIMESERIES`` (which need referenced boundary data) are not yet supported.
- Water quality / pollutants, LID controls and groundwater are out of scope for
  this version.
