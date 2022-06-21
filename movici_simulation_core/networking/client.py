import typing as t

import zmq

from movici_simulation_core.exceptions import InvalidMessage
from movici_simulation_core.messages import ErrorMessage, Message
from movici_simulation_core.networking.stream import get_message_socket


class Sockets:
    def __init__(self, socket_factory=get_message_socket):
        self.cache = {}
        self.get_message_socket = socket_factory

    def get(self, name: str, address: str):
        try:
            return self.cache[(name, address)]
        except KeyError:
            socket = self.get_message_socket(zmq.REQ, ident=name.encode())
            socket.connect(address)
            self.cache[(name, address)] = socket
            return socket

    def close(self, linger=-1):
        for socket in self.cache.values():
            socket.close(linger)


class RequestClient:
    def __init__(self, name: str, sockets: Sockets = None):
        self.name = name
        self.sockets = sockets or Sockets()

    def request(
        self,
        address,
        msg,
        *,
        valid_responses: t.Union[t.Type[Message], t.Tuple[t.Type[Message], ...], None] = None,
    ):
        socket = self.sockets.get(self.name, address)
        socket.send(msg)
        resp = socket.recv()
        self.raise_on_invalid_message(resp, valid_responses)
        return resp

    @staticmethod
    def raise_on_invalid_message(
        message,
        valid_messages: t.Optional[t.Union[t.Type[Message], t.Tuple[t.Type[Message], ...]]] = None,
    ):
        if isinstance(message, ErrorMessage):
            raise ValueError(message.error)
        if valid_messages is not None and not isinstance(message, valid_messages):
            raise InvalidMessage(message)

    def close(self):
        self.sockets.close()
