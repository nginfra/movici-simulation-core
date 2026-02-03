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

> **Status:** Most items below have been resolved. This section is kept for historical reference.

### 1. Attribute Naming Convention — RESOLVED

All attributes now use `drinking_water.*` prefix, `shape.*` for shape attributes, and
`geometry.z` for elevation. The old `water.*` prefix has been removed.

### 2. Missing Attributes — RESOLVED

All previously missing attributes have been implemented:
- Junction: `drinking_water.demand`, PDD attributes (`minimum_pressure`, `required_pressure`, `pressure_exponent`)
- Tank: `drinking_water.overflow`
- Pipe: `drinking_water.check_valve`
- Pump: `drinking_water.head_curve` as CSR data
- Valve: type-specific setting attributes and `drinking_water.valve_curve` for GPV

### 3. Removed Legacy Attributes — RESOLVED

The following legacy attributes have been removed:
- `water.demand_pattern`, `water.actual_demand`, `water.demand_deficit`
- `water.flow_direction`, `water.bulk_coeff`, `water.wall_coeff`
- `water.head_pattern`, `water.initial_level`

### 4. Attribute Flag Differences — RESOLVED

Attribute flags now match the documentation specification.

### 5. Structural Differences — RESOLVED

- Curves are stored as CSR data directly in attributes
- Valve settings use separate type-specific attributes
- Tank level uses a single `level` attribute with `INIT|PUB` flags

### 6. Model Configuration Options — RESOLVED

Options are now split between two sources:
- **Data options** in dataset `"general"` section: `headloss`, `viscosity`, `specific_gravity`,
  `demand_model`, `demand_multiplier`, `minimum_pressure`, `required_pressure`, `pressure_exponent`
- **Solver options** in model config `"options"` key: `trials`, `accuracy`, `headerror`,
  `flowchange`, `damplimit`, `checkfreq`, `maxcheck`, `unbalanced`, `unbalanced_value`

Both are merged at initialization via `_deep_merge()` and applied through
`NetworkWrapper.configure_options()`.

### 7. Controls Implementation — RESOLVED

`ControlManager` has been removed. Controls are handled externally by the Movici Rules Model.
See `test_rules_model_equivalence.py` for verification tests.

### 8. Pause/Restart Capability

- **Documentation:** WNTR supports pause/restart via `reset_initial_values()`
- **Implementation:** Uses `reset_initial_values()` before each simulation run

### 9. demand_deficit Handling — RESOLVED

`demand_deficit` has been removed from the implementation. It was not a standard WNTR attribute.
If needed, it can be calculated externally as `expected_demand - actual_demand` for PDD simulations.

### 10. Entity Group Names — No Changes Needed

All entity group names match between documentation and implementation.

---

## Summary of Required Changes

> **Status:** All items below have been completed.

### High Priority (Breaking Changes) — DONE
1. ~~Rename all `water.*` attributes to `drinking_water.*`~~
2. ~~Rename `shape.*` attributes appropriately~~
3. ~~Use `geometry.z` for elevation~~
4. ~~Add missing `overflow` attribute to tanks~~
5. ~~Add missing `check_valve` attribute to pipes~~
6. ~~Remove `demand_deficit` (not a standard WNTR attribute)~~

### Medium Priority (Functional Gaps) — DONE
7. ~~Split options: data options in dataset general, solver options in model config~~
8. ~~Implement headloss from dataset general section~~
9. ~~Implement pause/restart via `reset_initial_values()`~~
10. ~~Add valve-specific setting attributes~~

### Low Priority (Enhancements) — DONE
11. ~~Support curves as embedded CSR data~~
12. ~~Align tank level handling (single INIT|PUB)~~
13. ~~Move controls to Rules Model (ControlManager removed)~~

---

## Implementation Plan

> **Status:** All phases have been completed. This section is kept for historical reference.

### Phase 1: Attribute Renaming — DONE
All `water.*` attributes renamed to `drinking_water.*`, `shape.*`, `geometry.z` as appropriate.
See `attributes.py` for the current attribute definitions.

### Phase 2: Entity Definition Updates — DONE
All entity classes updated in `dataset.py` with correct attribute names, flags, and new attributes
(PDD support, overflow, check_valve, valve-specific settings, CSR curves).

### Phase 3: Model Logic Updates — DONE
- Options split implemented: data options from dataset general, solver options from model config
- `_deep_merge()` combines both sources
- `NetworkWrapper.configure_options()` applies all options
- `demand_deficit` removed (not a standard WNTR attribute)
- Check valve, tank overflow, and per-junction PDD attributes supported

### Phase 4: Collection Updates — DONE
All collections updated with new fields (check_valves, overflows, PDD arrays, valve-specific
settings, CSR curve data).

### Phase 5: Utility Function Updates — DONE
All `get_*` functions in `wntr_util.py` updated for new attribute names and new attributes.

### Phase 6: Configuration Schema Update — DONE
`water_network_simulation.json` updated:
- Removed `mode` and `inp_file` (INP file mode no longer supported)
- Added `options` key for solver settings
- `dataset` is now required

### Phase 7: Remove ControlManager — DONE
`ControlManager` removed. Controls handled externally by the Movici Rules Model.

### Phase 8: Rules Model Equivalence — DONE
Test scenarios implemented in `test_rules_model_equivalence.py` verifying that the Movici Rules
Model produces equivalent results to WNTR internal controls for time-based, conditional, and
combined control scenarios.

### Phase 9: Testing — DONE
All tests updated and passing.

### Migration Guide

For existing users migrating from the old `water.*` attribute naming:

1. Rename all `water.*` attributes to `drinking_water.*` in existing datasets
2. Rename `water.elevation` to `geometry.z`
3. Rename shape-related attributes to `shape.*` prefix
4. Remove `mode` and `inp_file` from model configurations
5. Move data-related options to the dataset `"general"` section
6. Move solver-related options to the model config `"options"` key

---

## Design Decisions (Resolved and Implemented)

1. **Backward Compatibility:** ❌ No — Clean break, old `water.*` attribute names not supported
2. **Curves as CSR vs References:** ✅ CSR data only — Curve data embedded directly in attributes
3. **Controls:** ✅ Rules Model only — `ControlManager` removed, controls handled externally
4. **Type Enums:** ✅ String values — `"power"`/`"head"` for pumps, `"PRV"`/`"PSV"`/etc. for valves
5. **demand_deficit:** ❌ Removed — Not a standard WNTR attribute
6. **Options Split:** ✅ Data options in dataset general section, solver options in model config `"options"` key
7. **Per-junction PDD:** ✅ Supported — `minimum_pressure`, `required_pressure`, `pressure_exponent` as OPT junction attributes with NaN fallback to global
8. **INP file mode:** ❌ Removed — Only Movici dataset mode supported
