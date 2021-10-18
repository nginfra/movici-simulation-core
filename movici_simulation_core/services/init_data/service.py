import logging
import typing as t
from functools import singledispatchmethod
from pathlib import Path

from movici_simulation_core.core import Service
from movici_simulation_core.networking.messages import (
    ModelMessage,
    ErrorMessage,
    GetDataMessage,
    PathMessage,
)
from movici_simulation_core.networking.stream import Stream, MessageRouterSocket
from movici_simulation_core.simulation import Simulation
from movici_simulation_core.utils.settings import Settings


class InitDataService(Service):
    stream: Stream[ModelMessage]
    socket: MessageRouterSocket
    logger: logging.Logger
    root: Path

    def __init__(self):
        self.store: t.Dict[str, dict] = {}

    @classmethod
    def install(cls, sim: Simulation):
        sim.register_service("init_data", cls, auto_use=True)

    def setup(self, *, stream: Stream, logger: logging.Logger, settings: Settings, **_):
        self.stream = stream
        self.stream.set_handler(self.handle_request)
        self.logger = logger
        self.root = settings.data_dir

    def run(self):
        self.stream.run()

    def handle_request(self, req: ModelMessage):
        ident, msg = req
        try:
            resp = self.handle_message(msg)
        except Exception as e:
            self.logger.error(f'Error when handling message "{msg}": {type(e).__name__}({str(e)})')
            resp = ErrorMessage()
        self.stream.send((ident, resp))

    @singledispatchmethod
    def handle_message(self, _):
        return ErrorMessage()

    @handle_message.register
    def get(self, msg: GetDataMessage):
        if msg.mask is not None:
            self.logger.warning("Ignoring data mask")
        try:
            path = next(
                file for file in self.root.glob(msg.key + ".*") if file.is_file()
            ).resolve()
        except StopIteration:
            path = None

        return PathMessage(path)
