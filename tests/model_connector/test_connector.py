from pathlib import Path
from unittest.mock import Mock, call

import pytest

from movici_simulation_core.core.types import ModelAdapterBase
from movici_simulation_core.exceptions import InvalidMessage, StreamDone
from movici_simulation_core.messages import (
    AcknowledgeMessage,
    ClearDataMessage,
    DataMessage,
    ErrorMessage,
    GetDataMessage,
    NewTimeMessage,
    PutDataMessage,
    QuitMessage,
    RegistrationMessage,
    ResultMessage,
    UpdateMessage,
    UpdateSeriesMessage,
)
from movici_simulation_core.model_connector.connector import (
    ConnectorStreamHandler,
    ModelConnector,
    UpdateDataClient,
)
from movici_simulation_core.model_connector.init_data import (
    DirectoryInitDataHandler,
    FileType,
    InitDataHandler,
)
from movici_simulation_core.networking.client import Sockets


@pytest.fixture
def stream():
    class FakeStream:
        def __init__(self):
            self.send = Mock()
            self.handler = None

        def set_handler(self, func):
            self.handler = func

        def invoke_handler(self, payload):
            if self.handler is not None:
                self.handler(payload)

    return FakeStream()


class TestConnectorStreamHandler:
    @pytest.fixture
    def connector(self):
        mock = Mock(ModelConnector)
        mock.initialize.return_value = RegistrationMessage({}, {})
        return mock

    @pytest.fixture
    def stream_handler(self, connector, stream):
        return ConnectorStreamHandler(connector, stream)

    def test_calls_initialize_on_initialize(self, stream_handler):
        stream_handler.initialize()
        assert stream_handler.connector.initialize.call_count == 1

    def test_sends_registration_on_initialize(self, stream_handler, connector, stream):
        stream_handler.initialize()
        assert stream.send.call_args == call(RegistrationMessage({}, {}))

    @pytest.mark.parametrize(
        "msg, method",
        [
            (NewTimeMessage(0), "new_time"),
            (UpdateMessage(0), "update"),
            (UpdateSeriesMessage(updates=[]), "update_series"),
        ],
    )
    def test_handle_message_dispatches_to_method(self, stream_handler, connector, msg, method):
        stream_handler.handle_message(msg)
        assert getattr(connector, method).call_args == call(msg)

    def test_handle_quit_message_calls_close(self, stream_handler, connector):
        with pytest.raises(StreamDone):
            stream_handler.handle_message(QuitMessage())
        assert connector.close.call_count == 1

    @pytest.mark.usefixtures("stream_handler")
    def test_sets_handler(self, connector, stream):
        message = NewTimeMessage(0)
        stream.invoke_handler(message)
        assert connector.new_time.call_args == call(message)


class TestModelConnector:
    @pytest.fixture
    def data_mask(self):
        return {"pub": {"pub": None}, "sub": {"sub": None}}

    @pytest.fixture
    def model(self, data_mask):
        mock = Mock(ModelAdapterBase)
        mock.initialize.return_value = data_mask
        mock.update.return_value = (b"some_data", None)
        return mock

    @pytest.fixture
    def update_data(self):
        return b"update_data"

    @pytest.fixture
    def update_handler(self, update_data):
        mock = Mock(UpdateDataClient)
        mock.put.return_value = ("address", "key")
        mock.get.return_value = update_data
        return mock

    @pytest.fixture
    def init_data_handler(self):
        return Mock(InitDataHandler)

    @pytest.fixture
    def connector(self, model, update_handler, init_data_handler):
        return ModelConnector(model, updates=update_handler, init_data=init_data_handler)

    @pytest.fixture
    def initialized_connector(self, connector):
        connector.initialize()
        return connector

    @pytest.fixture
    def update_series_message(self):
        return UpdateSeriesMessage(
            [UpdateMessage(1, None, None), UpdateMessage(1, "a_key", "an_address")]
        )

    def test_initialize_calls_model_with_handler(self, connector, model, init_data_handler):
        connector.initialize()
        assert model.initialize.call_args == call(init_data_handler)

    def test_initialize_returns_registration_message(self, connector, model, data_mask):
        msg = connector.initialize()
        assert msg == RegistrationMessage(**data_mask)

    def test_new_time_calls_model_with_new_time(self, connector, model):
        connector.new_time(NewTimeMessage(42))
        assert model.new_time.call_args == call(NewTimeMessage(42))

    def test_update_calls_model_with_timestamp(self, initialized_connector, model, update_data):
        msg = UpdateMessage(42, key=None, address=None)
        initialized_connector.update(msg)
        assert model.update.call_args == call(msg, data=None)

    def test_update_doesnt_get_data_on_empty_update(self, initialized_connector, update_handler):
        initialized_connector.update(UpdateMessage(42, key=None, address=None))
        assert update_handler.get.call_count == 0

    def test_update_gets_update_data_when_update_has_data(
        self, initialized_connector, update_handler, data_mask
    ):
        initialized_connector.update(UpdateMessage(1, key="key_a", address="address_a"))
        assert update_handler.get.call_args == call(
            key="key_a", address="address_a", mask=data_mask["sub"]
        )

    def test_update_sends_update_data_to_handler(self, initialized_connector, update_handler):
        initialized_connector.update(UpdateMessage(1))
        assert update_handler.put.call_args == call(b"some_data")

    def test_update_series_timestamp_matches(
        self, initialized_connector, model, update_series_message
    ):
        model.update_series.return_value = (None, None)
        initialized_connector.update_series(update_series_message)
        assert model.update_series.call_args[0][0].timestamp == 1

    def test_update_series_supplies_update_data(
        self, initialized_connector, model, update_series_message, update_handler, data_mask
    ):
        def update_series(timestamp, data):
            list(data)
            return b"some_data", 1

        model.update_series.side_effect = update_series
        initialized_connector.update_series(update_series_message)
        assert update_handler.get.call_args == call(
            address="an_address", key="a_key", mask=data_mask["sub"]
        )

    def test_update_series_processes_result(self, initialized_connector, model):
        model.update_series.return_value = b"some_data", 12
        result = initialized_connector.update_series(UpdateSeriesMessage([]))
        assert result == ResultMessage(key="key", address="address", next_time=12)

    @pytest.mark.parametrize("origin", ["origin", None])
    def test_sends_origin(self, origin, initialized_connector, model):
        initialized_connector.name = origin
        result = initialized_connector.update(UpdateMessage(1))
        assert result == ResultMessage(key="key", address="address", origin=origin)

    def test_closes_model(self, initialized_connector, model):
        initialized_connector.close(object())
        assert model.close.call_count == 1


class TestUpdateHandler:
    @pytest.fixture
    def name(self):
        return "some_model"

    @pytest.fixture
    def home_address(self):
        return "tcp://1.2.3.4:5"

    @pytest.fixture
    def update_data(self):
        return b"some_data"

    @pytest.fixture
    def socket(self, update_data):
        mock = Mock()
        mock.recv.return_value = AcknowledgeMessage()
        return mock

    @pytest.fixture
    def socket_factory(self, socket):
        def get_socket(*_, **__):
            return socket

        return get_socket

    @pytest.fixture
    def update_handler(self, name, home_address, socket_factory):
        sockets = Sockets(socket_factory)
        return UpdateDataClient(name, home_address, sockets=sockets)

    def test_get_data_calls_right_address(self, update_handler, socket):
        socket.recv.return_value = DataMessage(b"data")
        update_handler.get("address", "key", None)
        assert socket.connect.call_args == call("address")

    def test_get_data_requests_for_key_with_mask(self, update_handler, socket):
        socket.recv.return_value = DataMessage(b"data")

        update_handler.get("address", "key", mask={"some": "mask"})
        assert socket.send.call_args == call(GetDataMessage("key", {"some": "mask"}))

    def test_get_data_return_data(self, update_handler, socket):
        socket.recv.return_value = DataMessage(b"data")

        result = update_handler.get("address", "key", None)
        assert result == b"data"

    @pytest.mark.parametrize(
        "message, error_type",
        [
            (ErrorMessage(), ValueError),
            (QuitMessage(), InvalidMessage),
        ],
    )
    def test_get_data_raises_on_invalid_response(
        self, update_handler, socket, message, error_type
    ):
        socket.recv.return_value = message
        with pytest.raises(error_type):
            update_handler.get("address", "key", None)

    def test_put_sends_data_to_home_address(self, home_address, update_handler, socket, name):
        update_handler.put(b"some_data")
        assert socket.connect.call_args == call(home_address)
        assert socket.send.call_args == call(PutDataMessage(key=f"{name}_0", data=b"some_data"))

    def test_put_returns_address_and_key(self, update_handler, home_address, name):
        resp = update_handler.put(b"some_data")
        assert resp == (home_address, f"{name}_0")

    def test_put_returns_consecutive_keys(self, update_handler, name):
        _, key1 = update_handler.put(b"some_data")
        _, key2 = update_handler.put(b"some_data")
        assert (key1, key2) == (f"{name}_0", f"{name}_1")

    def test_clear_sends_clear_message(self, update_handler, socket, name):
        update_handler.clear()
        assert socket.send.call_args == call(ClearDataMessage(name))

    def test_clear_resets_counter(self, update_handler, socket, name):
        _, key = update_handler.put(b"some_data")
        assert key == f"{name}_0"

        update_handler.clear()

        _, key = update_handler.put(b"some_data")
        assert key == f"{name}_0"


@pytest.mark.parametrize(
    "extension, dstype",
    [
        (".csv", FileType.CSV),
        (".CSV", FileType.CSV),
        (".json", FileType.JSON),
        (".msgpack", FileType.MSGPACK),
        (".nc", FileType.NETCDF),
        (".png", FileType.OTHER),
    ],
)
def test_data_type(extension, dstype):
    assert FileType.from_extension(extension) == dstype


class TestInitDataHandler:
    @pytest.fixture
    def default_data(self):
        return "123"

    @pytest.fixture
    def add_file(self, tmp_path, default_data):
        def _create_dummy_file(path: Path, data=default_data):
            full_path = (tmp_path / path).resolve()
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(data)

        return _create_dummy_file

    @pytest.fixture
    def handler(self, tmp_path):
        return DirectoryInitDataHandler(tmp_path)

    @pytest.mark.parametrize(
        "name, filename, data_type",
        [
            ("some_name", "some_name.json", FileType.JSON),
            ("some_name", "some_name.csv", FileType.CSV),
            ("some_name", "path/to/some_name.csv", FileType.CSV),
        ],
    )
    def test_get_init_data(self, handler, add_file, name, filename, data_type):
        data = "some_data"
        add_file(Path(filename), data)
        dstype, path = handler.get(name)
        assert dstype == data_type
        assert path.read_text() == data
