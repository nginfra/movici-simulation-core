# WNTR Drinking Water Model - Research Findings

This document contains answers to questions raised in `drinking_water_model.rst` based on research from WNTR documentation and source code.

## Question 1: Pause and Restart (Lines 68-74)

**Q:** Can WNTR be "paused" at a certain internal timestamp and then "resumed" later with small changes to the input state?

**A: Yes!** The WNTRSimulator supports this functionality.

### Implementation Options

1. **Reset Initial Values Method:**
   - Use `wn.reset_initial_values()` to restore simulation parameters to starting values
   - Works well when only baseline conditions require adjustment between runs

2. **Pickle Serialization Method:**
   - Save complete network models using pickle files before/after simulation cycles
   - Preserves custom controls and full network state

### Usage Example
```python
# Run simulation for 10 hours
sim = wntr.sim.WNTRSimulator(wn)
results1 = sim.run_sim(duration=10*3600)

# Modify network state (e.g., close a pipe)
wn.get_link('pipe1').status = 'CLOSED'

# Continue simulation for 14 more hours
results2 = sim.run_sim(duration=14*3600)
```

### Important Notes
- **Only WNTRSimulator supports pause/restart** - EpanetSimulator resets automatically with each run
- Reference: https://usepa.github.io/WNTR/hydraulics.html#pause-and-restart

---

## Question 2: demand_deficit Attribute (Lines 100-104)

**Q:** Where does the `demand_deficit` attribute come from and what does it mean?

**A: `demand_deficit` is NOT a standard WNTR result attribute.**

### Standard Node Result Attributes
- `demand` - water demand at nodes
- `leak_demand` - WNTRSimulator only; total demand = demand + leak_demand
- `head` - hydraulic head
- `pressure` - pressure at nodes
- `quality` - EpanetSimulator only (water age, tracer, or chemical concentration)

### Calculating Demand Deficit
Demand deficit must be calculated manually for Pressure-Dependent Demand (PDD) simulations:

```python
# Get expected demand
expected_demand = wntr.metrics.expected_demand(wn)

# Get actual delivered demand from results
actual_demand = results.node['demand'].loc[:, wn.junction_name_list]

# Calculate deficit
demand_deficit = expected_demand - actual_demand
```

### Context
In PDD simulations, when pressure is insufficient, less water is delivered than requested. The deficit represents this shortfall.

### Reference
- https://github.com/usepa/WNTR/blob/main/documentation/resultsobject.rst

---

## Question 3: Tank Full but Not Overflowable (Lines 123-127)

**Q:** What happens to a tank when it's full but not overflowable?

**A: EPANET/WNTR stops any inflow when tank reaches max_level.**

### Behavior
- **overflow=False (default):** Tank acts as a closed boundary at max_level - no more water can enter
- **overflow=True:** Any input beyond max_level becomes spillage and is removed from the system

### Technical Details
- Tank is effectively "closed" for inflow when at max_level
- Outflow is still permitted until tank drops below max_level
- Similarly, outflow stops at min_level

### Reference
- http://wateranalytics.org/EPANET/_tanks_page.html

---

## Question 4: min_level, min_volume, max_level Interaction (Lines 148-155)

**Q:** How do min_level, min_volume, max_level work? Can they be combined?

**A: They are mutually exclusive based on tank type.**

### Cylindrical Tanks (constant diameter)
Use these attributes:
- `diameter` - tank diameter
- `min_level` - minimum water level for drainage
- `max_level` - maximum water level (overflow threshold if enabled)

### Volume-Curve Tanks
Use these attributes:
- `vol_curve_name` - references a volume curve defining volume vs. depth
- `min_vol` - minimum volume for drainage

### Important Notes
- When `vol_curve_name` is defined, `diameter` becomes irrelevant
- The `get_volume(level)` method handles both cases automatically
- **Documentation assumption is correct:** Use one group of attributes OR the other, not both

### Reference
- https://usepa.github.io/WNTR/apidoc/wntr.network.elements.Tank.html

---

## Question 5: Reservoirs as Drains (Lines 182-186)

**Q:** Can reservoirs be used as water drains? Can they connect directly to pipes?

**A: Yes to both, with caveats.**

### Reservoir as Drain
- Reservoirs are designed as **fixed-head boundary conditions**
- If reservoir head is lower than connected nodes, water flows INTO the reservoir (acts as drain)
- Pressure property is always 0 for reservoirs

### Direct Pipe Connection
- Reservoirs **CAN connect directly to pipes** - no pump required
- However: **PRV, PSV, FCV cannot connect directly to reservoir/tank** (use an intermediate pipe)

### Reference
- https://usepa.github.io/WNTR/apidoc/wntr.network.elements.Reservoir.html

---

## Question 6: Flow Direction and Check Valve (Lines 229-233)

**Q:** Is flow direction given by the sign of velocity? What direction does a check valve restrict to?

**A: Yes, and check valve allows from_node → to_node only.**

### Flow Direction Convention
- **Positive velocity/flow:** from `from_node` (start) to `to_node` (end)
- **Negative velocity/flow:** reverse direction (end to start)

### Check Valve Behavior
- Allows flow **only from start_node to end_node** (positive direction)
- Blocks reverse flow completely
- Check valve allows flow only if start node's head > end node's head

### Reference
- http://wateranalytics.org/EPANET/_pipes_page.html

---

## Question 7: Pump Status (open vs active vs closed) (Lines 257-261)

**Q:** Can we model pump status with just `open` and `closed`?

**A: Yes, with speed as a separate attribute.**

### WNTR Pump States
- **Active:** Pump is open AND has specific speed/setting applied
- **Opened:** Pump is open at base speed (speed=1)
- **Closed:** Pump is not operating

### Simplified Modeling Approach
Use two attributes:
- `operational.status` (boolean): `True` = Open, `False` = Closed
- `drinking_water.speed`: Speed multiplier (default 1.0)

The "Active" state is effectively `status=True` + `speed != 1.0`

### Reference
- https://usepa.github.io/WNTR/apidoc/wntr.network.elements.Pump.html

---

## Question 8: Power Pump Speed (Lines 263-267)

**Q:** Is speed ignored for power pumps? What does speed=1 mean?

**A: Speed = 1.0 means nominal (design) operating speed.**

### HeadPump Behavior
- Speed scales the pump curve proportionally
- Different speeds shift both flow and head characteristics
- Formula: H = A - B*Q^C (coefficients derived from pump curve)

### PowerPump Behavior (CONFIRMED FROM SOURCE CODE)
- Primary characteristic is **fixed power value** stored as `_base_power`
- **Speed is IGNORED for PowerPumps** - WNTR source code explicitly states:
  ```python
  link_res['setting'][name].append(1)  # power pumps have no speed
  ```
- PowerPumps operate at constant capacity without variable speed control
- Speed attributes are inherited from parent class but not used in simulation

### Reference
- https://usepa.github.io/WNTR/apidoc/wntr.network.elements.HeadPump.html
- https://usepa.github.io/WNTR/apidoc/wntr.network.elements.PowerPump.html
- WNTR source: https://github.com/USEPA/WNTR/blob/main/wntr/sim/hydraulics.py

---

## Question 9: Valve Types Explained (Lines 303-305)

**Q:** How do the different valve types work?

### Valve Type Summary

| Valve | Full Name | Purpose | Setting Unit |
|-------|-----------|---------|--------------|
| **PRV** | Pressure Reducing Valve | Limits downstream pressure to setting | Pressure (m) |
| **PSV** | Pressure Sustaining Valve | Maintains upstream pressure at setting | Pressure (m) |
| **PBV** | Pressure Breaker Valve | Maintains constant pressure DROP across valve | Pressure drop (m) |
| **FCV** | Flow Control Valve | Limits maximum flow to setting | Flow (m³/s) |
| **TCV** | Throttle Control Valve | Uses minor loss coefficient to restrict flow | Loss coefficient |
| **GPV** | General Purpose Valve | User-defined head loss vs flow curve | Curve ID |

### Placement Rules
- PRVs cannot share same output node or be daisy-chained
- PSVs cannot share same input node or be connected in series
- PSV cannot connect to output of PRV
- **PRV, PSV, FCV cannot connect directly to reservoir/tank** (use intermediate pipe)

### Reference
- http://wateranalytics.org/EPANET/_valves_page.html

---

## Question 10: Valve Status in WNTR vs EPANET (Lines 308-312)

**Q:** What does `open`/`closed` status mean for valves in WNTR?

**A: Status overrides the valve setting.**

### Valve Status States
- **Active:** Valve is controlling based on its setting (normal operation)
- **Open:** Valve acts as fully open link - **setting is IGNORED**
- **Closed:** Valve acts as closed link - no flow allowed

### EPANET .inp File Behavior
- In `.inp` files, valves only have settings (no explicit status)
- Status is controlled via [CONTROLS] or [RULES] sections

### Recommendation
For simplicity, consider:
- Not exposing Open/Closed status for valves
- Using only the Active state with settings
- Let settings control valve behavior

### Reference
- https://github.com/OpenWaterAnalytics/epanet/issues/1

---

## Resolved Items (from WNTR Source Code Investigation)

### 1. PowerPump Speed Interaction - RESOLVED
- **Speed is IGNORED for PowerPumps** - confirmed from WNTR source code
- PowerPumps always report setting=1 regardless of any speed configuration
- Only HeadPumps use the speed attribute

### 2. demand_deficit in Current Implementation - RESOLVED
- **`demand_deficit` is NOT a standard WNTR attribute** - confirmed via GitHub search
- Not found anywhere in the official WNTR repository
- If the current Movici implementation has this attribute, it must be:
  - Calculated internally as `expected_demand - actual_demand`
  - Or a custom extension

### 3. Tank Overflow Edge Cases
- When tank reaches max_level, inflow is blocked
- WNTR/EPANET handles this as a boundary condition
- Known issue: Edge cases during timestep transitions may show small numerical artifacts

---

## Additional Context: Rules Model for Controls

The drinking water model documentation states that **Controls are handled by the Rules Model** (not the WNTR model directly). This is documented in `rules_model.rst`.

### WNTR Controls vs Movici Rules Model

EPANET/WNTR has built-in control mechanisms:
- Simple controls (time-based or condition-based)
- Rule-based controls (IF-THEN-ELSE logic)

In the Movici integration, these are NOT implemented in the WNTR wrapper. Instead, Movici's generic **Rules Model** handles control logic:

### Rules Model Capabilities
- Update attributes based on other attributes or simulation time
- Support `<simtime>` (simulation time since start) and `<clocktime>` (wall clock time)
- Support AND/OR logical conditions
- Can reference entities by `id` or `reference`

### Example: Tank Level Control
```json
{
  "from_reference": "some tank",
  "if": "drinking_water.level >= 23",
  "to_reference": "some pump",
  "output": "operational.status",
  "value": false,
  "else_value": true
}
```

### Implications for Implementation
- WNTR model does NOT need to implement controls
- Control logic is decoupled and handled externally
- Rules dataset can be generated from EPANET `.inp` [CONTROLS] and [RULES] sections

---

## Differences: Documentation vs Current Implementation

Analysis comparing `drinking_water_model.rst` specification with the current implementation in `movici_simulation_core/models/water_network_simulation/`.

### 1. Attribute Naming Convention

| Aspect | Documentation | Implementation |
|--------|---------------|----------------|
| Prefix | `drinking_water.*` | `water.*` |
| Shape prefix | `shape.*` (diameter, length) | `water.*` |
| Elevation | `geometry.z` | `water.elevation` |

**Impact:** All attributes need renaming to match documentation.

### 2. Missing Attributes in Implementation

#### Junctions
- `drinking_water.demand` (effective demand = base_demand × demand_factor) - **MISSING**

#### Tanks
- `drinking_water.overflow` (boolean for overflow behavior) - **MISSING**

#### Pipes
- `drinking_water.check_valve` (boolean for flow restriction) - **MISSING**

#### Pumps
- `drinking_water.head_curve` as CSR data - current impl uses string reference to named curve

#### Valves
- `drinking_water.valve_curve` for GPV (as CSR data) - **MISSING**
- Valve-specific setting attributes:
  - `drinking_water.valve_pressure` (PRV/PSV/PBV)
  - `drinking_water.valve_flow` (FCV)
  - `drinking_water.valve_loss_coefficient` (TCV)
  - `drinking_water.valve_open_factor` (PCV) - Note: PCV not in EPANET standard

### 3. Extra Attributes in Implementation (not in docs)

| Entity | Attribute | Notes |
|--------|-----------|-------|
| Junction | `water.demand_pattern` | String pattern reference |
| Junction | `water.actual_demand` | Renamed to `drinking_water.demand`? |
| Junction | `water.demand_deficit` | Not standard WNTR - should be calculated |
| Pipe | `water.flow_direction` | Extra output |
| Pipe | `water.bulk_coeff` | Water quality coefficient |
| Pipe | `water.wall_coeff` | Water quality coefficient |
| Reservoir | `water.head_pattern` | String pattern reference |
| Tank | `water.initial_level` | Doc combines with `level` as INIT|PUB |
| Valve | `water.velocity` | Extra output |
| Valve | `water.headloss` | Extra output |

### 4. Attribute Flag Differences

| Entity | Attribute | Doc Flags | Impl Flags |
|--------|-----------|-----------|------------|
| Tank | diameter | OPT | INIT |
| Tank | min_level | OPT | INIT |
| Tank | max_level | OPT | INIT |
| Tank | level | INIT\|PUB | PUB only (separate init_level) |
| Reservoir | head | INIT (base) + PUB (calculated) | INIT only |

### 5. Structural Differences

#### Curves as Data vs References
- **Documentation:** Curves stored as CSR data directly in attributes (e.g., `(2,)-csr` for pump curves, volume curves)
- **Implementation:** Curves referenced by name string, actual curve data stored elsewhere

#### Valve Settings
- **Documentation:** Separate attributes per valve type (`valve_pressure`, `valve_flow`, `valve_loss_coefficient`)
- **Implementation:** Single `valve_setting` attribute with meaning derived from valve type

#### Tank Level
- **Documentation:** Single `level` attribute with `INIT|PUB` flags
- **Implementation:** Split into `initial_level` (INIT) and `level` (PUB)

### 6. Missing Model Configuration Options

| Option | Documentation | Implementation |
|--------|---------------|----------------|
| Viscosity | Yes (default 1) | **MISSING** |
| Specific gravity | Yes (default 1) | **MISSING** |
| rtol | Yes (default 1e-3) | **MISSING** |
| headloss_method | From dataset general section | **MISSING** |

### 7. Controls Implementation

- **Documentation:** Controls handled by Rules Model (external)
- **Implementation:** Has internal `ControlManager` + supports `control_rules` in model config

This is a design decision - both approaches work, but documentation suggests decoupling.

### 8. Pause/Restart Capability

- **Documentation:** Questions about WNTR pause/restart support
- **Implementation:** Not implemented - runs fresh simulation each update

### 9. demand_deficit Handling

- **Documentation:** Questions where this comes from (answer: NOT a WNTR attribute)
- **Implementation:** Tries to read from WNTR results (will be None)
  ```python
  # network_wrapper.py:244-245
  if "demand_deficit" in results.node:
      node_demand_deficits = results.node["demand_deficit"].loc[last_time].values
  ```
- **Fix needed:** Calculate as `expected_demand - actual_demand` for PDD simulations

### 10. Entity Group Names

| Documentation | Implementation | Match |
|---------------|----------------|-------|
| `water_junction_entities` | `water_junction_entities` | ✓ |
| `water_tank_entities` | `water_tank_entities` | ✓ |
| `water_reservoir_entities` | `water_reservoir_entities` | ✓ |
| `water_pipe_entities` | `water_pipe_entities` | ✓ |
| `water_pump_entities` | `water_pump_entities` | ✓ |
| `water_valve_entities` | `water_valve_entities` | ✓ |

---

## Summary of Required Changes

### High Priority (Breaking Changes)
1. Rename all `water.*` attributes to `drinking_water.*`
2. Rename `shape.*` attributes appropriately
3. Use `geometry.z` for elevation
4. Add missing `overflow` attribute to tanks
5. Add missing `check_valve` attribute to pipes
6. Calculate `demand_deficit` instead of reading from WNTR

### Medium Priority (Functional Gaps)
7. Add model config options: viscosity, specific gravity, rtol
8. Implement headloss_method from dataset general section
9. Consider implementing pause/restart for transient simulation
10. Add valve-specific setting attributes or document unified approach

### Low Priority (Enhancements)
11. Support curves as embedded CSR data (alternative to named references)
12. Align tank level handling (single INIT|PUB vs split attributes)
13. Consider moving controls to Rules Model for decoupling

---

## Implementation Plan

### Phase 1: Attribute Renaming (Breaking Changes)

#### 1.1 Create New Attribute Specifications

**File:** `movici_simulation_core/models/water_network_simulation/attributes.py`

Replace all `water.*` attributes with `drinking_water.*`:

```python
# OLD                                    # NEW
Water_Elevation                       -> # Use geometry.z from PointEntity
Water_BaseDemand                      -> DrinkingWater_BaseDemand
Water_DemandMultiplier                -> DrinkingWater_DemandFactor
Water_Pressure                        -> DrinkingWater_Pressure
Water_Head                            -> DrinkingWater_Head
Water_ActualDemand                    -> DrinkingWater_Demand (effective demand)
Water_DemandDeficit                   -> # Calculate, don't store as attribute
Water_Diameter                        -> Shape_Diameter
Water_Roughness                       -> DrinkingWater_Roughness
Water_MinorLoss                       -> DrinkingWater_MinorLoss
Water_LinkStatus                      -> Operational_Status (boolean)
Water_Flow                            -> DrinkingWater_Flow
Water_Velocity                        -> DrinkingWater_Velocity
Water_Headloss                        -> DrinkingWater_Headloss
Water_PumpCurve                       -> DrinkingWater_HeadCurve (CSR data)
Water_PumpSpeed                       -> DrinkingWater_Speed
Water_Power                           -> DrinkingWater_Power
Water_PumpType                        -> Type (enum: power, head)
Water_ValveType                       -> Type (enum: PRV, PSV, PBV, FCV, TCV, GPV)
Water_ValveSetting                    -> Split into type-specific attributes
Water_InitialLevel                    -> DrinkingWater_Level (INIT|PUB)
Water_MinLevel                        -> DrinkingWater_MinLevel
Water_MaxLevel                        -> DrinkingWater_MaxLevel
Water_TankDiameter                    -> Shape_Diameter
Water_Level                           -> DrinkingWater_Level (combined)
Water_MinVolume                       -> DrinkingWater_MinVolume
Water_VolumeCurve                     -> Shape_VolumeCurve (CSR data)
Water_HeadMultiplier                  -> DrinkingWater_HeadFactor
```

#### 1.2 New Attribute Definitions

```python
# attributes.py - New attributes to add

# Geometry (reuse existing or define)
Geometry_Z = AttributeSpec("geometry.z", data_type=DataType(float))

# Shape attributes
Shape_Diameter = AttributeSpec("shape.diameter", data_type=DataType(float))
Shape_Length = AttributeSpec("shape.length", data_type=DataType(float))
Shape_VolumeCurve = AttributeSpec("shape.volume_curve", data_type=DataType(float, (2,), csr=True))

# Drinking water attributes
DrinkingWater_BaseDemand = AttributeSpec("drinking_water.base_demand", data_type=DataType(float))
DrinkingWater_DemandFactor = AttributeSpec("drinking_water.demand_factor", data_type=DataType(float))
DrinkingWater_Demand = AttributeSpec("drinking_water.demand", data_type=DataType(float))
DrinkingWater_Pressure = AttributeSpec("drinking_water.pressure", data_type=DataType(float))
DrinkingWater_Head = AttributeSpec("drinking_water.head", data_type=DataType(float))
DrinkingWater_Roughness = AttributeSpec("drinking_water.roughness", data_type=DataType(float))
DrinkingWater_MinorLoss = AttributeSpec("drinking_water.minor_loss", data_type=DataType(float))
DrinkingWater_CheckValve = AttributeSpec("drinking_water.check_valve", data_type=DataType(bool))
DrinkingWater_Flow = AttributeSpec("drinking_water.flow", data_type=DataType(float))
DrinkingWater_Velocity = AttributeSpec("drinking_water.velocity", data_type=DataType(float))
DrinkingWater_Headloss = AttributeSpec("drinking_water.headloss", data_type=DataType(float))
DrinkingWater_Speed = AttributeSpec("drinking_water.speed", data_type=DataType(float))
DrinkingWater_Power = AttributeSpec("drinking_water.power", data_type=DataType(float))
DrinkingWater_HeadCurve = AttributeSpec("drinking_water.head_curve", data_type=DataType(float, (2,), csr=True))
DrinkingWater_Level = AttributeSpec("drinking_water.level", data_type=DataType(float))
DrinkingWater_MinLevel = AttributeSpec("drinking_water.min_level", data_type=DataType(float))
DrinkingWater_MaxLevel = AttributeSpec("drinking_water.max_level", data_type=DataType(float))
DrinkingWater_MinVolume = AttributeSpec("drinking_water.min_volume", data_type=DataType(float))
DrinkingWater_Overflow = AttributeSpec("drinking_water.overflow", data_type=DataType(bool))
DrinkingWater_BaseHead = AttributeSpec("drinking_water.base_head", data_type=DataType(float))
DrinkingWater_HeadFactor = AttributeSpec("drinking_water.head_factor", data_type=DataType(float))

# Valve-specific attributes
DrinkingWater_ValvePressure = AttributeSpec("drinking_water.valve_pressure", data_type=DataType(float))
DrinkingWater_ValveFlow = AttributeSpec("drinking_water.valve_flow", data_type=DataType(float))
DrinkingWater_ValveLossCoefficient = AttributeSpec("drinking_water.valve_loss_coefficient", data_type=DataType(float))
DrinkingWater_ValveCurve = AttributeSpec("drinking_water.valve_curve", data_type=DataType(float, (2,), csr=True))

# Operational attributes
Operational_Status = AttributeSpec("operational.status", data_type=DataType(bool))

# Type attributes (string values per design decision)
Type_PumpType = AttributeSpec("type", data_type=DataType(str))  # "power" or "head"
Type_ValveType = AttributeSpec("type", data_type=DataType(str))  # "PRV", "PSV", "PBV", "FCV", "TCV", "GPV"
```

### Phase 2: Entity Definition Updates

**File:** `movici_simulation_core/models/water_network_simulation/dataset.py`

#### 2.1 WaterJunctionEntity

```python
class WaterJunctionEntity(PointEntity):
    __entity_name__ = "water_junction_entities"

    # INIT attributes
    # geometry.x, geometry.y inherited from PointEntity
    elevation = field(Geometry_Z, flags=INIT)  # Was water.elevation
    base_demand = field(DrinkingWater_BaseDemand, flags=INIT)

    # OPT attributes
    demand_factor = field(DrinkingWater_DemandFactor, flags=OPT)  # Was demand_multiplier

    # PUB attributes
    demand = field(DrinkingWater_Demand, flags=PUB)  # Effective demand (NEW)
    pressure = field(DrinkingWater_Pressure, flags=PUB)
    head = field(DrinkingWater_Head, flags=PUB)
```

#### 2.2 WaterTankEntity

```python
class WaterTankEntity(PointEntity):
    __entity_name__ = "water_tank_entities"

    # INIT attributes
    elevation = field(Geometry_Z, flags=INIT)

    # OPT attributes (either diameter group OR volume_curve group)
    diameter = field(Shape_Diameter, flags=OPT)
    min_level = field(DrinkingWater_MinLevel, flags=OPT)
    max_level = field(DrinkingWater_MaxLevel, flags=OPT)
    volume_curve = field(Shape_VolumeCurve, flags=OPT)  # CSR data
    min_volume = field(DrinkingWater_MinVolume, flags=OPT)
    overflow = field(DrinkingWater_Overflow, flags=OPT)  # NEW

    # INIT|PUB attributes
    level = field(DrinkingWater_Level, flags=INIT|PUB)  # Combined init + output

    # PUB attributes
    pressure = field(DrinkingWater_Pressure, flags=PUB)
    head = field(DrinkingWater_Head, flags=PUB)
```

#### 2.3 WaterReservoirEntity

```python
class WaterReservoirEntity(PointEntity):
    __entity_name__ = "water_reservoir_entities"

    # INIT attributes
    base_head = field(DrinkingWater_BaseHead, flags=INIT)  # Was head

    # OPT attributes
    head_factor = field(DrinkingWater_HeadFactor, flags=OPT)  # Was head_multiplier

    # PUB attributes
    head = field(DrinkingWater_Head, flags=PUB)  # Calculated: base_head * head_factor
    flow = field(DrinkingWater_Flow, flags=PUB)
```

#### 2.4 WaterPipeEntity

```python
class WaterPipeEntity(LinkEntity, LineEntity):
    __entity_name__ = "water_pipe_entities"

    # INIT attributes (from LinkEntity: from_node_id, to_node_id)
    # OPT: linestring_2d or linestring_3d from LineEntity
    length = field(Shape_Length, flags=OPT)  # Or calculated from geometry
    diameter = field(Shape_Diameter, flags=INIT)
    roughness = field(DrinkingWater_Roughness, flags=INIT)

    # OPT attributes
    minor_loss = field(DrinkingWater_MinorLoss, flags=OPT)
    check_valve = field(DrinkingWater_CheckValve, flags=OPT)  # NEW

    # OPT|PUB attributes
    status = field(Operational_Status, flags=OPT|PUB)

    # PUB attributes
    flow = field(DrinkingWater_Flow, flags=PUB)
    velocity = field(DrinkingWater_Velocity, flags=PUB)
    headloss = field(DrinkingWater_Headloss, flags=PUB)
```

#### 2.5 WaterPumpEntity

```python
class WaterPumpEntity(LinkEntity):
    __entity_name__ = "water_pump_entities"

    # INIT attributes
    pump_type = field(Type_PumpType, flags=INIT)  # enum: power, head

    # OPT attributes (depends on pump_type)
    power = field(DrinkingWater_Power, flags=OPT)  # For power pumps
    head_curve = field(DrinkingWater_HeadCurve, flags=OPT)  # CSR data for head pumps
    speed = field(DrinkingWater_Speed, flags=OPT)  # Default 1.0

    # OPT|PUB attributes
    status = field(Operational_Status, flags=OPT|PUB)

    # PUB attributes
    flow = field(DrinkingWater_Flow, flags=PUB)
```

#### 2.6 WaterValveEntity

```python
class WaterValveEntity(LinkEntity):
    __entity_name__ = "water_valve_entities"

    # INIT attributes
    valve_type = field(Type_ValveType, flags=INIT)  # enum: PRV, PSV, PBV, FCV, TCV, GPV
    diameter = field(Shape_Diameter, flags=INIT)

    # OPT attributes (depends on valve_type)
    valve_pressure = field(DrinkingWater_ValvePressure, flags=OPT)  # PRV, PSV, PBV
    valve_flow = field(DrinkingWater_ValveFlow, flags=OPT)  # FCV
    valve_loss_coefficient = field(DrinkingWater_ValveLossCoefficient, flags=OPT)  # TCV
    valve_curve = field(DrinkingWater_ValveCurve, flags=OPT)  # GPV (CSR data)
    minor_loss = field(DrinkingWater_MinorLoss, flags=OPT)

    # PUB attributes
    flow = field(DrinkingWater_Flow, flags=PUB)
```

### Phase 3: Model Logic Updates

**File:** `movici_simulation_core/models/water_network_simulation/model.py`

#### 3.1 Add Configuration Options

```python
class Model(TrackedModel, name="water_network_simulation"):
    def __init__(self, model_config: dict):
        super().__init__(model_config)
        # ... existing init ...

        # NEW: Simulation options
        self.viscosity = model_config.get("viscosity", 1.0)
        self.specific_gravity = model_config.get("specific_gravity", 1.0)
        self.rtol = model_config.get("rtol", 1e-3)
```

#### 3.2 Update run_simulation to Use Options

```python
def run_simulation(self, ...):
    # Set hydraulic options
    self.wn.options.hydraulic.viscosity = self.viscosity
    self.wn.options.hydraulic.specific_gravity = self.specific_gravity
    # Note: rtol may need WNTRSimulator-specific handling
```

#### 3.3 Calculate demand_deficit

```python
def _publish_results(self, state: TrackedState, results):
    # For junctions, calculate demand_deficit if using PDD
    if self.junctions:
        # Get expected demand (base_demand * demand_factor)
        expected = self.junctions.base_demand.array.copy()
        if self.junctions.demand_factor.has_data():
            expected *= self.junctions.demand_factor.array

        # Actual demand from results
        actual = np.array(demands)

        # Effective demand = actual (what was delivered)
        self.junctions.demand.array[junction_indices] = actual

        # Note: demand_deficit removed from entity, calculate on-demand if needed
```

#### 3.4 Handle Check Valve

```python
def add_pipes(self, pipes: PipeCollection):
    for i, name in enumerate(pipes.link_names):
        # ... existing code ...

        # Set check valve if specified
        if pipes.check_valves is not None and pipes.check_valves[i]:
            pipe = self.wn.get_link(name)
            pipe.check_valve = True
```

#### 3.5 Handle Tank Overflow

```python
def add_tanks(self, tanks: TankCollection):
    for i, name in enumerate(tanks.node_names):
        # ... existing code ...

        # Set overflow flag
        if tanks.overflows is not None:
            tank = self.wn.get_node(name)
            tank.overflow = bool(tanks.overflows[i])
```

### Phase 4: Collection Updates

**File:** `movici_simulation_core/integrations/wntr/collections.py`

#### 4.1 Update PipeCollection

```python
@dataclasses.dataclass
class PipeCollection:
    # ... existing fields ...
    check_valves: t.Optional[np.ndarray] = None  # NEW: boolean array
```

#### 4.2 Update TankCollection

```python
@dataclasses.dataclass
class TankCollection:
    # ... existing fields ...
    overflows: t.Optional[np.ndarray] = None  # NEW: boolean array
```

#### 4.3 Update ValveCollection for Type-Specific Settings

```python
@dataclasses.dataclass
class ValveCollection:
    link_names: t.List[str]
    from_nodes: t.List[str]
    to_nodes: t.List[str]
    valve_types: t.List[str]
    diameters: np.ndarray

    # Type-specific settings (only one will be used per valve)
    valve_pressures: t.Optional[np.ndarray] = None  # PRV, PSV, PBV
    valve_flows: t.Optional[np.ndarray] = None  # FCV
    valve_loss_coefficients: t.Optional[np.ndarray] = None  # TCV
    valve_curves: t.Optional[t.List] = None  # GPV (list of curve data)

    minor_losses: t.Optional[np.ndarray] = None
```

### Phase 5: Utility Function Updates

**File:** `movici_simulation_core/models/common/wntr_util.py`

Update all `get_*` functions to use new attribute names and handle new attributes.

### Phase 6: Configuration Schema Update

**File:** `movici_simulation_core/json_schemas/models/water_network_simulation.json`

Add new configuration options:

```json
{
  "properties": {
    "viscosity": {
      "type": "number",
      "default": 1.0,
      "description": "Kinematic viscosity"
    },
    "specific_gravity": {
      "type": "number",
      "default": 1.0,
      "description": "Specific gravity of fluid"
    },
    "rtol": {
      "type": "number",
      "default": 0.001,
      "description": "Relative tolerance for convergence"
    }
  }
}
```

### Phase 7: Remove ControlManager

**Files to modify/remove:**
- `movici_simulation_core/integrations/wntr/control_manager.py` - **DELETE**
- `movici_simulation_core/integrations/wntr/__init__.py` - Remove ControlManager export
- `movici_simulation_core/models/water_network_simulation/model.py` - Remove:
  - `self.pending_control_rules` initialization
  - `control_rules` config handling
  - `_add_control_from_config` method
  - Control rule application in `initialize`

### Phase 8: Verify Rules Model Equivalence

Create test scenarios comparing WNTR internal controls vs Rules Model external controls:

#### Test Case 1: Time-Based Control
```
Scenario: Close pump at t=2h
WNTR Control: TimeOfDayControl that closes pump at 2:00:00
Rules Model: Rule with "<simtime> == 2h" -> operational.status = false
Expected: Same pump flow becomes 0 at t=2h
```

#### Test Case 2: Conditional Control (Tank Level)
```
Scenario: Start pump when tank level drops below 3m
WNTR Control: ConditionalControl on tank level
Rules Model: Rule with "drinking_water.level < 3" -> operational.status = true
Expected: Same pump activation timing
```

#### Test Case 3: Combined Conditions
```
Scenario: Close valve when tank full AND time > 6h
WNTR Control: Rule-based control with AND condition
Rules Model: Rule with {"and": ["drinking_water.level >= max_level", "<simtime> > 6h"]}
Expected: Same valve closure behavior
```

**Key Difference to Verify:**
- WNTR applies controls within simulation timestep
- Rules Model applies between timesteps (at Movici update boundaries)
- For most scenarios this should be equivalent, but edge cases may differ

### Phase 9: Testing

1. Update existing tests for attribute name changes
2. Add tests for new attributes (overflow, check_valve)
3. Add tests for CSR curve handling
4. Add tests for new config options
5. Integration test with sample INP file
6. **Rules Model equivalence tests** (Phase 8 scenarios)

### Migration Guide

For existing users:

1. **Attribute Migration Script:** Create script to rename attributes in existing datasets
2. **Deprecation Warnings:** Add warnings for old attribute names (optional transition period)
3. **Documentation:** Update all examples and documentation

---

## Implementation Order

### Sprint 1: Core Attribute Changes
1. Define new attributes in `attributes.py` (with CSR data types for curves)
2. Update entity definitions in `dataset.py` (string type enums, no demand_deficit)
3. Update utility functions in `wntr_util.py`
4. Update collections in `collections.py`

### Sprint 2: Model Logic & ControlManager Removal
5. Update model.py for new attribute access
6. Add config options (viscosity, specific_gravity, rtol)
7. Implement CSR curve handling (convert to WNTR curve objects)
8. Add check_valve and overflow handling
9. **Remove ControlManager** - delete control_manager.py, remove from model

### Sprint 3: Rules Model Verification
10. Create test scenarios for WNTR controls vs Rules Model
11. Verify equivalence for time-based controls
12. Verify equivalence for conditional controls
13. Document any behavioral differences

### Sprint 4: Testing & Documentation
14. Update/add unit tests
15. Integration testing with sample INP file
16. Update JSON schema
17. Create migration script for existing datasets
18. Update documentation

---

## Design Decisions (Resolved)

1. **Backward Compatibility:** ❌ **No** - Clean break, do not support old attribute names

2. **Curves as CSR vs References:** ✅ **CSR data only** - Follow documentation, embed curve data directly in attributes

3. **Controls:** ✅ **Drop ControlManager, use Rules Model** - Movici applies rules externally rather than WNTR internally. Need to verify this produces equivalent results.

4. **Type Enums:** ✅ **String values** - Use `"power"`, `"head"` for pumps; `"PRV"`, `"PSV"`, etc. for valves

5. **demand_deficit:** ❌ **Remove entirely** - Do not include as attribute

---

## Impact of Design Decisions

### Decision 1: No Backward Compatibility
- Simpler implementation (no deprecation logic)
- Existing datasets must be migrated before use
- Create migration script/tool for users

### Decision 2: CSR Data for Curves
- Remove `pump_curve`, `volume_curve` as string references
- Implement CSR data handling for:
  - `drinking_water.head_curve` (pump curves)
  - `shape.volume_curve` (tank volume curves)
  - `drinking_water.valve_curve` (GPV curves)
- Need to update WNTR wrapper to convert CSR data to WNTR curve objects

### Decision 3: Rules Model for Controls
- **Remove:** `ControlManager` class and `control_rules` config option
- **Remove:** `control_manager.py` integration file
- **Verify:** Test that Rules Model produces equivalent behavior to WNTR internal controls
- **Document:** How to configure rules for common control scenarios

### Decision 4: String Type Values
- `pump_type`: `"power"` or `"head"`
- `valve_type`: `"PRV"`, `"PSV"`, `"PBV"`, `"FCV"`, `"TCV"`, `"GPV"`
- Use `DataType(str)` instead of `DataType(int)` for type attributes

### Decision 5: Remove demand_deficit
- Remove `Water_DemandDeficit` attribute spec
- Remove from `WaterJunctionEntity`
- Remove from `SimulationResults` dataclass
- Remove collection logic in `_publish_results`
