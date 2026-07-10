import typing as t
from unittest.mock import Mock, call

import pytest

from movici_simulation_core.messages import QuitMessage
from movici_simulation_core.services.orchestrator.context import ConnectedModel, ModelCollection
from movici_simulation_core.services.orchestrator.fsm import FSMDone, FSMError
from movici_simulation_core.services.orchestrator.states import (
    EndFinalizingPhase,
    NewTime,
    OrchestratorState,
    StartFinalizingPhase,
    StartInitializingPhase,
    StartRunningPhase,
    WaitForModels,
)


class BaseTestState:
    state_cls: t.Type[OrchestratorState]

    @pytest.fixture
    def state(self, context):
        return self.state_cls(context)


class TestStartInitializingState(BaseTestState):
    state_cls = StartInitializingPhase

    def test_initializing_start_starts_timers(self, state, context):
        state.run()
        assert context.phase_timer.start.call_count == 1
        assert context.global_timer.start.call_count == 1


class TestWaitForModels(BaseTestState):
    state_cls = WaitForModels

    @pytest.fixture
    def event(self):
        return object()

    @pytest.fixture
    def model_mock(self):
        mock = Mock()
        mock.name = "model_a"
        return mock

    @pytest.fixture
    def context(self, context, model_mock):
        context.models = ModelCollection(
            model_a=model_mock, model_b=ConnectedModel("model_b", Mock(), Mock())
        )
        return context

    @pytest.fixture
    def send_message(self, state, event):

        def _send(name=None, msg=None):
            msg = msg or event
            name = name or "model_a"
            state.handle_event((name, msg))

        return _send

    def test_handles_event(self, state, send_message, model_mock, event):
        state.valid_messages = ("dummy",)
        send_message()
        assert model_mock.recv_event.call_args == call(event)

    def test_ignores_unknown_models(self, send_message, context):
        context.recv_message = Mock()

        # a known model is called
        send_message(name="model_a")
        assert context.recv_message.call_count == 1
        context.recv_message.reset_mock()

        # an unknown model is ignored
        send_message(name="unknown")
        assert context.recv_message.call_count == 0


class TestStartRunningPhase(BaseTestState):
    state_cls = StartRunningPhase

    def test_restarts_phase_timer(self, state, context):
        state.run()
        assert state.context.phase_timer.restart.call_count == 1

    def test_initializing_calculates_interdependencies(self, state, context):
        state.run()
        assert context.models.determine_interdependency.call_count == 1


class TestNewTime(BaseTestState):
    state_cls = NewTime

    @pytest.fixture
    def context(self):
        return Mock()

    def test_queues_models(self, state, context):
        state.run()
        assert context.queue_models_for_next_time.call_count == 1


class TestStartFinalizingPhase(BaseTestState):
    state_cls = StartFinalizingPhase

    def test_restarts_phase_timer(self, state, context):
        state.run()
        assert context.phase_timer.restart.call_count == 1

    def test_replaces_queue_with_quit_message(self, state, context):
        context.recv_for_all = Mock()
        state.run()
        assert type(context.recv_for_all.call_args[0][0]) is QuitMessage


class TestEndFinalizingPhase(BaseTestState):
    state_cls = EndFinalizingPhase

    @pytest.fixture
    def context(self, context):
        context.models = ModelCollection(model_b=ConnectedModel("model", Mock(), Mock()))
        return context

    def run_silent(self, state):
        try:
            state.run()
        except FSMDone:
            pass

    def test_finalizes_context(self, context, state):
        context.finalize = Mock()
        with pytest.raises(FSMDone):
            state.run()
        assert context.finalize.call_count == 1

    def test_raises_FSMError_on_error(self, context, state):
        context.finalize = Mock()
        next(iter(context.models.values())).failed = True
        with pytest.raises(FSMError):
            state.run()
        assert context.finalize.call_count == 1
