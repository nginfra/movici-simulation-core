"""Tests for the combiner solver helper. See issue #127."""

from __future__ import annotations

import jsonschema
import pytest

from movici_simulation_core.core.attribute_spec import AttributeSpec
from movici_simulation_core.core.schema import DataType
from movici_simulation_core.messages import RemapMessage
from movici_simulation_core.models.combiner import Combiner
from movici_simulation_core.testing.model_tester import ModelTester
from movici_simulation_core.types import Priority


@pytest.fixture
def init_data():
    return {
        "the_dataset": {
            "the_entities": {"id": [1, 2, 3]},
        }
    }


def _config(method="sum"):
    return {
        "name": "combiner_demand",
        "type": "combiner",
        "attribute": {
            "dataset": "the_dataset",
            "entity_group": "the_entities",
            "name": "cargo_demand",
        },
        "method": method,
    }


def _initialised_tester(config, init_data, tmp_path):
    model = Combiner(config)
    tester = ModelTester(model, tmp_dir=tmp_path)
    tester.add_init_data("the_dataset", init_data)
    return tester


def test_publishing_priority_is_solver_helper():
    assert Combiner.priority == int(Priority.SOLVER_HELPER)


@pytest.mark.parametrize(
    "method, expected",
    [
        ("sum", [40.0, 60.0, 80.0]),
        ("mean", [20.0, 30.0, 40.0]),
        ("min", [10.0, 20.0, 30.0]),
        ("max", [30.0, 40.0, 50.0]),
    ],
)
def test_combiner_reduces_internal_variants(method, expected, init_data, tmp_path):
    tester = _initialised_tester(_config(method), init_data, tmp_path)
    tester.initialize()
    tester.remap(
        RemapMessage(
            sub={
                "the_dataset": {
                    "the_entities": {
                        "cargo_demand:model_a:i": "cargo_demand",
                        "cargo_demand:model_b:i": "cargo_demand",
                    }
                }
            }
        )
    )
    tester.new_time(0)
    result_data, _ = tester.update(
        0,
        {
            "the_dataset": {
                "the_entities": {
                    "id": [1, 2, 3],
                    "cargo_demand:model_a:i": [10.0, 20.0, 30.0],
                    "cargo_demand:model_b:i": [30.0, 40.0, 50.0],
                }
            }
        },
    )
    canonical = result_data["the_dataset"]["the_entities"]["cargo_demand"]
    assert list(canonical) == expected


def test_invalid_method_rejected_by_config_schema():
    with pytest.raises(jsonschema.ValidationError):
        Combiner(_config(method="median"))


def test_invalid_method_rejected_without_config_validation():
    with pytest.raises(ValueError, match="unsupported method"):
        Combiner(_config(method="median"), validate_config=False)


def test_remap_with_no_sub_section_is_noop(init_data, tmp_path):
    tester = _initialised_tester(_config(), init_data, tmp_path)
    tester.initialize()
    # No sub section — combiner should not register any extra attributes.
    tester.remap(RemapMessage())
    inner_model = tester.model
    assert inner_model.inputs == []


def test_combiner_waits_for_all_inputs_before_emitting(init_data, tmp_path):
    # Partial-aggregation results are ambiguous (a sum that drops a publisher silently
    # underreports, a mean shifts) so the combiner must wait until every registered input
    # has data before producing a canonical value. Adversarial-review major finding.
    tester = _initialised_tester(_config("sum"), init_data, tmp_path)
    tester.initialize()
    tester.remap(
        RemapMessage(
            sub={
                "the_dataset": {
                    "the_entities": {
                        "cargo_demand:model_a:i": "cargo_demand",
                        "cargo_demand:model_b:i": "cargo_demand",
                    }
                }
            }
        )
    )
    tester.new_time(0)
    # Only model_a has published — combiner emits nothing.
    result_data, _ = tester.update(
        0,
        {
            "the_dataset": {
                "the_entities": {
                    "id": [1, 2, 3],
                    "cargo_demand:model_a:i": [10.0, 20.0, 30.0],
                }
            }
        },
    )
    assert result_data is None

    # Now model_b publishes too — combiner emits the combined value.
    result_data, _ = tester.update(
        0,
        {
            "the_dataset": {
                "the_entities": {
                    "id": [1, 2, 3],
                    "cargo_demand:model_b:i": [40.0, 50.0, 60.0],
                }
            }
        },
    )
    assert list(result_data["the_dataset"]["the_entities"]["cargo_demand"]) == [
        50.0,
        70.0,
        90.0,
    ]


def test_combiner_rejects_csr_output(init_data, tmp_path):
    # CSR (variable-length) attributes can't be stacked with np.stack. The output spec is
    # validated at setup time; the input variants reuse it, so this covers both sides.
    tester = _initialised_tester(_config(), init_data, tmp_path)
    csr_spec = AttributeSpec(name="cargo_demand", data_type=DataType(float, csr=True))
    tester._model.model.schema.add_attribute(csr_spec)
    with pytest.raises(ValueError, match="CSR"):
        tester.initialize()


def test_combiner_rejects_string_attributes(init_data, tmp_path):
    tester = _initialised_tester(_config(), init_data, tmp_path)
    tester._model.model.schema.add_attribute(
        AttributeSpec(name="cargo_demand", data_type=DataType(str))
    )
    with pytest.raises(ValueError, match="string"):
        tester.initialize()


@pytest.mark.parametrize("method", ["sum", "mean"])
def test_combiner_rejects_non_minmax_methods_for_bool(method, init_data, tmp_path):
    tester = _initialised_tester(_config(method), init_data, tmp_path)
    tester._model.model.schema.add_attribute(
        AttributeSpec(name="cargo_demand", data_type=DataType(bool))
    )
    with pytest.raises(ValueError, match="boolean"):
        tester.initialize()


def _remap_two_variants(tester):
    tester.remap(
        RemapMessage(
            sub={
                "the_dataset": {
                    "the_entities": {
                        "cargo_demand:model_a:i": "cargo_demand",
                        "cargo_demand:model_b:i": "cargo_demand",
                    }
                }
            }
        )
    )


def test_variants_reuse_canonical_spec(init_data, tmp_path):
    # The :i variants are the same quantity as the canonical attribute; their specs must
    # be reused (renamed), not re-inferred (which would fall back to float).
    tester = _initialised_tester(_config("min"), init_data, tmp_path)
    tester._model.model.schema.add_attribute(
        AttributeSpec(name="cargo_demand", data_type=DataType(int))
    )
    tester.initialize()
    _remap_two_variants(tester)
    combiner = tester.model
    assert all(attr.data_type == DataType(int) for attr in combiner.inputs)


def test_back_propagation_entry_is_not_an_input(init_data, tmp_path):
    # A {canonical: canonical} sub entry (back-propagation) preserves the combiner's own
    # canonical subscription; it must not be registered as an aggregation input.
    tester = _initialised_tester(_config(), init_data, tmp_path)
    tester.initialize()
    tester.remap(
        RemapMessage(
            sub={
                "the_dataset": {
                    "the_entities": {
                        "cargo_demand:model_a:i": "cargo_demand",
                        "cargo_demand": "cargo_demand",
                    }
                }
            }
        )
    )
    combiner = tester.model
    # Only the :i variant is an input; registering the canonical entry would have added
    # the combiner's own output attribute to its inputs.
    assert len(combiner.inputs) == 1
    assert combiner.output not in combiner.inputs


def test_partially_undefined_input_defers_output(init_data, tmp_path):
    # Aggregating an undefined sentinel would produce garbage (nan sums, shifted means).
    # The inputs are registered as SUB (required), so the adapter defers update() until
    # every input is fully defined; the combiner emits nothing until then.
    tester = _initialised_tester(_config("sum"), init_data, tmp_path)
    tester.initialize()
    _remap_two_variants(tester)
    tester.new_time(0)
    result_data, _ = tester.update(
        0,
        {
            "the_dataset": {
                "the_entities": {
                    "id": [1, 2, 3],
                    "cargo_demand:model_a:i": [10.0, None, 30.0],
                    "cargo_demand:model_b:i": [30.0, 40.0, 50.0],
                }
            }
        },
    )
    assert result_data is None

    # Once the missing entity receives a value, the combiner emits the full result.
    result_data, _ = tester.update(
        0,
        {
            "the_dataset": {
                "the_entities": {
                    "id": [2],
                    "cargo_demand:model_a:i": [20.0],
                }
            }
        },
    )
    assert list(result_data["the_dataset"]["the_entities"]["cargo_demand"]) == [
        40.0,
        60.0,
        80.0,
    ]


def test_mean_of_int_attributes_rounds_instead_of_truncating(init_data, tmp_path):
    tester = _initialised_tester(_config("mean"), init_data, tmp_path)
    tester._model.model.schema.add_attribute(
        AttributeSpec(name="cargo_demand", data_type=DataType(int))
    )
    tester.initialize()
    _remap_two_variants(tester)
    tester.new_time(0)
    result_data, _ = tester.update(
        0,
        {
            "the_dataset": {
                "the_entities": {
                    "id": [1, 2, 3],
                    "cargo_demand:model_a:i": [1, 2, 3],
                    "cargo_demand:model_b:i": [2, 3, 4],
                }
            }
        },
    )
    # means are [1.5, 2.5, 3.5]; np.rint rounds half to even: [2, 2, 4]. Plain casting
    # would have truncated to [1, 2, 3].
    assert list(result_data["the_dataset"]["the_entities"]["cargo_demand"]) == [2, 2, 4]
