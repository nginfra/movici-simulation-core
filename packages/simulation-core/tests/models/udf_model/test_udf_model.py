import itertools
import json
import typing as t

import pytest

from movici_simulation_core.core.attribute import REQUIRED, SUB, UniformAttribute
from movici_simulation_core.core.schema import AttributeSchema, AttributeSpec, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.models.udf_model import MODEL_CONFIG_SCHEMA_PATH
from movici_simulation_core.models.udf_model.udf_model import (
    UDFInfo,
    UDFModel,
    get_input_attributes,
    get_udf_infos,
    prepare_optional_attributes,
)
from movici_simulation_core.testing.helpers import data_mask_compare
from movici_simulation_core.testing.model_tester import ModelTester
from movici_simulation_core.validate import validate_and_process


@pytest.fixture
def additional_attributes():
    return [
        AttributeSpec("id", DataType(int)),
        AttributeSpec("in_a", DataType(float)),
        AttributeSpec("in_b", DataType(float)),
        AttributeSpec("in_c", DataType(float)),
        AttributeSpec("in_bool", DataType(bool)),
        AttributeSpec("in_csr", DataType(float, csr=True)),
        AttributeSpec("in_csr2", DataType(float, csr=True)),
        AttributeSpec("undef", DataType(float)),
        AttributeSpec("undef_csr", DataType(float, csr=True)),
        AttributeSpec("out_csr", DataType(float, csr=True)),
        AttributeSpec("in_2d", DataType(float, (2,))),
        AttributeSpec("out_bool", DataType(bool)),
    ]


@pytest.fixture
def schema(additional_attributes):
    return AttributeSchema(additional_attributes)


@pytest.fixture
def init_data():
    return {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "in_a": [1.0, 2.0, 3.0],
                "in_b": [1.1, 2.2, 3.3],
                "in_c": [1.1, 2.1, 2.9],
                "in_bool": [True, True, False],
                "in_csr": [[10, 11], [20, 22], []],
                "undef_csr": [[10], [], None],
                "in_csr2": [[100, 110], [200, 220], []],
            }
        }
    }


@pytest.fixture
def legacy_config():
    return {
        "entity_group": [["some_dataset", "some_entities"]],
        "inputs": {"a": [None, "in_a"], "b": [None, "in_b"], "c": [None, "in_c"]},
        "functions": [
            {
                "expression": "a+b",
                "output": [None, "out_d"],
            },
            {
                "expression": "a*c",
                "output": [None, "out_e"],
            },
        ],
    }


@pytest.fixture
def config():
    return {
        "entity_group": ["some_dataset", "some_entities"],
        "inputs": {"a": "in_a", "b": "in_b", "c": "in_c"},
        "functions": [
            {
                "expression": "a+b",
                "output": "out_d",
            },
            {
                "expression": "a*c",
                "output": "out_e",
            },
        ],
    }


class TestConfigParsing:
    @pytest.fixture
    def state(self):
        return TrackedState()

    def test_get_input_attributes_returns_correct_keys(self, config, state, schema):
        attrs = get_input_attributes(config, schema, state)
        assert attrs.keys() == {"a", "b", "c"}

    def test_get_input_attributes_returns_correct_attributes(self, config, state, schema):
        attrs = get_input_attributes(config, schema, state)
        assert isinstance(attrs["a"], UniformAttribute)
        assert attrs["a"].data_type == DataType(float)

    def test_get_input_attributes_registers_as_sub(self, config, state, schema):
        attrs = get_input_attributes(config, schema, state)
        assert attrs["a"].flags == SUB

    def test_get_udf_infos(self, config):
        assert list(get_udf_infos(config)) == [
            UDFInfo(
                dataset="some_dataset",
                entity_group="some_entities",
                output_attribute="out_d",
                expression="a+b",
            ),
            UDFInfo(
                dataset="some_dataset",
                entity_group="some_entities",
                output_attribute="out_e",
                expression="a*c",
            ),
        ]

    @pytest.mark.parametrize(
        "optional",
        [["a"], ["a", "b"], ["a", "a"]],
    )
    def test_prepare_optional_attributes(self, optional, config, state, schema):
        config["optional"] = optional
        inputs = get_input_attributes(config, schema, state)
        prepare_optional_attributes(config, inputs)
        unique_opts = set(optional)
        for k, v in inputs.items():
            if k in unique_opts:
                assert not v.flags & REQUIRED
            else:
                assert v.flags & REQUIRED


def test_model_data_mask(config):
    model = UDFModel(config)
    with ModelTester(model) as tester:
        assert data_mask_compare(tester.initialize()) == {
            "sub": {"some_dataset": {"some_entities": {"in_a", "in_b", "in_c"}}},
            "pub": {"some_dataset": {"some_entities": {"out_d", "out_e"}}},
        }


def test_detects_intermediate_attributes_as_pub():
    config = {
        "entity_group": [["some_dataset", "some_entities"]],
        "inputs": {
            "a": [None, "in_a"],
            "b": [None, "in_out_b"],
        },
        "functions": [
            {
                "expression": "a",
                "output": [None, "in_out_b"],
            },
            {
                "expression": "b",
                "output": [None, "out_d"],
            },
        ],
    }
    model = UDFModel(config)

    with ModelTester(model) as tester:
        assert data_mask_compare(tester.initialize()) == {
            "sub": {"some_dataset": {"some_entities": {"in_a"}}},
            "pub": {"some_dataset": {"some_entities": {"in_out_b", "out_d"}}},
        }


@pytest.fixture
def create_model_tester(tmp_path_factory, init_data, global_schema):
    testers: t.List[ModelTester] = []
    counter = itertools.count()

    def _create(config, **kwargs):
        model = UDFModel(config)
        tmp_dir = kwargs.pop("tmp_dir", tmp_path_factory.mktemp(f"init_data_{next(counter)}"))
        global_schema_ = kwargs.pop("global_schema", global_schema)

        tester = ModelTester(model, tmp_dir=tmp_dir, schema=global_schema_, **kwargs)
        tester.add_init_data("some_dataset", init_data)
        testers.append(tester)
        return tester

    yield _create

    for tester in testers:
        tester.close()
        tester.cleanup()


def test_model_with_one_function(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"a": [None, "in_a"], "b": [None, "in_b"]},
            "functions": [
                {
                    "expression": "a+b",
                    "output": [None, "out_d"],
                },
            ],
            "optional": ["a"],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out_d": [2.1, 4.2, 6.3],
            }
        }
    }


def test_can_produce_and_use_intermediate_results(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"a": [None, "in_a"], "b": [None, "in_b"], "c": [None, "in_out_c"]},
            "functions": [
                {
                    "expression": "a+b",
                    "output": [None, "in_out_c"],
                },
                {
                    "expression": "a+c",
                    "output": [None, "out_d"],
                },
            ],
        }
    )

    tester.initialize()

    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "in_out_c": [2.1, 4.2, 6.3],
                "out_d": [3.1, 6.2, 9.3],
            }
        }
    }


def test_with_csr_aggregation(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"a": [None, "in_csr"]},
            "functions": [
                {
                    "expression": "sum(a)",
                    "output": [None, "out_d"],
                },
            ],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)

    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out_d": [21, 42, 0],
            }
        }
    }


def test_with_csr_to_csr(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"a": [None, "in_csr"], "b": [None, "in_csr2"]},
            "functions": [
                {
                    "expression": "a+b",
                    "output": [None, "out_csr"],
                },
            ],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out_csr": [[110, 121], [220, 242], []],
            }
        }
    }


def test_csr_with_uniform(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"csr": [None, "in_csr"], "a": [None, "in_a"]},
            "functions": [
                {
                    "expression": "csr+a",
                    "output": [None, "out_csr"],
                },
            ],
        }
    )

    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out_csr": [[11, 12], [22, 24], []],
            }
        }
    }


def test_default(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"a": [None, "in_a"], "undef": [None, "undef"]},
            "optional": ["undef"],
            "functions": [
                {
                    "expression": "default(undef, a)",
                    "output": [None, "out"],
                },
            ],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out": [1, 2, 3],
            }
        }
    }


def test_default_csr_to_csr(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"a": [None, "undef_csr"]},
            "optional": ["a"],
            "functions": [
                {
                    "expression": "default(a, 0)",
                    "output": [None, "out_csr"],
                },
            ],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out_csr": [[10], [], [0]],
            }
        }
    }


def test_multi_arg_min(create_model_tester):
    tester: ModelTester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"a": [None, "in_a"], "b": [None, "in_b"]},
            "functions": [
                {
                    "expression": "min(a, b, 2)",
                    "output": [None, "out"],
                },
            ],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out": [1, 2, 2],
            }
        }
    }


def test_csr_uniform_min(create_model_tester):
    tester: ModelTester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"csr": [None, "in_csr"], "a": [None, "in_a"]},
            "functions": [
                {
                    "expression": "min(csr, a)",
                    "output": [None, "out_csr"],
                },
            ],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)

    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out_csr": [[1, 1], [2, 2], []],
            }
        }
    }


def test_csr_uniform_if(create_model_tester):
    tester: ModelTester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"cond": "in_bool", "a": "in_a", "b": "in_b"},
            "functions": [
                {
                    "expression": "if(cond, a, b)",
                    "output": "out",
                },
            ],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)

    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out": [1.0, 2.0, 3.3],
            }
        }
    }


def test_csr_uniform_if_2(create_model_tester):
    tester: ModelTester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"c": "in_c", "a": "in_a", "b": "in_b"},
            "functions": [
                {
                    "expression": "if(a<c, 3, 4)",
                    "output": "out",
                },
            ],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)

    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out": [3, 3, 4],
            }
        }
    }


def test_csr_scalar_min(create_model_tester):
    tester: ModelTester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"csr": [None, "in_csr"]},
            "functions": [
                {
                    "expression": "min(csr, 11)",
                    "output": [None, "out_csr"],
                },
            ],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)

    assert result == {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "out_csr": [[10, 11], [11, 11], []],
            }
        }
    }


@pytest.mark.parametrize(
    "config_",
    [
        None,
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"a": "undef_csr"},
            "optional": ["a"],
            "functions": [
                {
                    "expression": "default(a, 0)",
                    "output": "out_csr",
                },
            ],
        },
    ],
)
def test_model_config_schema(config_, config):
    config = config_ or config
    schema = json.loads(MODEL_CONFIG_SCHEMA_PATH.read_text())
    assert validate_and_process(config, schema)


def test_convert_legacy_model_config(legacy_config, config):
    assert UDFModel(legacy_config).config == config


def test_identifiers_may_contain_digits(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"a_1": "in_a", "a_2": "in_b"},
            "functions": [{"expression": "a_1+a_2", "output": "out"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {"some_dataset": {"some_entities": {"id": [1, 2, 3], "out": [2.1, 4.2, 6.3]}}}


def test_model_with_power_and_math_functions(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"a": "in_a"},
            "functions": [{"expression": "sqrt(a**2)", "output": "out"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {"some_dataset": {"some_entities": {"id": [1, 2, 3], "out": [1, 2, 3]}}}


def test_model_with_boolean_operators(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"a": "in_a", "b": "in_b", "c": "in_c"},
            "functions": [{"expression": "a<b and a<c", "output": "out_bool"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {"some_entities": {"id": [1, 2, 3], "out_bool": [True, True, False]}}
    }


def test_division_by_zero_yields_an_undefined_value(create_model_tester):
    """a division that cannot produce a finite number results in an undefined value, which
    `default` can then fill in
    """
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"a": "in_a", "b": "in_b"},
            "functions": [{"expression": "default(b/(a-a), 0)", "output": "out"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {"some_dataset": {"some_entities": {"id": [1, 2, 3], "out": [0, 0, 0]}}}


def test_csr_with_scalar_on_the_left(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"csr": "in_csr"},
            "functions": [{"expression": "100-csr", "output": "out_csr"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {"some_entities": {"id": [1, 2, 3], "out_csr": [[90, 89], [80, 78], []]}}
    }


def test_csr_with_uniform_attribute_on_the_left(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"csr": "in_csr", "a": "in_a"},
            "functions": [{"expression": "a*csr", "output": "out_csr"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {"some_entities": {"id": [1, 2, 3], "out_csr": [[10, 11], [40, 44], []]}}
    }


class TestResultTypeInference:
    """The data type of an output attribute that the attribute schema does not define follows from
    the expression, rather than always being a float
    """

    @pytest.fixture
    def make_model(self, global_schema):
        def _make(expression, output, inputs=None):
            model = UDFModel(
                {
                    "entity_group": ["some_dataset", "some_entities"],
                    "inputs": inputs or {"a": "in_a", "b": "in_b", "csr": "in_csr"},
                    "functions": [{"expression": expression, "output": output}],
                }
            )
            state = TrackedState()
            model.setup(state=state, schema=global_schema)
            return model

        return _make

    @pytest.mark.parametrize(
        "expression, expected",
        [
            ("a+b", DataType(float)),
            ("a<b", DataType(bool)),
            ("a<b and b<a", DataType(bool)),
            ("csr+a", DataType(float, csr=True)),
            ("sum(csr)", DataType(float)),
        ],
    )
    def test_infers_the_output_data_type(self, expression, expected, make_model):
        model = make_model(expression, "some_new_attribute")
        assert model.udfs[0].output.data_type == expected

    def test_attribute_schema_takes_precedence_over_inference(self, make_model):
        """`out_csr` is a csr attribute in the schema, so it stays one"""
        model = make_model("csr+a", "out_csr")
        assert model.udfs[0].output.data_type == DataType(float, csr=True)

    def test_rejects_a_csr_expression_written_to_a_uniform_attribute(self, make_model):
        with pytest.raises(ValueError, match="variable number of values per entity"):
            make_model("csr+a", "in_a")

    def test_rejects_a_uniform_expression_written_to_a_csr_attribute(self, make_model):
        with pytest.raises(ValueError, match="single value per entity"):
            make_model("a+b", "out_csr")

    def test_rejects_an_unknown_name(self, make_model):
        with pytest.raises(NameError, match="'typo' is not one of the inputs"):
            make_model("a+typo", "out")


def test_boolean_expression_publishes_booleans(create_model_tester):
    """without inference the output attribute would default to a float and publish 1.0/0.0"""
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"a": "in_a", "c": "in_c"},
            "functions": [{"expression": "a<c", "output": "some_new_flag"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {"some_entities": {"id": [1, 2, 3], "some_new_flag": [True, True, False]}}
    }


def test_group_reducer_gives_each_entity_its_share(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"a": "in_a"},
            "functions": [{"expression": "a/total(a)", "output": "out"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {
        "some_dataset": {"some_entities": {"id": [1, 2, 3], "out": [1 / 6, 2 / 6, 3 / 6]}}
    }


def test_group_reducer_broadcasts_a_scalar_over_the_entities(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"a": "in_a"},
            "functions": [{"expression": "mean(a)", "output": "out"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {"some_dataset": {"some_entities": {"id": [1, 2, 3], "out": [2.0, 2.0, 2.0]}}}


def test_group_reducer_skips_undefined_values(create_model_tester):
    """`undef` has no data at all, `total` of it is 0 rather than undefined"""
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"a": "in_a", "undef": "undef"},
            "optional": ["undef"],
            "functions": [{"expression": "a+total(undef)", "output": "out"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {"some_dataset": {"some_entities": {"id": [1, 2, 3], "out": [1, 2, 3]}}}


def test_group_reducer_over_a_csr_attribute(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": ["some_dataset", "some_entities"],
            "inputs": {"csr": "in_csr"},
            "functions": [{"expression": "count(csr)", "output": "out"}],
        }
    )
    tester.initialize()
    result, _ = tester.update(0, None)
    assert result == {"some_dataset": {"some_entities": {"id": [1, 2, 3], "out": [4, 4, 4]}}}
