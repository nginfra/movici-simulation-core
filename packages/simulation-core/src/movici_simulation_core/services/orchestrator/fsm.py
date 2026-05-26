from __future__ import annotations

import dataclasses
import functools
import inspect
import itertools
import typing as t
from abc import ABC, abstractmethod

from movici_simulation_core.exceptions import FSMDone, FSMError, FSMException, FSMStarted

T = t.TypeVar("T")
E = t.TypeVar("E")


def send_silent(coro: t.Generator, value: t.Any):
    try:
        coro.send(value)
    except StopIteration:
        pass


def fsm_conditional_raise(attribute: str, exc: t.Type[Exception]):
    def _decorator(func):
        @functools.wraps(func)
        def wrapper(fsm: FSM, *args, **kwargs):
            if getattr(fsm, attribute):
                raise exc()
            return func(fsm, *args, **kwargs)

        return wrapper

    return _decorator


not_started = fsm_conditional_raise(attribute="started", exc=FSMStarted)
not_done = fsm_conditional_raise(attribute="done", exc=FSMDone)


@dataclasses.dataclass
class FSMConfig(t.Generic[T]):
    """A config for setting up a :class:`FSM` final state machine

    :param initial_state: the initial state
    :param states: a dictionary of all possible states as ``type``s and their transitions.
        Transitions are a sequence of ``(type[Condition], type[State])`` tuples
    :pararm strict: a boolean whether to validate that all states mentioned in the transitions
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
                    f"State {state.__name__} was mentioned in a transition but it is not a member"
                    "of 'states' and 'strict' was set"
                )


class FSM(t.Generic[T, E]):
    def __init__(
        self,
        config: FSMConfig[T],
        context: T = None,
        raise_on_done=True,
    ):
        self.context = context
        self.config = config
        self.state = config.initial_state(context=self.context)
        self.runner = None
        self.started = False
        self.done = False
        self.failure = False
        self.raise_on_done = raise_on_done

    @not_done
    @not_started
    def start(self):
        self.started = True
        self.runner = self._run()
        send_silent(self.runner, None)

    def _run(self):
        try:
            self.state.on_enter()
            while True:
                if inspect.isgeneratorfunction(self.state.run):
                    yield from self.state.run()
                else:
                    self.state.run()
                self.transition()
        except FSMException as e:
            self.done = True
            if isinstance(e, FSMError):
                self.failure = True

            if self.raise_on_done:
                raise

    @not_done
    def send(self, event: E):
        assert self.runner is not None
        send_silent(self.runner, event)

    def transition(self):
        if new_state := next_state(self.context, self.config.states.get(type(self.state), [])):
            self.state = new_state(self.context)
            self.state.on_enter()


def next_state(context, transitions: TransitionsT):
    for cond, new_state in transitions:
        if cond(context):
            return new_state
    return None


class Event:
    pass


class State(ABC, t.Generic[T]):
    def __init__(self, context: T):
        self.context = context

    def on_enter(self):
        pass

    @abstractmethod
    def run(self):
        raise NotImplementedError

    def transitions(self) -> TransitionsT:
        return []


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
