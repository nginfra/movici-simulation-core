from __future__ import annotations

import logging
import typing as t
from collections import deque
from dataclasses import dataclass, field
from functools import singledispatchmethod
from itertools import product

from movici_simulation_core.exceptions import SimulationExit
from movici_simulation_core.networking.messages import (
    Message,
    RegistrationMessage,
    UpdateMessage,
    ResultMessage,
    NewTimeMessage,
    AcknowledgeMessage,
    UpdateSeriesMessage,
    ErrorMessage,
)
from movici_simulation_core.utils.data_mask import masks_overlap
from .interconnectivity import format_matrix
from .stopwatch import Stopwatch, ReportingStopwatch


@dataclass
class Context:
    models: ModelCollection
    timeline: TimelineController
    global_timer: Stopwatch = field(default=None)
    phase_timer: Stopwatch = field(default=None)
    logger: logging.Logger = field(default_factory=logging.getLogger)

    def __post_init__(self):
        self.global_timer = self.global_timer or ReportingStopwatch(
            on_reset=self.log_elapsed_global_time
        )
        self.phase_timer = self.phase_timer or ReportingStopwatch(
            on_reset=self.log_elapsed_phase_time
        )

    @property
    def failed(self):
        return self.models.failed

    def log_new_phase(self, phase: str):
        self.logger.info(f"Entering {phase}")

    def log_new_time(self):
        self.logger.info(f"New time: {self.models.next_time}")

    def log_elapsed_phase_time(self, seconds: float):
        self.logger.info(f"Phase finished in {seconds:.1f} seconds")

    def log_elapsed_global_time(self, seconds: float):
        self.logger.info(f"Total elapsed time: {seconds:.1f}")

    def log_interconnectivity_matrix(self):
        self.logger.info("Model interconnectivity matrix:\n" + format_matrix(self.models.values()))

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


class Queue:
    def __init__(self, iterable: t.Iterable[Message] = ()):
        self._inner: t.Deque[Message] = deque(iterable)

    def __len__(self):
        return self._inner.__len__()

    def __getitem__(self, item):
        return self._inner.__getitem__(item)

    def add(self, message):
        self._inner.append(message)

    def pop(self):
        return self._inner.popleft()


class MultipleUpdatesAwareQueue:
    def __init__(self, iterable: t.Iterable[Message] = ()):
        self._inner: t.Deque[Message] = deque(iterable)
        self.upd_pos = None

    def __len__(self):
        return self._inner.__len__()

    def __getitem__(self, item):
        return self._inner.__getitem__(item)

    def add(self, message: Message):
        if isinstance(message, UpdateMessage):
            self._add_update(message)
        else:
            self._inner.append(message)

    def pop(self) -> Message:
        if self.upd_pos == 0:
            self.upd_pos = None
        if self.upd_pos is not None:
            self.upd_pos -= 1
        return self._inner.popleft()

    def _add_update(self, message: UpdateMessage):
        if self.upd_pos is None:
            self.upd_pos = len(self._inner)
            self._inner.append(message)
        else:
            self._merge_into_existing_update(message)

    def _merge_into_existing_update(self, update: UpdateMessage):
        curr: t.Union[UpdateMessage, UpdateSeriesMessage] = t.cast(
            t.Union[UpdateMessage, UpdateSeriesMessage], self._inner[self.upd_pos]
        )
        if isinstance(curr, UpdateMessage):
            self._inner[self.upd_pos] = UpdateSeriesMessage([curr, update])
        else:
            curr.updates.append(update)


@dataclass
class ConnectedModel:
    """Holds connection state and other data concerning a (connected) model"""

    name: str
    timeline: TimelineController
    send: t.Callable[[Message], None]

    logger: logging.Logger = field(default_factory=logging.getLogger)
    message_queue: MultipleUpdatesAwareQueue = field(default_factory=MultipleUpdatesAwareQueue)
    subscribers: t.Optional[t.List[ConnectedModel]] = field(default_factory=list)
    timer: Stopwatch = field(default=None)
    pub: t.Optional[dict] = field(default_factory=dict)
    sub: t.Optional[dict] = field(default_factory=dict)

    waiting: bool = field(default=False, init=False)
    next_time: t.Optional[int] = field(default=None, init=False)
    failed: bool = field(default=False, init=False)

    def __post_init__(self):
        self.timer = self.timer or ReportingStopwatch(
            on_stop=lambda s: self.logger.info(
                f"Model '{self.name}' returned in {s:.1f} seconds "
            ),
            on_reset=lambda s: self.logger.info(
                f"Total time spent in in model '{self.name}': {s:.1f} seconds "
            ),
        )

    def queue_message(self, message):
        """add a message to the message queue"""
        if not self.failed:
            self.message_queue.add(message)

    def send_pending_message(
        self,
    ) -> None:
        """If there are any messages in the queue, send the first one and start the timer, also,
        start waiting"""

        if not self.waiting and self.message_queue:
            self.send(self.message_queue.pop())
            self.timer.start()
            self.waiting = True

    def clear_queue(self):
        self.message_queue = MultipleUpdatesAwareQueue()

    def handle_message(
        self,
        event: Message,
        valid_events: t.Optional[t.Tuple[t.Type[Message]]] = None,
        raise_on_invalid=True,
    ):
        if self.timer.running:
            self.timer.stop()
        self.waiting = False

        if valid_events is not None and not isinstance(event, valid_events):
            if raise_on_invalid:
                raise SimulationExit
            return

        self._handle(event)

    @singledispatchmethod
    def _handle(self, event: Message) -> None:
        """By default, reject a message and stop the simulation, some model misbehaved"""
        raise SimulationExit

    @_handle.register
    def _(self, event: RegistrationMessage):
        self.timeline.set_model_to_start(self)
        self.pub = event.pub
        self.sub = event.sub

    @_handle.register
    def _(self, event: AcknowledgeMessage) -> None:
        """when a model sends an accepted message, don't do extra logic"""
        pass

    @_handle.register
    def _(self, event: ResultMessage) -> None:
        """When a result comes set the model's next_time and possibly add a message to the
        subscribers queues"""
        self.timeline.set_next_time(self, event.next_time)
        if event.has_data:
            for model in self.subscribers:
                model.queue_message(
                    UpdateMessage(
                        timestamp=self.timeline.current_time,
                        key=event.key,
                        address=event.address,
                        origin=event.origin,
                    )
                )

    @_handle.register
    def _(self, event: ErrorMessage) -> None:
        """When a model reports an error, set it to failed"""
        self.failed = True
        self.clear_queue()


class ModelCollection(dict, t.Dict[bytes, ConnectedModel]):
    @property
    def waiting(self):
        return any(model.waiting for model in self.values())

    @property
    def waiting_for(self):
        return [model for model in self.values() if model.waiting]

    @property
    def messages_pending(self):
        return any(model.message_queue for model in self.values())

    @property
    def next_time(self):
        try:
            return min(model.next_time for model in self.values() if model.next_time is not None)
        except ValueError:  # no model has a next_time
            return None

    @property
    def failed(self):
        return [model.name for model in self.values() if model.failed]

    def queue_all(self, message: Message):
        """add a message to the queue of all models"""
        for model in self.values():
            model.queue_message(message)

    def queue_models_for_next_time(self):
        """Queue an update message to the model(s) that have the specified next_time"""
        next_time = self.next_time
        for model in self.values():
            if model.next_time == next_time:
                model.queue_message(UpdateMessage(timestamp=next_time))

    def determine_interdependency(self):
        """calculate the subscribers for every model based on the pub/sub mask."""
        for publisher, subscriber in product(self.values(), self.values()):
            if publisher is not subscriber and masks_overlap(publisher.pub, subscriber.sub):
                publisher.subscribers.append(subscriber)

    def send_pending_messages(self):
        """Send the first pending message for all models"""
        for model in self.values():
            model.send_pending_message()

    def wait_for_all(self):
        """wait for all models"""
        for model in self.values():
            model.waiting = True

    def clear_queue(self):
        """clear the queue for all models"""
        for model in self.values():
            model.clear_queue()

    def start_model_timers(self):
        for model in self.values():
            model.timer.start()

    def reset_model_timers(self):
        for model in self.values():
            model.timer.reset()


@dataclass
class TimelineController:
    start: int
    end: int
    current_time: int = None

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

    def queue_for_next_time(self, models: ModelCollection):
        next_time = models.next_time
        if next_time != self.current_time:
            self.current_time = next_time
            models.queue_all(NewTimeMessage(next_time))
        models.queue_models_for_next_time()
