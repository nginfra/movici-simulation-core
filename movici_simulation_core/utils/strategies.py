import typing as t

instances = {}
types = {}

T = t.TypeVar("T")


def reset():
    global instances, types
    instances = {}
    types = {}


def get_type(strat: t.Type[T]) -> t.Type[T]:
    return types[strat]


def get_instance(strat: t.Type[T], **kwargs) -> T:
    try:
        return instances[strat]
    except KeyError:
        inst = types[strat](**kwargs)
        set(inst)
        return inst


def set(strat):
    if not isinstance(strat, type):
        cls = type(strat)
        for base in cls.__mro__:
            instances[base] = strat
    else:
        cls = strat

    for base in cls.__mro__:
        types[base] = cls
