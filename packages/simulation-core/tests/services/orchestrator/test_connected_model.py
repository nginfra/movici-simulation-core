from unittest.mock import Mock, call

import pytest

from movici_simulation_core.core.priority import Priority
from movici_simulation_core.messages import (
    AcknowledgeMessage,
    NewTimeMessage,
    RegistrationMessage,
    RemapMessage,
    ResultMessage,
    UpdateMessage,
)
from movici_simulation_core.services.orchestrator.context import (
    AwaitingRemap,
    ConnectedModel,
    Idle,
    Remapping,
    TimelineController,
)


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


class TestConnectedModelRemap:
    """Per-model FSM behaviour around REMAP. See issue #127."""

    @pytest.fixture
    def model(self, timeline):
        model = get_model(timeline=timeline)
        model.recv_event(RegistrationMessage(None, None))
        return model

    def test_registration_captures_priority(self, timeline):
        model = get_model(timeline=timeline)
        model.recv_event(RegistrationMessage(None, None, priority=int(Priority.SOLVER_HELPER)))
        assert model.priority == int(Priority.SOLVER_HELPER)

    def test_registration_default_priority(self, model):
        # The default value is REGULAR (10).
        assert model.priority == int(Priority.REGULAR)

    def test_post_registration_state_is_awaiting_remap(self, model):
        assert isinstance(model.fsm.state, AwaitingRemap)

    def test_remap_message_sent_to_model(self, model):
        msg = RemapMessage(pub={"ds": {"eg": {"x": "x:m:i"}}})
        model.recv_event(msg)
        assert model.send.call_args == call(msg)

    def test_remap_busy_until_ack(self, model):
        model.recv_event(RemapMessage(pub={"ds": {"eg": {"x": "x:m:i"}}}))
        assert model.busy
        assert isinstance(model.fsm.state, Remapping)

    def test_remap_ack_transitions_to_idle(self, model):
        model.recv_event(RemapMessage(pub={"ds": {"eg": {"x": "x:m:i"}}}))
        model.recv_event(AcknowledgeMessage())
        assert not model.busy
        assert isinstance(model.fsm.state, Idle)

    def test_new_time_in_awaiting_remap_falls_through(self, model):
        # Models that don't get a REMAP can receive NewTime directly while sitting in
        # AwaitingRemap. This is the path for the no-conflict no-helper case.
        msg = NewTimeMessage(0)
        model.recv_event(msg)
        assert model.send.call_args == call(msg)

    def test_remap_with_quit_pending_drops_remap(self, model):
        # If a QuitMessage arrives in AwaitingRemap before the orchestrator's REMAP, we
        # transition out via the standard quit path and never honour the REMAP.
        from movici_simulation_core.messages import QuitMessage

        model.recv_event(QuitMessage())
        assert model.quit is not None

    def test_update_message_in_awaiting_remap_queues_pending(self, model):
        # AwaitingRemap inherits Idle's update handling: an UpdateMessage that arrives
        # before any NewTime is queued to pending_updates and the model transitions out
        # to ProcessPendingUpdates. Adversarial-review test-coverage gap.
        update = UpdateMessage(0)
        model.recv_event(update)
        # The original UpdateMessage was consumed by ProcessPendingUpdates and dispatched
        # to the model — pending_updates is drained, but the dispatch went out the wire.
        assert any(call_args == call(update) for call_args in model.send.call_args_list)
