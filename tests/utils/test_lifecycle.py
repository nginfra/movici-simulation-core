import pytest

from movici_simulation_core.utils.lifecycle import deprecated, has_deprecations


@deprecated(alternative="new_func")
def old_func(a):
    return a


@deprecated(alternative="NewCls")
class OldCls:
    def __init__(self, a=None):
        self.a = a

    def method(self):
        return self.a


def match(old, new):
    return f"'{old}' is deprecated, use '{new}' instead"


def test_calling_deprecated_function_warns():
    with pytest.warns(DeprecationWarning, match=match("old_func", "new_func")):
        old_func(42)


def test_deprecated_function_still_works():
    with pytest.warns(DeprecationWarning):
        result = old_func(42)
    assert result == 42


def test_instantiating_deprecated_class_warns():
    with pytest.warns(DeprecationWarning, match=match("OldCls", "NewCls")):
        OldCls()


def test_deprecated_cls_still_works():
    with pytest.warns(DeprecationWarning, match=match("OldCls", "NewCls")):
        obj = OldCls(42)

    assert obj.method() == 42


def test_deprecated_cls_passes_instance_checks():
    with pytest.warns(DeprecationWarning, match=match("OldCls", "NewCls")):
        obj = OldCls()

    assert isinstance(obj, OldCls)


@pytest.mark.parametrize("method_type", (None, classmethod, staticmethod))
def test_methods(method_type):
    class Class:
        def old_method(self=None):
            return 42

    if method_type is not None:
        Class.old_method = method_type(Class.old_method)
        to_test = Class
    else:
        to_test = Class()

    Class.old_method = deprecated(Class.old_method, alternative="Class.other_method")

    with pytest.warns(
        DeprecationWarning,
        match=match("Class.old_method", "Class.other_method"),
    ):
        result = to_test.old_method()
    assert result == 42


def test_correctly_deprecates_methods_in_subclass():
    @has_deprecations
    class Class:
        @deprecated(alternative="new_method")
        def method(self):
            pass

    class Subclass(Class):
        pass

    with pytest.warns(DeprecationWarning, match=match("Class.method", "new_method")):
        Subclass().method()


def test_works_with_property_decorator():
    @has_deprecations
    class Class:
        @deprecated(alternative="Class.new_prop")
        @property
        def some_prop(self):
            return 12

    with pytest.warns(DeprecationWarning, match=match("Class.some_prop", "Class.new_prop")):
        result = Class().some_prop

    assert result == 12
