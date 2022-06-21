from unittest.mock import Mock, call

import pytest

from movici_simulation_core.exceptions import SimulationExit
from movici_simulation_core.messages import QuitMessage
from movici_simulation_core.services.orchestrator.context import ConnectedModel, ModelCollection
from movici_simulation_core.services.orchestrator.fsm import FSMDone, send_silent
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
    state_cls = OrchestratorState

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
        runner = state.run()
        send_silent(runner, None)

        def _send(name=None, msg=None):
            msg = msg or event
            name = name or "model_a"
            send_silent(runner, (name, msg))
            return runner

        return _send

    def test_handles_event(self, state, send_message, model_mock, event):
        state.valid_messages = ("dummy",)
        send_message()
        assert model_mock.recv_event.call_args == call(event)

    def test_quits_when_model_crashes(self, send_message, model_mock, state):
        model_mock.handle_message.side_effect = SimulationExit
        send_message(name="model_a")
        assert state.context.failed == ["model_a"]

    def test_ignores_unknown_models(self, send_message, model_mock):
        send_message(name="unknown")
        assert model_mock.handle_message.call_count == 0


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

    def test_queues_models(self, state, context):
        state.run()
        assert context.timeline.queue_for_next_time.call_args == call(context.models)


class TestStartFinalizingPhase(BaseTestState):
    state_cls = StartFinalizingPhase

    def test_restarts_phase_timer(self, state, context):
        state.run()
        assert context.phase_timer.restart.call_count == 1

    def test_replaces_queue_with_quit_message(self, state, context):
        state.run()
        assert type(context.models.queue_all.call_args[0][0]) == QuitMessage


class TestEndFinalizingPhase(BaseTestState):
    state_cls = EndFinalizingPhase

    def run_silent(self, state):
        try:
            state.run()
        except FSMDone:
            pass

    def test_finalizes_context(self, context, state):
        context.finalize = Mock()
        self.run_silent(state)
        assert context.finalize.call_count == 1
