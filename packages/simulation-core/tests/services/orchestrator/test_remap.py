"""Tests for the pure REMAP planner. See issue #127."""

from __future__ import annotations

import pytest

from movici_simulation_core.core.priority import Priority
from movici_simulation_core.messages import RemapMessage
from movici_simulation_core.services.orchestrator.remap import (
    ModelRegistration,
    RemapConflictError,
    compute_remap_plan,
)


def _reg(name, pub=None, sub=None, priority=int(Priority.REGULAR)):
    return ModelRegistration(name=name, pub=pub, sub=sub, priority=priority)


def _attr(name):
    return {"the_dataset": {"the_entities": [name]}}


class TestNoRemapNeeded:
    def test_empty_registration_set(self):
        assert compute_remap_plan([]) == {}

    def test_single_publisher_no_conflict(self):
        plan = compute_remap_plan([_reg("a", pub=_attr("x"))])
        assert plan == {}

    def test_disjoint_publishers(self):
        plan = compute_remap_plan(
            [
                _reg("a", pub=_attr("x")),
                _reg("b", pub=_attr("y")),
            ]
        )
        assert plan == {}

    def test_pub_only_subscribers_no_conflict(self):
        plan = compute_remap_plan(
            [
                _reg("a", pub=_attr("x")),
                _reg("b", sub=_attr("x")),
            ]
        )
        assert plan == {}


class TestConflictDetection:
    def test_two_regular_models_publish_same_attribute(self):
        with pytest.raises(RemapConflictError) as exc_info:
            compute_remap_plan(
                [
                    _reg("demand_a", pub=_attr("cargo_demand")),
                    _reg("demand_b", pub=_attr("cargo_demand")),
                ]
            )
        err = exc_info.value
        assert err.priority == int(Priority.REGULAR)
        assert err.models == ("demand_a", "demand_b")
        msg = str(err)
        assert "'demand_a'" in msg and "'demand_b'" in msg
        assert "both publish" in msg
        assert "the_dataset/the_entities/cargo_demand" in msg
        assert "priority 10" in msg
        assert "REGULAR" in msg
        assert "solver helper" in msg

    def test_two_solver_helpers_same_attribute_is_conflict(self):
        with pytest.raises(RemapConflictError) as exc_info:
            compute_remap_plan(
                [
                    _reg("combiner_1", pub=_attr("a"), priority=int(Priority.SOLVER_HELPER)),
                    _reg("combiner_2", pub=_attr("a"), priority=int(Priority.SOLVER_HELPER)),
                ]
            )
        err = exc_info.value
        assert err.priority == int(Priority.SOLVER_HELPER)
        assert err.models == ("combiner_1", "combiner_2")

    def test_three_way_conflict_lists_all(self):
        with pytest.raises(RemapConflictError) as exc_info:
            compute_remap_plan(
                [
                    _reg("a", pub=_attr("x")),
                    _reg("b", pub=_attr("x")),
                    _reg("c", pub=_attr("x")),
                ]
            )
        assert exc_info.value.models == ("a", "b", "c")
        # Three publishers is "all publish", not "both publish" — verbiage cleanup
        # from the adversarial review.
        assert "all publish" in str(exc_info.value)

    def test_non_top_level_multiple_publishers_is_not_a_conflict(self):
        # Two priority-10 publishers + one priority-20 owner is the canonical combiner
        # case; it must NOT raise — that's the whole point of the proposal.
        plan = compute_remap_plan(
            [
                _reg("model_a", pub=_attr("a")),
                _reg("model_a2", pub=_attr("a")),
                _reg("combiner_a", pub=_attr("a"), priority=int(Priority.SOLVER_HELPER)),
            ]
        )
        assert set(plan) == {"model_a", "model_a2", "combiner_a"}


class TestTwoLevelChain:
    def test_relaxer_case_from_proposal(self):
        # Per the iterative-relaxation worked example in the issue body.
        plan = compute_remap_plan(
            [
                _reg("model_a", pub=_attr("a"), sub=_attr("b")),
                _reg("model_b", pub=_attr("b"), sub=_attr("a")),
                _reg(
                    "relaxer_b",
                    pub=_attr("b"),
                    sub=None,
                    priority=int(Priority.SOLVER_HELPER),
                ),
            ]
        )
        assert set(plan) == {"model_b", "relaxer_b"}
        assert plan["model_b"] == RemapMessage(
            pub={"the_dataset": {"the_entities": {"b": "b:model_b:i"}}},
            sub=None,
        )
        assert plan["relaxer_b"] == RemapMessage(
            pub=None,
            sub={"the_dataset": {"the_entities": {"b:model_b:i": "b"}}},
        )

    def test_combiner_case_from_proposal(self):
        # Per the conflict-combiner worked example. model_a2 explicitly subscribes to "a"
        # for divergence tracking — the proposal keeps its sub mask untouched (the connector
        # never alters subs unless the REMAP says so), so model_a2 continues to receive the
        # canonical value via its original subscription.
        plan = compute_remap_plan(
            [
                _reg("model_a", pub=_attr("a"), sub=None),
                _reg("model_a2", pub=_attr("a"), sub=_attr("a")),
                _reg(
                    "combiner_a",
                    pub=_attr("a"),
                    sub=None,
                    priority=int(Priority.SOLVER_HELPER),
                ),
            ]
        )
        assert set(plan) == {"model_a", "model_a2", "combiner_a"}

        assert plan["model_a"] == RemapMessage(
            pub={"the_dataset": {"the_entities": {"a": "a:model_a:i"}}},
            sub=None,
        )
        assert plan["model_a2"] == RemapMessage(
            pub={"the_dataset": {"the_entities": {"a": "a:model_a2:i"}}},
            sub=None,
        )
        assert plan["combiner_a"] == RemapMessage(
            pub=None,
            sub={
                "the_dataset": {
                    "the_entities": {
                        "a:model_a:i": "a",
                        "a:model_a2:i": "a",
                    }
                }
            },
        )


class TestThreeLevelChain:
    def test_chain_routes_level_by_level(self):
        # Chain 10 -> 20 -> 30 with single publishers at each level. Per the proposal:
        # "All models at priority 10 publish to all models at priority 20, and all models
        # at priority 20 publish to the single model at priority 30 (highest priority)."
        plan = compute_remap_plan(
            [
                _reg("base", pub=_attr("b"), priority=10),
                _reg("helper", pub=_attr("b"), priority=20),
                _reg("converter", pub=_attr("b"), priority=30),
            ]
        )
        assert set(plan) == {"base", "helper", "converter"}
        # Bottom publishes its internal variant, no extra sub.
        assert plan["base"] == RemapMessage(
            pub={"the_dataset": {"the_entities": {"b": "b:base:i"}}},
            sub=None,
        )
        # Intermediate gets both: remapped pub AND a sub for the level below.
        assert plan["helper"] == RemapMessage(
            pub={"the_dataset": {"the_entities": {"b": "b:helper:i"}}},
            sub={"the_dataset": {"the_entities": {"b:base:i": "b"}}},
        )
        # Top (owner) keeps the canonical pub name; sub is the level-below internal.
        # Crucially the sub does NOT include "b:base:i" — that's the intermediate's job.
        assert plan["converter"] == RemapMessage(
            pub=None,
            sub={"the_dataset": {"the_entities": {"b:helper:i": "b"}}},
        )


class TestMultiAttributePublisher:
    def test_priority_applies_uniformly_across_pub_mask(self):
        # Kian's clarification (comment 5): a solver helper at priority 20 publishing both
        # "speed" and "flow" applies that priority uniformly; only attributes with conflicts
        # get remapped.
        plan = compute_remap_plan(
            [
                _reg("regular", pub={"ds": {"eg": ["speed"]}}),
                _reg(
                    "multi_helper",
                    pub={"ds": {"eg": ["speed", "flow"]}},
                    priority=int(Priority.SOLVER_HELPER),
                ),
            ]
        )
        # Only "speed" had a conflict; "flow" had a single (and therefore canonical)
        # publisher in the helper, so it stays unmapped.
        assert set(plan) == {"regular", "multi_helper"}
        assert plan["regular"] == RemapMessage(
            pub={"ds": {"eg": {"speed": "speed:regular:i"}}},
            sub=None,
        )
        assert plan["multi_helper"] == RemapMessage(
            pub=None,
            sub={"ds": {"eg": {"speed:regular:i": "speed"}}},
        )


class TestBackPropagation:
    def test_lower_priority_publisher_keeps_its_own_sub_mask(self):
        # Per the proposal: a non-owner publisher with an explicit canonical subscription
        # (for divergence tracking) does NOT get its sub mask altered by REMAP. The
        # connector simply never touches it, so the model continues to receive canonical
        # values via its original subscription.
        plan = compute_remap_plan(
            [
                _reg("model_a2", pub=_attr("a"), sub=_attr("a")),
                _reg("model_a", pub=_attr("a")),
                _reg("combiner", pub=_attr("a"), priority=int(Priority.SOLVER_HELPER)),
            ]
        )
        assert plan["model_a2"].sub is None

    def test_higher_priority_subscriber_canonical_preserved(self):
        # A higher-priority model that explicitly subscribed to the canonical name in
        # READY gets that canonical preserved in the sub remap (as ``{canonical: canonical}``)
        # so the connector ends up subscribed to BOTH the variants and the canonical. See
        # the proposal's "Backpropagating results" section.
        plan = compute_remap_plan(
            [
                _reg("model_a", pub=_attr("a")),
                _reg("model_a2", pub=_attr("a")),
                _reg(
                    "combiner_a",
                    pub=_attr("a"),
                    sub=_attr("a"),
                    priority=int(Priority.SOLVER_HELPER),
                ),
            ]
        )
        assert plan["combiner_a"].sub == {
            "the_dataset": {
                "the_entities": {
                    "a:model_a:i": "a",
                    "a:model_a2:i": "a",
                    "a": "a",
                }
            }
        }

    def test_no_back_propagation_when_publisher_did_not_subscribe(self):
        plan = compute_remap_plan(
            [
                _reg("model_a", pub=_attr("a")),
                _reg("model_b", pub=_attr("a")),
                _reg("combiner", pub=_attr("a"), priority=int(Priority.SOLVER_HELPER)),
            ]
        )
        assert plan["model_a"].sub is None
        assert plan["model_b"].sub is None


class TestMaskHandling:
    def test_none_masks_are_ignored(self):
        # A model with no pub mask is a pure subscriber; it can never participate in a
        # conflict.
        plan = compute_remap_plan(
            [
                _reg("collector", pub=None, sub=None),
                _reg("producer", pub=_attr("x")),
            ]
        )
        assert plan == {}

    def test_empty_pub_section_is_ignored(self):
        plan = compute_remap_plan(
            [
                _reg("a", pub={"ds": {"eg": []}}),
                _reg("b", pub=_attr("x")),
            ]
        )
        assert plan == {}

    def test_multiple_datasets_resolved_independently(self):
        plan = compute_remap_plan(
            [
                _reg("a", pub={"ds1": {"eg": ["x"]}}),
                _reg("b", pub={"ds2": {"eg": ["x"]}}),
            ]
        )
        # Same attribute name in different datasets is a different attribute — no conflict.
        assert plan == {}

    def test_multiple_entity_groups_resolved_independently(self):
        # Same attribute name in different entity groups of the same dataset is also a
        # different attribute and resolves independently. Adversarial-review minor finding.
        plan = compute_remap_plan(
            [
                _reg("a", pub={"ds": {"eg1": ["x"], "eg2": ["x"]}}),
                _reg(
                    "b",
                    pub={"ds": {"eg1": ["x"], "eg2": ["x"]}},
                    priority=int(Priority.SOLVER_HELPER),
                ),
            ]
        )
        assert plan["a"].pub == {"ds": {"eg1": {"x": "x:a:i"}, "eg2": {"x": "x:a:i"}}}
        assert plan["b"].sub == {"ds": {"eg1": {"x:a:i": "x"}, "eg2": {"x:a:i": "x"}}}


class TestBackPropagationPartial:
    def test_only_subscribed_attributes_get_canonical_preserved(self):
        # A higher-priority subscriber that subs to only some of the conflicted attributes
        # gets canonical preservation only for those — not for the others. Adversarial-
        # review minor finding.
        plan = compute_remap_plan(
            [
                _reg("publisher_x", pub={"ds": {"eg": ["x"]}}),
                _reg("publisher_y", pub={"ds": {"eg": ["y"]}}),
                _reg(
                    "owner",
                    pub={"ds": {"eg": ["x", "y"]}},
                    sub={"ds": {"eg": ["x"]}},
                    priority=int(Priority.SOLVER_HELPER),
                ),
            ]
        )
        assert plan["owner"].sub == {
            "ds": {
                "eg": {
                    "x:publisher_x:i": "x",
                    "x": "x",
                    "y:publisher_y:i": "y",
                }
            }
        }
