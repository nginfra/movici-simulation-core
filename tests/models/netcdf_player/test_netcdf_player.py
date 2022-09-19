import json
import typing as t
from pathlib import Path

import netCDF4
import numpy as np
import pytest

from movici_simulation_core.models.netcdf_player import MODEL_CONFIG_SCHEMA_PATH, NetCDFPlayer
from movici_simulation_core.testing.helpers import assert_dataset_dicts_equal
from movici_simulation_core.testing.model_tester import ModelTester
from movici_simulation_core.validate import validate_and_process


@pytest.fixture
def netcdf_tape_name():
    return "some_netcdf_tape"


@pytest.fixture
def netcdf_tape(tmp_path: Path, netcdf_tape_name):
    file = (tmp_path / netcdf_tape_name).with_suffix(".nc")
    add_netcdf_data(file, [0, 1, 2], "time", ("time",))
    add_netcdf_data(file, [[0, 1], [10, 11], [20, 21]], "data", ("time", "nElem"))
    return file


def add_netcdf_data(netcdf_file, data, varname, dimensions):
    data = np.asarray(data)
    with netCDF4.Dataset(netcdf_file, mode="r+") as nc:
        for idx, dim in enumerate(dimensions):
            if dim not in nc.dimensions:
                nc.createDimension(dim, data.shape[idx])
        try:
            var = nc.variables[varname]
        except KeyError:
            var = nc.createVariable(varname, datatype=data.dtype, dimensions=dimensions)
        var[...] = data


@pytest.fixture
def dataset_name():
    return "some_dataset"


@pytest.fixture
def some_dataset():
    return {
        "name": "some_dataset",
        "data": {
            "some_entities": {"id": [1, 2]},
        },
    }


@pytest.fixture
def model_config(netcdf_tape_name, dataset_name):
    return {
        "entity_group": [dataset_name, "some_entities"],
        "netcdf_tape": netcdf_tape_name,
        "attributes": [
            {"source": "data", "target": "target"},
        ],
    }


@pytest.fixture
def init_data(netcdf_tape_name, netcdf_tape, dataset_name, some_dataset):

    return [(netcdf_tape_name, netcdf_tape), (dataset_name, some_dataset)]


@pytest.fixture
def tester(create_model_tester, model_config):
    return create_model_tester(
        model_type=NetCDFPlayer, config=model_config, raise_on_premature_shutdown=False
    )


def test_netcdf_player_datamask(tester: ModelTester, dataset_name):
    datamask = tester.initialize()

    def setify(dm):
        for k, v in dm.items():
            if isinstance(v, t.Sequence):
                dm[k] = set(v)
            else:
                setify(v)
        return datamask

    assert setify(datamask) == {
        "pub": {
            dataset_name: {
                "some_entities": {
                    "target",
                }
            },
        },
        "sub": {},
    }


def test_netcdf_player_update_0(tester: ModelTester, dataset_name):
    tester.initialize()
    result, next_time = tester.update(0, data=None)
    assert next_time == 1
    assert_dataset_dicts_equal(
        result,
        {
            dataset_name: {
                "some_entities": {
                    "id": [1, 2],
                    "target": [0, 1],
                }
            }
        },
    )


def test_netcdf_player_update_2(tester: ModelTester, dataset_name):
    tester.initialize()
    tester.update(0, data=None)
    result, next_time = tester.update(2, data=None)
    assert next_time is None
    assert_dataset_dicts_equal(
        result,
        {
            dataset_name: {
                "some_entities": {
                    "id": [1, 2],
                    "target": [20, 21],
                }
            }
        },
    )


def test_model_config_schema(model_config):
    schema = json.loads(MODEL_CONFIG_SCHEMA_PATH.read_text())
    assert validate_and_process(model_config, schema)
