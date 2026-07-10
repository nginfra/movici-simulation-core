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
        Transitions are a sequence of ``(type[Condition], type[State])`` tuples. When determining
        which State to transition to, the transitions are checked starting from the top entry in
        the transitions sequence. The FSM transitions to the state belonging to the first
        transition that is matched.
    :param strict: a boolean whether to validate that all states mentioned in the transitions
        and ``initial`` state must have an entry in the states  dictionary
    """

    initial_state: t.Type[State[T]]
    states: dict[t.Type[State[T]], TransitionsT] = dataclasses.field(default_factory=dict)
    strict: bool = True

    def __post_init__(self):
        if not self.strict:
            return
        if self.initial_state not in self.states:
            raise ValueError(
                f"'initial_state' {self.initial_state.__name__} is not a member of 'states' "
                "and 'strict' was set"
            )

        for state in self.states.keys():
            if not state.requires_event and state.run is State.run:
                raise ValueError(
                    f"State {state.__name__} has 'requires_event' unset but did not implement a"
                    " 'run' method"
                )
            if state.requires_event and state.handle_event is State.handle_event:
                raise ValueError(
                    f"State {state.__name__} has 'requires_event' set but did not implement a"
                    " 'handle_event' method"
                )

        for _, state in itertools.chain.from_iterable(self.states.values()):
            if state not in self.states:
                raise ValueError(
                    f"State {state.__name__} was mentioned in a transition but it is not a member "
                    "of 'states' and 'strict' was set"
                )


class FSM(t.Generic[T, E]):
    """Implementation of a Finite State Machine runner. Requires a ``FSMConfig`` as a definition
    of the available states and the possible transitions. The config contains an ``initial_state``
    that is entered when the ``FSM`` is started by invoking the :meth:`FSM.start` method. If the
    initial state is configured with ``requires_event=True``, then the ``FSM`` waits until the
    :meth:`FSM.handle_event` method is called upon which it will pass the event through to the
    active state by calling the state's ``handle_event`` method, which the State must have
    implemented if it has ``requires_event`` set to ``True``. If the active state does not have
    ``requires_event=True`` it will call the ``run`` method instead. After every state is invoked
    (by calling either the ``handle_event`` or ``run`` method) the configured transitions for the
    state (as given by the ``FSMConfig``) are evaluated against the context. The FSM transitions
    to State belonging to the first matched transition, which will become the active state. If no
    condition is matched, then the current state remains the active state for the next iteration.
    The FSM continues to call the active state's ``run`` method and transition until it encounters
    a state that has ``requires_event=True`` upon which it will wait for :meth:`FSM.handle_event`
    to be called.

    The FSM may terminate iff a state raises an ``FSMException``, usually ``FSMDone`` to indicate
    a normal end to the FSM, or ``FSMError`` in case of an abnormal end to the ``FSM``. If an
    ``FSMError`` was raised then the :attr:`FSM.failure` flag will be set. If no valid state ever
    raises an ``FSMException`` then the ``FSM`` may run indefinitely

    :param config: An ``FSMConfig`` for the finite state machine.
    :param context: An arbitrary, mutalbe object that is kept for the lifetime of the FSM. It can
        be used to store state that must be shared between States and will be used to evaluate any
        transition conditions
    :param raise_on_done: A boolean to indicate whether to raise an ``FSMException`` in case the
        FSM terminates. The exception will be the same as the exception that terminated the ``FSM``
    """

    state: State[T]

    def __init__(self, config: FSMConfig[T], context: T = None, raise_on_done=True):
        self.config = config
        self.context = context
        self.state = config.initial_state(context=self.context)
        self.started = False
        self.done = False
        self.failure = False
        self.raise_on_done = raise_on_done

    def start(self):
        """Start the FSM"""
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
    """Base class for FSM States. When subclassing a State, implement one of the ``run`` or
    ``handle_event`` methods. If a state is a transient state and needs to run its logic and
    transition to a new state immediately, implement the ``run`` method. If a state needs to wait
    for an event to be sent, set the ``State.requires_event`` class variable to ``True`` and
    implement the ``handle_event`` method
    """

    requires_event = False

    def __init__(self, context: T):
        self.context = context

    def run(self):
        """Entry point for a state that does not require an event. This method will be called
        unconditionally by the ``FSM`` when ``requires_event`` is set to ``False`` (the default).
        States that do no have ``requires_event`` set are generally transient states that need to
        run some logic before immediately transitioning to another state
        """
        raise NotImplementedError(
            f"'run' was called on an instance of {type(self).__name__} while it did not implement"
            f" the method. Either implement 'run', or set '{type(self).__name__}.requires_event'"
            " and implement 'handle_event'"
        )

    def handle_event(self, event: t.Any):
        """Entry point for a state that requires an event. This method will be called by the FSM
        when the class variable ``requires_event`` is set to ``True`` and it receives an event
        from upstream
        """
        raise NotImplementedError(
            f"'handle_event' was called on an instance of {type(self).__name__} while it did not"
            f" implement the method. Either implement 'handle_event', or set"
            f" '{type(self).__name__}.requires_event' and implement 'run'"
        )

    def on_enter(self):
        """Called once by the ``FSM`` when entering a state"""
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


TransitionsT = t.Sequence[tuple[t.Type[Condition], t.Type[State]]]
