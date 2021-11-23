from __future__ import annotations

import logging
import typing as t
from abc import ABC
from dataclasses import dataclass, field
from functools import singledispatchmethod

from movici_simulation_core.networking.messages import (
    Message,
    UpdateMessage,
    UpdateSeriesMessage,
    RegistrationMessage,
    AcknowledgeMessage,
    ResultMessage,
    ErrorMessage,
    QuitMessage,
    NewTimeMessage,
)
from movici_simulation_core.services.orchestrator.fsm import State, TransitionsT, Always, FSM
from movici_simulation_core.services.orchestrator.stopwatch import Stopwatch, ReportingStopwatch
from movici_simulation_core.services.orchestrator.timeline import TimelineController


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
    publishes_to: t.Optional[t.List[ConnectedModel]] = field(default_factory=list)
    subscribed_to: t.Optional[t.List[ConnectedModel]] = field(default_factory=list)
    timer: Stopwatch = field(default=None)
    pub: t.Optional[dict] = field(default_factory=dict)
    sub: t.Optional[dict] = field(default_factory=dict)

    busy: bool = field(default=False, init=False)
    next_time: t.Optional[int] = field(default=None, init=False)
    failed: bool = field(default=False, init=False)
    ack: bool = field(default=False, init=False)

    quit: t.Optional[QuitMessage] = field(default=None, init=False)
    pending_updates: t.List[UpdateMessage] = field(default_factory=list, init=False)

    fsm: FSM[ConnectedModel] = field(init=False)

    def __post_init__(self):
        self.timer = self.timer or ReportingStopwatch(
            on_stop=lambda s: self.logger.info(
                f"Model '{self.name}' returned in {s:.1f} seconds "
            ),
            on_reset=lambda s: self.logger.info(
                f"Total time spent in in model '{self.name}': {s:.1f} seconds "
            ),
        )
        self.fsm = FSM(Registration, self, raise_on_done=False)
        self.fsm.start()

    def recv_event(self, event: Message):
        self.fsm.send(event)

    def send_command(self, message: Command) -> None:
        """If there are any messages in the queue, send the first one and start the timer, also,
        start waiting"""
        self.send(message)
        self.timer.start()
        self.busy = True


class BaseModelState(State[ConnectedModel], ABC):
    valid_commands: t.Tuple[t.Type[Command], ...] = ()
    valid_responses: t.Tuple[t.Type[Response], ...] = ()
    next_state: t.Type[BaseModelState] = None

    def transitions(self) -> TransitionsT:
        if self.next_state is not None:
            return [(Always, self.next_state)]
        return self._transitions()

    def _transitions(self):
        return []


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
            self.handle_invalid(msg)
            return

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
            self.handle_invalid(msg)
        else:
            self._handle_response(msg)

    def process_new_time(self, msg: NewTimeMessage):
        pass

    def process_no_update(self, msg: NoUpdateMessage):
        pass

    def process_update(self, msg: UpdateMessage):
        pass

    def process_quit(self, msg: QuitMessage):
        pass

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
        self.context.ack = True

    @_handle_response.register
    def _(self, msg: ResultMessage) -> None:
        """When a result comes set the model's next_time and possibly add a message to the
        subscribers queues"""
        self.context.timeline.set_next_time(self.context, msg.next_time)
        if msg.has_data:
            command = UpdateMessage(
                timestamp=self.context.timeline.current_time,
                key=msg.key,
                address=msg.address,
                origin=msg.origin,
            )
        else:
            command = NoUpdateMessage()
        for model in self.context.publishes_to:
            model.recv_event(command)

    @_handle_response.register
    def _(self, msg: ErrorMessage) -> None:
        """When a model reports an error, set it to failed"""
        self.context.failed = True
        self.context.quit = None
        self.context.pending_updates = []

    def handle_invalid(self, msg: Message):
        # TODO: what if a model sends an invalid message after it's received a QuitMessage. Another
        #   QuitMessage should not be sent

        self.context.failed = True
        if not self.context.quit:
            self.context.quit = QuitMessage()
            self.context.pending_updates = []
            self.next_state = ProcessPendingQuit


class Idle(WaitingForMessage):
    """Base class for if a model is awaiting further instructions"""

    valid_commands = (NewTimeMessage, NoUpdateMessage, UpdateMessage, QuitMessage)
    valid_responses = ()

    def process_new_time(self, msg: NewTimeMessage):
        self.context.ack = False
        self.context.send_command(msg)
        self.next_state = NewTime

    def process_update(self, msg: UpdateMessage):
        self.context.pending_updates.append(msg)
        self.next_state = ProcessPendingUpdates

    def process_quit(self, msg: QuitMessage):
        self.context.quit = msg
        self.next_state = ProcessPendingQuit


class Busy(WaitingForMessage):
    """Base class for if a model is doing something and a response is required. While busy,
    one or more Command-s may come in, which need to be processed later. These are stored
    until the model returns and they can be processed
    """

    valid_commands = (UpdateMessage, NoUpdateMessage, QuitMessage)
    valid_responses = (ErrorMessage,)

    def process_update(self, msg: UpdateMessage):
        self.context.pending_updates.append(msg)

    def process_quit(self, msg: QuitMessage):
        self.context.quit = msg

    def _transitions(self):
        return [
            (lambda c: c.failed, Done),
            (lambda c: (not c.busy) and c.quit, ProcessPendingQuit),
            (lambda c: (not c.busy) and c.pending_updates, ProcessPendingUpdates),
            (lambda c: not c.busy, Idle),
        ]


class Registration(Busy):
    """A RegistrationMessage is expected from the model"""

    valid_commands = (QuitMessage,)
    valid_responses = (RegistrationMessage, ErrorMessage)

    def on_enter(self):
        self.context.busy = True
        self.context.timer.start()


class NewTime(Busy):
    """A NewTime message has been sent to the model, and it needs to Acknowledge that"""

    valid_commands = (UpdateMessage, NoUpdateMessage, QuitMessage)
    valid_responses = (AcknowledgeMessage, ErrorMessage)


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

    def process_update(self, msg: UpdateMessage):
        self.context.pending_updates.append(msg)

    def _transitions(self):
        return [(Always, ProcessPendingUpdates)]


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
            self.next_state = PendingMoreUpdates
            return

        self.process_pending_updates()
        self.next_state = Updating

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
        if not isinstance(self.context.quit, QuitMessage):
            raise RuntimeError(
                "can only enter ProcessPendingQuit when there is a QuitMessage pending"
            )
        self.process_pending_quit()
        self.next_state = Finalizing

    def process_pending_quit(self):
        self.context.ack = False
        self.context.send_command(self.context.quit)


class Finalizing(Busy):
    """A QuitMessage has been sent to the model, which needs to acknowledge it and shut down,
    ignore all commands"""

    valid_commands = (NewTimeMessage, NoUpdateMessage, UpdateMessage, QuitMessage)
    valid_responses = (AcknowledgeMessage, ErrorMessage)

    def process_command(self, msg: Command):
        pass

    def _transitions(self):
        return [
            (lambda c: not c.busy, Done),
        ]


class Done(BaseModelState):
    """The model is either done or failed, ignore any further messages"""

    def run(self):
        yield
