from __future__ import annotations

import functools
import inspect
import typing as t
from abc import ABC, abstractmethod

T = t.TypeVar("T")
E = t.TypeVar("E")


class FSMError(Exception):
    pass


class FSMStarted(FSMError):
    pass


class FSMDone(FSMError):
    pass


def send_silent(coro: t.Generator, value: t.Any):
    try:
        coro.send(value)
    except StopIteration:
        pass


def fsm_conditional_raise(func=None, attribute: str = None, exc: t.Type[Exception] = None):
    if func is None:
        return functools.partial(fsm_conditional_raise, attribute=attribute, exc=exc)

    @functools.wraps(func)
    def wrapper(fsm: FSM, *args, **kwargs):
        if getattr(fsm, attribute):
            raise exc()
        return func(fsm, *args, **kwargs)

    return wrapper


not_started = fsm_conditional_raise(attribute="started", exc=FSMStarted)
not_done = fsm_conditional_raise(attribute="done", exc=FSMDone)


class FSM(t.Generic[T, E]):
    def __init__(self, initial_state: t.Type[State], context: T = None, raise_on_done=True):
        self.context = context
        self.state = initial_state(context=self.context)
        self.runner = None
        self.started = False
        self.done = False
        self.raise_on_done = raise_on_done

    @not_done
    @not_started
    def start(self):
        self.started = True
        self.runner = self._run()
        send_silent(self.runner, None)

    def _run(self):
        try:
            while True:
                if inspect.isgeneratorfunction(self.state.run):
                    yield from self.state.run()
                else:
                    self.state.run()
                self.transition()
        except FSMDone:
            self.done = True
            if self.raise_on_done:
                raise

    @not_done
    def send(self, event: E):
        send_silent(self.runner, event)

    def transition(self):
        if new_state := next_state(self.state):
            self.state = new_state(self.context)


def next_state(state: State) -> t.Optional[t.Type[State]]:
    for cond, new_state in state.transitions():
        if cond(state.context):
            return new_state
    return None


class Event:
    pass


class State(ABC, t.Generic[T]):
    def __init__(self, context: T):
        self.context = context
        self.on_enter()

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


TransitionsT = t.List[t.Tuple[t.Type[Condition], t.Type[State]]]
