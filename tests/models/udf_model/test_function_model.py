import itertools
import json
import typing as t

import pytest

from movici_simulation_core.core.schema import AttributeSchema, PropertySpec, DataType
from movici_simulation_core.data_tracker.property import UniformProperty, SUB, REQUIRED
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.udf_model import MODEL_CONFIG_SCHEMA_PATH
from movici_simulation_core.models.udf_model.udf_model import (
    get_input_attributes,
    get_udf_infos,
    UDFInfo,
    UDFModel,
    prepare_optional_attributes,
)
from movici_simulation_core.testing.helpers import data_mask_compare
from movici_simulation_core.testing.model_schema import model_config_validator
from movici_simulation_core.testing.model_tester import ModelTester


@pytest.fixture
def schema():
    return AttributeSchema(
        [
            PropertySpec("in_a", DataType(float)),
            PropertySpec("in_b", DataType(float)),
            PropertySpec("in_csr", DataType(float, csr=True)),
            PropertySpec("in_csr2", DataType(float, csr=True)),
            PropertySpec("undef", DataType(float)),
            PropertySpec("undef_csr", DataType(float, csr=True)),
            PropertySpec("out_csr", DataType(float, csr=True)),
            PropertySpec("in_2d", DataType(float, (2,))),
        ]
    )


@pytest.fixture
def init_data():
    return {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "in_a": [1.0, 2.0, 3.0],
                "in_b": [1.1, 2.2, 3.3],
                "in_csr": [[10, 11], [20, 22], []],
                "undef_csr": [[10], [], None],
                "in_csr2": [[100, 110], [200, 220], []],
            }
        }
    }


@pytest.fixture
def config():
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
                "output": ["comp_e", "out_e"],
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

    def test_get_input_attributes_returns_correct_properties(self, config, state, schema):
        attrs = get_input_attributes(config, schema, state)
        assert isinstance(attrs["a"], UniformProperty)
        assert attrs["a"].data_type == DataType(float)

    def test_get_input_attributes_registers_as_sub(self, config, state, schema):
        attrs = get_input_attributes(config, schema, state)
        assert attrs["a"].flags == SUB

    def test_get_udf_infos(self, config):
        assert list(get_udf_infos(config)) == [
            UDFInfo(
                dataset="some_dataset",
                entity_group="some_entities",
                output_component=None,
                output_attribute="out_d",
                expression="a+b",
            ),
            UDFInfo(
                dataset="some_dataset",
                entity_group="some_entities",
                output_component="comp_e",
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
    tester = ModelTester(model)
    assert data_mask_compare(tester.initialize()) == {
        "sub": {"some_dataset": {"some_entities": {"in_a", "in_b", "in_c"}}},
        "pub": {"some_dataset": {"some_entities": {"out_d", "comp_e/out_e"}}},
    }


def test_detects_intermediate_properties_as_pub():
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
    tester = ModelTester(model)
    assert data_mask_compare(tester.initialize()) == {
        "sub": {"some_dataset": {"some_entities": {"in_a"}}},
        "pub": {"some_dataset": {"some_entities": {"in_out_b", "out_d"}}},
    }


@pytest.fixture
def create_model_tester(tmp_path_factory, init_data, schema):
    testers: t.List[ModelTester] = []
    counter = itertools.count()

    def _create(config, **kwargs):
        model = UDFModel(config)
        tmp_dir = kwargs.pop("tmp_dir", tmp_path_factory.mktemp(f"init_data_{next(counter)}"))
        global_schema = kwargs.pop("global_schema", schema)

        tester = ModelTester(model, tmp_dir=tmp_dir, global_schema=global_schema, **kwargs)
        tester.add_init_data("some_dataset", init_data)
        testers.append(tester)
        return tester

    yield _create

    for tester in testers:
        tester.close()


def test_model_with_one_function(create_model_tester):
    tester = create_model_tester(
        {
            "entity_group": [["some_dataset", "some_entities"]],
            "inputs": {"a": [None, "in_a"], "b": [None, "in_b"]},
            "functions": [
                {
                    "optional": ["a"],
                    "expression": "a+b",
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


@pytest.mark.parametrize(
    "config_",
    [
        None,
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
        },
    ],
)
def test_model_config_schema(config_, config):
    config = config_ or config
    schema = json.loads(MODEL_CONFIG_SCHEMA_PATH.read_text())
    assert model_config_validator(schema)(config)
