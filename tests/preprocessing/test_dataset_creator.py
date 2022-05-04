from dataclasses import dataclass, field
import itertools
import json
from pathlib import Path
import typing as t
import geopandas
import jsonschema
from jsonschema.validators import validator_for
import numpy as np

import pytest

from movici_simulation_core.preprocessing.dataset_creator import (
    AttributeDataLoading,
    BoundingBoxCalculation,
    CRSTransformation,
    DataSource,
    DatasetCreator,
    EnumConversion,
    GeopandasSource,
    IDGeneration,
    IDLinking,
    MetadataSetup,
    SourcesSetup,
    SpecialValueCollection,
    get_dataset_creator_schema,
)


class Feature:
    attributes: t.Dict[str, t.Any]

    def as_feature(self):
        return {
            "type": "Feature",
            "geometry": {"type": self.feature_type(), "coordinates": self.get_coordinates()},
            "properties": self.attributes.copy(),
        }

    def feature_type(self) -> str:
        raise NotImplementedError

    def get_coordinates(self):
        raise NotImplementedError


@dataclass
class Point(Feature):
    x: float
    y: float
    z: t.Optional[float] = None
    attributes: t.Dict[str, t.Any] = field(default_factory=dict)

    def feature_type(self):
        return "Point"

    def get_coordinates(self):
        return [self.x, self.y, self.z] if self.z is not None else [self.x, self.y]


@dataclass
class LineString(Feature):
    geometry: t.List[t.Union[t.Tuple[float, float], t.Tuple[float, float, float]]]
    attributes: t.Dict[str, t.Any] = field(default_factory=dict)

    def feature_type(self):
        return "LineString"

    def get_coordinates(self):
        return [list(point) for point in self.geometry]


@dataclass
class Polygon(LineString):
    geometry: t.List[t.Tuple[float, float]]
    attributes: t.Dict[str, t.Any] = field(default_factory=dict)

    def feature_type(self):
        return "Polygon"

    def get_coordinates(self):
        return [[list(point) for point in self.geometry]]


def create_feature_collection(features: t.List[Feature]):
    return {
        "type": "FeatureCollection",
        "features": [f.as_feature() for f in features],
    }


@pytest.fixture
def create_geojson(tmp_path: Path):
    ctr = itertools.count()

    def _inner(features: t.List[Feature]):
        path = tmp_path / f"features_{next(ctr)}.geojson"
        path.write_text(json.dumps(create_feature_collection(features)))
        return path

    return _inner


@pytest.fixture
def create_gdf(create_geojson):
    def _inner(features: t.List[Feature]):
        # we first convert the features to a geojson file, and then read that file
        # into a GeoDataFrame since geopandas.read_file is the most flexible/powerful way to
        # create a gdf, since it uses Fiona under the hood

        return geopandas.read_file(create_geojson(features))

    return _inner


@pytest.fixture
def create_data_sources(create_gdf):
    def inner(features: t.Dict[str, t.Sequence[Feature]]):
        return {key: GeopandasSource(create_gdf(feats)) for key, feats in features.items()}

    return inner


@pytest.fixture
def config():
    return {
        "data": {
            "some_entities": {
                "__meta__": {"source": "foo"},
                "attribute": {"property": "prop"},
            }
        }
    }


@pytest.fixture(scope="session")
def validator():
    schema = get_dataset_creator_schema()
    return validator_for(schema)(schema)


@pytest.fixture(scope="session", autouse=True)
def validate_schema(validator):
    assert validator.check_schema(get_dataset_creator_schema()) is None


@pytest.fixture(autouse=True)
def validate_config(config, validator, request):
    defaults = {"name": "some_name"}
    if "no_validate_config" not in request.keywords:
        assert validator.validate({**defaults, **config}) is None


class TestGeopandasDataSource:
    @pytest.fixture
    def points_geojson(self, create_gdf):
        return create_gdf(
            [
                Point(0, 0, attributes={"attr": 10}),
                Point(1, 1, attributes={"attr": 11}),
            ]
        )

    @pytest.fixture
    def lines_geojson(self, create_gdf):
        return create_gdf(
            [
                LineString([(0, 0), (1, 1)], {"attr": 10}),
                LineString([(2, 2), (3, 3)], {"attr": 11}),
            ]
        )

    @pytest.fixture
    def lines_3d_geojson(self, create_gdf):
        return create_gdf(
            [
                LineString([(0, 0, 0), (1, 1, 0)], {"attr": 10}),
                LineString([(2, 2, 0), (3, 3, 0)], {"attr": 11}),
            ]
        )

    @pytest.fixture
    def mixed_lines_geojson(self, create_gdf):
        return create_gdf(
            [
                LineString([(0, 0), (1, 1)], {"attr": 10}),
                LineString([(2, 2, 0), (3, 3, 0)], {"attr": 11}),
            ]
        )

    @pytest.fixture
    def polygons_geojson(self, create_gdf):
        return create_gdf(
            [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)], {"attr": 10}),
                Polygon(
                    [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9), (0.1, 0.1)], {"attr": 11}
                ),
            ]
        )

    @pytest.fixture
    def complex_polygon_geojson(self, tmp_path):
        file = tmp_path / "complex_polygon.geojson"
        file.write_text(
            json.dumps(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)],
                            [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9), (0.1, 0.1)],
                        ],
                    },
                }
            )
        )
        return geopandas.read_file(file)

    def test_get_attribute_from_feature_collection(self, points_geojson):
        source = GeopandasSource(points_geojson)
        assert source.get_attribute("attr") == [10, 11]

    def test_get_point_geometry(self, points_geojson):
        source = GeopandasSource(points_geojson)
        assert source.get_geometry("points") == {
            "geometry.x": [0, 1],
            "geometry.y": [0, 1],
        }

    def test_3d_point_geometry(self, create_gdf):
        source = GeopandasSource(
            create_gdf(
                [
                    Point(1, 1),
                    Point(1, 1, 0),
                ]
            )
        )
        assert source.get_geometry("points") == {
            "geometry.x": [1, 1],
            "geometry.y": [1, 1],
            "geometry.z": [None, 0],
        }

    def test_get_linestring_geometry(self, lines_geojson):
        source = GeopandasSource(lines_geojson)
        assert source.get_geometry("lines") == {
            "geometry.linestring_2d": [
                [[0, 0], [1, 1]],
                [[2, 2], [3, 3]],
            ]
        }

    def test_get_linestring_3d_geometry(self, lines_3d_geojson):
        source = GeopandasSource(lines_3d_geojson)
        assert source.get_geometry("lines") == {
            "geometry.linestring_3d": [
                [[0, 0, 0], [1, 1, 0]],
                [[2, 2, 0], [3, 3, 0]],
            ]
        }

    def test_get_mixed_linestring_geometry_as_2d(self, mixed_lines_geojson):
        source = GeopandasSource(mixed_lines_geojson)
        assert source.get_geometry("lines") == {
            "geometry.linestring_2d": [
                [[0, 0], [1, 1]],
                [[2, 2], [3, 3]],
            ]
        }

    def test_get_polygon(self, polygons_geojson):
        source = GeopandasSource(polygons_geojson)
        assert source.get_geometry("polygons") == {
            "geometry.polygon": [
                [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
                [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9], [0.1, 0.1]],
            ]
        }

    def test_only_gets_outer_ring_for_complex_polygon(self, complex_polygon_geojson):
        source = GeopandasSource(complex_polygon_geojson)
        assert source.get_geometry("polygons") == {
            "geometry.polygon": [
                [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
            ]
        }

    def test_converts_open_polygon_into_closed_polygon(self, create_gdf):
        source = GeopandasSource(
            create_gdf(
                [
                    Polygon([(0, 0), (1, 0), (1, 1), (0, 1)], {"attr": 10}),
                ]
            )
        )

        assert source.get_geometry("polygons") == {
            "geometry.polygon": [
                [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
            ]
        }

    @pytest.mark.parametrize(
        "input, expected",
        [
            ([10, None], [10.0, float("NaN")]),
            ([10.1, None], [10.1, float("NaN")]),
            ([True, None], [True, None]),
            (["bla", None], ["bla", None]),
        ],
    )
    def test_undefined_property(self, input, expected, create_gdf):
        source = GeopandasSource(create_gdf([Point(0, 0, attributes={"attr": a}) for a in input]))
        np.testing.assert_array_equal(source.get_attribute("attr"), expected)


@pytest.fixture
def sources(create_data_sources):
    return create_data_sources(
        {
            "some_points": [
                Point(0, 0, attributes={"attr": 10, "json_list": "[1,2]"}),
                Point(1, 1, attributes={"attr": 11, "json_list": "[3,4]"}),
            ],
            "some_lines": [LineString([(-1, -1), (0.5, 0.5)])],
            "empty": [],
        }
    )


class TestSourcesSetup:
    @pytest.fixture
    def sources(self):
        return {
            "some_points": [
                Point(0, 0, attributes={"attr": 10, "json_list": "[1,2]"}),
                Point(1, 1, attributes={"attr": 11, "json_list": "[3,4]"}),
            ],
            "some_lines": [LineString([(-1, -1), (0.5, 0.5)])],
            "empty": [],
        }

    @pytest.fixture
    def source_files(self, sources, create_geojson):
        return {k: create_geojson(v) for k, v in sources.items()}

    @pytest.fixture
    def config(self, source_files):
        return {
            "__sources__": {
                k: {"source_type": "file", "path": str(v)} for k, v in source_files.items()
            },
            "data": {},
        }

    def test_populates_sources_dict(self, config):
        op = SourcesSetup(config)
        sources = {}
        op({}, sources=sources)
        assert sources.keys() == {"some_points", "some_lines", "empty"}
        assert all(isinstance(s, DataSource) for s in sources.values())


class TestCRSTransformation:
    @pytest.fixture
    def sources(self, create_data_sources):
        return create_data_sources(
            {
                "some_points": [
                    Point(5.38721, 52.15517),
                ],
            }
        )

    @pytest.fixture
    def source_files(self, sources, create_geojson):
        return {k: create_geojson(v) for k, v in sources.items()}

    @pytest.mark.parametrize(
        "x, y, target_crs, exp_x, exp_y",
        [
            (5.38721, 52.15517, None, 155000, 463000),
            (5.38721, 52.15517, 28992, 155000, 463000),
            (5.38721, 52.15517, "EPSG:28992", 155000, 463000),
            (5.38721, 52.15517, "EPSG:3857", 599701, 6828231),
            (5.38721, 52.15517, "WGS 84", 5, 52),
        ],
    )
    def test_crs_transformation_to_epsg_28992(
        self, x, y, target_crs, exp_x, exp_y, create_data_sources
    ):
        config = {"data": {}}
        sources = create_data_sources({"foo": [Point(x, y)]})
        if target_crs is not None:
            config["__meta__"] = {"crs": target_crs}

        op = CRSTransformation(config)
        op({}, sources)
        geom = sources["foo"].get_geometry("points")
        assert {k: [round(x) for x in vals] for k, vals in geom.items()} == {
            "geometry.x": [exp_x],
            "geometry.y": [exp_y],
        }


class TestAttributeDataExtraction:
    @pytest.fixture
    def config(self):
        return {
            "data": {
                "some_entities": {
                    "__meta__": {"source": "some_points", "geometry": "points"},
                    "some.attr": {"property": "attr"},
                }
            }
        }

    def test_data_loading(self, config, sources):
        operation = AttributeDataLoading(config)

        assert operation({}, sources) == {
            "data": {
                "some_entities": {
                    "geometry.x": [0, 1],
                    "geometry.y": [0, 1],
                    "some.attr": [10, 11],
                }
            }
        }

    @pytest.mark.parametrize(
        "config",
        [
            {
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "some_points"},
                        "multidim": {"property": "json_list", "loaders": ["json"]},
                    }
                }
            }
        ],
    )
    def test_data_loading_with_json_data(self, config, sources):
        op = AttributeDataLoading(config)
        result = op({}, sources=sources)
        assert result["data"]["some_entities"]["multidim"] == [[1, 2], [3, 4]]

    @pytest.mark.parametrize(
        "raw_data, loaders, expected",
        [
            ("[42]", "json", [42]),
            ("a,b", "csv", ["a", "b"]),
            ("1.1", ["float", "int"], 1),
            ("0.1", "bool", True),
            ("0.1", ["float", "int", "bool"], False),
        ],
    )
    def test_complex_data_loading(
        self, raw_data, loaders, expected, create_data_sources, validator
    ):
        sources = create_data_sources({"source": [Point(0, 0, attributes={"attr": raw_data})]})
        loaders = [loaders] if isinstance(loaders, str) else loaders
        config = {
            "name": "some_name",
            "data": {
                "some_entities": {
                    "__meta__": {"source": "source"},
                    "attribute": {"property": "attr", "loaders": loaders},
                }
            },
        }
        validator.validate(config)

        op = AttributeDataLoading(config)
        result = op({}, sources=sources)
        assert result["data"]["some_entities"]["attribute"] == [expected]

    @pytest.mark.parametrize(
        "config",
        [
            {
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "some_points"},
                        "non-existing": {"property": "invalid"},
                    }
                }
            }
        ],
    )
    def test_raises_when_property_does_not_exists(self, config, sources):
        with pytest.raises(ValueError):
            AttributeDataLoading(config)({}, sources=sources)

    @pytest.mark.parametrize(
        "config",
        [
            {
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "primary"},
                        "foo": {"property": "foo", "source": "secondary"},
                    }
                }
            }
        ],
    )
    def test_read_attribute_from_secondary_source(self, config, create_data_sources):
        sources = create_data_sources(
            {
                "primary": [Point(0, 0), Point(0, 0)],
                "secondary": [
                    Point(0, 0, attributes={"foo": 10}),
                    Point(0, 0, attributes={"foo": 11}),
                ],
            }
        )
        result = AttributeDataLoading(config)({}, sources=sources)["data"]["some_entities"]
        assert result == {"foo": [10, 11]}

    @pytest.mark.parametrize(
        "config",
        [
            {
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "primary"},
                        "foo": {"property": "foo", "source": "secondary"},
                    }
                }
            }
        ],
    )
    def test_validates_length_of_secondary_source(self, config, create_data_sources):
        sources = create_data_sources(
            {
                "primary": [Point(0, 0), Point(0, 0)],
                "secondary": [
                    Point(0, 0, attributes={"foo": 10}),
                ],
            }
        )
        with pytest.raises(ValueError):
            AttributeDataLoading(config)({}, sources=sources)

    def test_converts_nan_to_none(self, config, create_data_sources):
        sources = create_data_sources(
            {
                "some_points": [Point(0, 0, attributes={"attr": float("NaN")})],
            }
        )
        result = AttributeDataLoading(config)({}, sources=sources)
        result = result["data"]["some_entities"]["some.attr"]
        assert result == [None]

    @pytest.mark.parametrize(
        "config",
        [
            {
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "source"},
                        "some.attr": {"property": "foo", "loaders": ["csv", "int"]},
                    }
                }
            }
        ],
    )
    def test_skips_None_in_loaders(self, config, create_data_sources):
        sources = create_data_sources(
            {
                "source": [Point(0, 0, attributes={"foo": None})],
            }
        )
        result = AttributeDataLoading(config)({}, sources=sources)
        result = result["data"]["some_entities"]["some.attr"]
        assert result == [None]


class TestEnumConversion:
    @pytest.fixture
    def sources_dict(self):
        return {
            "enumerable": [
                Point(0, 0, attributes={"attr": "bar"}),
                Point(1, 1, attributes={"attr": "baz"}),
            ],
        }

    @pytest.fixture
    def sources(self, sources_dict, create_data_sources):
        return create_data_sources(sources_dict)

    @pytest.fixture
    def dataset(self, sources, config):
        return DatasetCreator(
            [
                MetadataSetup,
                AttributeDataLoading,
            ],
            sources=sources,
            validate_config=False,
        ).create(config)

    @pytest.mark.parametrize(
        "config",
        [
            {
                "general": {},
                "data": {
                    "foo": {"__meta__": {"count": 2}},
                },
            }
        ],
    )
    def test_leaves_general_section_without_enums_in_tact(self, config, dataset):
        result = EnumConversion(config)(dataset, sources={})
        assert result["general"] == {}

    @pytest.mark.parametrize(
        "config",
        [
            {
                "general": {"enum": {"foo": ["bar", "baz"]}},
                "data": {
                    "foo": {"__meta__": {"count": 2}},
                },
            }
        ],
    )
    def test_leaves_general_section_with_enums_in_tact(self, config, dataset):
        result = EnumConversion(config)(dataset, sources={})
        assert result["general"] == {"enum": {"foo": ["bar", "baz"]}}

    @pytest.mark.parametrize(
        "config",
        [
            {
                "data": {
                    "foo": {
                        "__meta__": {"source": "enumerable"},
                        "attr": {"property": "attr", "enum": "foo"},
                    },
                },
            }
        ],
    )
    def test_adds_new_enums_to_general_section(self, config, sources, dataset):
        result = EnumConversion(config)(dataset, sources=sources)
        assert result["general"]["enum"]["foo"] == ["bar", "baz"]

    @pytest.mark.parametrize(
        "config",
        [
            {
                "general": {"enum": {"foo": ["baz"]}},
                "data": {
                    "foo": {
                        "__meta__": {"source": "enumerable"},
                        "attr": {"property": "attr", "enum": "foo"},
                    },
                },
            }
        ],
    )
    def test_appends_new_items_to_existing_enums(self, config, sources, dataset):
        result = EnumConversion(config)(dataset, sources=sources)
        assert result["general"]["enum"]["foo"] == ["baz", "bar"]

    @pytest.mark.parametrize(
        "config",
        [
            {
                "data": {
                    "foo_entities": {
                        "__meta__": {"source": "enumerable"},
                        "attr": {"property": "attr", "enum": "foo"},
                    },
                },
            }
        ],
    )
    def test_converts_string_into_enum_values(self, config, sources, dataset):
        result = EnumConversion(config)(dataset, sources=sources)
        assert result["data"]["foo_entities"]["attr"] == [0, 1]

    @pytest.mark.parametrize(
        "config, sources_dict",
        [
            (
                {
                    "data": {
                        "foo_entities": {
                            "__meta__": {"source": "enumerable"},
                            "attr": {"property": "attr", "enum": "foo", "loaders": ["json"]},
                        },
                    },
                },
                {
                    "enumerable": [
                        Point(0, 0, attributes={"attr": '["bar", "baz"]'}),
                        Point(1, 1, attributes={"attr": '["baz"]'}),
                    ],
                },
            )
        ],
    )
    def test_converts_nested_values(self, config, sources, dataset):
        result = EnumConversion(config)(dataset, sources=sources)
        assert result["data"]["foo_entities"]["attr"] == [[0, 1], [1]]

    @pytest.mark.parametrize(
        "config, sources_dict",
        [
            (
                {
                    "general": {"enum": {"foo": ["bar", "baz"]}},
                    "data": {
                        "foo_entities": {
                            "__meta__": {"source": "enumerable"},
                            "attr": {"property": "attr", "enum": "foo"},
                        },
                    },
                },
                {
                    "enumerable": [
                        Point(0, 0, attributes={"attr": 0}),
                        Point(1, 1, attributes={"attr": 1}),
                    ],
                },
            )
        ],
    )
    def test_leaves_integer_values_in_tact(self, config, sources, dataset):
        result = EnumConversion(config)(dataset, sources=sources)
        assert result["data"]["foo_entities"]["attr"] == [0, 1]

    @pytest.mark.parametrize(
        "sources_dict",
        [
            {
                "enumerable": [
                    Point(0, 0, attributes={"attr": 0}),
                    Point(1, 1, attributes={"attr": 1}),
                ],
            }
        ],
    )
    @pytest.mark.parametrize(
        "config, msg",
        [
            (
                {
                    "data": {
                        "foo_entities": {
                            "__meta__": {"source": "enumerable"},
                            "attr": {"property": "attr", "enum": "foo"},
                        },
                    },
                },
                "Enum foo must be defined",
            ),
            (
                {
                    "general": {"enum": {"foo": ["bar"]}},
                    "data": {
                        "foo_entities": {
                            "__meta__": {"source": "enumerable"},
                            "attr": {"property": "attr", "enum": "foo"},
                        },
                    },
                },
                "1 out of bounds for enum foo",
            ),
        ],
    )
    def test_validates_integer_values(self, config, msg, sources, dataset):
        with pytest.raises(ValueError) as e:
            EnumConversion(config)(dataset, sources=sources)
        assert msg in str(e.value)


class TestSpecialValueCollection:
    params = [
        {
            "name": "Can collect special values",
            "config": {
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "foo"},
                        "some_attribute": {
                            "special": 42,
                            "property": "bar",
                        },
                        "other_attribute": {"property": "bar", "special": 12},
                        "attr_without_special": {"property": "bar"},
                    },
                    "other_entities": {
                        "__meta__": {"source": "foo"},
                        "some_attribute": {"property": "bar", "special": 43},
                    },
                }
            },
            "expected": {
                "general": {
                    "special": {
                        "some_entities.some_attribute": 42,
                        "some_entities.other_attribute": 12,
                        "other_entities.some_attribute": 43,
                    }
                }
            },
        },
        {
            "name": "Merges with exisiting special values",
            "config": {
                "general": {"special": {"some_entities.attr_without_special": 13}},
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "foo"},
                        "some_attribute": {"property": "bar", "special": 42},
                        "attr_without_special": {
                            "property": "bar",
                        },
                    }
                },
            },
            "expected": {
                "general": {
                    "special": {
                        "some_entities.some_attribute": 42,
                        "some_entities.attr_without_special": 13,
                    }
                }
            },
        },
        {
            "name": "Doesn't overwrite exisiting special values",
            "config": {
                "general": {"special": {"some_entities.some_attribute": 13}},
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "foo"},
                        "some_attribute": {"property": "bar", "special": 42},
                        "attr_without_special": {"property": "bar", "enum": "bla"},
                    },
                },
            },
            "expected": {
                "general": {
                    "special": {
                        "some_entities.some_attribute": 13,
                    }
                }
            },
        },
    ]

    @pytest.mark.parametrize(
        "config, expected",
        [(p["config"], p["expected"]) for p in params],
        ids=[p["name"] for p in params],
    )
    def test_collect_special_values(self, config, expected):
        assert SpecialValueCollection(config)({}, {}) == expected


class TestBoundingBoxCalculation:
    @pytest.fixture
    def dataset(self, sources, config):
        return AttributeDataLoading(config)({}, sources=sources)

    @pytest.mark.parametrize(
        "config, expected",
        [
            (
                {
                    "data": {
                        "points": {"__meta__": {"source": "some_points", "geometry": "points"}},
                        "lines": {"__meta__": {"source": "some_lines", "geometry": "lines"}},
                    }
                },
                [-1, -1, 1, 1],  # multiple sources with geometry
            ),
            (
                {
                    "data": {
                        "empty": {"__meta__": {"source": "empty", "geometry": "points"}},
                    }
                },
                None,  # single source without geometry
            ),
            (
                {
                    "data": {
                        "empty": {"__meta__": {"source": "empty", "geometry": "points"}},
                        "lines": {"__meta__": {"source": "some_lines", "geometry": "lines"}},
                    }
                },
                [-1, -1, 0.5, 0.5],  # multiple sources, but only one with geometry
            ),
            (
                {
                    "data": {
                        "empty": {"__meta__": {"source": "empty", "geometry": "points"}},
                        "no_geom": {"__meta__": {"count": 10}},
                    }
                },
                None,  # source without geometry and entity group withtout source
            ),
        ],
    )
    def test_calculates_bounding_box(self, config, expected, sources, dataset):
        op = BoundingBoxCalculation(config)
        assert op(dataset, sources=sources).get("bounding_box") == expected


class TestIDGeneration:
    @pytest.fixture
    def config(self):
        return {
            "data": {
                "points": {"__meta__": {"source": "some_points", "geometry": "points"}},
                "lines": {"__meta__": {"source": "some_lines", "geometry": "lines"}},
            }
        }

    @pytest.fixture
    def dataset(self, sources, config):
        return AttributeDataLoading(config)({}, sources=sources)

    def test_id_generation(self, dataset, config, sources):
        op = IDGeneration(config)
        result = op(dataset, sources=sources)
        ids = list(itertools.chain.from_iterable(eg["id"] for eg in result["data"].values()))
        assert len(ids) == 3
        assert set(ids) == {0, 1, 2}

    @pytest.mark.parametrize("config", [{"data": {"virtual": {"__meta__": {"count": 3}}}}])
    def test_id_generation_without_attributes(self, config, dataset):
        op = IDGeneration(config)
        result = op(dataset, sources={})

        assert result["data"]["virtual"] == {"id": [0, 1, 2]}

    @pytest.mark.parametrize("config", [{"data": {"virtual": {"__meta__": {"source": "empty"}}}}])
    def test_id_generation_with_empty_data_source(self, config, create_data_sources):
        dataset = {"data": {"virtual": {}}}
        op = IDGeneration(config)
        result = op(dataset, sources=create_data_sources({"empty": []}))

        assert result["data"]["virtual"] == {"id": []}

    @pytest.mark.parametrize(
        "config",
        [
            {"data": {"points": {"__meta__": {"source": "some_points"}}}},
        ],
    )
    def test_reads_source_length_when_no_attributes_are_specified(self, config, dataset, sources):
        result = IDGeneration(config)(dataset, sources=sources)
        ids = result["data"]["points"]["id"]

        assert len(ids) == 2


class TestIDLinking:
    @pytest.fixture
    def sources(self, create_data_sources):
        return create_data_sources(
            {
                "some_points": [
                    Point(0, 0, attributes={"ref": "point_0"}),
                    Point(1, 1, attributes={"ref": "point_1"}),
                ],
                "some_lines": [
                    LineString([(-1, -1), (0.5, 0.5)], attributes={"node_ref": "point_0"}),
                    LineString([(-1, -1), (0.5, 0.5)], attributes={"node_ref": "point_1"}),
                    LineString([(-1, -1), (0.5, 0.5)], attributes={"node_ref": "point_0"}),
                ],
                "multi_ref_points": [
                    Point(0, 0, attributes={"node_ref": "[]"}),
                    Point(1, 1, attributes={"node_ref": '["point_1"]'}),
                    Point(1, 1, attributes={"node_ref": '["point_0", "point_1"]'}),
                ],
            }
        )

    @pytest.fixture
    def config(self):
        return {
            "data": {
                "points": {
                    "__meta__": {
                        "source": "some_points",
                        "geometry": "points",
                    },
                    "reference": {"property": "ref"},
                },
                "lines": {
                    "__meta__": {
                        "source": "some_lines",
                        "geometry": "lines",
                    },
                    "node_id": {
                        "property": "node_ref",
                        "id_link": {"entity_group": "points", "property": "ref"},
                    },
                },
            }
        }

    @pytest.fixture
    def dataset(self, sources, config):
        return DatasetCreator(
            [
                AttributeDataLoading,
                IDGeneration,
            ],
            sources=sources,
            validate_config=False,
        ).create(config)

    @staticmethod
    def get_val_for_id(entity_group, key, id):
        idx = entity_group["id"].index(id)
        return entity_group[key][idx]

    def test_links_ids_to_other_entity_group(self, config, dataset, sources):
        op = IDLinking(config)
        result = op(dataset, sources=sources)

        for node_id in result["data"]["lines"]["node_id"]:
            assert isinstance(node_id, int)
            assert self.get_val_for_id(result["data"]["points"], "reference", node_id), node_id

    @pytest.mark.parametrize(
        "config",
        [
            {
                "data": {
                    "points": {
                        "__meta__": {
                            "source": "some_points",
                            "geometry": "points",
                        },
                        "reference": {"property": "ref"},
                    },
                    "multi_ref": {
                        "__meta__": {
                            "source": "multi_ref_points",
                            "geometry": "points",
                        },
                        "node_ids": {
                            "property": "node_ref",
                            "id_link": {"entity_group": "points", "property": "ref"},
                            "loaders": ["json"],
                        },
                    },
                }
            }
        ],
    )
    def test_link_ids_from_list_of_entries(self, config, dataset, sources):
        op = IDLinking(config)
        result = op(dataset, sources=sources)

        for items, exp_len in zip(result["data"]["multi_ref"]["node_ids"], [0, 1, 2]):
            assert len(items) == exp_len
            for node_id in items:
                self.get_val_for_id(result["data"]["points"], "reference", node_id), node_id

    @pytest.mark.parametrize(
        "config, error_msg",
        [
            (
                {
                    "data": {
                        "lines": {
                            "__meta__": {
                                "source": "some_lines",
                                "geometry": "lines",
                            },
                            "node_id": {
                                "property": "node_ref",
                                "id_link": {"entity_group": "non-existing", "property": "ref"},
                            },
                        },
                    }
                },
                "Target entity group 'non-existing' not defined",
            ),
            (
                {
                    "data": {
                        "points": {
                            "__meta__": {
                                "source": "some_points",
                                "geometry": "points",
                            },
                            "reference": {"property": "ref"},
                        },
                        "lines": {
                            "__meta__": {
                                "source": "some_lines",
                                "geometry": "lines",
                            },
                            "node_id": {
                                "property": "node_ref",
                                "id_link": {"entity_group": "points", "property": "non-existing"},
                            },
                        },
                    }
                },
                (
                    "'non-existing' was not found as a feature property, perhaps it has an "
                    "incompatible data type and was not loaded"
                ),
            ),
        ],
    )
    def test_error_when_other_entity_group_does_not_exists(
        self, dataset, config, error_msg, sources
    ):
        op = IDLinking(config)
        with pytest.raises(ValueError) as e:
            op(dataset, sources=sources)
        assert error_msg in str(e.value)


class TestSchemaValidation:
    min_required = {
        "name": "some_name",
        "data": {
            "some_entities": {
                "__meta__": {"source": "foo"},
            }
        },
    }

    @pytest.mark.parametrize(
        "config",
        [
            {
                "name": "some_name",
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "foo"},
                        "attribute": {"property": "prop"},
                    }
                },
            },
            {
                "__sources__": {
                    "foo": "/some/path",
                    "bar": {"source_type": "file", "path": "/some/other/path"},
                },
                **min_required,
            },
            {
                "name": "some_name",
                "data": {
                    "point_entities": {
                        "__meta__": {"source": "foo", "geometry": "points"},
                    },
                    "line_entities": {
                        "__meta__": {"source": "foo", "geometry": "lines"},
                    },
                    "polygon_entities": {
                        "__meta__": {"source": "foo", "geometry": "polygons"},
                    },
                },
            },
            {"__meta__": {"crs": "EPSG:28992"}, **min_required},
            {"__meta__": {"crs": 28992}, **min_required},
            {
                "general": {
                    "enum": {"some": ["enum", "values"]},
                    "special": {"some.attribute": 42, "other.attribute": "bla"},
                    "additional": "entry",
                },
                **min_required,
            },
            {"version": 4, **min_required},
        ],
    )
    @pytest.mark.no_validate_config
    def test_valid_dataset_creator(self, validator, config):
        validator.validate(config)

    @pytest.mark.parametrize(
        "config",
        [
            {},
            {
                **min_required,
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "foo", "geometry": "invalid"},  # invalid geometry
                    }
                },
            },
            {**min_required, "data": {"some_entities": {}}},
            {
                **min_required,
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "foo", "count": 12},  # both source and count
                    }
                },
            },
            {
                **min_required,
                "data": {
                    "some_entities": {
                        "__meta__": {"count": -1},  # negative count
                    }
                },
            },
            {**min_required, "extra": "key"},
            {
                **min_required,
                "__sources__": {
                    "foo": {
                        "source_type": "invalid",  # invalid source type
                        "path": "/some/other/path",
                    },
                },
            },
            {"__meta__": {"crs": 12.3}, **min_required},
            {"general": {"enum": ["invalid"]}, **min_required},
            {"general": {"special": ["invalid"]}, **min_required},
            {
                **min_required,
                "data": {
                    "some_entities": {
                        "__meta__": {"source": "foo"},
                        "id": {"property": "prop"},
                    }
                },
            },
            {"version": 3, **min_required},
        ],
    )
    @pytest.mark.no_validate_config
    def test_invalid_dataset_creator(self, validator, config):
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(config)
