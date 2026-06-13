from __future__ import annotations

import contextlib
import dataclasses
import itertools
import typing as t
from abc import ABC, abstractmethod

from movici_simulation_core.exceptions import FSMDone, FSMError, FSMException, FSMStarted

T = t.TypeVar("T")
E = t.TypeVar("E")


@dataclasses.dataclass
class FSMConfig(t.Generic[T]):
    """A config for setting up a :class:`FSM` final state machine

    :param initial_state: the initial state
    :param states: a dictionary of all possible states as ``type``s and their transitions.
        Transitions are a sequence of ``(type[Condition], type[State])`` tuples
    :param strict: a boolean whether to validate that all states mentioned in the transitions
        and ``initial`` state must have an entry in the states  dictionary
    """

    initial_state: type[State[T]]
    states: dict[type[State[T]], TransitionsT] = dataclasses.field(default_factory=dict)
    strict: bool = True

    def __post_init__(self):
        if not self.strict:
            return
        if self.initial_state not in self.states:
            raise ValueError(
                f"'initial_state' {self.initial_state.__name__} is not a member of 'states' "
                "and 'strict' was set"
            )
        for _, state in itertools.chain.from_iterable(self.states.values()):
            if state not in self.states:
                raise ValueError(
                    f"State {state.__name__} was mentioned in a transition but it is not a member "
                    "of 'states' and 'strict' was set"
                )


class FSM(t.Generic[T, E]):
    state: State[T]

    def __init__(self, config: FSMConfig[T], context: T = None, raise_on_done=True):

        self.context = context
        self.config = config
        self.state = config.initial_state(context=self.context)
        self.started = False
        self.done = False
        self.failure = False
        self.raise_on_done = raise_on_done

    def start(self):
        self.ensure_not_done()
        self.ensure_not_started()
        self.started = True
        with self.catch_fsmexceptions():
            self.state.on_enter()
            self.run_until_event_required()

    def handle_event(self, event: E):
        self.ensure_not_done()
        assert self.state.requires_event

        with self.catch_fsmexceptions():
            self.state.handle_event(event)
            self.state = self.transition()
            self.run_until_event_required()

    def run_until_event_required(self):
        while not self.state.requires_event:
            self.state.run()
            self.state = self.transition()

    @contextlib.contextmanager
    def catch_fsmexceptions(self):
        try:
            yield
        except FSMException as e:
            self.done = True
            if isinstance(e, FSMError):
                self.failure = True

            if self.raise_on_done:
                raise

    def transition(self):
        if new_state := next_state(self.context, self.config.states.get(type(self.state), [])):
            self.state = new_state(self.context)
            self.state.on_enter()
        return self.state

    def ensure_not_started(self):
        if self.started:
            raise FSMStarted()

    def ensure_not_done(self):
        if self.done:
            raise FSMDone()


def next_state(context, transitions: TransitionsT):
    for cond, new_state in transitions:
        if cond(context):
            return new_state
    return None


class State(ABC, t.Generic[T]):
    requires_event = False

    def __init__(self, context: T):
        self.context = context

    def run(self):
        raise NotImplementedError

    def handle_event(self, event: t.Any):
        raise NotImplementedError

    def on_enter(self):
        pass


class Condition(ABC, t.Generic[T]):
    def __init__(self, context: T):
        self.context = context

    @abstractmethod
    def met(self) -> bool:
        raise NotImplementedError

    def __bool__(self):
        return self.met()


class Always(Condition):
    def met(self):
        return True


TransitionsT = t.Sequence[tuple[type[Condition], type[State]]]
