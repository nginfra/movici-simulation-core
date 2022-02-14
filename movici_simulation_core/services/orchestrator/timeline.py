from __future__ import annotations

from dataclasses import dataclass
import typing as t

from movici_simulation_core.networking.messages import NewTimeMessage
from movici_simulation_core.services.orchestrator import connected_model, model_collection


@dataclass
class TimelineController:
    start: int
    end: int
    current_time: int = None

    def set_model_to_start(self, model: connected_model.ConnectedModel):
        model.next_time = self.start

    def set_next_time(
        self, model: connected_model.ConnectedModel, next_time: t.Optional[int] = None
    ):
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

    def queue_for_next_time(self, models: model_collection.ModelCollection):
        next_time = models.next_time
        if next_time != self.current_time:
            self.current_time = next_time
            models.queue_all(NewTimeMessage(next_time))
        models.queue_models_for_next_time()
