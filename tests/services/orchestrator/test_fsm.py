from dataclasses import dataclass, field
from unittest.mock import Mock

import pytest

from movici_simulation_core.services.orchestrator.fsm import (
    FSM,
    FSMDone,
    State,
    TransitionsT,
    Always,
    Event,
    FSMStarted,
    Condition,
)


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
    is_final = False

    def run(self):
        event = yield
        self.context.states.append(type(self))
        self.context.events.append(event)
        if self.is_final:
            raise FSMDone


def test_calls_on_enter_when_starting():
    class StateA(DummyState):
        is_final = True
        on_enter = Mock()

    fsm = FSM(StateA, context=DummyContext(), raise_on_done=False)
    fsm.start()
    StateA.on_enter.call_count == 1


def test_fsm_runs_a_state():
    class StateA(DummyState):
        is_final = True

    fsm = FSM(StateA, context=DummyContext(), raise_on_done=False)
    fsm.start()
    assert fsm.context.states == [StateA]


def test_fsm_does_a_transition():
    class StateA(DummyState):
        def transitions(self) -> TransitionsT:
            return [(Always, StateB)]

    class StateB(DummyState):
        is_final = True

    fsm = FSM(StateA, context=DummyContext(), raise_on_done=False)
    fsm.start()
    assert fsm.context.states == [StateA, StateB]


def test_fsm_calls_on_enter_on_transition():
    class StateA(DummyState):
        def transitions(self) -> TransitionsT:
            return [(Always, StateB)]

    class StateB(DummyState):
        is_final = True
        on_enter = Mock()

    assert StateA.on_enter is not StateB.on_enter

    fsm = FSM(StateA, context=DummyContext(), raise_on_done=False)
    fsm.start()
    assert StateB.on_enter.call_count == 1


def test_fsm_doensnt_call_on_enter_when_not_transitioning():
    class StateA(DummyState):
        def run(self):
            super().run()
            self.is_final = True

    context = DummyContext()
    fsm = FSM(StateA, context=context, raise_on_done=False)
    fsm.start()
    assert context.states == [StateA, StateA]
    assert StateA.on_enter.call_count == 1


def test_evented_state_handles_event():
    class StateA(EventState):
        is_final = True

    event = Event()
    fsm = FSM(StateA, DummyContext(), raise_on_done=False)
    fsm.start()
    fsm.send(event)
    assert fsm.context.events == [event]


def test_fsm_runs_until_event_required():
    class StateA(DummyState):
        def transitions(self) -> TransitionsT:
            return [(Always, StateB)]

    class StateB(EventState):
        pass

    fsm = FSM(StateA, DummyContext(), raise_on_done=False)
    fsm.start()
    assert fsm.context.states == [StateA]
    assert isinstance(fsm.state, StateB)


def test_fsm_does_more_complex_transitions():
    """An FSM that goes A -event-> B -> A -event-> C"""

    class HaventTransitionedToB(Condition):
        def met(self) -> bool:
            return StateB not in self.context.states

    class StateA(EventState):
        def transitions(self) -> TransitionsT:
            return [(HaventTransitionedToB, StateB), (Always, StateC)]

    class StateB(DummyState):
        def transitions(self) -> TransitionsT:
            return [(Always, StateA)]

    class StateC(DummyState):
        is_final = True

    fsm = FSM(StateA, DummyContext(), raise_on_done=False)
    fsm.start()
    one = Event()
    two = Event()
    fsm.send(one)
    fsm.send(two)

    assert fsm.context.states == [StateA, StateB, StateA, StateC]
    assert fsm.context.events == [one, two]


def test_fsm_raises_when_trying_to_send_when_done():
    class DoneState(DummyState):
        is_final = True

    fsm = FSM(DoneState, DummyContext(), raise_on_done=False)
    fsm.start()
    with pytest.raises(FSMDone):
        fsm.send(Event())


def test_fsm_raises_when_trying_to_start_twice():
    class SomeState(EventState):
        def transitions(self) -> TransitionsT:
            return [(Always, FinalState)]

    class FinalState(DummyState):
        is_final = True

    fsm = FSM(SomeState, DummyContext(), raise_on_done=False)
    fsm.start()

    with pytest.raises(FSMStarted):
        fsm.start()

    fsm.send(Event())

    with pytest.raises(FSMDone):
        fsm.start()
