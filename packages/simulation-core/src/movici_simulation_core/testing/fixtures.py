"""Shared pytest fixtures for Movici model testing.

This module is registered as a pytest plugin via the ``pytest11`` entry point,
making these fixtures automatically available to any test suite that depends on
``movici-simulation-core``.
"""

import itertools
import json
import shutil
import typing as t
from pathlib import Path

import pytest

from movici_simulation_core.attributes import GlobalAttributes
from movici_simulation_core.core import Model
from movici_simulation_core.core.data_format import EntityInitDataFormat
from movici_simulation_core.core.moment import set_timeline_info
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.core.serialization import UpdateDataFormat
from movici_simulation_core.model_connector.init_data import DirectoryInitDataHandler
from movici_simulation_core.models.common.attributes import CommonAttributes
from movici_simulation_core.testing.model_tester import ModelTester
from movici_simulation_core.utils import strategies


def pytest_configure(config):
    config.addinivalue_line("markers", "no_global_timeline_info")


@pytest.fixture
def additional_attributes():
    return []


@pytest.fixture
def global_timeline_info():
    return None


@pytest.fixture(autouse=True)
def set_global_timeline_info(global_timeline_info, request):
    if "no_global_timeline_info" in request.keywords:
        yield
    else:
        with set_timeline_info(global_timeline_info):
            yield


@pytest.fixture
def global_schema(additional_attributes):
    schema = AttributeSchema(attributes=additional_attributes)
    schema.use(GlobalAttributes)
    schema.use(CommonAttributes)
    return schema


@pytest.fixture(autouse=True)
def clean_strategies(global_schema):
    strategies.set(EntityInitDataFormat(schema=global_schema))
    strategies.set(UpdateDataFormat)
    yield
    strategies.reset()


@pytest.fixture
def init_data():
    return []


@pytest.fixture
def model_name():
    return "some_model"


@pytest.fixture
def time_scale():
    return 1


@pytest.fixture
def init_data_handler(tmp_path_factory):
    root = tmp_path_factory.mktemp("init_data_handler")
    return DirectoryInitDataHandler(root)


@pytest.fixture
def add_init_data(init_data_handler):
    root = init_data_handler.root

    def _add_init_data(name, data: t.Union[dict, str, Path]):
        if isinstance(data, dict):
            root.joinpath(f"{name}.json").write_text(json.dumps(data))
            return
        path = Path(data)
        if not path.is_file():
            raise ValueError(f"{data} is not a valid file")
        target = (root / name).with_suffix(path.suffix)
        shutil.copyfile(path, target)

    return _add_init_data


@pytest.fixture
def config(
    model_config,
    init_data,
    time_scale,
):
    return {
        "config": {
            "version": 4,
            "simulation_info": {
                "reference_time": 1_577_833_200,
                "start_time": 0,
                "time_scale": time_scale,
                "duration": 730,
            },
            "models": [model_config],
        },
        "init_data": init_data,
    }


@pytest.fixture
def create_model_tester(tmp_path_factory, init_data, global_schema):
    testers: t.List[ModelTester] = []
    counter = itertools.count()

    def _create(
        model_type: t.Type[Model],
        config,
        tmp_dir: Path = None,
        schema: AttributeSchema = None,
        **kwargs,
    ):
        model = model_type(config)
        if tmp_dir is None:
            tmp_dir = tmp_path_factory.mktemp(f"init_data_{next(counter)}")
        if schema is None:
            schema = global_schema

        tester = ModelTester(model, tmp_dir=tmp_dir, schema=schema, **kwargs)
        for obj in init_data:
            if isinstance(obj, dict):
                tester.add_init_data(**obj)
            elif isinstance(obj, (tuple, list)) and len(obj) == 2:
                tester.add_init_data(*obj)
            else:
                raise TypeError(f"Unknown init_data definition {obj:r}")

        testers.append(tester)
        return tester

    yield _create

    for tester in testers:
        tester.close()
        tester.cleanup()
