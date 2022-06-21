import json
from unittest.mock import call

import pytest

from movici_simulation_core.core.moment import TimelineInfo, set_timeline_info
from movici_simulation_core.messages import UpdateMessage
from movici_simulation_core.testing.dummy import DummyModel
from movici_simulation_core.testing.model_tester import (
    DEFAULT_PREPROCESSORS,
    ModelTester,
    compare_results,
)


class TranparentProxy:
    def __init__(self, inner, *_, **__):
        self.inner = inner

    def __getattr__(self, item):
        return getattr(self.inner, item)


@pytest.fixture(autouse=True)
def register_preprocessor():
    DEFAULT_PREPROCESSORS[TranparentProxy] = TranparentProxy
    yield
    del DEFAULT_PREPROCESSORS[TranparentProxy]


class TestModelTester:
    @pytest.fixture
    def model(self):
        class FakeModel(DummyModel):
            def get_adapter(self):
                return TranparentProxy

            def process_input(self, input_data):
                return input_data

            def process_result(self, result):
                return result

        return FakeModel({})

    @pytest.fixture
    def temp_dir(self, tmp_path_factory):
        return tmp_path_factory.mktemp("model_tester")

    @pytest.fixture
    def tester(self, model, temp_dir):
        with set_timeline_info(TimelineInfo(0, 1, 0)):
            yield ModelTester(model, tmp_dir=temp_dir)

    @pytest.fixture
    def dict_init_data(self):
        return {"data": {"some_entities": {"id": [1, 2, 3]}}}

    @pytest.fixture
    def file_init_data(self, tmp_path):
        file = tmp_path / "some_file.bin"
        file.write_bytes(b"some_data")
        return file

    def test_add_dict_init_data(self, tester, temp_dir, dict_init_data):
        tester.add_init_data("some_dataset", dict_init_data)
        assert json.loads((temp_dir / "some_dataset.json").read_text()) == dict_init_data

    def test_add_file_init_data(self, tester, temp_dir, file_init_data):
        tester.add_init_data("some_dataset", file_init_data)
        assert (temp_dir / "some_dataset.bin").read_bytes() == b"some_data"

    def test_is_initialized_with_init_data_handler(self, tmp_path, dict_init_data):
        class Model(DummyModel):
            def setup(self, init_data_handler, **__):
                assert (
                    json.loads(init_data_handler.get("dataset")[1].read_text()) == dict_init_data
                )

        tester = ModelTester(Model({}), tmp_dir=tmp_path)
        tester.add_init_data("dataset", dict_init_data)
        tester.initialize()

    def test_updates_model(self, tester, model):
        tester.update(0, None)
        assert model.update.call_args == call(UpdateMessage(0), None)


@pytest.mark.parametrize("item", [None, {"some": "result"}])
def test_compare_results_no_errors(item):
    errors = compare_results([(0, item, None)], [(0, item, None)])
    assert not errors


@pytest.mark.parametrize(
    "expected, result, error",
    [
        (
            [(0, None, None)],
            [(0, "some_result", None)],
            {"result": "Expected None, got: some_result"},
        ),
        ([(0, None, None)], [(1, None, None)], {"timestamp": "timestamp differs: 1"}),
        ([(0, {}, None)], [(0, {"some": "result"}, None)], {"": "extra keys: {'some'}"}),
    ],
)
def test_compare_result_errors(expected, result, error):
    if isinstance(error, dict):
        error = [(0, error)]

    errors = compare_results(expected, result)
    assert errors == error
