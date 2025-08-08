Traffic Assignment Model
=======================

The Traffic Assignment model computes equilibrium traffic flows on transport networks using advanced assignment algorithms. Built on AequilibraE, it supports multiple transport modalities (roads, waterways, railways) and implements sophisticated volume delay functions to model realistic traffic conditions and congestion effects.

Overview
--------

The Traffic Assignment model is fundamental for:

- Equilibrium traffic flow calculation
- Network capacity analysis
- Congestion impact assessment
- Multi-modal transport assignment
- Route choice modeling
- Transport planning and policy analysis
- Infrastructure capacity planning

The model uses proven traffic assignment algorithms to distribute demand across network routes, accounting for capacity constraints and congestion-dependent travel times.

Key Features
------------

- **AequilibraE integration**: Professional-grade traffic assignment algorithms
- **Multi-modal support**: Roads, waterways, railways, and specialized tracks
- **Advanced algorithms**: All-or-nothing, MSA, Frank-Wolfe, and variants
- **Volume Delay Functions**: BPR and custom VDF implementations
- **Equilibrium convergence**: Robust convergence criteria and monitoring
- **Passenger Car Units**: Proper handling of mixed vehicle types
- **Network topology**: Sophisticated node-link network modeling

Supported Modalities
--------------------

Road Networks
^^^^^^^^^^^^^

For ``roads`` modality, the model supports:

- **Passenger demand**: Personal vehicles and shared mobility
- **Cargo demand**: Freight trucks and commercial vehicles
- **Mixed traffic**: Combined passenger and freight flow assignment
- **Congestion modeling**: Speed-flow relationships with capacity constraints

**Volume Delay Function**: BPR (Bureau of Public Roads) function with passenger car unit (PCU) weighting:

.. math::

    t = t_0 \\left(1 + \\alpha \\left(\\frac{v}{c}\\right)^\\beta\\right)

Where:

- ``t`` = Congested travel time
- ``t₀`` = Free-flow travel time  
- ``α`` = VDF alpha parameter (default: 4.0)
- ``β`` = VDF beta parameter (default: 0.64)
- ``v`` = Volume (passenger vehicles + cargo vehicles × cargo_pcu)
- ``c`` = Link capacity

Waterway Networks
^^^^^^^^^^^^^^^^^

For ``waterways`` modality:

- **Lock modeling**: Additional waiting times at navigation locks
- **Vessel capacity**: Different vessel types and sizes
- **Channel constraints**: Width and depth limitations
- **Weather dependencies**: Environmental impact considerations

**Special VDF parameters**: β=4.9 with variable α based on lock presence

Railway Networks
^^^^^^^^^^^^^^^^

**Base Tracks** (``tracks``):
- Simplified assignment with minimal congestion (α=0)
- Infrastructure capacity modeling
- Service frequency considerations

**Passenger Tracks** (``passenger_tracks``):
- Passenger-only demand assignment
- Service quality and comfort factors
- Station capacity constraints

**Cargo Tracks** (``cargo_tracks``):
- Freight-only rail assignment  
- ``cargo_allowed`` attribute filtering
- Loading/unloading time considerations

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "road_traffic_assignment",
        "type": "traffic_assignment",
        "dataset": "city_road_network",
        "modality": "roads"
    }

Advanced Configuration  
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "highway_assignment_with_trucks",
        "type": "traffic_assignment", 
        "dataset": "regional_highway_network",
        "modality": "roads",
        "vdf_alpha": 0.64,
        "vdf_beta": 4.0,
        "cargo_pcu": 2.5,
        "max_iterations": 1500,
        "convergence_gap": 0.001
    }

Multi-Modal Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "intermodal_freight_assignment",
        "type": "traffic_assignment",
        "dataset": "freight_network", 
        "modality": "waterways",
        "vdf_alpha": 1.2,
        "vdf_beta": 4.9
    }

Configuration Schema
^^^^^^^^^^^^^^^^^^^^

.. list-table:: Configuration Parameters
   :header-rows: 1
   :widths: 20 15 15 50

   * - Parameter
     - Type
     - Required
     - Description
   * - ``dataset``
     - string
     - Yes
     - Transport network dataset name
   * - ``modality``
     - string
     - Yes
     - Network type: "roads", "tracks", "waterways", "passenger_tracks", "cargo_tracks"
   * - ``vdf_alpha``
     - float
     - No
     - VDF α parameter (default: 4.0 for roads)
   * - ``vdf_beta``
     - float
     - No
     - VDF β parameter (default: 0.64 for roads)
   * - ``cargo_pcu``
     - float
     - No
     - Cargo vehicle PCU factor (default: 1.9)
   * - ``max_iterations``
     - integer
     - No
     - Maximum assignment iterations (default: 1000)
   * - ``convergence_gap``
     - float
     - No
     - Target relative gap (default: 0.001)

Data Requirements
-----------------

Network Structure
^^^^^^^^^^^^^^^^^

The traffic assignment model requires a specific network topology:

**Virtual Node Entities** (Origins/Destinations):
- Contain origin-destination demand matrices
- Connect to network via virtual links
- Support both passenger and cargo demand

**Virtual Link Entities** (Connectors):
- Connect virtual nodes to transport nodes
- Zero-cost, infinite-capacity connections
- Defined by ``connection.from_node_id`` and ``connection.to_node_id``

**Transport Node Entities** (Network Nodes):
- Junction points in the transport network
- Connect transport segments
- Maintain network topology

**Transport Segment Entities** (Network Links):
- Vary by modality: ``road_segment_entities``, ``waterway_segment_entities``, ``track_segment_entities``
- Contain capacity and performance attributes
- Form the core network infrastructure

Required Attributes
^^^^^^^^^^^^^^^^^^^

**Virtual Node Entities:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``transport.passenger_demand``
     - CSR matrix
     - OD matrix for passenger trips (vehicles/hour)
   * - ``transport.cargo_demand``
     - CSR matrix
     - OD matrix for cargo trips (vehicles/hour)

**Transport Segment Entities:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``transport.capacity``
     - array[float]
     - Link capacity (vehicles/hour)
   * - ``transport.max_speed``
     - array[float]
     - Maximum speed (km/hour)
   * - ``transport.layout``
     - array[tuple]
     - Lane configuration: [forward, reverse, bidirectional, unknown]
   * - ``geometry.length``
     - array[float]
     - Segment length (kilometers)
   * - ``connection.from_node_id``
     - array[int]
     - Origin node identifier
   * - ``connection.to_node_id``
     - array[int]
     - Destination node identifier

**Optional Attributes:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``transport.cargo_allowed``
     - array[bool]
     - Cargo access permissions (for specialized tracks)
   * - ``transport.lock_waiting_time``
     - array[float]
     - Additional delay at locks (waterways)

Output Data
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``transport.passenger_flow``
     - array[float]
     - Assigned passenger vehicle flow
   * - ``transport.cargo_flow``
     - array[float]
     - Assigned cargo vehicle flow
   * - ``transport.total_flow``
     - array[float]
     - Combined traffic flow (PCU-weighted)
   * - ``transport.volume_capacity_ratio``
     - array[float]
     - V/C ratio for capacity analysis
   * - ``transport.travel_time``
     - array[float]
     - Congested travel times
   * - ``assignment.convergence_gap``
     - float
     - Final relative gap value

Examples
--------

Urban Road Network
^^^^^^^^^^^^^^^^^^

City-wide traffic assignment with mixed passenger and freight traffic:

.. code-block:: json

    {
        "name": "city_traffic_assignment",
        "type": "traffic_assignment",
        "dataset": "urban_road_network",
        "modality": "roads",
        "vdf_alpha": 0.64,
        "vdf_beta": 4.0,
        "cargo_pcu": 1.9
    }

**Network Setup:**

.. code-block:: python

    # Virtual nodes (centroids) with demand
    virtual_nodes = {
        "transport.passenger_demand": csr_matrix,  # 50x50 OD matrix
        "transport.cargo_demand": csr_matrix       # 50x50 OD matrix
    }
    
    # Road segments with capacity constraints
    road_segments = {
        "transport.capacity": [1800, 3600, 1200],      # veh/hour
        "transport.max_speed": [50, 80, 30],           # km/hour  
        "geometry.length": [1.2, 2.5, 0.8],           # km
        "transport.layout": [[1,1,0,0], [2,2,0,0], [1,0,0,0]]
    }

Regional Highway System
^^^^^^^^^^^^^^^^^^^^^^^

Interstate highway assignment with truck-specific parameters:

.. code-block:: json

    {
        "name": "highway_freight_assignment", 
        "type": "traffic_assignment",
        "dataset": "interstate_highway_system",
        "modality": "roads",
        "vdf_alpha": 0.64,
        "vdf_beta": 4.5,
        "cargo_pcu": 2.8,
        "max_iterations": 2000,
        "convergence_gap": 0.0005
    }

Waterway Network
^^^^^^^^^^^^^^^^

Inland waterway system with lock constraints:

.. code-block:: json

    {
        "name": "river_barge_assignment",
        "type": "traffic_assignment",
        "dataset": "inland_waterway_network",
        "modality": "waterways",
        "vdf_alpha": 1.5,
        "vdf_beta": 4.9
    }

**Waterway-Specific Data:**

.. code-block:: python

    waterway_segments = {
        "transport.capacity": [20, 15, 25],           # vessels/day
        "transport.max_speed": [15, 12, 18],          # km/hour
        "transport.lock_waiting_time": [0, 30, 0],    # minutes
        "geometry.length": [25.5, 18.2, 32.1]        # km
    }

Railway Freight Network
^^^^^^^^^^^^^^^^^^^^^^^

Dedicated freight rail assignment:

.. code-block:: json

    {
        "name": "freight_rail_assignment",
        "type": "traffic_assignment", 
        "dataset": "national_rail_network",
        "modality": "cargo_tracks",
        "vdf_alpha": 0.0,
        "vdf_beta": 2.0
    }

Algorithm Details
-----------------

AequilibraE Integration
^^^^^^^^^^^^^^^^^^^^^^

The model uses AequilibraE's sophisticated assignment engine:

1. **Project Setup**: Creates SpatiaLite database with network topology
2. **Graph Building**: Constructs routing graph with node-link relationships  
3. **Assignment Execution**: Runs equilibrium assignment with convergence monitoring
4. **Results Processing**: Extracts flows and performance measures

**Assignment Algorithms Available:**

- **All-or-Nothing**: Simple shortest path assignment (no congestion)
- **MSA (Method of Successive Averages)**: Basic equilibrium approximation
- **Frank-Wolfe**: Linear approximation algorithm
- **Conjugate Frank-Wolfe**: Enhanced convergence variant
- **Biconjugate Frank-Wolfe**: Advanced algorithm for difficult networks

Convergence Monitoring
^^^^^^^^^^^^^^^^^^^^^^

**Relative Gap Calculation**:

.. math::

    \\text{RGap} = \\frac{\\sum_a v_a \\times (t_a - t_a^{\\text{AON}})}{\\sum_a v_a \\times t_a}

Where:
- ``vₐ`` = Flow on link a
- ``tₐ`` = Current travel time on link a  
- ``tₐᴬᴼᴺ`` = All-or-nothing travel time on link a

**Convergence Criteria**:
- Target relative gap (default: 0.001 = 0.1%)
- Maximum iterations (default: 1000)
- Stagnation detection for problematic networks

Performance Optimization
------------------------

Network Size Guidelines
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table:: Network Scalability
   :header-rows: 1
   :widths: 30 30 40

   * - Network Size
     - Recommended Setup
     - Performance Characteristics
   * - < 1,000 links
     - Standard parameters
     - Fast convergence, < 1 minute
   * - 1,000-10,000 links  
     - Relaxed gap: 0.005
     - Moderate time, 1-10 minutes
   * - 10,000-100,000 links
     - Gap: 0.01, Max iter: 500
     - Longer runtime, 10-60 minutes
   * - > 100,000 links
     - Specialized tuning needed
     - Requires performance optimization

Memory Requirements
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Memory estimation (approximate)
    def estimate_memory_mb(n_nodes, n_links, n_od_pairs):
        # Network storage
        network_mb = (n_nodes * 0.001) + (n_links * 0.002)
        
        # OD matrices (sparse)
        od_mb = n_od_pairs * 0.00002  # Sparse matrix efficiency
        
        # Assignment matrices
        assignment_mb = n_links * 0.001
        
        return network_mb + od_mb + assignment_mb
    
    # Example: 10,000 links, 2,000 nodes, 1M OD pairs
    # ≈ 35 MB total memory requirement

Algorithm Selection
^^^^^^^^^^^^^^^^^^^

.. list-table:: Algorithm Selection Guide
   :header-rows: 1
   :widths: 25 25 50

   * - Network Characteristics
     - Recommended Algorithm
     - Rationale
   * - Small, well-conditioned
     - Frank-Wolfe
     - Fast convergence, standard choice
   * - Large, sparse
     - MSA
     - Memory efficient, stable
   * - Congested, complex
     - Conjugate Frank-Wolfe
     - Better handling of congestion
   * - Testing/debugging
     - All-or-Nothing
     - No convergence issues, fast results

Best Practices
--------------

Network Preparation
^^^^^^^^^^^^^^^^^^^

1. **Topology Validation**:
   - Ensure network connectivity
   - Verify node-link consistency  
   - Check for isolated components
   - Validate coordinate systems

2. **Capacity Calibration**:
   - Use observed capacity values
   - Account for signal timing
   - Consider turn penalties
   - Validate speed-flow relationships

3. **Demand Matrix Preparation**:
   - Balance OD matrices (row/column sums)
   - Handle intrazonal trips appropriately
   - Validate demand magnitudes
   - Ensure temporal consistency

.. code-block:: python

    def validate_od_matrix(od_matrix):
        """Validate OD matrix properties"""
        # Check for negative values
        assert (od_matrix >= 0).all(), "Negative demand values found"
        
        # Check matrix balance
        row_sums = od_matrix.sum(axis=1)
        col_sums = od_matrix.sum(axis=0)
        balance_diff = abs(row_sums.sum() - col_sums.sum())
        
        if balance_diff > 0.01 * row_sums.sum():
            warnings.warn("OD matrix significantly unbalanced")

VDF Parameter Calibration
^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table:: VDF Parameter Ranges
   :header-rows: 1
   :widths: 20 25 25 30

   * - Road Type
     - α Range
     - β Range
     - Typical Values
   * - Urban arterial
     - 0.5-1.0
     - 3.0-5.0
     - α=0.64, β=4.0
   * - Highway
     - 0.3-0.8
     - 2.0-4.0
     - α=0.50, β=3.0
   * - Local streets
     - 0.8-1.5
     - 4.0-6.0
     - α=1.0, β=5.0

Convergence Tuning
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Progressive convergence strategy
    convergence_phases = [
        {"max_iter": 200, "gap": 0.05},    # Rough convergence
        {"max_iter": 500, "gap": 0.01},    # Medium convergence  
        {"max_iter": 1000, "gap": 0.001}   # Fine convergence
    ]

Common Issues and Troubleshooting
----------------------------------

Poor Convergence
^^^^^^^^^^^^^^^^

**Issue**: Assignment fails to converge or converges slowly

**Solutions**:

- Increase maximum iterations
- Relax convergence gap tolerance
- Check network connectivity issues
- Validate capacity and demand values
- Try different assignment algorithms

.. code-block:: python

    # Diagnostic convergence plot
    def plot_convergence(gap_values):
        plt.semilogy(gap_values)
        plt.xlabel('Iteration')
        plt.ylabel('Relative Gap')
        plt.title('Assignment Convergence')
        plt.grid(True)

Unrealistic Flow Patterns
^^^^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Traffic flows don't match expected patterns

**Solutions**:

- Review OD matrix accuracy and scaling
- Validate network capacity values
- Check for missing or incorrect links
- Verify VDF parameter appropriateness
- Inspect shortest path trees

Network Topology Errors
^^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Assignment fails due to network structure problems

**Solutions**:

- Verify all nodes have connecting links
- Check for duplicate or zero-length links
- Ensure virtual link connections are correct
- Validate node ID consistency
- Test with simplified network first

Performance Issues
^^^^^^^^^^^^^^^^^^

**Issue**: Assignment takes too long or runs out of memory

**Solutions**:

- Use coarser convergence criteria for large networks
- Implement network simplification
- Consider zone aggregation for demand
- Use more efficient assignment algorithms
- Implement parallel processing where possible

Integration with Other Models
-----------------------------

The Traffic Assignment model integrates effectively with:

- **Traffic Demand Calculation**: Uses updated demand matrices
- **Shortest Path Model**: Provides network flows for path analysis
- **Traffic KPI Model**: Supplies flow data for emission calculations
- **Generalized Journey Time**: Enhanced with congestion-dependent times

Advanced Features
-----------------

Multi-Class Assignment
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Handle different vehicle classes
    vehicle_classes = {
        "passenger": {"pcu": 1.0, "vot": 12.0},    # Value of time: $/hour
        "truck": {"pcu": 2.5, "vot": 25.0},
        "bus": {"pcu": 2.0, "vot": 30.0}
    }

Time-of-Day Assignment
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Multiple time periods
    time_periods = {
        "am_peak": {"duration": 3, "demand_factor": 1.2},
        "midday": {"duration": 6, "demand_factor": 0.8}, 
        "pm_peak": {"duration": 3, "demand_factor": 1.1},
        "evening": {"duration": 12, "demand_factor": 0.6}
    }

Stochastic Assignment
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Route choice with perception error
    def stochastic_assignment(network, theta=1.0):
        """Implement logit-based route choice"""
        # θ controls route choice dispersion
        # Higher θ = more deterministic choice
        # Lower θ = more random choice
        pass

Dynamic Assignment
^^^^^^^^^^^^^^^^^^

For time-varying conditions:

.. code-block:: python

    def dynamic_assignment_setup():
        """Configure time-dependent assignment"""
        return {
            "time_step": 300,     # 5-minute intervals
            "total_time": 14400,  # 4 hours
            "demand_profile": time_varying_demand,
            "capacity_profile": time_varying_capacity
        }

Post-Processing Analysis
------------------------

Flow Analysis
^^^^^^^^^^^^^

.. code-block:: python

    def analyze_assignment_results(flows, capacities):
        """Analyze assignment results"""
        # Volume-to-capacity ratios
        vc_ratios = flows / capacities
        
        # Congested links identification
        congested_links = np.where(vc_ratios > 0.9)[0]
        
        # Level of service calculation
        los_categories = {
            "A": vc_ratios < 0.3,
            "B": (vc_ratios >= 0.3) & (vc_ratios < 0.5),
            "C": (vc_ratios >= 0.5) & (vc_ratios < 0.7),
            "D": (vc_ratios >= 0.7) & (vc_ratios < 0.9),
            "E": (vc_ratios >= 0.9) & (vc_ratios < 1.0),
            "F": vc_ratios >= 1.0
        }
        
        return {
            "congested_links": congested_links,
            "los_distribution": {k: v.sum() for k, v in los_categories.items()}
        }

Route Analysis
^^^^^^^^^^^^^^

.. code-block:: python

    def extract_od_paths(assignment_results, origin, destination):
        """Extract paths used between specific OD pairs"""
        # Get path trees from assignment
        path_tree = assignment_results.get_path_tree(origin)
        
        # Trace path to destination
        path_links = path_tree.trace_path_to(destination)
        
        return {
            "links": path_links,
            "total_time": sum(link.travel_time for link in path_links),
            "total_distance": sum(link.length for link in path_links)
        }

See Also
--------

- :doc:`traffic_demand_calculation` - For demand modeling
- :doc:`shortest_path` - For path analysis
- :doc:`traffic_kpi` - For flow-based KPI calculation
- :doc:`generalized_journey_time` - For realistic travel times

API Reference
-------------

- :class:`movici_simulation_core.models.traffic_assignment_calculation.TrafficAssignmentModel`