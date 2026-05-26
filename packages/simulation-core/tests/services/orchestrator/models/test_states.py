from unittest.mock import Mock, call

import pytest

from movici_simulation_core.messages import (
    AcknowledgeMessage,
    ErrorMessage,
    Message,
    NewTimeMessage,
    QuitMessage,
    RegistrationMessage,
    ResultMessage,
    UpdateMessage,
)
from movici_simulation_core.services.orchestrator.context import (
    MODEL_BUSY_TRANSITIONS,
    MODEL_FSM_CONFIG,
    BaseModelState,
    Busy,
    ConnectedModel,
    Done,
    Idle,
    NewTime,
    ProcessPendingQuit,
    ProcessPendingUpdates,
    Registration,
    Updating,
    WaitingForMessage,
)
from movici_simulation_core.services.orchestrator.fsm import next_state as next_state_


@pytest.fixture
def state_cls():
    return BaseModelState


@pytest.fixture
def context():
    return ConnectedModel(name="model", timeline=Mock(), send=Mock())


@pytest.fixture
def state(state_cls, context):
    state = state_cls(context)
    state.on_enter()
    return state


@pytest.fixture
def send_message(state, context):

    def _send(msg: Message):
        runner = state.run()
        runner.send(None)
        try:
            runner.send(msg)
        except StopIteration:
            pass

    return _send


@pytest.fixture
def transitions(state_cls):
    return MODEL_FSM_CONFIG.states[state_cls]


@pytest.fixture
def next_state(context, transitions):
    def _calculate_next_state():
        return next_state_(context, transitions)

    return _calculate_next_state


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
            RegistrationMessage(pub=None, sub=None),
            AcknowledgeMessage(),
            ResultMessage(),
            ErrorMessage(),
        ],
    )
    def test_invalid_response_sets_failed(self, msg, send_message, context):
        send_message(msg)
        assert context.failed

    def test_invalid_command_raises(self, send_message):
        with pytest.raises(ValueError):
            send_message(NewTimeMessage(1))


class TestBusyTransitions:
    @pytest.fixture
    def state_cls(self):
        class DummyState(Busy):
            valid_responses = (ErrorMessage, AcknowledgeMessage)

        return DummyState

    @pytest.fixture
    def transitions(self):
        return MODEL_BUSY_TRANSITIONS

    @pytest.fixture
    def send_message(self, state):
        def _send(msg: Message):
            runner = state.run()
            runner.send(None)
            try:
                runner.send(msg)
            except StopIteration:
                pass

        return _send

    def test_transitions_after_invalid_response(self, send_message, next_state):
        send_message(ResultMessage())
        assert next_state() == ProcessPendingQuit

    def test_transitions_after_error_message(self, send_message, next_state):
        send_message(ErrorMessage())
        assert next_state() == Done

    def test_transitions_to_idle_when_no_pending_messages(self, send_message, context, next_state):
        assert not context.pending_quit
        assert not context.pending_updates
        send_message(AcknowledgeMessage())
        assert next_state() == Idle

    def test_transitions_on_pending_updates(self, send_message, next_state):
        send_message(UpdateMessage(1))
        send_message(AcknowledgeMessage())
        assert next_state() == ProcessPendingUpdates

    def test_transitions_on_pending_quit(self, send_message, next_state):
        send_message(QuitMessage())
        send_message(AcknowledgeMessage())
        assert next_state() == ProcessPendingQuit

    def test_quit_has_preference_over_updates(self, send_message, next_state):
        send_message(QuitMessage())
        send_message(UpdateMessage(1))
        send_message(AcknowledgeMessage())
        assert next_state() == ProcessPendingQuit


class TestIdle:
    @pytest.fixture
    def state_cls(self):
        return Idle

    def test_adds_pending_new_time(self, send_message, context: ConnectedModel):
        msg = NewTimeMessage(1)
        send_message(msg)
        assert context.pending_new_time == msg

    def test_adds_quit_to_pending(self, context, send_message):
        assert context.pending_quit is None
        send_message(QuitMessage())
        assert context.pending_quit == QuitMessage()

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
    def test_transitions_to_correct_state(self, msg, expected, send_message, next_state):
        send_message(msg)
        assert next_state() == expected


class TestBusy:
    @pytest.fixture
    def state_cls(self):
        return Busy

    def test_on_enter_starts_timer(self, context: ConnectedModel):
        assert not context.timer.running
        Busy(context).on_enter()
        assert context.timer.running

    def test_sets_quit_message_as_pending(self, send_message, context):
        assert context.pending_quit is None
        send_message(QuitMessage())
        assert context.pending_quit == QuitMessage()

    def test_adds_update_message_as_pending(self, send_message, context):
        context.pending_updates = [UpdateMessage(1)]
        send_message(UpdateMessage(2))
        assert context.pending_updates == [UpdateMessage(1), UpdateMessage(2)]

    def test_sets_failed_on_error_message(self, send_message, context):
        assert not context.failed
        send_message(ErrorMessage())
        assert context.failed

    def test_reset_pending_after_error(self, send_message, context):
        context.pending_quit = QuitMessage()
        context.pending_updates = [UpdateMessage(1)]
        send_message(ErrorMessage())
        assert not context.pending_quit
        assert not context.pending_updates


@pytest.mark.parametrize(
    "state_cls, msg",
    [
        (Registration, RegistrationMessage(None, None)),
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
    def context(self, context):
        context.pending_new_time = NewTimeMessage(1)
        return context

    @pytest.fixture
    def state_cls(self):
        return NewTime

    def test_sends_pending_new_time_and_resets(self, context, send_message):
        assert context.send.call_args == call(NewTimeMessage(1))
        assert context.pending_new_time is None

    def test_acknowledge_is_valid(self, send_message, context):
        send_message(AcknowledgeMessage())
        assert not context.failed
