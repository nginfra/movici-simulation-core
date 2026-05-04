import typing as t

import numpy as np

PointLike = t.Union[t.Tuple[float, float], t.List[float], np.ndarray]


class PointGenerator:
    """
    Since aequilibrae can't work with overlapping points
    we have to be able to generate unique points
    """

    def __init__(self, increment: float = 0.001) -> None:
        self._increment = increment
        self._points: t.Set[t.Tuple[float, float]] = set()

    def add_point(self, point: PointLike) -> None:
        if isinstance(point, np.ndarray):
            point = point.tolist()
        if isinstance(point, list):
            point = tuple(point)

        self._points.add(point)

    def add_points(self, points: t.Union[t.List[PointLike], np.ndarray]) -> None:
        if isinstance(points, np.ndarray):
            points = points.tolist()

        for point in points:
            self.add_point(point)

    def generate_and_add(self, reference_point: PointLike) -> np.ndarray:
        reference_point = np.asarray(reference_point, dtype=float)
        if reference_point.shape != (2,):
            raise TypeError("reference point must contain a single x and y value")

        new_point = reference_point
        while tuple(new_point) in self._points:
            new_point += [self._increment, self._increment]
        self.add_point(new_point)
        return new_point

    @property
    def point_count(self) -> int:
        return len(self._points)
