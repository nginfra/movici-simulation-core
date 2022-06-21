import logging

from movici_simulation_core.core.types import Service
from movici_simulation_core.messages import Message, ModelMessage
from movici_simulation_core.networking.stream import Stream
from movici_simulation_core.services.orchestrator.context import ConnectedModel, ModelCollection
from movici_simulation_core.settings import Settings
from movici_simulation_core.simulation import Simulation

from .context import Context, TimelineController
from .fsm import FSM, FSMDone
from .states import StartInitializingPhase


class Orchestrator(Service):
    """The class that manages the timeline and acts as a broker between models"""

    settings: Settings
    fsm: FSM[Context, ModelMessage]
    timeline: TimelineController
    logger: logging.Logger
    context: Context
    stream: Stream

    def setup(self, *, settings: Settings, stream: Stream, logger: logging.Logger, **_):
        self.settings = settings
        self.logger = logger
        self.stream = stream
        self._setup_timeline()
        self._setup_context()
        self._setup_fsm()

    def _setup_timeline(self):
        timeline_info = self.settings.timeline_info
        self.timeline = TimelineController(
            start=timeline_info.start_time, end=timeline_info.end_time
        )

    def _setup_context(self):
        model_names = self.settings.model_names
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
            if self.context.failed:
                return 1
            return 0

    @classmethod
    def install(cls, sim: Simulation):
        sim.register_service("orchestrator", cls, auto_use=True, daemon=False)
