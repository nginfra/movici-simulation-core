import numpy as np
import scipy.stats


def linreg(values):
    result = scipy.stats.linregress(values)
    return result.slope, result.intercept


_VALUES = [
    [0.5, 0.95],
    [0.75, 1.05],
    [1.0, 1.4],
    [1.25, 1.59],
    [1.5, 1.79],
    [1.75, 2.01],
    [2.0, 2.26],
]

A, B = linreg(_VALUES)
MIN_X = _VALUES[0][0]


def crowdedness(load_factor: np.ndarray):
    load_factor = np.array(load_factor, copy=True)
    load_factor[load_factor < MIN_X] = MIN_X
    return A * load_factor + B
