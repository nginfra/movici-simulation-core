import logging
from unittest.mock import Mock, call

import pytest

from movici_simulation_core.data_tracker.data_format import dump_update, load_update
from movici_simulation_core.networking.messages import (
    PutDataMessage,
    GetDataMessage,
    AcknowledgeMessage,
    DataMessage,
    ClearDataMessage,
    ErrorMessage,
)
from movici_simulation_core.networking.stream import Stream
from movici_simulation_core.services.update_data import UpdateDataService

DEFAULT_KEY = "default_key"
DEFAULT_PAYLOAD = {"some": "payload", "other": "other_payload"}
DEFAULT_RAW_PAYLOAD = dump_update(DEFAULT_PAYLOAD)


@pytest.fixture
def stream():
    return Mock(Stream)


@pytest.fixture
def logger():
    return Mock(logging.Logger)


@pytest.fixture
def default_key():
    return DEFAULT_KEY


@pytest.fixture
def payload():
    return DEFAULT_PAYLOAD


@pytest.fixture
def raw_payload():
    return DEFAULT_RAW_PAYLOAD


@pytest.fixture
def data_service(stream, default_key, payload, logger):
    service = UpdateDataService()
    service.setup(stream=stream, logger=logger)
    service.store[default_key] = payload
    return service


def extract_data(message: DataMessage):
    return load_update(message.data)


def test_install():
    simulation = Mock()
    UpdateDataService.install(simulation)
    assert simulation.register_service.call_args == call(
        "update_data", UpdateDataService, auto_use=True
    )


def test_setup_registers_handler(stream, data_service):
    assert stream.set_handler.call_count == 1


def test_run_starts_stream(stream, data_service):
    data_service.run()
    assert stream.run.call_count == 1


def test_get(data_service, default_key, raw_payload, payload):
    get = GetDataMessage(default_key)
    resp = data_service.handle_message(get)
    assert extract_data(resp) == payload


def test_get_with_mask(data_service, default_key):
    get = GetDataMessage(default_key, mask={"some": None})
    resp = data_service.handle_message(get)
    assert extract_data(resp) == {"some": "payload"}


def test_put(data_service, raw_payload, payload):
    put = PutDataMessage("some_key", raw_payload)
    data_service.handle_message(put)
    assert data_service.store["some_key"] == payload


def test_clear(data_service, default_key, payload):
    data_service.store["other_1"] = {"some": "data"}
    data_service.store["other_2"] = {"some": "data"}
    clear = ClearDataMessage("other")
    data_service.handle_message(clear)
    assert data_service.store == {default_key: payload}


@pytest.mark.parametrize(
    "req,expected",
    [
        (GetDataMessage(key=DEFAULT_KEY), DataMessage(DEFAULT_RAW_PAYLOAD)),
        (GetDataMessage(key="invalid"), ErrorMessage("Key not found")),
        (GetDataMessage(key=DEFAULT_KEY, mask="invalid"), ErrorMessage("Invalid mask")),
        (PutDataMessage(key=DEFAULT_KEY, data=DEFAULT_RAW_PAYLOAD), AcknowledgeMessage()),
        (PutDataMessage(key=DEFAULT_KEY, data=b"invalid"), ErrorMessage("Invalid data")),
        (
            PutDataMessage(key=DEFAULT_KEY, data=dump_update(b"invalid")),
            ErrorMessage("Invalid data"),
        ),
        (ClearDataMessage(prefix=DEFAULT_KEY), AcknowledgeMessage()),
        (AcknowledgeMessage(), ErrorMessage()),
    ],
)
def test_handle_request(data_service, stream, req, expected):
    request = ("model", req)
    data_service.handle_request(request)
    assert stream.send.call_args == call(("model", expected))


def test_handle_request_exception(data_service, stream, default_key, logger):
    data_service.handle_message = Mock(side_effect=ValueError("errormessage"))
    message = GetDataMessage(default_key)
    data_service.handle_request(("model", message))
    assert stream.send.call_args == call(("model", ErrorMessage()))
    assert logger.error.call_args == call(
        f'Error when handling message "{message}": ValueError(errormessage)'
    )
