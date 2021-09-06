import logging

from movici_simulation_core.core.plugins import Service
from ...core.simulation import Simulation
from movici_simulation_core.networking.messages import ModelMessage, Message
from movici_simulation_core.networking.stream import Stream
from .context import (
    Context,
    TimelineController,
    ModelCollection,
    ConnectedModel,
)
from .fsm import FSM, FSMDone
from .states import StartInitializingPhase


class Orchestrator(Service):
    """The class that manages the timeline and acts as a broker between models"""

    config: dict
    fsm: FSM[Context, ModelMessage]
    timeline: TimelineController
    logger: logging.Logger
    context: Context
    stream: Stream

    def setup(self, *, config: dict, stream: Stream, logger: logging.Logger, **_):
        self.config = config
        self.logger = logger
        self.stream = stream
        self._setup_timeline()
        self._setup_context()
        self._setup_fsm()

    def _setup_timeline(self):
        timeline_info = self.config["simulation_info"]
        self.timeline = TimelineController(
            start=timeline_info["start_time"], end=timeline_info["duration"]
        )

    def _setup_context(self):
        model_names = [model["name"] for model in self.config.get("models", [])]
        self.context = Context(
            models=ModelCollection(
                **{name: self._get_connected_model(name) for name in model_names}
            ),
            timeline=self.timeline,
            logger=self.logger,
        )

    def _setup_fsm(self):
        self.fsm = FSM(StartInitializingPhase, context=self.context)
        self.stream.set_handler(self.fsm.send)

    def _get_connected_model(self, identifier: str):
        return ConnectedModel(
            name=identifier,
            timeline=self.timeline,
            send=self.make_send(identifier),
            logger=self.logger,
        )

    def make_send(self, identifier: str):
        """create a send function that a can be used to send a message to a specific client
        connected to the ZMQ Router
        """

        def send(message: Message):
            return self.stream.send((identifier, message))

        return send

    def run(self):
        try:
            self.fsm.start()
            self.stream.run()
        except FSMDone:
            pass

    @classmethod
    def install(cls, sim: Simulation):
        sim.register_service("orchestrator", cls, auto_use=True)
