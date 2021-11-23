import typing as t
from itertools import product

from movici_simulation_core.networking.messages import Message, UpdateMessage
from movici_simulation_core.services.orchestrator.connected_model import ConnectedModel
from movici_simulation_core.utils.data_mask import masks_overlap


class ModelCollection(dict, t.Dict[bytes, ConnectedModel]):
    @property
    def busy(self):
        return any(model.busy for model in self.values())

    @property
    def waiting_for(self):
        return [model for model in self.values() if model.busy]

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
            model.recv_event(message)

    def queue_models_for_next_time(self):
        """Queue an update message to the model(s) that have the specified next_time"""
        next_time = self.next_time
        for model in self.values():
            if model.next_time == next_time:
                model.recv_event(UpdateMessage(timestamp=next_time))

    def determine_interdependency(self):
        """calculate the subscribers for every model based on the pub/sub mask."""
        for publisher, subscriber in product(self.values(), self.values()):
            if publisher is not subscriber and masks_overlap(publisher.pub, subscriber.sub):
                publisher.publishes_to.append(subscriber)
                subscriber.subscribed_to.append(publisher)

    def reset_model_timers(self):
        for model in self.values():
            model.timer.reset()
