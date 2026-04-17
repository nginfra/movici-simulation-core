from unittest.mock import Mock, call

import pytest

from movici_simulation_core.base_models.simple_model import SimpleModel, SimpleModelAdapter
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.messages import NewTimeMessage, UpdateMessage, UpdateSeriesMessage


class TestSimpleModelAdapter:
    @pytest.fixture
    def model(self):
        return Mock(SimpleModel)

    @pytest.fixture
    def schema(self):
        return AttributeSchema()

    @pytest.fixture
    def adapter(self, model, schema, settings):
        adapter = SimpleModelAdapter(model, settings, Mock())
        adapter.set_schema(schema)
        adapter.process_result = Mock(wraps=lambda x: x)
        adapter.process_input = Mock(wraps=lambda x: x)

        return adapter

    def test_initialize(self, adapter, model):
        adapter.initialize(object())
        assert model.initialize.call_count == 1

    def test_new_time(self, adapter, model):
        message = NewTimeMessage(12)
        adapter.new_time(message)
        assert model.new_time.call_args == call(new_time=message.timestamp, message=message)

    def test_update(self, adapter, model):
        message = UpdateMessage(12)
        data = b"data"
        sentinel = object()
        model.update.return_value = sentinel
        result = adapter.update(message, data)
        assert model.update.call_args == call(
            moment=Moment(message.timestamp), data=data, message=message
        )
        assert adapter.process_result.call_count == 1
        assert adapter.process_input.call_args == call(data)
        assert result == sentinel

    def test_update_series(self, adapter, model):
        message = UpdateSeriesMessage([UpdateMessage(12)])
        data = (b"data",)
        sentinel = object()
        model.update_series.return_value = sentinel
        result = adapter.update_series(message, data)
        assert result == sentinel


class TestSimpleModel:
    @pytest.fixture
    def model(self):
        class Implementation(SimpleModel):
            update = Mock(return_value=(None, 3))

        return Implementation({})

    def test_update_series(self, model):
        message = UpdateSeriesMessage([UpdateMessage(1), UpdateMessage(1)])
        rv = model.update_series(Moment(1), data=(None, None), message=message)
        assert model.update.call_count == 2
        assert rv == (None, 3)
