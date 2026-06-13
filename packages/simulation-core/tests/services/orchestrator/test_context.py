from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

import pytest

from movici_simulation_core.exceptions import InvalidCommand
from movici_simulation_core.messages import NewTimeMessage, UpdateMessage
from movici_simulation_core.services.orchestrator.context import (
    Context,
    ModelCollection,
    TimelineController,
)
from tests.services.orchestrator.test_connected_model import get_model


class TestTimelineController:
    def test_can_set_model_next_time_to_start(self):
        timeline = TimelineController(start=1, end=10)
        model = get_model(timeline=timeline)
        timeline.set_model_to_start(model)
        assert model.next_time == 1

    def test_sets_next_time_for_model(self):
        model = get_model()
        timeline = TimelineController(start=1, end=10)
        timeline.set_next_time(model, 2)
        assert model.next_time == 2

    def test_sets_next_time_for_model_at_end(self):
        model = get_model()
        timeline = TimelineController(start=1, end=10)
        timeline.set_next_time(model, 11)
        assert model.next_time == 10

    def test_prevents_next_time_in_past(self):
        timeline = TimelineController(start=1, end=10, current_time=5)
        assert timeline._get_validated_next_time(3) is None

    def test_clamps_next_time_to_end_time(self):
        timeline = TimelineController(start=1, end=10, current_time=9)
        assert timeline._get_validated_next_time(11) == 10

    def test_can_request_end_time_at_end_time(self):
        timeline = TimelineController(start=1, end=10, current_time=10)
        assert timeline._get_validated_next_time(10) == 10

    def test_prevents_next_time_beyond_end_time_at_end_time(self):
        timeline = TimelineController(start=1, end=10, current_time=10)
        assert timeline._get_validated_next_time(11) is None

    def test_can_register_at_current_time(self):
        timeline = TimelineController(start=1, end=20, current_time=10)
        assert timeline._get_validated_next_time(10) == 10


class TestContext:
    @pytest.fixture
    def make_context(self):
        sentinel = object()

        def _make(
            models=None,
            timeline=sentinel,
            phase_timer=sentinel,
            global_timer=sentinel,
            logger=sentinel,
            **kwargs,
        ):
            a, b = Mock(), Mock()
            return Context(
                models=models if models is not None else ModelCollection(a=a, b=b),
                timeline=timeline if timeline is not sentinel else Mock(),
                phase_timer=phase_timer if phase_timer is not sentinel else Mock(),
                global_timer=global_timer if global_timer is not sentinel else Mock(),
                logger=logger if logger is not sentinel else Mock(),
                **kwargs,
            )

        return _make

    @pytest.fixture
    def context(self, make_context):
        return make_context()

    def test_logs_on_global_timer_reset(self, make_context):
        context = make_context(global_timer=None, phase_timer=None)
        context.global_timer.reset()
        assert context.logger.info.call_args == call("Total elapsed time: 0.0")

    def test_logs_on_phase_timer_reset(self, make_context):
        context = make_context(global_timer=None, phase_timer=None)
        context.phase_timer.reset()
        assert context.logger.info.call_args == call("Phase finished in 0.0 seconds")

    def test_resets_timers_on_finalize(self, make_context):
        context = make_context(models=MagicMock(ModelCollection))
        context.finalize()
        assert context.phase_timer.reset.call_count == 1
        assert context.global_timer.reset.call_count == 1
        assert context.models.reset_model_timers.call_count == 1

    @pytest.mark.parametrize(
        "failures,loglevel,msg_endswith",
        [
            ([], "info", "successfully finished"),
            (["one"], "error", "component 'one'"),
            (["one", "two"], "error", "components 'one', 'two'"),
        ],
    )
    def test_logs_finalize_message(self, failures, loglevel, msg_endswith, context):
        with patch.object(Context, "failed", new_callable=PropertyMock) as failed:
            failed.return_value = failures
            context.finalize()

        assert getattr(context.logger, loglevel).call_args[0][0].endswith(msg_endswith)

    @pytest.mark.parametrize(
        "next_a, next_b, exp_a, exp_b",
        [
            (0, 1, [UpdateMessage(0)], []),
            (2, 1, [NewTimeMessage(1)], [NewTimeMessage(1), UpdateMessage(1)]),
            (1, 2, [NewTimeMessage(1), UpdateMessage(1)], [NewTimeMessage(1)]),
            (2, 2, [NewTimeMessage(2), UpdateMessage(2)], [NewTimeMessage(2), UpdateMessage(2)]),
            (2, None, [NewTimeMessage(2), UpdateMessage(2)], [NewTimeMessage(2)]),
            (None, 2, [NewTimeMessage(2)], [NewTimeMessage(2), UpdateMessage(2)]),
        ],
    )
    def test_queue_for_next_time(self, next_a, next_b, exp_a, exp_b, make_context):
        context = make_context(
            timeline=TimelineController(start=0, end=20, current_time=0),
        )
        a = context.models["a"]
        b = context.models["b"]
        a.next_time = next_a
        b.next_time = next_b

        context.queue_models_for_next_time()

        assert a.recv_event.call_args_list == [call(msg) for msg in exp_a]
        assert b.recv_event.call_args_list == [call(msg) for msg in exp_b]

    def test_recv_for_all(self, context):
        assert len(context.models) > 0
        message = object()
        context.recv_for_all(message)
        for model in context.models.values():
            assert model.recv_event.call_args == call(message)

    def test_invalid_command_sets_failed(self, make_context):
        model_a = Mock()
        model_a.recv_event.side_effect = InvalidCommand
        context: Context = make_context(models=ModelCollection(a=model_a))
        context.recv_message(model_a, UpdateMessage(12))
        assert context.orchestrator_failed
        assert "orchestrator" in context.failed
