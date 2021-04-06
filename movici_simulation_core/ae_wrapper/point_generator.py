from typing import Union, List, Tuple

import numpy as np

PointLike = Union[Tuple[float, float], List[float], np.ndarray]


class PointGenerator:
    """
    Since aequilibrae can't work with overlapping points
    we have to be able to generate unique points
    """

    def __init__(self, increment=0.001):
        self._increment = increment
        self._points = set()

    def add_point(self, point: PointLike):
        if isinstance(point, np.ndarray):
            point = point.tolist()
        if isinstance(point, list):
            point = tuple(point)

        self._points.add(point)

    def add_points(self, points: Union[List[PointLike], np.ndarray]):
        if isinstance(points, np.ndarray):
            points = points.tolist()

        for point in points:
            self.add_point(point)

    def generate_and_add(self, reference_point: Union[PointLike]) -> np.ndarray:
        if isinstance(reference_point, (list, tuple)):
            reference_point = np.array(reference_point)

        new_point = reference_point
        while tuple(new_point) in self._points:
            new_point += [self._increment, self._increment]
        self.add_point(new_point)
        return new_point

    @property
    def point_count(self):
        return len(self._points)
