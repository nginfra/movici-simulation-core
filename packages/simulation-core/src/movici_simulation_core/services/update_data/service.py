import logging
import typing as t
from functools import singledispatchmethod

from movici_simulation_core.core.types import Service
from movici_simulation_core.messages import (
    AcknowledgeMessage,
    ClearDataMessage,
    DataMessage,
    ErrorMessage,
    GetDataMessage,
    ModelMessage,
    PutDataMessage,
)
from movici_simulation_core.networking.stream import MessageRouterSocket, Stream
from movici_simulation_core.simulation import Simulation
from movici_simulation_core.types import InternalSerializationStrategy
from movici_simulation_core.utils import strategies
from movici_simulation_core.utils.data_mask import filter_data, validate_mask


class UpdateDataService(Service):
    stream: Stream[ModelMessage]
    socket: MessageRouterSocket
    logger: logging.Logger

    def __init__(self):
        self.store: t.Dict[str, dict] = {}
        self.serialization = strategies.get_instance(InternalSerializationStrategy)

    @classmethod
    def install(cls, sim: Simulation):
        sim.register_service("update_data", cls, auto_use=True)

    def setup(self, *, stream: Stream, logger: logging.Logger, **_):
        self.stream = stream
        self.stream.set_handler(self.handle_request)
        self.logger = logger

    def run(self):
        self.stream.run()

    def handle_request(self, req: ModelMessage):
        ident, msg = req
        try:
            resp = self.handle_message(msg)
        except Exception as e:
            self.logger.error(f'Error when handling message "{msg}": {type(e).__name__}({str(e)})')
            resp = ErrorMessage()
        if resp is None:
            resp = AcknowledgeMessage()
        self.stream.send((ident, resp))

    @singledispatchmethod
    def handle_message(self, _):
        return ErrorMessage()

    @handle_message.register
    def get(self, msg: GetDataMessage):
        if not validate_mask(msg.mask):
            return ErrorMessage("Invalid mask")
        if msg.key not in self.store:
            return ErrorMessage("Key not found")
        filtered = filter_data(self.store[msg.key], msg.mask)
        raw_data = self.serialization.dumps(filtered)
        return DataMessage(raw_data)

    @handle_message.register
    def put(self, msg: PutDataMessage):
        try:
            data = self.serialization.loads(msg.data)
            if not isinstance(data, dict):
                raise ValueError()
        except ValueError:
            return ErrorMessage("Invalid data")

        self.store[msg.key] = data

    @handle_message.register
    def clear(self, msg: ClearDataMessage):
        # Copy the list of keys to be able to delete keys while iterating
        for key in list(self.store.keys()):
            if key.startswith(msg.prefix):
                del self.store[key]
