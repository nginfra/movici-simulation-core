from unittest.mock import Mock, call

import pytest

from movici_simulation_core.networking.messages import (
    Message,
    ErrorMessage,
    QuitMessage,
    RegistrationMessage,
    NewTimeMessage,
    UpdateMessage,
    AcknowledgeMessage,
    ResultMessage,
)
from movici_simulation_core.services.orchestrator.connected_model import (
    BaseModelState,
    NewTime,
    Idle,
    Busy,
    ProcessPendingQuit,
    ProcessPendingUpdates,
    Updating,
    Done,
)
from movici_simulation_core.services.orchestrator.connected_model import (
    ConnectedModel,
    Registration,
    WaitingForMessage,
)
from movici_simulation_core.services.orchestrator.fsm import next_state


@pytest.fixture
def state_cls():
    return BaseModelState


@pytest.fixture
def context():
    return ConnectedModel(name="model", timeline=Mock(), send=Mock())


@pytest.fixture
def state(context, state_cls):
    return state_cls(context)


@pytest.fixture
def send_message(state, context):
    runner = state.run()
    runner.send(None)

    def _send(msg: Message):
        nonlocal runner
        try:
            runner.send(msg)
        except StopIteration:
            runner = state.run()
            runner.send(None)

    return _send


class TestWaitingForMessage:
    @pytest.fixture
    def state_cls(self):
        return WaitingForMessage

    def test_send_error_message(self, send_message, context):
        send_message(ErrorMessage())
        assert context.failed

    @pytest.mark.parametrize(
        "msg",
        [
            NewTimeMessage(1),
            UpdateMessage(1),
            QuitMessage(),
            RegistrationMessage(pub=None, sub=None),
            AcknowledgeMessage(),
            ResultMessage(),
            ErrorMessage(),
        ],
    )
    def test_invalid_message_sets_failed(self, msg, send_message, context):
        send_message(msg)
        assert context.failed

    def test_goes_to_process_quit_after_invalid_message(self, send_message, state):
        send_message(NewTimeMessage(1))
        assert next_state(state) == ProcessPendingQuit


class TestIdle:
    @pytest.fixture
    def state_cls(self):
        return Idle

    def test_sends_incoming_new_time_message(self, send_message, context: ConnectedModel):
        msg = NewTimeMessage(1)
        send_message(msg)
        assert context.send.call_args == call(msg)

    def test_adds_quit_to_pending(self, context, send_message):
        assert context.quit is None
        send_message(QuitMessage())
        assert context.quit == QuitMessage()

    def test_adds_update_to_pending(self, send_message, context):
        assert context.pending_updates == []
        send_message(UpdateMessage(1))
        assert context.pending_updates == [UpdateMessage(1)]

    @pytest.mark.parametrize(
        "msg, expected",
        [
            (NewTimeMessage(0), NewTime),
            (UpdateMessage(1), ProcessPendingUpdates),
            (QuitMessage(), ProcessPendingQuit),
        ],
    )
    def test_transitions_to_correct_state(self, msg, expected, send_message, state):
        send_message(msg)
        assert next_state(state) == expected


class TestBusy:
    @pytest.fixture
    def state_cls(self):
        return Busy

    def test_sets_quit_message_as_pending(self, send_message, context):
        assert context.quit is None
        send_message(QuitMessage())
        assert context.quit == QuitMessage()

    def test_adds_update_message_as_pending(self, send_message, context):
        context.pending_updates = [UpdateMessage(1)]
        send_message(UpdateMessage(2))
        assert context.pending_updates == [UpdateMessage(1), UpdateMessage(2)]

    def test_sets_failed_on_error_message(self, send_message, context):
        assert not context.failed
        send_message(ErrorMessage())
        assert context.failed

    def test_reset_pending_after_error(self, send_message, context):
        context.quit = QuitMessage()
        context.pending_updates = [UpdateMessage(1)]
        send_message(ErrorMessage())
        assert not context.quit
        assert not context.pending_updates


class TestBusyTransitions:
    @pytest.fixture
    def state_cls(self):
        # Use NewTime as a substitute for Busy state, since it has an implementation for a model
        # response (AcknowledgeMessage)
        return NewTime

    @pytest.fixture
    def context(self, context):
        context.busy = True
        return context

    def test_transitions_after_error_message(self, send_message, state):
        send_message(ErrorMessage())
        assert next_state(state) == Done

    def test_transitions_to_idle_when_no_pending_messages(self, send_message, state, context):
        assert not context.quit
        assert not context.pending_updates
        send_message(AcknowledgeMessage())
        assert next_state(state) == Idle

    def test_transitions_on_pending_updates(self, send_message, state, context):
        send_message(UpdateMessage(1))
        send_message(AcknowledgeMessage())
        assert next_state(state) == ProcessPendingUpdates

    def test_transitions_on_pending_quit(self, send_message, state, context):
        send_message(QuitMessage())
        send_message(AcknowledgeMessage())
        assert next_state(state) == ProcessPendingQuit

    def test_quit_has_preference_over_updates(self, send_message, state, context):
        send_message(QuitMessage())
        send_message(UpdateMessage(1))
        send_message(AcknowledgeMessage())
        assert next_state(state) == ProcessPendingQuit


@pytest.mark.parametrize(
    "state_cls, msg",
    [
        (Registration, RegistrationMessage(None, None)),
        (NewTime, AcknowledgeMessage()),
        (Updating, ResultMessage()),
    ],
)
def test_model_response_unsets_busy(state_cls, msg, send_message, context):
    context.busy = True
    send_message(msg)
    assert not context.busy


class TestRegistration:
    @pytest.fixture
    def state_cls(self):
        return Registration

    def test_sets_pub_sub(self, send_message, context):
        pub, sub = {"some": "pub"}, {"some": "sub"}
        send_message(RegistrationMessage(pub=pub, sub=sub))
        assert context.pub == pub
        assert context.sub == sub

    def test_sets_model_to_start(self, send_message, context):
        send_message(RegistrationMessage(None, None))
        assert context.timeline.set_model_to_start.call_args == call(context)


class TestNewTime:
    @pytest.fixture
    def state_cls(self):
        return NewTime

    def test_acknowledge_is_valid(self, send_message, context):
        send_message(AcknowledgeMessage())
        assert not context.failed
