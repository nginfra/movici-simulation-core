import numpy as np
import pytest

from movici_simulation_core.models.udf_model.functions import IGNORE_FLOATING_POINT_ERRORS


@pytest.fixture(autouse=True)
def ignore_floating_point_errors():
    """Dividing by zero and overflowing are not errors in an expression, they produce an undefined
    value. A compiled expression silences numpy's warnings about them itself, once per evaluation,
    but the tests here also call the functions behind the operators directly.
    """
    with np.errstate(**IGNORE_FLOATING_POINT_ERRORS):
        yield
