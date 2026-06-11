from unittest.mock import Mock, call

import pytest

from movici_simulation_core.core.priority import Priority
from movici_simulation_core.messages import NewTimeMessage, RemapMessage, UpdateMessage
from movici_simulation_core.services.orchestrator.context import (
    ConnectedModel,
    ModelCollection,
    TimelineController,
)
from movici_simulation_core.services.orchestrator.remap import RemapConflictError
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


def _make_model(name, pub=None, sub=None, priority=int(Priority.REGULAR)):
    model = ConnectedModel(name, Mock(), Mock())
    model.pub = pub or {}
    model.sub = sub or {}
    model.priority = priority
    return model


class TestModelCollectionRemap:
    """End-to-end behaviour for ``ModelCollection.compute_remap_plan`` and
    ``apply_remap_plan``. See issue #127."""

    def test_compute_remap_plan_combiner_case(self):
        models = ModelCollection(
            model_a=_make_model("model_a", pub={"ds": {"eg": ["a"]}}),
            model_b=_make_model("model_b", pub={"ds": {"eg": ["a"]}}),
            combiner=_make_model(
                "combiner",
                pub={"ds": {"eg": ["a"]}},
                priority=int(Priority.SOLVER_HELPER),
            ),
        )
        plan = models.compute_remap_plan()
        assert set(plan) == {"model_a", "model_b", "combiner"}
        assert plan["model_a"].pub == {"ds": {"eg": {"a": "a:model_a:i"}}}
        assert plan["combiner"].sub == {"ds": {"eg": {"a:model_a:i": "a", "a:model_b:i": "a"}}}

    def test_compute_remap_plan_raises_on_unresolved_conflict(self):
        models = ModelCollection(
            a=_make_model("a", pub={"ds": {"eg": ["x"]}}),
            b=_make_model("b", pub={"ds": {"eg": ["x"]}}),
        )
        with pytest.raises(RemapConflictError):
            models.compute_remap_plan()

    def test_apply_remap_plan_updates_masks_and_sends_messages(self):
        a = _make_model("a", pub={"ds": {"eg": ["x"]}})
        b = _make_model("b", pub={"ds": {"eg": ["x"]}}, sub={"ds": {"eg": ["x"]}})
        models = ModelCollection(a=a, b=b)

        plan = {
            "a": RemapMessage(pub={"ds": {"eg": {"x": "x:a:i"}}}),
            "b": RemapMessage(sub={"ds": {"eg": {"x:a:i": "x"}}}),
        }
        # Patch recv_event so we can verify it was called without driving the FSM.
        a.recv_event = Mock()
        b.recv_event = Mock()
        models.apply_remap_plan(plan)

        # Pub mask updated for the non-owner publisher.
        assert a.pub == {"ds": {"eg": ["x:a:i"]}}
        # Sub mask updated for the higher-priority subscriber.
        assert b.sub == {"ds": {"eg": ["x:a:i"]}}
        # Messages were dispatched.
        assert a.recv_event.call_args == call(plan["a"])
        assert b.recv_event.call_args == call(plan["b"])

    def test_apply_remap_plan_skips_unknown_model_names(self):
        models = ModelCollection(a=_make_model("a"))
        # Plan references a model that no longer exists — must not raise.
        models.apply_remap_plan({"ghost": RemapMessage()})

    def test_compute_remap_plan_no_conflict_returns_empty(self):
        models = ModelCollection(
            a=_make_model("a", pub={"ds": {"eg": ["x"]}}),
            b=_make_model("b", pub={"ds": {"eg": ["y"]}}),
        )
        assert models.compute_remap_plan() == {}
