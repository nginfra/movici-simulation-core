from __future__ import annotations

import logging
import typing as t
from collections import deque
from dataclasses import dataclass, field

from movici_simulation_core.networking.messages import (
    Message,
)
from .interconnectivity import format_matrix
from movici_simulation_core.services.orchestrator.model_collection import ModelCollection

from .stopwatch import Stopwatch, ReportingStopwatch
from .timeline import TimelineController

if t.TYPE_CHECKING:
    pass


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
        if self.models.next_time != self.timeline.current_time:
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
