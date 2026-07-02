"""Integration tests for the urban drainage (SWMM) simulation model."""

import numpy as np
import pytest
from jsonschema import ValidationError

from movici_urban_drainage_model.model import Model

DS = "urban_drainage"

ENUMS = {
    "xsection_shape": ["CIRCULAR", "RECT_CLOSED", "RECT_OPEN"],
    "outfall_type": ["FREE", "NORMAL", "FIXED", "TIDAL", "TIMESERIES"],
    "pump_curve_type": ["IDEAL", "PUMP1", "PUMP2", "PUMP3", "PUMP4"],
    "orifice_type": ["SIDE", "BOTTOM"],
    "orifice_shape": ["CIRCULAR", "RECT_CLOSED"],
    "weir_type": ["TRANSVERSE", "SIDEFLOW", "V-NOTCH", "TRAPEZOIDAL", "ROADWAY"],
    "outlet_rating_type": ["FUNCTIONAL/DEPTH", "FUNCTIONAL/HEAD", "TABULAR/DEPTH", "TABULAR/HEAD"],
}


@pytest.fixture
def additional_attributes():
    return Model.get_schema_attributes()


class TestConfigSchema:
    def test_valid_config(self):
        model = Model({"dataset": "drainage", "options": {"report_timestep": 600}})
        assert model.dataset_name == "drainage"
        assert model.report_timestep == 600

    def test_default_report_step(self):
        model = Model({"dataset": "drainage"})
        assert model.report_timestep == 300

    def test_invalid_config_raises(self):
        with pytest.raises(ValidationError):
            Model({})


class TestUrbanDrainageModelBase:
    """A simple rainfall-driven drainage network::

    S1 (subcatchment, gage RG1) -> J1 -(C1)-> J2 -(C2)-> O1 (outfall)
    """

    @pytest.fixture
    def model_config(self):
        return {"dataset": DS, "options": {"hydraulic_timestep": 30, "report_timestep": 300}}

    @pytest.fixture
    def network_data(self):
        return {
            "version": 4,
            "name": DS,
            "type": "urban_drainage_network",
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

    @pytest.fixture
    def init_data(self, network_data):
        return [(DS, network_data)]

    @pytest.fixture
    def tester(self, create_model_tester, model_config):
        return create_model_tester(Model, model_config)


class TestSimpleNetwork(TestUrbanDrainageModelBase):
    def test_initial_state_at_t0(self, tester):
        tester.initialize()
        result, _ = tester.update(0, None)
        assert result is not None
        junctions = result[DS]["drainage_junction_entities"]
        # At t=0 with zero initial depth, head equals the invert elevation
        np.testing.assert_allclose(junctions["urban_drainage.water_depth"], [0.0, 0.0], atol=1e-9)
        np.testing.assert_allclose(junctions["urban_drainage.hydraulic_head"], [10.0, 9.0])

    def test_results_published_for_nodes_and_links(self, tester):
        tester.initialize()
        result, _ = tester.update(0, None)
        data = result[DS]
        assert "urban_drainage.water_depth" in data["drainage_junction_entities"]
        assert "urban_drainage.flow" in data["drainage_conduit_entities"]
        assert "urban_drainage.runoff" in data["drainage_subcatchment_entities"]

    def test_rainfall_drives_runoff_and_flow(self, tester):
        tester.initialize()
        tester.update(0, None)

        # Drive rainfall through the rain gage from t=0 onwards. The gage's
        # rainfall is published in the step where it changes (0 -> 5).
        rain_update = {
            DS: {
                "drainage_raingage_entities": {
                    "id": [4],
                    "urban_drainage.rainfall_intensity": [5.0],
                }
            }
        }
        tester.new_time(300)
        result_rain, _ = tester.update(300, rain_update)
        gages = result_rain[DS]["drainage_raingage_entities"]
        assert gages["urban_drainage.rainfall"][0] == pytest.approx(5.0, rel=1e-3)

        # Let the rain keep falling so runoff routes into the network
        tester.new_time(600)
        result, _ = tester.update(600, None)
        assert result is not None

        subs = result[DS]["drainage_subcatchment_entities"]
        assert subs["urban_drainage.runoff"][0] > 0.0

        # Runoff enters the network and produces conduit flow
        conduits = result[DS]["drainage_conduit_entities"]
        assert max(conduits["urban_drainage.flow"]) > 0.0

    def test_same_moment_reentry_does_not_advance(self, tester):
        tester.initialize()
        _, next_time = tester.update(0, None)
        elapsed_before = tester.model.network.elapsed_seconds()

        # A late control input arriving at the already-simulated moment t=0 must NOT
        # re-step the engine (SWMM cannot rewind): the model returns early without
        # advancing. The control is not lost - it is consumed on the next forward
        # step, where process_changes() re-reads it from the array.
        _, reentry_next_time = tester.update(
            0,
            {
                DS: {
                    "drainage_raingage_entities": {
                        "id": [4],
                        "urban_drainage.rainfall_intensity": [5.0],
                    }
                }
            },
        )
        assert reentry_next_time == next_time
        assert tester.model.network.elapsed_seconds() == elapsed_before

        # On the next forward step the late rainfall takes effect, proving it was
        # retained on the array and applied rather than dropped on the re-entry.
        tester.new_time(300)
        result, _ = tester.update(300, None)
        gages = result[DS]["drainage_raingage_entities"]
        assert gages["urban_drainage.rainfall"][0] == pytest.approx(5.0, rel=1e-3)

    @pytest.mark.parametrize(
        "infiltration",
        ["HORTON", "MODIFIED_HORTON", "GREEN_AMPT", "MODIFIED_GREEN_AMPT", "CURVE_NUMBER"],
    )
    def test_infiltration_models_run_and_produce_runoff(self, create_model_tester, infiltration):
        config = {
            "dataset": DS,
            "options": {
                "hydraulic_timestep": 30,
                "report_timestep": 300,
                "infiltration_model_override": infiltration,
            },
        }
        tester = create_model_tester(Model, config)
        tester.initialize()
        tester.update(0, None)
        tester.new_time(300)
        tester.update(
            300,
            {
                DS: {
                    "drainage_raingage_entities": {
                        "id": [4],
                        "urban_drainage.rainfall_intensity": [30.0],
                    }
                }
            },
        )
        tester.new_time(600)
        result, _ = tester.update(600, None)
        # the impervious area sheds runoff for every model...
        assert result[DS]["drainage_subcatchment_entities"]["urban_drainage.runoff"][0] > 0.0
        # ...and infiltration is actually applied to the pervious area, confirming the
        # model-specific [INFILTRATION] columns are interpreted, not ignored. Read the
        # live array (infiltration may reach a steady rate and drop out of the delta).
        subcatchments = tester.model.dataset.subcatchments
        assert subcatchments.infiltration_loss.array[0] > 0.0


class TestNextTime(TestUrbanDrainageModelBase):
    def test_initial_next_time(self, tester):
        report_timestep = tester.model.report_timestep
        tester.initialize()
        _, next_time = tester.update(0, None)
        assert next_time == report_timestep

    def test_next_time_progression(self, tester):
        report_timestep = tester.model.report_timestep
        tester.initialize()
        _, next_time = tester.update(0, None)
        tester.new_time(next_time)
        _, new_next_time = tester.update(next_time, None)
        assert new_next_time == next_time + report_timestep


def _infiltration_row(inp_text, name):
    """Return the [INFILTRATION] token row for *name* from synthesised .inp text."""
    section = inp_text.split("[INFILTRATION]", 1)[1]
    for line in section.splitlines():
        toks = line.split()
        if toks and toks[0] == name:
            return toks
        if line.startswith("["):  # next section
            break
    raise AssertionError(f"no INFILTRATION row for {name}")


class TestInfiltrationColumns(TestUrbanDrainageModelBase):
    """Guards the per-model [INFILTRATION] column ordering (not just that it runs)."""

    @pytest.fixture
    def model_config(self):
        return {
            "dataset": DS,
            "options": {
                "hydraulic_timestep": 30,
                "report_timestep": 300,
                "infiltration_model_override": "GREEN_AMPT",
            },
        }

    @pytest.fixture
    def network_data(self):
        # Green-Ampt subcatchment with distinguishable per-column values so a
        # transposition of suction_head / conductivity / initial_deficit is caught.
        return {
            "version": 4,
            "name": DS,
            "type": "urban_drainage_network",
            "general": {"enum": ENUMS},
            "data": {
                "drainage_junction_entities": {
                    "id": [1],
                    "geometry.x": [0.0],
                    "geometry.y": [0.0],
                    "urban_drainage.invert_elevation": [10.0],
                },
                "drainage_outfall_entities": {
                    "id": [2],
                    "geometry.x": [100.0],
                    "geometry.y": [0.0],
                    "urban_drainage.invert_elevation": [8.0],
                    "urban_drainage.outfall_type": [0],
                },
                "drainage_conduit_entities": {
                    "id": [10],
                    "topology.from_node_id": [1],
                    "topology.to_node_id": [2],
                    "shape.length": [100.0],
                    "urban_drainage.roughness": [0.01],
                    "urban_drainage.cross_section_shape": [0],
                    "urban_drainage.cross_section_geometry": [[1.0, 0.0, 0.0, 0.0]],
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
                    "urban_drainage.suction_head": [12.5],
                    "urban_drainage.conductivity": [3.4],
                    "urban_drainage.initial_deficit": [0.21],
                },
            },
        }

    def test_green_ampt_columns_in_order(self, tester):
        tester.initialize()
        with open(tester.model.network._inp_path) as fh:
            row = _infiltration_row(fh.read(), "S5")
        # [INFILTRATION] for GREEN_AMPT: Name  SuctionHead  Conductivity  InitialDeficit
        assert row[0] == "S5"
        assert [float(t) for t in row[1:4]] == pytest.approx([12.5, 3.4, 0.21])


class TestNonIntegerTimeScale(TestUrbanDrainageModelBase):
    """SWMM advances in whole seconds, so a fractional time_scale must warn."""

    @pytest.fixture
    def global_timeline_info(self):
        from movici_simulation_core.core.moment import TimelineInfo

        return TimelineInfo(0, 0.5, 0)  # fractional time_scale

    def test_fractional_time_scale_warns(self, tester, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            tester.initialize()
        assert "Non-integer time_scale" in caplog.text


class TestPumpControl:
    """A pumped network: inflow -> wet well (storage) -> pump -> outfall."""

    @pytest.fixture
    def model_config(self):
        return {"dataset": DS, "options": {"hydraulic_timestep": 30, "report_timestep": 300}}

    @pytest.fixture
    def network_data(self):
        return {
            "version": 4,
            "name": DS,
            "type": "urban_drainage_network",
            "general": {"enum": ENUMS},
            "data": {
                "drainage_storage_entities": {
                    "id": [1],
                    "geometry.x": [0.0],
                    "geometry.y": [0.0],
                    "urban_drainage.invert_elevation": [0.0],
                    "urban_drainage.max_depth": [10.0],
                    "urban_drainage.storage_constant": [100.0],
                    "urban_drainage.generated_inflow": [0.1],
                },
                "drainage_outfall_entities": {
                    "id": [2],
                    "geometry.x": [100.0],
                    "geometry.y": [0.0],
                    "urban_drainage.invert_elevation": [0.0],
                    "urban_drainage.outfall_type": [0],
                },
                "drainage_pump_entities": {
                    "id": [20],
                    "topology.from_node_id": [1],
                    "topology.to_node_id": [2],
                    "urban_drainage.pump_curve_type": [4],
                    "urban_drainage.pump_curve": [[[0.0, 0.2], [10.0, 0.2]]],
                },
            },
        }

    @pytest.fixture
    def init_data(self, network_data):
        return [(DS, network_data)]

    @pytest.fixture
    def tester(self, create_model_tester, model_config):
        return create_model_tester(Model, model_config)

    def test_pump_runs_then_stops_on_control(self, tester):
        tester.initialize()
        tester.update(0, None)

        # Let the pump run a while - it should move water to the outfall
        tester.new_time(600)
        result_running, _ = tester.update(600, None)
        pump_flow_running = result_running[DS]["drainage_pump_entities"]["urban_drainage.flow"][0]
        assert pump_flow_running > 0.0

        # Turn the pump off via target_setting; the change takes effect over the
        # next step, where the pump flow drops to zero (and so is republished).
        tester.new_time(900)
        result_stopped, _ = tester.update(
            900,
            {DS: {"drainage_pump_entities": {"id": [20], "urban_drainage.target_setting": [0.0]}}},
        )
        pump_flow_stopped = result_stopped[DS]["drainage_pump_entities"]["urban_drainage.flow"][0]
        assert pump_flow_stopped < 1e-9


class TestReportStepFromGeneral:
    """report_timestep supplied via the dataset general section must drive both the
    Movici wake cadence and the SWMM report step (single authoritative value)."""

    @pytest.fixture
    def model_config(self):
        # no report_timestep here; it comes from the dataset general section
        return {"dataset": DS, "options": {"hydraulic_timestep": 30}}

    @pytest.fixture
    def init_data(self):
        return [
            (
                DS,
                {
                    "version": 4,
                    "name": DS,
                    "type": "urban_drainage_network",
                    "general": {"enum": ENUMS, "report_timestep": 600},
                    "data": {
                        "drainage_junction_entities": {
                            "id": [1],
                            "geometry.x": [0.0],
                            "geometry.y": [0.0],
                            "urban_drainage.invert_elevation": [10.0],
                        },
                        "drainage_outfall_entities": {
                            "id": [2],
                            "geometry.x": [100.0],
                            "geometry.y": [0.0],
                            "urban_drainage.invert_elevation": [9.0],
                            "urban_drainage.outfall_type": [0],
                        },
                        "drainage_conduit_entities": {
                            "id": [10],
                            "topology.from_node_id": [1],
                            "topology.to_node_id": [2],
                            "shape.length": [100.0],
                            "urban_drainage.roughness": [0.01],
                            "urban_drainage.cross_section_shape": [0],
                            "urban_drainage.cross_section_geometry": [[1.0, 0.0, 0.0, 0.0]],
                        },
                    },
                },
            )
        ]

    @pytest.fixture
    def tester(self, create_model_tester, model_config):
        return create_model_tester(Model, model_config)

    def test_report_step_resolved_from_general_section(self, tester):
        # provisional config default before initialize
        assert tester.model.report_timestep == 300
        tester.initialize()
        # resolved from the merged options (general section wins) in initialize
        assert tester.model.report_timestep == 600
        _, next_time = tester.update(0, None)
        assert next_time == 600
