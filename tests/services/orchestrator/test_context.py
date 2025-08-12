from unittest.mock import Mock, call

import pytest

from movici_simulation_core.messages import NewTimeMessage, UpdateMessage
from movici_simulation_core.services.orchestrator.context import ModelCollection, TimelineController
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

    @pytest.mark.parametrize(
        "next_a, next_b, exp_a, exp_b",
        [
            (0, 1, [UpdateMessage(0)], []),
            (2, 1, [NewTimeMessage(1)], [NewTimeMessage(1), UpdateMessage(1)]),
            (1, 2, [NewTimeMessage(1), UpdateMessage(1)], [NewTimeMessage(1)]),
            (2, None, [NewTimeMessage(2), UpdateMessage(2)], [NewTimeMessage(2)]),
            (None, 2, [NewTimeMessage(2)], [NewTimeMessage(2), UpdateMessage(2)]),
        ],
    )
    def test_queue_for_next_time(self, next_a, next_b, exp_a, exp_b):
        timeline = TimelineController(start=0, end=20, current_time=0)
        a, b = Mock(), Mock()
        models = ModelCollection(
            a=a,
            b=b,
        )
        a.next_time = next_a
        b.next_time = next_b

        timeline.queue_for_next_time(models)
        assert a.recv_event.call_args_list == [call(msg) for msg in exp_a]
        assert b.recv_event.call_args_list == [call(msg) for msg in exp_b]
