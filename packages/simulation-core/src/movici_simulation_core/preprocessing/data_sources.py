import typing as t
from pathlib import Path

import geopandas
import netCDF4
import numpy as np
import pandas as pd
from pyproj import CRS

from movici_simulation_core.attributes import (
    Geometry_Linestring2d,
    Geometry_Linestring3d,
    Geometry_Polygon2d,
    Geometry_Polygon3d,
    Geometry_X,
    Geometry_Y,
    Geometry_Z,
    Grid_GridPoints,
)

GeometryType = t.Literal["points", "lines", "polygons", "cells"]


class MultiEntitySource:
    r"""Base class for data sources that provide multiple entity types from a single file or
    connection, such as a network file that contains both node and link collections.

    Use bracket notation to access individual entity types as ``DataSource``\s::

        source = MySource("network.file")
        nodes = source["nodes"]  # returns a DataSource

    In dataset creator configs, use dot notation to reference entity types::

        {"source": "network.nodes"}
    """

    def keys(self) -> t.Iterable[str]:
        """Return the available entity type names."""
        raise NotImplementedError

    def __getitem__(self, entity_type: str) -> "DataSource":
        """Return a ``DataSource`` for the given entity type."""
        raise NotImplementedError

    def __contains__(self, entity_type: str) -> bool:
        """Check whether an entity type is available."""
        raise NotImplementedError

    def to_crs(self, crs: t.Union[str, int, "CRS"]) -> None:
        """Convert all sub-sources to the target CRS."""
        return None

    def get_bounding_box(self) -> t.Optional[t.Tuple[float, float, float, float]]:
        """Return the combined bounding box across all entity types, or ``None``."""
        return None


def resolve_source(name: str, sources: "SourcesDict") -> "DataSource":
    """Resolve a source reference to a ``DataSource``.

    Supports dot notation for multi-entity sources: ``"source_name.entity_type"``.

    :param name: Source reference, optionally with dot notation
    :param sources: The sources dictionary
    :raises ValueError: If the source or entity type is not found
    :raises TypeError: If a bare name references a ``MultiEntitySource``
    """
    if "." in name:
        source_name, entity_type = name.split(".", 1)
        try:
            source = sources[source_name]
        except KeyError:
            raise ValueError(f"Source '{source_name}' not available") from None
        if not isinstance(source, MultiEntitySource):
            raise TypeError(
                f"Source '{source_name}' is not a multi-entity source, "
                f"cannot select entity type '{entity_type}'"
            )
        try:
            return source[entity_type]
        except KeyError:
            raise ValueError(
                f"Entity type '{entity_type}' not found in source '{source_name}'"
            ) from None

    try:
        source = sources[name]
    except KeyError:
        raise ValueError(f"Source '{name}' not available") from None

    if isinstance(source, MultiEntitySource):
        available = ", ".join(sorted(source.keys()))
        raise TypeError(
            f"Source '{name}' is a multi-entity source; "
            f"use '{name}.<entity_type>' to select an entity type "
            f"(available: {available})"
        )
    return source


class DataSource:
    r"""Base class for creating custom ``DataSource``\s. Subclasses must implement
    ``get_attribute`` and ``__len``. In case the ``DataSource`` handles geospatial data, subclasses
    must also implement ``to_crs``, ``get_geometry`` and ``get_bounding_box``
    """

    def get_attribute(self, name: str):
        """Return a property as a ``list`` of values from the source data, one entry per feature.

        :param name: The property name

        """
        raise NotImplementedError

    def to_crs(self, crs: t.Union[str, int, CRS]) -> None:
        """Convert the source geometry data the coordinate reference system specified in the
        ``crs`` argument

        :param crs: The CRS to convert to, either a CRS string (eg. "WGS 84" or "EPSG:28992")
          or an EPSG code integer (eg. 4326).

        """
        return None

    def get_geometry(self, geometry_type: GeometryType) -> t.Optional[dict]:
        """Return the geometry of the source features as a dictionary attribute lists. The
        resulting dictionary should have attributes based on the ``geometry_type``:

        * ``points``: ``geometry.x``, ``geometry.y`` and optionally ``geometry.z``
        * ``lines``: either ``geometry.linestring_2d`` or ``geometry.linestring_3d``
        * ``polygons``: ``geometry.polygon``

        See :ref:`movici-geometries` for more information on geometry attributes.

        This method may raise an Exception if a ``geometry_type`` is requested that does not match
        the source geometry.

        :param geometry_type: One of ``points``, ``lines``, ``polygons`` or ``cells``
        """
        raise ValueError("No geometry available")

    def get_bounding_box(self) -> t.Optional[t.Tuple[float, float, float, float]]:
        """Return the bounding box that envelops all geospatial features in the source data

        :return: A bounding box as a tuple of four values: (min_x, min_y, max_x, max_y) or ``None``
          in case no bounding box can be calculated
        """
        return None

    def __len__(self):
        """Return the number of features in the source data"""
        raise NotImplementedError


class NumpyDataSource(DataSource):
    """DataSource for non-geospatial Numpy or pandas data

    :param data: Either a dictionary ``typing.Dict[str, np.ndarray]`` with keys being the property
        names and the values being the property data array or a Pandas dataframe
    """

    def __init__(self, data: t.Mapping[str, np.ndarray] | pd.DataFrame) -> None:
        self.data = data

    def get_attribute(self, name: str):
        try:
            return self.data[name].tolist()
        except KeyError as e:
            raise ValueError(f"'{name}' was not found as a property") from e

    def __len__(self):
        # this ensures compatibility with both a dictionary of numpy arrays an pandas.DataFrame
        return len(self.data[next(iter(self.data.keys()))])


PandasDataSource = NumpyDataSource


class GeopandasSource(DataSource):
    """DataSource for querying a ``geopandas.GeoDataFrame``"""

    def __init__(self, geodataframe: geopandas.GeoDataFrame):
        self.gdf = geodataframe

    @classmethod
    def from_source_info(cls, source_info):
        gdf = geopandas.read_file(source_info["path"])
        return cls(gdf)

    def to_crs(self, crs: t.Union[str, int, CRS]):
        self.gdf = self.gdf.to_crs(crs)

    def get_geometry(self, geometry_type: GeometryType):
        methods = {
            "points": self.get_points,
            "lines": self.get_lines,
            "polygons": self.get_polygons,
        }
        try:
            method = methods[geometry_type]
        except KeyError:
            raise ValueError(
                "Unknown geometry type, must be one of 'points', 'lines', or 'polygons"
            ) from None
        return method(self.gdf["geometry"])

    def get_points(self, geom):
        xs, ys, zs = [], [], []
        has_z = False
        for feat in geom:
            self.feature_type_or_raise(feat, "Point")

            xs.append(feat.x)
            ys.append(feat.y)
            if feat.has_z:
                has_z = True
                zs.append(feat.z)
            else:
                zs.append(None)

        rv = {
            Geometry_X.name: xs,
            Geometry_Y.name: ys,
        }
        if has_z:
            rv[Geometry_Z.name] = zs
        return rv

    def get_lines(self, geom):
        all_coordinates = []
        size = 3
        for feat in geom:
            self.feature_type_or_raise(feat, "LineString")

            coords = np.asarray(feat.coords)
            if coords.shape[1] == 2:
                size = 2
            all_coordinates.append(coords)

        attr = (Geometry_Linestring2d if size == 2 else Geometry_Linestring3d).name

        return {attr: [coord[:, :size].tolist() for coord in all_coordinates]}

    def get_polygons(self, geom):
        all_coordinates = []
        size = 3
        for feat in geom:
            self.feature_type_or_raise(feat, "Polygon")
            coords = np.asarray(feat.exterior.coords)
            if coords.shape[1] == 2:
                size = 2
            all_coordinates.append(coords)

        attr = (Geometry_Polygon2d if size == 2 else Geometry_Polygon3d).name

        return {attr: [coord[:, :size].tolist() for coord in all_coordinates]}

    def get_bounding_box(self):
        return self.gdf.total_bounds

    @staticmethod
    def _get_python_value(val):
        """coerce nan's into None and np scalars into python types"""
        if isinstance(val, (float, np.floating)) and np.isnan(val):
            return None
        if isinstance(val, np.generic):
            return val.item()
        return val

    def get_attribute(self, name: str):
        try:
            return [self._get_python_value(i) for i in self.gdf[name].array]
        except KeyError as e:
            raise ValueError(
                f"'{name}' was not found as a feature property, perhaps it has an "
                "incompatible data type and was not loaded"
            ) from e

    @staticmethod
    def feature_type_or_raise(feature, expected):
        if feature.geom_type != expected:
            raise TypeError(f"Invalid feature {feature.geom_type}, must be '{expected}'")

    def __len__(self):
        return len(self.gdf)


class NetCDFGridSource(DataSource):
    points: np.ndarray = None
    cells: np.ndarray = None

    def __init__(
        self, file: t.Union[Path, str], x_var="gridCellX", y_var="gridCellY", time_var="time"
    ):
        self.file = Path(file)
        self.data = {}
        self.x_var = x_var
        self.y_var = y_var
        self.time_var = time_var

    @classmethod
    def from_source_info(cls, source_info):
        args = {"file": source_info["path"]}
        for param in ("x_var", "y_var", "time_var"):
            if param in source_info:
                args[param] = source_info[param]
        return cls(**args)

    def get_attribute(self, name: str, time_idx=0):
        if name in self.data:
            full_data = self.data[name]
        else:
            full_data = self._read_netcdf([name])[name]
        return full_data[time_idx].tolist()

    def get_geometry(self, geometry_type: GeometryType) -> t.Optional[dict]:
        if geometry_type in ("points", "cells"):
            self._ensure_grid()

        if geometry_type == "points":
            return {
                Geometry_X.name: self.points[:, 0].tolist(),
                Geometry_Y.name: self.points[:, 1].tolist(),
            }
        if geometry_type == "cells":
            return {Grid_GridPoints.name: self.cells.tolist()}

        raise ValueError("Unknown geometry type, must be one of 'points' or 'cells'")

    def get_bounding_box(self) -> t.Optional[t.Tuple[float, float, float, float]]:
        self._ensure_grid()
        return (
            self.points[:, 0].min(),
            self.points[:, 1].min(),
            self.points[:, 0].max(),
            self.points[:, 1].max(),
        )

    def get_timestamps(self):
        return self._read_netcdf([self.time_var])[self.time_var].tolist()

    def _read_netcdf(self, attributes: t.Sequence[str]) -> t.Dict[str, np.ndarray]:
        rv = {}
        with netCDF4.Dataset(self.file, mode="r") as raw_data:
            for attr in attributes:
                rv[attr] = np.asarray(raw_data.variables[attr])
        self.data.update(rv)
        return rv

    def _ensure_grid(self):
        if self.points is not None and self.cells is not None:
            return
        data = self._read_netcdf((self.x_var, self.y_var))
        self.points, self.cells = self._create_grid(data[self.x_var], data[self.y_var])

    def _create_grid(self, xs, ys) -> t.Tuple[np.ndarray, np.ndarray]:
        coords = np.stack((xs, ys), axis=-1)
        coords_set = set()
        unique_coords = []
        for coord in coords.reshape(-1, *coords.shape[-1:]):
            tup = tuple(coord)
            if tup not in coords_set:
                coords_set.add(tup)
                unique_coords.append(tup)
        dict_coords = {(x, y): idx for idx, (x, y) in enumerate(unique_coords)}
        cells = [[dict_coords[(x, y)] for x, y in single_cell] for single_cell in coords]
        return np.array(unique_coords, dtype=float), np.array(cells, dtype=np.int32)


SourcesDict = t.MutableMapping[str, t.Union[DataSource, MultiEntitySource]]
