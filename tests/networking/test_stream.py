from unittest.mock import MagicMock, Mock, call

import pytest
import zmq

from movici_simulation_core.exceptions import InvalidMessage
from movici_simulation_core.messages import AcknowledgeMessage, Message, QuitMessage, dump_message
from movici_simulation_core.networking.stream import (
    MessageDealerSocket,
    MessageReqSocket,
    MessageRouterSocket,
    Stream,
    get_message_socket,
)


@pytest.fixture
def socket():
    class FakeSocket(MagicMock):
        def set_messages(self, *messages):
            self.recv_multipart.side_effect = messages + (RuntimeError,)

    return FakeSocket(zmq.Socket)


@pytest.fixture
def model():
    return "some_model"


@pytest.fixture
def set_messages(model, socket, serialize_message):
    def _create(messages: list[Message]):
        serialized = [serialize_message(message) for message in messages]
        socket.set_messages(*serialized)

    return _create


@pytest.fixture
def req_socket_adapter(socket):
    return MessageReqSocket(socket)


@pytest.fixture
def serialize_message():
    def _serialize(message):
        return dump_message(message)

    return _serialize


def run_stream(stream):
    try:
        stream.run()
    except RuntimeError:
        pass


class TestRouterSocket:
    @pytest.fixture
    def model(self):
        return "some_model"

    @pytest.fixture
    def serialize_message(self, model):
        def _serialize(message):
            return [model.encode(), b"", *dump_message(message)]

        return _serialize

    @pytest.fixture
    def socket_adapter(self, socket):
        return MessageRouterSocket(socket)

    def test_send(self, socket_adapter, model):
        socket_adapter.send((model, AcknowledgeMessage()))
        assert socket_adapter.socket.send_multipart.call_args == call(
            [b"some_model", b"", b"ACK", b"{}"]
        )

    def test_receive(self, model, set_messages, socket_adapter):
        set_messages([AcknowledgeMessage()])
        assert socket_adapter.recv() == (model, AcknowledgeMessage())

    def test_invalid_message(self, socket_adapter):
        socket_adapter.socket.set_messages([b"some_model", b"", b"invalid"])
        with pytest.raises(InvalidMessage):
            socket_adapter.recv()

    def test_make_send(self, socket_adapter):
        send = socket_adapter.make_send("model")
        send(AcknowledgeMessage())
        assert socket_adapter.socket.send_multipart.call_args == call(
            [b"model", b"", b"ACK", b"{}"]
        )


class TestDealerSocket:
    @pytest.fixture
    def serialize_message(self):
        def _serialize(message: Message):
            return [b"", *dump_message(message)]

        return _serialize

    @pytest.fixture
    def socket_adapter(self, socket):
        return MessageDealerSocket(socket)

    def test_receive_on_dealer_socket_adapter(self, set_messages, socket_adapter):
        set_messages([AcknowledgeMessage()])
        assert socket_adapter.recv() == AcknowledgeMessage()

    def test_send_to_socket_adapter(self, socket, socket_adapter):
        socket_adapter.send(AcknowledgeMessage())
        assert socket.send_multipart.call_args == call([b"", b"ACK", b"{}"])


class TestReqSocket:
    @pytest.fixture
    def serialize_message(self):
        def _serialize(message):
            return [*dump_message(message)]

        return _serialize

    @pytest.fixture
    def socket_adapter(self, socket):
        return MessageReqSocket(socket)

    def test_receive_on_req_socket_adapter(self, set_messages, socket_adapter):
        set_messages([AcknowledgeMessage()])
        assert socket_adapter.recv() == AcknowledgeMessage()

    def test_send_to_req_socket_adapter(self, socket, socket_adapter):
        socket_adapter.send(AcknowledgeMessage())
        assert socket.send_multipart.call_args == call([b"ACK", b"{}"])


def test_stream(model, req_socket_adapter, set_messages):
    set_messages([AcknowledgeMessage(), QuitMessage()])
    stream = Stream(req_socket_adapter)
    handler = Mock()
    stream.set_handler(handler)
    run_stream(stream)
    assert handler.call_args_list == [
        call(AcknowledgeMessage()),
        call(QuitMessage()),
    ]


def test_stream_logs_on_invalid_message(model, req_socket_adapter, set_messages):
    req_socket_adapter.socket.set_messages([b"invalid"])
    logger = Mock()
    stream = Stream(req_socket_adapter, logger)
    run_stream(stream)
    assert logger.warning.call_args == call("Invalid message '[b'invalid']'")


@pytest.mark.parametrize(
    "socket_type, cls",
    [
        (zmq.REQ, MessageReqSocket),
        (zmq.ROUTER, MessageRouterSocket),
        (zmq.DEALER, MessageDealerSocket),
    ],
)
def test_get_message_socket(socket_type, cls):
    socket = get_message_socket(socket_type)
    assert type(socket) is cls
    assert socket.socket.type == socket_type


def test_get_message_socket_identity():
    socket = get_message_socket(zmq.REQ, ident=b"some_ident")
    assert socket.socket.get(zmq.IDENTITY) == b"some_ident"


def test_context_manager(req_socket_adapter, socket):
    with req_socket_adapter:
        pass
    assert socket.__exit__.call_count == 1


@pytest.mark.parametrize("method", ["connect", "bind"])
def test_proxy_methods(req_socket_adapter, socket, method):
    payload = object()
    getattr(req_socket_adapter, method)(payload)
    assert getattr(socket, method).call_args == call(payload)
