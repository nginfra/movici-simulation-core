import functools
import inspect
import warnings

deprecation_warning = functools.partial(warnings.warn, category=DeprecationWarning, stacklevel=2)


def deprecated(obj=None, alternative: str = None):
    if obj is None:
        return functools.partial(deprecated, alternative=alternative)

    def do_warn(old_name):
        deprecation_warning(f"'{old_name}' is deprecated, use '{alternative}' instead ")

    if inspect.isclass(obj):

        @functools.wraps(obj, updated=())
        class ClassWrapper(obj):
            def __new__(cls, *args, **kwargs):
                do_warn(obj.__name__)
                if obj.__new__ is object.__new__:
                    return obj.__new__(cls)
                return obj.__new__(cls, *args, **kwargs)

        return ClassWrapper

    if any(
        (
            inspect.isfunction(obj),
            inspect.ismethod(obj),
            hasattr(obj, "__func__"),  # classmethod
            hasattr(obj, "fget"),  # property
        )
    ):

        @functools.wraps(obj, updated=())
        class FunctionWrapper:
            __deprecated__ = True

            def __init__(self, obj):
                self.obj = obj
                self.owner = None

            def __get__(self, instance, owner):
                if hasattr(self.obj, "__func__"):
                    func_name = self.obj.__func__.__name__
                elif hasattr(self.obj, "fget"):
                    func_name = self.obj.fget.__name__
                else:
                    func_name = self.obj.__name__

                if self.owner is not None:
                    owner_name = self.owner.__name__
                else:
                    owner_name = owner.__name__
                do_warn(owner_name + "." + func_name)
                return self.obj.__get__(instance, owner)

            def __call__(self, *args, **kwargs):
                do_warn(self.obj.__name__)
                return self.obj(*args, **kwargs)

            def set_owner(self, owner):
                self.owner = owner

        return FunctionWrapper(obj)

    raise TypeError(f"unsupported type for {obj}, must be a class, method or function")


def has_deprecations(cls):
    for attr in vars(cls).values():
        if getattr(attr, "__deprecated__", False) and hasattr(attr, "set_owner"):
            attr.set_owner(cls)
    return cls
