from dataclasses import dataclass, field
from unittest.mock import Mock

import pytest

from movici_simulation_core.exceptions import FSMDone, FSMStarted
from movici_simulation_core.services.orchestrator.fsm import (
    FSM,
    Always,
    Condition,
    FSMConfig,
    State,
)


class Event:
    pass


@dataclass
class DummyContext:
    states: list = field(default_factory=list)
    events: list = field(default_factory=list)


class DummyState(State[DummyContext]):
    is_final = False

    def run(self):
        self.context.states.append(type(self))
        if self.is_final:
            raise FSMDone

    on_enter = Mock()


@pytest.fixture(autouse=True)
def reset_mock():
    DummyState.on_enter.reset_mock()


class EventState(State[DummyContext]):
    requires_event = True
    is_final = False

    def handle_event(self, event):
        self.context.states.append(type(self))
        self.context.events.append(event)
        if self.is_final:
            raise FSMDone


def test_calls_on_enter_when_starting():
    class StateA(DummyState):
        is_final = True
        on_enter = Mock()

    fsm = FSM(
        FSMConfig(initial_state=StateA, states={StateA: []}),
        context=DummyContext(),
        raise_on_done=False,
    )
    fsm.start()
    assert StateA.on_enter.call_count == 1


def test_calls_on_enter_when_transitioning():
    class StateA(DummyState):
        pass

    class StateB(DummyState):
        on_enter = Mock()
        is_final = True

    fsm = FSM(
        FSMConfig(
            initial_state=StateA,
            states={
                StateA: [(Always, StateB)],
                StateB: [],
            },
        ),
        context=DummyContext(),
        raise_on_done=False,
    )
    fsm.start()
    assert StateB.on_enter.call_count == 1


def test_fsm_runs_a_state():
    class StateA(DummyState):
        is_final = True

    fsm = FSM(
        FSMConfig(initial_state=StateA, states={StateA: []}),
        context=DummyContext(),
        raise_on_done=False,
    )
    fsm.start()
    assert fsm.context.states == [StateA]


def test_fsm_does_a_transition():
    class StateA(DummyState):
        pass

    class StateB(DummyState):
        is_final = True

    fsm = FSM(
        FSMConfig(
            initial_state=StateA,
            states={
                StateA: [(Always, StateB)],
                StateB: [],
            },
        ),
        context=DummyContext(),
        raise_on_done=False,
    )
    fsm.start()
    assert fsm.context.states == [StateA, StateB]


def test_fsm_calls_on_enter_on_transition():
    class StateA(DummyState):
        pass

    class StateB(DummyState):
        is_final = True
        on_enter = Mock()

    assert StateA.on_enter is not StateB.on_enter

    fsm = FSM(
        FSMConfig(
            initial_state=StateA,
            states={
                StateA: [(Always, StateB)],
                StateB: [],
            },
        ),
        context=DummyContext(),
        raise_on_done=False,
    )
    fsm.start()
    assert StateB.on_enter.call_count == 1


def test_fsm_doensnt_call_on_enter_when_not_transitioning():
    class StateA(DummyState):
        def run(self):
            super().run()
            self.is_final = True

    context = DummyContext()
    fsm = FSM(
        FSMConfig(
            initial_state=StateA,
            states={
                StateA: [],
            },
        ),
        context=context,
        raise_on_done=False,
    )
    fsm.start()
    assert context.states == [StateA, StateA]
    assert StateA.on_enter.call_count == 1


def test_evented_state_handles_event():
    class StateA(EventState):
        is_final = True

    event = Event()
    fsm = FSM(
        FSMConfig(
            initial_state=StateA,
            states={
                StateA: [],
            },
        ),
        context=DummyContext(),
        raise_on_done=False,
    )
    fsm.start()
    fsm.handle_event(event)
    assert fsm.context.events == [event]


def test_fsm_runs_until_event_required():
    class StateA(DummyState):
        pass

    class StateB(EventState):
        pass

    fsm = FSM(
        FSMConfig(
            initial_state=StateA,
            states={
                StateA: [(Always, StateB)],
                StateB: [],
            },
        ),
        context=DummyContext(),
        raise_on_done=False,
    )
    fsm.start()
    assert fsm.context.states == [StateA]
    assert isinstance(fsm.state, StateB)


def test_fsm_does_more_complex_transitions():
    """An FSM that goes A -event-> B -> A -event-> C"""

    class HaventTransitionedToB(Condition):
        def met(self) -> bool:
            return StateB not in self.context.states

    class StateA(EventState):
        pass

    class StateB(DummyState):
        pass

    class StateC(DummyState):
        is_final = True

    fsm = FSM(
        FSMConfig(
            StateA,
            states={
                StateA: [
                    (HaventTransitionedToB, StateB),
                    (Always, StateC),
                ],
                StateB: [
                    (Always, StateA),
                ],
                StateC: [],
            },
        ),
        context=DummyContext(),
        raise_on_done=False,
    )
    fsm.start()
    one = Event()
    two = Event()
    fsm.handle_event(one)
    fsm.handle_event(two)

    assert fsm.context.states == [StateA, StateB, StateA, StateC]
    assert fsm.context.events == [one, two]


def test_fsm_raises_when_trying_to_send_when_done():
    class DoneState(DummyState):
        is_final = True

    fsm = FSM(
        FSMConfig(
            DoneState,
            states={DoneState: []},
        ),
        context=DummyContext(),
        raise_on_done=False,
    )
    fsm.start()
    with pytest.raises(FSMDone):
        fsm.handle_event(Event())


def test_fsm_raises_when_trying_to_start_twice():
    class SomeState(EventState):
        pass

    class FinalState(DummyState):
        is_final = True

    fsm = FSM(
        FSMConfig(
            SomeState,
            states={
                SomeState: [(Always, FinalState)],
                FinalState: [],
            },
        ),
        context=DummyContext(),
        raise_on_done=False,
    )
    fsm.start()

    with pytest.raises(FSMStarted):
        fsm.start()

    fsm.handle_event(Event())

    with pytest.raises(FSMDone):
        fsm.start()


class TestFSMConfig:
    def test_validates_initial_state(self):
        class StateA(State):
            def run(self):
                pass

        class StateB(State):
            def run(self):
                pass

        with pytest.raises(ValueError, match="StateA is not a member of 'states"):
            FSMConfig(initial_state=StateA, states={StateB: []})

    def test_all_transition_states_are_given(self):
        class StateA(State):
            def run(self):
                pass

        class StateB(State):
            def run(self):
                pass

        with pytest.raises(ValueError, match="State StateB was mentioned in a transition"):
            FSMConfig(initial_state=StateA, states={StateA: [(Always, StateB)]})

    def test_validates_require_event_state_has_handle_event_method(self):
        class StateA(State):
            requires_event = True

            def run(self):
                pass

        with pytest.raises(ValueError, match="did not implement a 'handle_event' method"):
            FSMConfig(initial_state=StateA, states={StateA: []})

    def test_validates_not_require_event_state_has_run_method(self):
        class StateA(State):
            requires_event = False

            def handle_event(self, event):
                pass

        with pytest.raises(ValueError, match="did not implement a 'run' method"):
            FSMConfig(initial_state=StateA, states={StateA: []})
