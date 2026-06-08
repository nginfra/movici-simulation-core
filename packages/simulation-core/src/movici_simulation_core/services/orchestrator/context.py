from __future__ import annotations

import logging
import typing as t
from abc import ABC
from dataclasses import dataclass, field
from functools import singledispatchmethod
from itertools import product

from movici_simulation_core.exceptions import InvalidCommand
from movici_simulation_core.messages import (
    AcknowledgeMessage,
    ErrorMessage,
    Message,
    NewTimeMessage,
    QuitMessage,
    RegistrationMessage,
    ResultMessage,
    UpdateMessage,
    UpdateSeriesMessage,
)
from movici_simulation_core.utils.data_mask import masks_overlap

from .fsm import FSM, Always, Condition, FSMConfig, State
from .interconnectivity import Publisher, format_matrix
from .stopwatch import ReportingStopwatch, Stopwatch


@dataclass
class Context:
    models: ModelCollection
    timeline: TimelineController
    global_timer: Stopwatch = field(default=None)
    phase_timer: Stopwatch = field(default=None)
    logger: logging.Logger = field(default_factory=logging.getLogger)
    orchestrator_failed: bool = False

    def __post_init__(self):
        self.global_timer = self.global_timer or ReportingStopwatch(
            on_reset=self.log_elapsed_global_time
        )
        self.phase_timer = self.phase_timer or ReportingStopwatch(
            on_reset=self.log_elapsed_phase_time
        )

    @property
    def failed(self):
        return self.orchestrator_failed or self.models.failed

    def log_new_phase(self, phase: str):
        self.logger.info(f"Entering {phase}")

    def queue_models_for_next_time(self):
        next_time = self.models.next_time
        if next_time is None:
            raise RuntimeError(
                "Cannot progress to next time when all models are done,"
                " should finalize simulation instead"
            )

        if next_time != self.timeline.current_time:
            self.timeline.current_time = next_time
            self.recv_for_all(NewTimeMessage(next_time))

        for model in self.models.values():
            if model.next_time == next_time:
                self.recv_message(model, UpdateMessage(timestamp=next_time))

    def recv_for_all(self, message: Message):
        """Receive a Message for all models"""
        for model in self.models.values():
            self.recv_message(model, message)

    def recv_message(self, model: ConnectedModel, message: Message):
        try:
            model.recv_event(message)
        except InvalidCommand:
            self.logger.exception("Error while sending command")
            self.orchestrator_failed = True

    def log_new_time(self):
        if self.models.next_time != self.timeline.current_time:
            self.logger.info(f"New time: {self.models.next_time}")

    def log_elapsed_phase_time(self, seconds: float):
        self.logger.info(f"Phase finished in {seconds:.1f} seconds")

    def log_elapsed_global_time(self, seconds: float):
        self.logger.info(f"Total elapsed time: {seconds:.1f}")

    def log_interconnectivity_matrix(self):
        self.logger.info(
            "Model interconnectivity matrix:\n"
            + format_matrix(t.cast(list[Publisher], list(self.models.values())))
        )

    def finalize(self):
        self.phase_timer.reset()
        self.global_timer.reset()
        self.models.reset_model_timers()
        self.log_finalize_message()

    def log_finalize_message(self):
        if len(self.failed) == 0:
            self.logger.info("Simulation successfully finished")
        elif len(self.failed) == 1:
            self.logger.error(
                f"Simulation unexpectedly ended due to a failure of model '{self.failed[0]}'"
            )
        else:
            self.logger.error(
                "Simulation unexpectedly ended due to a failure of models "
                + ", ".join(f"'{model}'" for model in self.failed)
            )


@dataclass
class TimelineController:
    start: int
    end: int
    current_time: int | None = None

    def set_model_to_start(self, model: ConnectedModel):
        model.next_time = self.start

    def set_next_time(self, model: ConnectedModel, next_time: t.Optional[int] = None):
        model.next_time = self._get_validated_next_time(next_time)

    def _get_validated_next_time(self, next_time: t.Optional[int]):
        current_time = self.current_time if self.current_time is not None else self.start
        if (
            next_time is None
            or next_time < current_time
            or (current_time == self.end and next_time > self.end)
        ):
            return None

        return min(next_time, self.end)


class NoUpdateMessage(Message):
    """A NoUpdateMessage is sent to a subscribed (dependent) ConnectedModel to indicate that it's
    dependency has finished calculating (but not produced any data) so that the subscribed
    ConnectedModel can determine whether to send out any pending updates
    """

    pass


Command = t.Union[NewTimeMessage, UpdateMessage, NoUpdateMessage, UpdateSeriesMessage, QuitMessage]
Response = t.Union[RegistrationMessage, AcknowledgeMessage, ResultMessage, ErrorMessage]


@dataclass
class ConnectedModel:
    """Holds connection state and other data concerning a (connected) model"""

    name: str
    timeline: TimelineController
    send: t.Callable[[Message], None]

    logger: logging.Logger = field(default_factory=logging.getLogger)
    publishes_to: list[ConnectedModel] = field(default_factory=list)
    subscribed_to: list[ConnectedModel] = field(default_factory=list)
    timer: Stopwatch = field(init=False)
    pub: dict | None = field(default_factory=dict)
    sub: dict | None = field(default_factory=dict)

    busy: bool = field(default=False, init=False)
    next_time: t.Optional[int] = field(default=None, init=False)
    failed: bool = field(default=False, init=False)

    pending_new_time: NewTimeMessage | None = field(default=None, init=False)
    pending_updates: t.List[UpdateMessage] = field(default_factory=list, init=False)
    pending_quit: QuitMessage | None = field(default=None, init=False)

    fsm_config: FSMConfig | None = None
    fsm: FSM[ConnectedModel, Message] = field(init=False)

    def __post_init__(self):
        self.timer = ReportingStopwatch(
            on_stop=lambda s: self.logger.debug(
                f"Model '{self.name}' returned in {s:.1f} seconds "
            ),
            on_reset=lambda s: self.logger.info(
                f"Total time spent in in model '{self.name}': {s:.1f} seconds "
            ),
        )
        self.fsm = FSM(self.fsm_config or MODEL_FSM_CONFIG, self, raise_on_done=False)

    def start(self):
        self.fsm.start()

    def recv_event(self, event: Message):
        self.fsm.send(event)

    def send_command(self, message: Command) -> None:
        """Send a message and start the timer. Also, start waiting"""
        self.send(message)

    def log_invalid(self, message, valid_messages: t.Iterable[t.Type[Message]]):
        self.logger.error(
            f"Received invalid message {message} from model '{self.name}'. Expected one of "
            + ", ".join(m.__name__ for m in valid_messages)
        )


class BaseModelState(State[ConnectedModel], ABC):
    valid_commands: t.Tuple[t.Type[Command], ...] = ()
    valid_responses: t.Tuple[t.Type[Response], ...] = ()


class WaitingForMessage(BaseModelState):
    def run(self):
        msg = yield
        self.recv_message(msg)

    def recv_message(self, msg: Message):
        # Here we make use of the fact that for a typing.Union object, __args__ contains the
        # classes inside the union
        if isinstance(msg, Command.__args__):
            self.process_command(msg)
        elif isinstance(msg, Response.__args__):
            self.handle_response(msg)
        else:
            raise TypeError("Unknown Message")

    def process_command(self, msg: Command):
        if not isinstance(msg, self.valid_commands):
            raise InvalidCommand(
                f"Received invalid command {msg} for model '{self.context.name}'. Expected one of "
                + ", ".join(m.__name__ for m in self.valid_commands)
            )

        if isinstance(msg, NewTimeMessage):
            self.process_new_time(msg)
        if isinstance(msg, NoUpdateMessage):
            self.process_no_update(msg)
        if isinstance(msg, UpdateMessage):
            self.process_update(msg)
        if isinstance(msg, QuitMessage):
            self.process_quit(msg)

    def handle_response(self, msg: Response):
        if self.context.timer.running:
            self.context.timer.stop()
        self.context.busy = False

        if not isinstance(msg, self.valid_responses):
            self.handle_invalid_response(msg, self.valid_responses)
        else:
            self._handle_response(msg)

    def process_new_time(self, msg: NewTimeMessage):
        self.context.pending_new_time = msg

    def process_no_update(self, msg: NoUpdateMessage):
        pass

    def process_update(self, msg: UpdateMessage):
        self.context.pending_updates.append(msg)

    def process_quit(self, msg: QuitMessage):
        self.context.pending_quit = msg

    @singledispatchmethod
    def _handle_response(self, msg: Message) -> None:
        pass

    @_handle_response.register
    def _(self, msg: RegistrationMessage):
        self.context.timeline.set_model_to_start(self.context)
        self.context.pub = msg.pub
        self.context.sub = msg.sub

    @_handle_response.register
    def _(self, msg: AcknowledgeMessage) -> None:
        """when a model sends an accepted message, don't do extra logic"""
        if not self.context.pending_updates:
            self.notify_subscribers()

    @_handle_response.register
    def _(self, msg: ResultMessage) -> None:
        """When a result comes set the model's next_time and possibly add a message to the
        subscribers queues"""
        self.context.timeline.set_next_time(self.context, msg.next_time)
        command = None
        if msg.has_data:
            command = UpdateMessage(
                timestamp=self.context.timeline.current_time,
                key=msg.key,
                address=msg.address,
                origin=msg.origin,
            )
        self.notify_subscribers(command)

    @_handle_response.register
    def _(self, msg: ErrorMessage) -> None:
        """When a model reports an error, set it to failed"""
        self.context.failed = True
        self.context.pending_quit = None
        self.context.pending_updates = []

    def handle_invalid_response(self, msg: Response, valid_messages: t.Iterable[t.Type[Response]]):
        self.context.failed = True
        self.context.log_invalid(msg, valid_messages)
        if not self.context.pending_quit:
            self.context.pending_quit = QuitMessage()
            self.context.pending_updates = []

    def notify_subscribers(self, command: t.Optional[Command] = None):
        command = command or NoUpdateMessage()
        for model in self.context.publishes_to:
            model.recv_event(command)


class Idle(WaitingForMessage):
    """Base class for if a model is awaiting further instructions"""

    valid_commands = (NewTimeMessage, NoUpdateMessage, UpdateMessage, QuitMessage)
    valid_responses = ()


class Busy(WaitingForMessage):
    """Base class for if a model is doing something and a response is required. While busy,
    one or more Command-s may come in, which need to be processed later. These are stored
    until the model returns and they can be processed
    """

    valid_commands = (UpdateMessage, NoUpdateMessage, QuitMessage)
    valid_responses = (ErrorMessage,)

    def on_enter(self):
        self.context.busy = True
        self.context.timer.start()


class Registration(Busy):
    """A RegistrationMessage is expected from the model"""

    valid_commands = (QuitMessage,)
    valid_responses = (RegistrationMessage, ErrorMessage)


class NewTime(Busy):
    """A NewTime message will be sent to the model, and it needs to Acknowledge that"""

    valid_commands = (UpdateMessage, NoUpdateMessage, QuitMessage)
    valid_responses = (AcknowledgeMessage, ErrorMessage)

    def on_enter(self):
        if not isinstance(self.context.pending_new_time, NewTimeMessage):
            raise RuntimeError("can only enter NewTime when there is a pending NewTimeMessage")
        self.context.send_command(self.context.pending_new_time)
        self.context.pending_new_time = None
        super().on_enter()


class Updating(Busy):
    """The model is processing an UpdateMessage and calculating a ResultMessage is expected"""

    valid_commands = (UpdateMessage, NoUpdateMessage, QuitMessage)
    valid_responses = (ResultMessage, ErrorMessage)


class PendingMoreUpdates(Idle):
    """The model has one or more dependencies that are still calculating. We wait until a
    dependency returns before re-evaluating whether we can send the update to the model
    """

    valid_commands = (NoUpdateMessage, UpdateMessage, QuitMessage)
    valid_responses = ()


class ProcessPendingUpdates(BaseModelState):
    """While the model was Busy, one or more updates came in which needs to be processed, this
    state doesn't wait for messages. If the model has one or more dependencies that are still
    calculating, we can't send the update yet but have to wait until all dependencies are finished
    """

    def run(self):
        updates = self.context.pending_updates
        if not updates:
            raise RuntimeError(
                "can only enter ProcessPendingUpdates when there are pending UpdateMessage-s"
            )

        if any(model.busy for model in self.context.subscribed_to):
            return

        self.process_pending_updates()

    def process_pending_updates(self):
        updates = self.context.pending_updates
        msg = updates[0] if len(updates) == 1 else UpdateSeriesMessage(updates)

        self.context.send_command(msg)
        self.context.pending_updates = []


class ProcessPendingQuit(BaseModelState):
    """While the model was Busy, a QuitMessage came in which needs to be processed, this
    state doesn't wait for messages
    """

    def run(self):
        if not isinstance(self.context.pending_quit, QuitMessage):
            raise RuntimeError(
                "can only enter ProcessPendingQuit when there is a QuitMessage pending"
            )
        self.context.send_command(self.context.pending_quit)


class Finalizing(Busy):
    """A QuitMessage has been sent to the model, which needs to acknowledge it and shut down,
    ignore all commands"""

    valid_commands = (NewTimeMessage, NoUpdateMessage, UpdateMessage, QuitMessage)
    valid_responses = (AcknowledgeMessage, ErrorMessage)

    def process_command(self, msg: Command):
        pass


class Done(BaseModelState):
    """The model is either done or failed, ignore any further messages"""

    def run(self):
        yield


class ModelCollection(dict[bytes, ConnectedModel]):
    @property
    def busy(self):
        return any(model.busy for model in self.values())

    @property
    def next_time(self):
        try:
            return min(model.next_time for model in self.values() if model.next_time is not None)
        except ValueError:  # no model has a next_time
            return None

    @property
    def failed(self):
        return [model.name for model in self.values() if model.failed]

    def determine_interdependency(self):
        """calculate the subscribers for every model based on the pub/sub mask."""
        for publisher, subscriber in product(self.values(), self.values()):
            if publisher is not subscriber and masks_overlap(publisher.pub, subscriber.sub):
                publisher.publishes_to.append(subscriber)
                subscriber.subscribed_to.append(publisher)

    def reset_model_timers(self):
        for model in self.values():
            model.timer.reset()


class ModelHasFailed(Condition[ConnectedModel]):
    def met(self) -> bool:
        return self.context.failed


class HasPendingQuitAndIdle(Condition[ConnectedModel]):
    def met(self) -> bool:
        return bool(self.context.pending_quit and not self.context.busy)


class HasPendingUpdatesAndIdle(Condition[ConnectedModel]):
    def met(self) -> bool:
        return bool(self.context.pending_updates and not self.context.busy)


class HasPendingNewTimeAndIdle(Condition[ConnectedModel]):
    def met(self) -> bool:
        return bool(self.context.pending_new_time and not self.context.busy)


class IsIdle(Condition[ConnectedModel]):
    def met(self) -> bool:
        return not self.context.busy


class ModelWaitingForDependencies(Condition[ConnectedModel]):
    def met(self) -> bool:
        return any(model.busy for model in self.context.subscribed_to)


MODEL_BUSY_TRANSITIONS = (
    (HasPendingQuitAndIdle, ProcessPendingQuit),
    (ModelHasFailed, Done),
    (HasPendingUpdatesAndIdle, ProcessPendingUpdates),
    (IsIdle, Idle),
)

MODEL_FSM_CONFIG = FSMConfig(
    initial_state=Registration,
    states={
        Registration: MODEL_BUSY_TRANSITIONS,
        NewTime: MODEL_BUSY_TRANSITIONS,
        Updating: MODEL_BUSY_TRANSITIONS,
        Idle: [
            (HasPendingQuitAndIdle, ProcessPendingQuit),
            (HasPendingUpdatesAndIdle, ProcessPendingUpdates),
            (HasPendingNewTimeAndIdle, NewTime),
        ],
        ProcessPendingUpdates: [
            (ModelWaitingForDependencies, PendingMoreUpdates),
            (Always, Updating),
        ],
        PendingMoreUpdates: [
            (Always, ProcessPendingUpdates),
        ],
        ProcessPendingQuit: [
            (Always, Finalizing),
        ],
        Finalizing: [
            (IsIdle, Done),
        ],
        Done: [],
    },
)
