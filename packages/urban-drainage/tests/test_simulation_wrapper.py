"""Tests for the pyswmm SimulationWrapper and its ``.inp`` synthesis."""

import copy
import dataclasses

import pytest

from movici_simulation_core.core.attribute import PUBLISH
from movici_simulation_core.core.data_format import EntityInitDataFormat
from movici_simulation_core.core.state import TrackedState
from movici_urban_drainage_model.model import Model
from movici_urban_drainage_model.simulation_wrapper import IdMapper, SimulationWrapper

DS = "urban_drainage"

ENUMS = {
    "xsection_shape": ["CIRCULAR", "RECT_CLOSED", "RECT_OPEN"],
    "outfall_type": ["FREE", "NORMAL", "FIXED", "TIDAL", "TIMESERIES"],
    "pump_curve_type": ["IDEAL", "PUMP1", "PUMP2", "PUMP3", "PUMP4"],
}

NETWORK = {
    "version": 4,
    "name": DS,
    "type": DS,
    "general": {"enum": ENUMS},
    "data": {
        "drainage_junction_entities": {
            "id": [1, 2],
            "geometry.x": [0.0, 100.0],
            "geometry.y": [0.0, 0.0],
            "urban_drainage.invert_elevation": [10.0, 9.0],
            "urban_drainage.max_depth": [5.0, 5.0],
        },
        "drainage_outfall_entities": {
            "id": [3],
            "geometry.x": [200.0],
            "geometry.y": [0.0],
            "urban_drainage.invert_elevation": [8.0],
            "urban_drainage.outfall_type": [0],
        },
        "drainage_conduit_entities": {
            "id": [10, 11],
            "topology.from_node_id": [1, 2],
            "topology.to_node_id": [2, 3],
            "shape.length": [100.0, 100.0],
            "urban_drainage.roughness": [0.01, 0.01],
            "urban_drainage.cross_section_shape": [0, 0],
            "urban_drainage.cross_section_geometry": [
                [1.0, 0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0, 0.0],
            ],
        },
        "drainage_raingage_entities": {
            "id": [4],
            "geometry.x": [-100.0],
            "geometry.y": [100.0],
        },
        "drainage_subcatchment_entities": {
            "id": [5],
            "geometry.polygon": [[[0.0, 0.0], [0.0, 50.0], [50.0, 50.0], [0.0, 0.0]]],
            "urban_drainage.area": [4.0],
            "urban_drainage.width": [400.0],
            "urban_drainage.percent_impervious": [50.0],
            "urban_drainage.slope": [0.5],
            "urban_drainage.outlet_node_id": [1],
            "urban_drainage.raingage_id": [4],
        },
    },
}


class TestIdMapper:
    def test_register_and_lookup(self):
        mapper = IdMapper()
        mapper.register(1, "J1")
        assert mapper.get_swmm_name(1) == "J1"

    def test_duplicate_id_raises(self):
        mapper = IdMapper()
        mapper.register(1, "J1")
        with pytest.raises(ValueError, match="Duplicate entity id"):
            mapper.register(1, "OF1")


@pytest.fixture
def additional_attributes():
    return Model.get_schema_attributes()


@pytest.fixture
def schema(global_schema):
    global_schema.register_attributes(Model.get_schema_attributes())
    return global_schema


@pytest.fixture
def state(schema):
    return TrackedState(schema=schema)


@pytest.fixture
def initialize_wrapper(schema, state):
    converter = EntityInitDataFormat(schema)
    created = []

    def _initialize(network=NETWORK, dataset_name=DS):
        # deep-copy: state.process_general_section pops "enum" from the dict
        network = copy.deepcopy(network)
        dataset = Model._register_dataset(state, dataset_name=dataset_name)
        state.receive_update(converter.load_json(network), is_initial=True)
        for f in dataclasses.fields(dataset):
            eg = getattr(dataset, f.name)
            for attr_name in eg.attributes:
                attr = getattr(eg, attr_name)
                if attr.flags & PUBLISH and not attr.has_data():
                    attr.initialize(len(eg))
        wrapper = SimulationWrapper()
        created.append(wrapper)
        wrapper.configure_options({"routing_step": 30, "report_step": 300})
        wrapper.initialize(dataset)
        return wrapper, dataset

    yield _initialize

    # EPA-SWMM allows only one open simulation per process, so always release it -
    # even if a test fails mid-run - or subsequent tests hit MultiSimulationError.
    for wrapper in created:
        try:
            wrapper.close()
        except Exception:
            pass


class TestInpSynthesis:
    def test_inp_contains_expected_sections(self, initialize_wrapper):
        wrapper, _ = initialize_wrapper()
        with open(wrapper._inp_path) as fh:
            inp = fh.read()
        for section in (
            "[JUNCTIONS]",
            "[OUTFALLS]",
            "[CONDUITS]",
            "[XSECTIONS]",
            "[SUBCATCHMENTS]",
            "[RAINGAGES]",
            "[COORDINATES]",
        ):
            assert section in inp
        assert "J1" in inp and "J2" in inp  # junction prefix
        assert "OF3" in inp  # outfall prefix
        assert "C10" in inp and "C11" in inp  # conduit prefix
        wrapper.close()

    def test_id_mapper_prefixes(self, initialize_wrapper):
        wrapper, _ = initialize_wrapper()
        assert wrapper.id_mapper.get_swmm_name(1) == "J1"
        assert wrapper.id_mapper.get_swmm_name(3) == "OF3"
        assert wrapper.id_mapper.get_swmm_name(10) == "C10"
        wrapper.close()


class TestStepping:
    def test_t0_reads_initial_conditions(self, initialize_wrapper):
        wrapper, dataset = initialize_wrapper()
        wrapper.advance_to(0)
        wrapper.write_results()
        # head == invert at t=0 with zero initial depth
        assert list(dataset.junctions.hydraulic_head.array) == pytest.approx([10.0, 9.0])
        wrapper.close()

    def test_advance_reaches_target(self, initialize_wrapper):
        wrapper, _ = initialize_wrapper()
        routing_step = 30
        wrapper.advance_to(600)
        elapsed = wrapper.elapsed_seconds()
        # advance_to only exits once within <1s of the target, so the lower bound
        # is tight; it may overshoot by at most one routing step.
        assert 599 <= elapsed <= 600 + routing_step
        # re-advancing to the same (already reached) target is a no-op
        wrapper.advance_to(600)
        assert wrapper.elapsed_seconds() == pytest.approx(elapsed)
        wrapper.close()

    def test_rainfall_control_produces_runoff(self, initialize_wrapper):
        wrapper, dataset = initialize_wrapper()
        # inject rainfall via the rain gage control input
        if not dataset.raingages.rainfall_intensity.has_data():
            dataset.raingages.rainfall_intensity.initialize(len(dataset.raingages))
        dataset.raingages.rainfall_intensity.array[:] = [10.0]
        for target in (300, 600, 900):
            wrapper.apply_controls()
            wrapper.advance_to(target)
        wrapper.write_results()
        assert dataset.raingages.rainfall.array[0] == pytest.approx(10.0, rel=1e-3)
        assert dataset.subcatchments.runoff.array[0] > 0.0
        assert max(dataset.conduits.flow.array) > 0.0
        wrapper.close()


# Enum set covering the control-structure types
STRUCT_ENUMS = {
    "outfall_type": ["FREE", "NORMAL", "FIXED", "TIDAL", "TIMESERIES"],
    "orifice_type": ["SIDE", "BOTTOM"],
    "orifice_shape": ["CIRCULAR", "RECT_CLOSED"],
    "weir_type": ["TRANSVERSE", "SIDEFLOW", "V-NOTCH", "TRAPEZOIDAL", "ROADWAY"],
    "outlet_rating_type": [
        "FUNCTIONAL/DEPTH",
        "FUNCTIONAL/HEAD",
        "TABULAR/DEPTH",
        "TABULAR/HEAD",
    ],
}


def _one_link_network(link_group, link_attrs, inflow=0.3):
    """Storage fed by a constant inflow, draining through a single link.

    With one drain the link conveys the whole inflow at equilibrium, so its flow
    is guaranteed positive once the storage has filled - making per-structure
    result assertions robust.
    """
    data = {
        "drainage_storage_entities": {
            "id": [1],
            "geometry.x": [0.0],
            "geometry.y": [0.0],
            "urban_drainage.invert_elevation": [0.0],
            "urban_drainage.max_depth": [10.0],
            "urban_drainage.storage_constant": [200.0],
            "urban_drainage.generated_inflow": [inflow],
        },
        "drainage_outfall_entities": {
            "id": [2],
            "geometry.x": [100.0],
            "geometry.y": [0.0],
            "urban_drainage.invert_elevation": [0.0],
            "urban_drainage.outfall_type": [0],
        },
        link_group: {
            "id": [20],
            "topology.from_node_id": [1],
            "topology.to_node_id": [2],
            **link_attrs,
        },
    }
    return {"version": 4, "name": DS, "type": DS, "general": {"enum": STRUCT_ENUMS}, "data": data}


def _run(wrapper, until=2400):
    for target in range(300, until + 1, 300):
        wrapper.apply_controls()
        wrapper.advance_to(target)
    wrapper.write_results()


class TestStructures:
    def test_orifice_runs(self, initialize_wrapper):
        network = _one_link_network(
            "drainage_orifice_entities",
            {
                "urban_drainage.orifice_type": [1],  # BOTTOM
                "urban_drainage.orifice_shape": [1],  # RECT_CLOSED
                "urban_drainage.cross_section_geometry": [[1.0, 1.0, 0.0, 0.0]],
                "urban_drainage.discharge_coefficient": [0.65],
                "urban_drainage.crest_height": [0.0],
            },
        )
        wrapper, dataset = initialize_wrapper(network)
        _run(wrapper)
        assert dataset.orifices.flow.array[0] > 0.0
        # current_setting reads back for an uncontrolled structure
        assert dataset.orifices.current_setting.array[0] == pytest.approx(1.0)

    def test_vnotch_weir_builds_triangular_and_runs(self, initialize_wrapper):
        network = _one_link_network(
            "drainage_weir_entities",
            {
                "urban_drainage.weir_type": [2],  # V-NOTCH -> TRIANGULAR xsection
                "urban_drainage.cross_section_geometry": [[3.0, 3.0, 0.0, 0.0]],
                "urban_drainage.discharge_coefficient": [1.8],
                "urban_drainage.crest_height": [0.0],
            },
        )
        wrapper, dataset = initialize_wrapper(network)
        # The bug this guards: a V-NOTCH weir must emit a TRIANGULAR opening, not
        # RECT_OPEN, or SWMM rejects the model (ERROR 143).
        with open(wrapper._inp_path) as fh:
            assert "TRIANGULAR" in fh.read()
        _run(wrapper)
        assert dataset.weirs.flow.array[0] > 0.0

    def test_trapezoidal_weir_builds_trapezoidal(self, initialize_wrapper):
        network = _one_link_network(
            "drainage_weir_entities",
            {
                "urban_drainage.weir_type": [3],  # TRAPEZOIDAL -> TRAPEZOIDAL xsection
                "urban_drainage.cross_section_geometry": [[3.0, 3.0, 0.5, 0.5]],
                "urban_drainage.discharge_coefficient": [1.8],
                "urban_drainage.crest_height": [0.0],
            },
        )
        wrapper, dataset = initialize_wrapper(network)
        with open(wrapper._inp_path) as fh:
            assert "TRAPEZOIDAL" in fh.read()
        _run(wrapper)
        assert dataset.weirs.flow.array[0] >= 0.0  # built and runs without ERROR 143

    def test_functional_outlet_runs(self, initialize_wrapper):
        network = _one_link_network(
            "drainage_outlet_entities",
            {
                "urban_drainage.outlet_rating_type": [0],  # FUNCTIONAL/DEPTH
                "urban_drainage.rating_coefficient": [1.5],
                "urban_drainage.rating_exponent": [0.5],
            },
        )
        wrapper, dataset = initialize_wrapper(network)
        _run(wrapper)
        assert dataset.outlets.flow.array[0] > 0.0

    def test_tabular_outlet_builds_curve_and_runs(self, initialize_wrapper):
        network = _one_link_network(
            "drainage_outlet_entities",
            {
                "urban_drainage.outlet_rating_type": [2],  # TABULAR/DEPTH
                "urban_drainage.rating_curve": [[[0.0, 0.0], [1.0, 0.3], [2.0, 0.6]]],
            },
        )
        wrapper, dataset = initialize_wrapper(network)
        with open(wrapper._inp_path) as fh:
            inp = fh.read()
        assert "[CURVES]" in inp and "Rating" in inp
        _run(wrapper)
        assert dataset.outlets.flow.array[0] > 0.0

    def test_tabular_outlet_without_curve_raises(self, initialize_wrapper):
        network = _one_link_network(
            "drainage_outlet_entities",
            {"urban_drainage.outlet_rating_type": [2]},  # TABULAR but no rating_curve
        )
        with pytest.raises(ValueError, match="requires a rating_curve"):
            initialize_wrapper(network)

    def test_storage_volume_and_inflow_mapping(self, initialize_wrapper):
        # small orifice so the storage keeps filling; the injected inflow shows up
        # as lateral_inflow (distinct from total_outflow) and the volume rises.
        network = _one_link_network(
            "drainage_orifice_entities",
            {
                "urban_drainage.orifice_type": [1],
                "urban_drainage.orifice_shape": [1],
                "urban_drainage.cross_section_geometry": [[0.2, 0.2, 0.0, 0.0]],
                "urban_drainage.discharge_coefficient": [0.65],
                "urban_drainage.crest_height": [0.0],
            },
            inflow=0.3,
        )
        wrapper, dataset = initialize_wrapper(network)
        wrapper.apply_controls()
        wrapper.advance_to(300)
        wrapper.write_results()
        volume_early = dataset.storage.stored_volume.array[0]
        wrapper.apply_controls()
        wrapper.advance_to(1200)
        wrapper.write_results()
        st = dataset.storage
        # injected inflow maps to lateral_inflow / total_inflow (not total_outflow)
        assert st.lateral_inflow.array[0] == pytest.approx(0.3, rel=1e-2)
        assert st.total_inflow.array[0] == pytest.approx(0.3, rel=1e-2)
        assert st.total_outflow.array[0] < st.total_inflow.array[0]  # still filling
        # stored volume is positive and rises while filling
        assert volume_early > 0.0
        assert st.stored_volume.array[0] > volume_early


class TestNodeInflowControl:
    def test_generated_inflow_injects_node_inflow(self, initialize_wrapper):
        wrapper, dataset = initialize_wrapper()
        # inject inflow at junction id 1 via the control input
        if not dataset.junctions.generated_inflow.has_data():
            dataset.junctions.generated_inflow.initialize(len(dataset.junctions))
        dataset.junctions.generated_inflow.array[:] = [0.2, 0.0]
        for target in (300, 600):
            wrapper.apply_controls()
            wrapper.advance_to(target)
        wrapper.write_results()
        # the injected inflow shows up as inflow on the fed node and routes downstream
        assert dataset.junctions.total_inflow.array[0] > 0.0
        assert max(dataset.conduits.flow.array) > 0.0
        wrapper.close()


class TestEndOfHorizon:
    def test_advance_past_end_logs_and_freezes(self, initialize_wrapper, caplog):
        import logging
        from datetime import datetime

        wrapper, _ = initialize_wrapper()
        # close the real simulation first (only one may be open per process), then
        # swap in a stub whose iteration is immediately exhausted
        wrapper.close()

        class _ExhaustedSim:
            _t = datetime(2020, 1, 1)
            start_time = _t
            current_time = _t

            def step_advance(self, seconds):
                pass

            def __next__(self):
                raise StopIteration

            def report(self):
                pass

            def close(self):
                pass

        wrapper.sim = _ExhaustedSim()
        with caplog.at_level(logging.WARNING):
            wrapper.advance_to(600)  # must not raise
        assert "reached its end time" in caplog.text


class TestMultiRainGage:
    def test_distinct_intensities_route_to_correct_subcatchments(self, initialize_wrapper):
        enums = {"outfall_type": ["FREE", "NORMAL", "FIXED", "TIDAL", "TIMESERIES"]}
        network = {
            "version": 4,
            "name": DS,
            "type": DS,
            "general": {"enum": enums},
            "data": {
                "drainage_junction_entities": {
                    "id": [1, 2],
                    "geometry.x": [0.0, 50.0],
                    "geometry.y": [0.0, 0.0],
                    "urban_drainage.invert_elevation": [10.0, 10.0],
                },
                "drainage_outfall_entities": {
                    "id": [3, 4],
                    "geometry.x": [0.0, 50.0],
                    "geometry.y": [-50.0, -50.0],
                    "urban_drainage.invert_elevation": [8.0, 8.0],
                    "urban_drainage.outfall_type": [0, 0],
                },
                "drainage_conduit_entities": {
                    "id": [10, 11],
                    "topology.from_node_id": [1, 2],
                    "topology.to_node_id": [3, 4],
                    "shape.length": [50.0, 50.0],
                    "urban_drainage.roughness": [0.01, 0.01],
                    "urban_drainage.cross_section_shape": [0, 0],
                    "urban_drainage.cross_section_geometry": [
                        [1.0, 0.0, 0.0, 0.0],
                        [1.0, 0.0, 0.0, 0.0],
                    ],
                },
                "drainage_raingage_entities": {
                    "id": [5, 6],
                    "geometry.x": [-50.0, 100.0],
                    "geometry.y": [50.0, 50.0],
                },
                "drainage_subcatchment_entities": {
                    "id": [7, 8],
                    "urban_drainage.area": [4.0, 4.0],
                    "urban_drainage.width": [400.0, 400.0],
                    "urban_drainage.percent_impervious": [80.0, 80.0],
                    "urban_drainage.slope": [0.5, 0.5],
                    "urban_drainage.outlet_node_id": [1, 2],
                    "urban_drainage.raingage_id": [5, 6],
                },
            },
        }
        enums["xsection_shape"] = ["CIRCULAR"]
        wrapper, dataset = initialize_wrapper(network)
        if not dataset.raingages.rainfall_intensity.has_data():
            dataset.raingages.rainfall_intensity.initialize(len(dataset.raingages))
        dataset.raingages.rainfall_intensity.array[:] = [12.0, 0.0]  # gage 5 wet, gage 6 dry
        for target in (300, 600):
            wrapper.apply_controls()
            wrapper.advance_to(target)
        wrapper.write_results()
        # each gage reports its own intensity
        assert dataset.raingages.rainfall.array[0] == pytest.approx(12.0, rel=1e-3)
        assert dataset.raingages.rainfall.array[1] == pytest.approx(0.0, abs=1e-6)
        # only the subcatchment fed by the wet gage produces runoff
        assert dataset.subcatchments.runoff.array[0] > 0.0
        assert dataset.subcatchments.runoff.array[1] == pytest.approx(0.0, abs=1e-9)
        wrapper.close()


def _filling_storage_network():
    """Storage filled by a constant inflow, drained by a small orifice."""
    return _one_link_network(
        "drainage_orifice_entities",
        {
            "urban_drainage.orifice_type": [1],
            "urban_drainage.orifice_shape": [1],
            "urban_drainage.cross_section_geometry": [[0.2, 0.2, 0.0, 0.0]],
            "urban_drainage.discharge_coefficient": [0.65],
            "urban_drainage.crest_height": [0.0],
        },
        inflow=0.3,
    )


class TestHotstart:
    """The checkpoint/rollback engine primitives (not wired into the model loop)."""

    def test_checkpoint_and_rollback_restores_state(self, initialize_wrapper):
        wrapper, dataset = initialize_wrapper(_filling_storage_network())
        for target in (300, 600):
            wrapper.apply_controls()
            wrapper.advance_to(target)
        wrapper.write_results()
        volume = dataset.storage.stored_volume.array[0]
        depth = dataset.storage.water_depth.array[0]
        assert volume > 0.0

        checkpoint = wrapper.checkpoint()  # snapshot the state at t=600

        # advance further, then roll back to the checkpoint
        wrapper.apply_controls()
        wrapper.advance_to(1200)
        assert wrapper.elapsed_seconds() > 600
        wrapper.rollback_to(checkpoint)

        # state and reported clock are restored exactly to the checkpoint instant
        assert wrapper.elapsed_seconds() == pytest.approx(600, abs=30)
        wrapper.write_results()
        assert dataset.storage.stored_volume.array[0] == pytest.approx(volume, rel=1e-4)
        assert dataset.storage.water_depth.array[0] == pytest.approx(depth, rel=1e-4)
        # and it can keep stepping forward from there
        wrapper.apply_controls()
        wrapper.advance_to(900)
        assert wrapper.elapsed_seconds() >= 870

    def test_rollback_enables_step_replay_with_different_control(self, initialize_wrapper):
        wrapper, dataset = initialize_wrapper(_filling_storage_network())
        for target in (300, 600):
            wrapper.apply_controls()
            wrapper.advance_to(target)
        checkpoint = wrapper.checkpoint()

        # re-run [600 -> 900] with the orifice open
        wrapper.apply_controls()
        wrapper.advance_to(900)
        wrapper.write_results()
        flow_open = dataset.orifices.flow.array[0]
        assert flow_open > 0.0

        # roll the step back and re-run it with the (sole) orifice closed
        wrapper.rollback_to(checkpoint)
        if not dataset.orifices.target_setting.has_data():
            dataset.orifices.target_setting.initialize(len(dataset.orifices))
        dataset.orifices.target_setting.array[:] = [0.0]
        wrapper.apply_controls()
        wrapper.advance_to(900)
        wrapper.write_results()
        # the re-run diverges from the trajectory it was rolled back from
        assert dataset.orifices.flow.array[0] < 1e-6


class TestOneSimulationPerProcess:
    def test_concurrent_simulation_raises_clear_error(self, initialize_wrapper):
        # the fixture's wrapper holds the one simulation EPA-SWMM allows
        initialize_wrapper()
        other = SimulationWrapper()
        with pytest.raises(RuntimeError, match="already open"):
            other._open_simulation()
