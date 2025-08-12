import numpy as np
from movici_geo_query.geo_query import GeoQuery
from movici_geo_query.geometry import LinestringGeometry, PointGeometry

from movici_simulation_core import (
    INIT,
    PUB,
    SUB,
    AttributeSchema,
    AttributeSpec,
    EntityGroup,
    TrackedModel,
    TrackedState,
    field,
)
from movici_simulation_core.attributes import (
    Geometry_Linestring2d,
    Geometry_X,
    Geometry_Y,
    GlobalAttributes,
)
from movici_simulation_core.testing import ModelTester, assert_dataset_dicts_equal

SignalStrength = AttributeSpec("antennas.signal_strength", float)


class AntennaEntities(EntityGroup, name="antenna_entities"):
    x = field(Geometry_X, flags=INIT)
    y = field(Geometry_Y, flags=INIT)
    signal_strength = field(SignalStrength, flags=SUB)

    def get_geometry(self) -> PointGeometry:
        return PointGeometry(points=np.stack((self.x.array, self.y.array), axis=-1))


class RoadSegmentEntities(EntityGroup, name="road_segment_entities"):
    geometry = field(Geometry_Linestring2d, flags=INIT)
    signal_strength = field(SignalStrength, flags=PUB)

    def get_geometry(self) -> LinestringGeometry:
        return LinestringGeometry(points=self.geometry.csr.data, row_ptr=self.geometry.csr.row_ptr)


class SignalStrengthModel(TrackedModel, name="signal_strength"):
    antennas: AntennaEntities
    roads: RoadSegmentEntities
    nearest_antennas: np.ndarray
    distances: np.ndarray

    def setup(self, state: TrackedState, **_):
        # We only have the model config available. The goal is to setup the state properly
        # with our pub/sub datamask
        antennas_ds = self.config["antennas"]
        roads_ds = self.config["roads"]

        self.antennas = state.register_entity_group(antennas_ds, AntennaEntities)
        self.roads = state.register_entity_group(roads_ds, RoadSegmentEntities)

    def initialize(self, **_):
        # all ``INIT`` attributes are available, we can use them to link every road segment to
        # its nearest antenna tower
        antennas_as_geometry = self.antennas.get_geometry()
        roads_as_geometry = self.roads.get_geometry()
        gq = GeoQuery(antennas_as_geometry)
        result = gq.nearest_to(roads_as_geometry)

        # self.nearest_antennas contains the index of the nearest antenna (in the self.antennas
        # entity group) for every road
        self.nearest_antennas = result.indices

        # self.distances contains the distance to the nearest antenna for every road
        # the reference signal strength is at a distance of 1 m. If the mapping results in a
        # distance <1m it would result wrong results, or even raise ZeroDivisionError. We set the
        # minimum distance to one meter
        self.distances = np.maximum(result.distances, 1)

    def update(self, **_):
        # update will only be called once initialized has returned succesfully. We can be sure
        # that self.nearest_antennas and self.distances are set

        l_ref = self.antennas.signal_strength[self.nearest_antennas]

        # In the signal strength formula we need to divide by r_ref inside the logarithm. Here
        # r_ref == 1 so we don't strictly need to include it. However for completeness sake we
        # still divide by 1
        self.roads.signal_strength[:] = l_ref - 20 * np.log10(self.distances / 1)


def get_model():
    return SignalStrengthModel({"antennas": "some_antennas", "roads": "some_roads"})


def get_schema():
    schema = AttributeSchema([SignalStrength])
    schema.use(GlobalAttributes)
    return schema


def get_tester(model):
    schema = get_schema()
    rv = ModelTester(model, schema=schema)
    rv.add_init_data(
        "some_antennas",
        {
            "name": "some_antennas",
            "data": {
                "antenna_entities": {
                    "id": [1, 2, 3],
                    "geometry.x": [1, 7, 5],
                    "geometry.y": [1, 2, 1],
                }
            },
        },
    )
    rv.add_init_data(
        "some_roads",
        {
            "name": "some_roads",
            "data": {
                "road_segment_entities": {
                    "id": [1, 2],
                    "geometry.linestring_2d": [[[2, 0], [3, 5]], [[3, 5], [6, 6]]],
                }
            },
        },
    )
    return rv


def test_intialize():
    model = get_model()
    tester = get_tester(model)
    tester.initialize()
    np.testing.assert_equal(model.nearest_antennas, [0, 1])


def test_update():
    model = get_model()
    tester = get_tester(model)
    tester.initialize()
    result, next_time = tester.update(
        timestamp=0,
        data={
            "some_antennas": {
                "antenna_entities": {
                    "id": [1, 2, 3],
                    "antennas.signal_strength": [-30, -30, -30],
                }
            }
        },
    )

    # the Model is a steady state model, so we expect no next_time
    assert next_time is None  # nosec assert_used

    # do a deep equality check on the update data
    assert_dataset_dicts_equal(
        result,
        {
            "some_roads": {
                "road_segment_entities": {
                    "id": [1, 2],
                    "antennas.signal_strength": [-31.42, -42.28],
                }
            }
        },
        rtol=1e-2,
    )


def test_signal_strength_calculation():
    model = get_model()
    schema = get_schema()

    tester = ModelTester(model, schema=schema)
    ref_signal_strength = 0

    tester.add_init_data(
        "some_antennas",
        {
            "name": "some_antennas",
            "data": {
                "antenna_entities": {
                    "id": [1],
                    "geometry.x": [0],
                    "geometry.y": [1],
                    "antennas.signal_strength": [ref_signal_strength],
                }
            },
        },
    )
    tester.add_init_data(
        "some_roads",
        {
            "name": "some_roads",
            "data": {
                "road_segment_entities": {
                    "id": [1, 2, 3, 4],
                    "geometry.linestring_2d": [
                        [[0, 0], [0, 2]],
                        [[1, 0], [1, 2]],
                        [[2, 0], [2, 2]],
                        [[10, 0], [10, 2]],
                    ],
                }
            },
        },
    )
    tester.initialize()

    expected_signal_loss = np.array([0, 0, 6.0206, 20])

    expected = ref_signal_strength - expected_signal_loss
    result, _ = tester.update(0, None)
    signal_strength = result["some_roads"]["road_segment_entities"]["antennas.signal_strength"]
    np.testing.assert_allclose(signal_strength, expected)


def test_all():
    test_intialize()
    test_update()
    test_signal_strength_calculation()


if __name__ == "__main__":
    test_all()
    print("Success!")
