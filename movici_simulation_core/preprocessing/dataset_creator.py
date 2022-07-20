from __future__ import annotations

import functools
import itertools
import typing as t
from pathlib import Path

import geopandas
import numpy as np
import orjson as json
import pyproj
from jsonschema.validators import validator_for

from movici_simulation_core.attributes import (
    Geometry_Linestring2d,
    Geometry_Linestring3d,
    Geometry_Polygon,
    Geometry_X,
    Geometry_Y,
    Geometry_Z,
)
from movici_simulation_core.json_schemas import PATH

GeometryType = t.Literal["points", "lines", "polygons"]

_dataset_creator_schema = None


def get_dataset_creator_schema():
    global _dataset_creator_schema

    if _dataset_creator_schema is None:
        _dataset_creator_schema = json.loads(
            Path(PATH).joinpath("dataset_creator.json").read_text()
        )
    return _dataset_creator_schema


def create_dataset(config: dict, sources: t.Optional[SourcesDict] = None):
    r"""Shorthand function to create a entity-based Dataset from a dataset creator config
    dictionary. This is the preferred way of creating Datasets from dataset creator config as
    it requires the least amount of boilerplate code. ``DataSource``\s are created from the
    config ``__sources__`` field. However, it is also possible to provide (additional)
    ``DataSource``\s through the optional ``sources`` argument.

    :param config: a dataset creator config
    :param sources: (Optional) a dictionary with configured ``DataSource``\s

    :return: A entity based dataset in dictionary format
    """
    return DatasetCreator.with_default_operations(sources=sources).create(config)


class DatasetCreator:
    r"""Use DatasetCreator to convert different ``DataSource``\s into an entity-based Dataset.

    :param operations: The sequence of desired operations types
    :param sources: (Optional) a dictionary with configured ``DataSource``\s
    :param validate_config: validate any dataset creator configs

    """

    def __init__(
        self,
        operations: t.Sequence[t.Type[DatasetOperation]],
        sources: t.Optional[SourcesDict] = None,
        validate_config=True,
    ):
        self.operations = operations
        self.sources = sources or {}
        self.validate_config = validate_config

    def create(self, config: dict):
        if self.validate_config:
            schema = get_dataset_creator_schema()
            validator = validator_for(schema)(schema)
            validator.validate(config)

        dataset = {}
        return pipe((op(config) for op in self.operations), dataset, sources=self.sources)

    @staticmethod
    def default_operations():
        return (
            SourcesSetup,
            CRSTransformation,
            MetadataSetup,
            SpecialValueCollection,
            AttributeDataLoading,
            EnumConversion,
            BoundingBoxCalculation,
            IDGeneration,
            IDLinking,
        )

    @classmethod
    def with_default_operations(cls, **kwargs):
        r"""Alternative initializer that creates a DatasetCreator with all ``DatasetOperation``\s
        configured that provide full functionality to create datasets. This is the preferred way
        of instantiating ``DatasetCreator``.
        """
        return cls(
            cls.default_operations(),
            **kwargs,
        )


def pipe(operations: t.Sequence[callable], initial, **kwargs):
    return functools.reduce(lambda obj, op: op(obj, **kwargs), operations, initial)


class DatasetOperation:
    def __init__(self, config):
        self.config = config

    def __call__(self, dataset: dict, sources: SourcesDict) -> dict:
        raise NotImplementedError


class SourcesSetup(DatasetOperation):
    r"""The ``SourcesSetup`` operation is responsible for reading the ``__sources__`` field of the
    config and create ``DatasetSource``\s from it
    """

    def __call__(self, dataset: dict, sources: SourcesDict) -> dict:
        read_sources = self.config.get("__sources__", {})
        for (key, source_info) in read_sources.items():
            if key not in sources:
                source = self.make_source(source_info)
                sources[key] = source
        return dataset

    def make_source(self, source_info):
        if isinstance(source_info, str):
            source_info = {"source_type": "file", "path": source_info}

        if source_info["source_type"] == "file":
            return GeopandasSource(geodataframe=geopandas.read_file(source_info["path"]))

    @staticmethod
    def get_file_path(path_str):
        path = Path(path_str)
        if not path.is_file():
            raise ValueError(f"{path_str} is not a valid file")
        return path


class CRSTransformation(DatasetOperation):
    """The ``CRSTransformation`` operation converts every ``DatasetSource`` into the target-crs
    specified in the config
    """

    DEFAULT_CRS = "EPSG:28992"

    def __init__(self, config, default_crs=DEFAULT_CRS):
        super().__init__(config)
        self.default_crs = default_crs

    def __call__(self, dataset: dict, sources: SourcesDict) -> dict:
        crs_code = deep_get(self.config, "__meta__", "crs", default=self.default_crs)
        target_crs = pyproj.CRS.from_user_input(crs_code)
        dataset["epsg_code"] = target_crs.to_epsg()
        for source in sources.values():
            source.to_crs(target_crs)
        return dataset


class MetadataSetup(DatasetOperation):
    """``MetadataSetup`` copies the metadata fields from the config into the dataset, and/or fills
    them with their respective default values
    """

    _missing = object()
    keys = (
        ("general", _missing),
        ("name", _missing),
        ("display_name", _missing),
        ("version", 4),
    )

    def __call__(self, dataset: dict, sources: SourcesDict) -> dict:
        for (key, default) in self.keys:
            result = self.config.get(key, default)
            if result is self._missing:
                continue
            if callable(result):
                result = result()
            dataset[key] = result
        return dataset


class SpecialValueCollection(DatasetOperation):
    """``SpecialValueCollection`` compiles the ``general.special`` field in the dataset from the
    config. If a special value is defined both in the attribute as well as in the
    ``general.special`` field of the config, then the field in the config takes precedence
    """

    def __call__(self, dataset: dict, sources: SourcesDict) -> dict:
        result = {
            **self.extract_special_values(self.config["data"]),
            **deep_get(self.config, "general", "special", default={}),
        }
        if result:
            general = dataset.setdefault("general", {})
            general["special"] = result
        return dataset

    def extract_special_values(self, config: dict, key=None, level=0):
        if not config:
            return {}
        if level == 2:
            if isinstance(config, dict) and "special" in config:
                return {key: config["special"]}
            return {}
        else:
            return functools.reduce(
                lambda prev, curr: {**prev, **curr},
                (
                    self.extract_special_values(
                        conf, key=f"{key}.{new_key}" if key else new_key, level=level + 1
                    )
                    for new_key, conf in config.items()
                    if not new_key.startswith("__")
                ),
            )


def load_csv(obj: str):
    if not isinstance(obj, str):
        raise TypeError("can only use strings in 'csv' loader")
    return obj.split(",")


def load_primitive(prim):
    def _to_primitive_helper(obj):
        if isinstance(obj, (tuple, list)):
            return [_to_primitive_helper(item) for item in obj]
        if obj is None or (isinstance(obj, (float, np.number)) and np.isnan(obj)):
            return None
        return prim(obj)

    return _to_primitive_helper


class AttributeDataLoading(DatasetOperation):
    r"""Extracts the actual data from the ``DataSource``\s into the attribute arrays. It also
    supports transforming the raw data using so called ``loaders`` in the attribute config.
    Currently supported loaders are: ``json``, ``csv``, ``bool``, ``int``, ``float`` and ``str``
    See :func:`~movici_simulation_core.preprocessing.dataset_creator.create_dataset` for more
    information on the available loaders.
    """

    loaders = {
        "json": json.loads,
        "csv": load_csv,
        "bool": load_primitive(bool),
        "int": load_primitive(int),
        "float": load_primitive(float),
        "str": load_primitive(str),
    }

    sources: SourcesDict

    def __init__(self, config):
        super().__init__(config)
        self.enums = {}

    def __call__(self, dataset: dict, sources: SourcesDict) -> dict:
        self.sources = sources

        data = dataset.get("data")
        if not isinstance(data, dict):
            data = {}
        general_section = dataset.get("general", {})
        for key, conf in self.config.get("data", {}).items():
            data[key] = self.get_data(conf)
        dataset["data"] = data
        if general_section:
            dataset["general"] = general_section
        return dataset

    def get_data(self, entity_config: dict):
        meta = entity_config["__meta__"]
        primary_source = meta.get("source")
        if primary_source is None:
            return {}

        if geom := meta.get("geometry"):
            rv = self.get_geometry(geom, source_name=primary_source)
        else:
            rv = {}

        for key in entity_config.keys() - {"__meta__"}:
            attr_config = entity_config[key]
            rv[key] = self.get_attribute_data(attr_config, primary_source)

        return rv

    def get_geometry(self, geom_type: GeometryType, source_name) -> t.Optional[dict]:
        source = self.get_source(source_name)
        rv = source.get_geometry(geom_type)
        if rv is None:
            raise ValueError(f"No geometry available for source '{source_name}'")
        return rv

    def get_attribute_data(self, attr_config: dict, primary_source_name: str):
        source = self.get_source(primary_source_name)
        if source_override := attr_config.get("source"):
            attr_source = self.get_source(source_override)
            if len(attr_source) != len(source):
                raise ValueError(
                    f"Secondary source '{source_override}' must have the same number of features "
                    f"as the entity group's primary source '{primary_source_name}'"
                )
            source = attr_source

        loaders = self.get_loaders(attr_config)
        return [pipe(loaders, attr) for attr in source.get_attribute(attr_config["property"])]

    def get_source(self, source_name):
        try:
            return self.sources[source_name]
        except KeyError:
            raise ValueError(f"Source '{source_name}' not available")

    def get_loaders(self, attr_config):
        def skip_none(loader):
            return lambda v: v if v is None else loader(v)

        loaders = (self.loaders[key] for key in attr_config.get("loaders", []))
        return [skip_none(l) for l in itertools.chain(loaders, self.default_loaders())]

    def default_loaders(self):
        return [
            self.nan_loader,
        ]

    @staticmethod
    def nan_loader(val):
        if isinstance(val, float) and np.isnan(val):
            return None
        return val


class EnumConversion(DatasetOperation):
    """The ``EnumConversion`` operation is responsible for converting and validating enumerated
    attributes (indicated by the ``enum`` field in the attribute config). It converts strings into
    integers, matching with the position of the value in the ``enum``\\'s array. If the values are
    already integer, then it validates whether the value is matching an enum's value
    """

    enums: t.Dict[str, EnumInfo]

    def __call__(self, dataset: dict, sources: SourcesDict) -> dict:
        self.get_enums(dataset)
        for enum_name, attr_array in self.iter_enum_attributes(dataset):
            attr_array[:] = self.convert_enums(attr_array, enum_name)
        self.set_enums(dataset)
        return dataset

    def get_enums(self, dataset):
        self.enums = {
            enum_name: EnumInfo(enum_name, values)
            for enum_name, values in deep_get(dataset, "general", "enum", default={}).items()
        }

    def set_enums(self, dataset: dict):
        if self.enums:
            general = dataset.setdefault("general", {})
            general["enum"] = {k: info.to_list() for k, info in self.enums.items()}

    def iter_enum_attributes(self, dataset) -> t.Tuple[str, list]:
        for entity_type, entity_dict in self.config["data"].items():
            for attr, attr_conf in entity_dict.items():
                if attr == "__meta__":
                    continue
                if enum_name := attr_conf.get("enum"):
                    yield enum_name, dataset["data"][entity_type][attr]

    def convert_enums(self, attr, enum_name: str):
        enum_info = self.enums.get(enum_name)

        if isinstance(attr, (list, tuple)):
            return type(attr)(self.convert_enums(a, enum_name) for a in attr)
        if isinstance(attr, int):
            if enum_info is None:
                raise ValueError(f"Enum {enum_name} must be defined when supplying integer values")
            if attr >= len(enum_info):
                raise ValueError(f"Attribute value {attr} out of bounds for enum {enum_info.name}")
            return attr
        elif isinstance(attr, str):
            if enum_info is None:
                enum_info = self.enums[enum_name] = EnumInfo(enum_name, [])
            return enum_info.ensure(attr)

        else:
            raise TypeError(
                f"Enum attributes must be of type int or str, not {type(attr).__name__}"
            )


class EnumInfo:
    def __init__(self, name: str, enum_values: t.Sequence[str]) -> None:
        self.name = name
        self.items: t.Dict[str, int] = {val: idx for idx, val in enumerate(enum_values)}

    def ensure(self, text: str) -> int:
        if pos := self.get_pos(text) is not None:
            return pos
        return self.add(text)

    def get_pos(self, text: str) -> t.Optional[int]:
        return self.items.get(text)

    def add(self, text: str) -> int:
        pos = len(self)
        self.items[text] = pos
        return pos

    def to_list(self):
        return list(self.items)

    def __len__(self):
        return len(self.items)


class BoundingBoxCalculation(DatasetOperation):
    """Calculate the bounding box of the entire dataset"""

    def __call__(self, dataset: dict, sources: SourcesDict) -> dict:
        bboxes = []
        for source in self.get_active_sources(sources):
            bbox = source.get_bounding_box()
            if bbox is not None and not np.any(np.isnan(bbox)):
                bboxes.append(bbox)
        if bboxes:
            bboxes = np.stack(bboxes)
            dataset["bounding_box"] = [
                bboxes[:, 0].min(),
                bboxes[:, 1].min(),
                bboxes[:, 2].max(),
                bboxes[:, 3].max(),
            ]

        return dataset

    def get_active_sources(self, sources: SourcesDict):
        active_sources_keys = {
            eg["__meta__"].get("source") for eg in self.config["data"].values()
        } - {None}
        return (sources[key] for key in active_sources_keys)


class IDGeneration(DatasetOperation):
    r"""Generate ``id``\s for every entity"""

    def __call__(self, dataset: dict, sources: SourcesDict) -> dict:
        ctr = itertools.count()
        for entity_type, entity_data in dataset["data"].items():
            try:
                # the entity group size can be dermined by the length of the first attribute
                # array that is encountered
                size = len(next(iter(entity_data.values())))
            except StopIteration:
                size = self.get_entity_count_from_meta(
                    self.config["data"][entity_type]["__meta__"], sources
                )

            entity_data["id"] = [next(ctr) for _ in range(size)]
        return dataset

    def get_entity_count_from_meta(self, entity_meta: dict, sources: dict) -> int:
        if source := entity_meta.get("source"):
            return len(sources[source])
        if count := entity_meta.get("count"):
            return count
        return 0


class IDLinking(DatasetOperation):
    """some attributes may reference another entity's id in the same dataset using the ``id_link``
    field in the attribute config. The ``IDLinking`` operation, looks up the correct id for an
    entity's id-link and places the correct id in the attribute. See <create datasets> for more
    information.
    """

    # keys are (entity_type, property_name)
    index: t.Dict[(t.Tuple[str, str]), dict]

    def __call__(self, dataset: dict, sources: SourcesDict) -> dict:
        self.index = {}
        for entity_type, entity_dict in self.config["data"].items():
            for attr, conf in entity_dict.items():
                if attr == "__meta__":
                    continue
                if link_config := conf.get("id_link"):
                    try:
                        current_values = dataset["data"][entity_type][attr]
                    except KeyError:
                        continue
                    dataset["data"][entity_type][attr] = self.link_attribute(
                        link_config, values=current_values, dataset=dataset, sources=sources
                    )
        return dataset

    def link_attribute(
        self, link_config: t.Union[list, dict], values: list, dataset: dict, sources: SourcesDict
    ) -> t.List[int]:
        if not isinstance(link_config, list):
            link_config = [link_config]
        link_indexers = [
            self.get_link_index(conf, dataset=dataset, sources=sources) for conf in link_config
        ]
        return self.get_indexed_values_or_raise(values, link_indexers)

    def get_link_index(self, link_config: dict, dataset: dict, sources: SourcesDict):
        entity_type = link_config["entity_group"]
        prop = link_config["property"]
        try:
            target_entity_group = self.config["data"][entity_type]
        except KeyError:
            raise ValueError(f"Target entity group '{entity_type}' not defined") from None

        try:
            source = sources[target_entity_group["__meta__"]["source"]]
        except KeyError:
            raise ValueError(f"Source not defined for '{entity_type}'") from None

        try:
            ids = dataset["data"][entity_type]["id"]
        except KeyError:
            raise ValueError(f"ids not found for '{entity_type}'")

        key = (entity_type, prop)
        if key not in self.index:
            self.index[key] = {
                val: target for (val, target) in zip(source.get_attribute(prop), ids)
            }

        return self.index[key]

    @classmethod
    def get_indexed_values_or_raise(cls, values, indexers):
        if isinstance(values, t.Sequence) and not isinstance(values, (bytes, str)):
            return [cls.get_indexed_values_or_raise(item, indexers) for item in values]
        return cls.get_single_indexed_value_or_raise(values, indexers)

    @staticmethod
    def get_single_indexed_value_or_raise(value, indexers):
        for index in indexers:
            try:
                return index[value]
            except KeyError:
                pass
        raise ValueError(f"cannot find link for value {value}")


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

    def to_crs(self, crs: t.Union[str, int]) -> None:
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

        :param geometry_type: One of ``points``, ``lines`` or ``polygons``
        """
        return None

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
    """DataSource non geospatial Numpy or pandas data

    :param data: Either a dictionary ``typing.Dict[str, np.ndarray]`` with keys being the property
        names and the values being the property data array or a Pandas dataframe
    """

    def __init__(self, data: t.Mapping[str, np.ndarray]) -> None:
        self.data = data

    def get_attribute(self, name: str):
        try:
            return list(self.data[name])
        except KeyError:
            raise ValueError(f"'{name}' was not found as a property")

    def __len__(self):
        # this ensures compatibility with both a dictionary of numpy arrays an pandas.DataFrame
        return len(self.data[next(iter(self.data.keys()))])


PandasDataSource = NumpyDataSource


class GeopandasSource(DataSource):
    """DataSource for querying a ``geopandas.GeoDataFrame``"""

    def __init__(self, geodataframe: geopandas.GeoDataFrame):
        self.gdf = geodataframe

    def to_crs(self, crs: t.Union[str, int]):
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
        polygons = []
        for feat in geom:
            self.feature_type_or_raise(feat, "Polygon")
            polygons.append(np.asarray(feat.exterior.coords)[:, :2].tolist())
        return {Geometry_Polygon.name: polygons}

    def get_bounding_box(self):
        return self.gdf.total_bounds

    def get_attribute(self, name: str):
        try:
            return list(self.gdf[name])
        except KeyError:
            raise ValueError(
                f"'{name}' was not found as a feature property, perhaps it has an "
                "incompatible data type and was not loaded"
            )

    @staticmethod
    def feature_type_or_raise(feature, expected):
        if feature.geom_type != expected:
            raise TypeError(f"Invalid feature {feature.geom_type}, must be '{expected}'")

    def __len__(self):
        return len(self.gdf)


SourcesDict = t.Dict[str, DataSource]


def deep_get(obj, *path: t.Union[str, int], default=None):
    if not path:
        raise ValueError("No path given")
    nxt, *rest = path
    try:
        obj = obj[nxt]
    except (KeyError, IndexError):
        return default
    if not rest:
        return obj
    return deep_get(obj, *rest, default=default)
