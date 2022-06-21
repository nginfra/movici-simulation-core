from unittest.mock import Mock, call

import pytest

from movici_simulation_core.messages import (
    AcknowledgeMessage,
    RegistrationMessage,
    ResultMessage,
    UpdateMessage,
)
from movici_simulation_core.services.orchestrator.context import ConnectedModel, TimelineController


@pytest.fixture
def timeline():
    return TimelineController(0, 10, 0)


def get_model(name="dummy", timeline=None, send=None, **kwargs):
    send = send or Mock()
    return ConnectedModel(name, timeline, send, **kwargs)


class TestConnectedModel:
    @pytest.fixture
    def message(self):
        return RegistrationMessage(None, None)

    @pytest.fixture
    def subscriber(self, timeline):
        model = get_model(
            "subscriber",
            timeline=timeline,
            send=Mock(),
        )
        model.recv_event(RegistrationMessage(None, None))
        model.recv_event(UpdateMessage(0))
        return model

    @pytest.fixture
    def model(self, message, timeline, subscriber):
        model = get_model(
            send=Mock(),
            timeline=timeline,
            publishes_to=[subscriber],
        )
        model.recv_event(message)
        return model

    @pytest.fixture
    def running_model(self, model):
        model.recv_event(UpdateMessage(0))
        return model

    def test_queues_update_message_on_busy_model(self, running_model):
        running_model.send.reset_mock()
        msg2 = UpdateMessage(1)
        running_model.recv_event(msg2)
        assert running_model.pending_updates == [msg2]
        assert running_model.send.call_count == 0

    def test_sends_message_on_idle_model(self, model):
        msg = UpdateMessage(1)
        model.recv_event(msg)
        assert model.send.call_args == call(msg)

    def test_send_command_starts_timer(self, model):
        model.send_command(UpdateMessage(1))
        assert model.timer.running

    def test_send_command_marks_model_as_waiting(self, model):
        model.send_command(UpdateMessage(1))
        assert model.busy

    def test_response_stops_timer_and_busy(self, running_model):
        running_model.recv_event(ResultMessage())
        assert not running_model.timer.running
        assert not running_model.busy

    def test_registration_message_sets_next_time_to_start(self, timeline):
        model = get_model(
            send=Mock(),
            timeline=timeline,
        )
        assert model.next_time is None
        model.recv_event(RegistrationMessage(None, None))
        assert model.next_time == 0

    def test_result_message_sets_next_time(self, running_model):
        message = ResultMessage(next_time=1)
        running_model.recv_event(message)
        assert running_model.next_time == 1

    def test_result_message_queues_subscriber(self, running_model, subscriber, timeline):
        result = ResultMessage(next_time=1, key="bla", address="some_address", origin="some_model")
        running_model.recv_event(result)
        assert subscriber.pending_updates[0] == UpdateMessage(
            timestamp=timeline.current_time,
            key=result.key,
            address=result.address,
            origin="some_model",
        )

    def test_result_doesnt_queue_subscriber_on_empty_result(
        self, running_model, subscriber, timeline
    ):
        result = ResultMessage(next_time=1)
        running_model.recv_event(result)
        assert len(subscriber.pending_updates) == 0

    def test_accepts_valid_message(self, running_model):
        running_model.recv_event(ResultMessage())
        assert not running_model.failed

    def test_sets_model_failed_on_invalid_message(self, running_model):
        assert not running_model.failed
        running_model.recv_event(AcknowledgeMessage())
        assert running_model.failed
