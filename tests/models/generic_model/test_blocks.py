from unittest.mock import Mock

import numpy as np
import pytest
from movici_geo_query import GeoQuery

from movici_simulation_core.core.attribute import PUB, UniformAttribute
from movici_simulation_core.core.attribute_spec import AttributeSpec
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.models.common.entity_groups import (
    GridCellEntity,
    LineEntity,
    PointEntity,
    PolygonEntity,
)
from movici_simulation_core.models.generic_model.blocks import (
    Block,
    EntityGroupBlock,
    FunctionBlock,
    GeoMapBlock,
    GeoReduceBlock,
    InputBlock,
    OutputBlock,
)
from movici_simulation_core.models.generic_model.common import ValidationError


class TestBlock:
    def test_calling_update_marks_as_updated(self):
        class SomeBlock(Block):
            def update(self):
                pass

        block = SomeBlock()
        block.is_updated = False
        block.update()
        assert block.is_updated

    @pytest.mark.parametrize("method", ["setup", "initialize", "update"])
    def test_performs_method_only_once(self, method):
        mock = Mock()
        cls = type("SomeBlock", (Block,), {method: mock})

        block = cls()
        assert mock.call_count == 0

        getattr(block, method)()
        assert mock.call_count == 1

        getattr(block, method)()
        assert mock.call_count == 1

    def test_updates_again_after_reset(self):
        mock = Mock()

        class SomeBlock(Block):
            update = mock

        block = SomeBlock()
        block.update()
        block.reset()
        block.update()

        assert mock.call_count == 2

    def test_sets_up_sources(self):
        source = Mock()

        class SomeBlock(Block):
            def setup(self):
                pass

            def get_sources(self):
                return [source]

        block = SomeBlock()
        block.setup()
        assert source.setup.call_count == 1

    @pytest.mark.parametrize("method", ["setup", "initialize", "update"])
    def test_proxies_method_to_sources(self, method):
        source = Mock()

        SomeBlock = type(
            "SomeBlock", (Block,), {method: Mock(), "get_sources": Mock(return_value=[source])}
        )

        block = SomeBlock()
        getattr(block, method)(state=Mock())
        assert getattr(source, method).call_count == 1


class BaseTestBlock:
    @pytest.fixture
    def entity_group(self):
        return EntityGroupBlock("my_dataset", "my_entities", "point")

    @pytest.fixture
    def additional_attributes(self):
        return [AttributeSpec("some.attribute", float)]

    @pytest.fixture
    def state(self, global_schema):
        return TrackedState(schema=global_schema)

    @pytest.fixture
    def add_data(
        self, state: TrackedState, entity_group: EntityGroupBlock, dataset_to_array_format
    ):
        def add_data_(attribute_data, entity_name=None, is_initial=False):
            entity_name = entity_name or entity_group.entity_name
            state.receive_update(
                dataset_to_array_format({entity_group.dataset: {entity_name: attribute_data}}),
                is_initial=is_initial,
            )

        return add_data_

    def test_validates_succesfully(self, block: Block):
        assert block.validate() is None


class TestInputBlock(BaseTestBlock):
    @pytest.fixture
    def block(self, entity_group):
        return InputBlock(entity_group, "some.attribute")

    def test_setup_sets_attribute_object(self, block: InputBlock, state, global_schema):
        block.setup(state=state, schema=global_schema)
        assert isinstance(block.attribute_object, UniformAttribute)


class TestEntityGroupBlock(BaseTestBlock):
    @pytest.fixture
    def block(src, entity_group):
        entity_group.grid_points = "some_points"
        return entity_group

    @pytest.mark.parametrize(
        "geometry, entity_cls",
        [
            ("point", PointEntity),
            ("line", LineEntity),
            ("polygon", PolygonEntity),
            ("cell", GridCellEntity),
        ],
    )
    def test_registers_geometric_attributes(
        self, geometry, entity_cls, block: EntityGroupBlock, state
    ):
        block.geometry = geometry
        block.setup(state=state)
        assert isinstance(block.entity_group, entity_cls)
        if isinstance(block.entity_group, GridCellEntity):
            assert isinstance(block.entity_group.points, PointEntity)

    def test_invalidates_with_missing_grid_points_when_required(self, block):
        block.geometry = "cell"
        block.grid_points = None
        with pytest.raises(ValidationError):
            block.validate()

    def test_can_retrieve_spatial_index(
        self, block: EntityGroupBlock, add_data, state: TrackedState
    ):
        block.setup(state=state)
        add_data(
            {"id": [0], "geometry.x": [0], "geometry.y": [0]},
            is_initial=True,
        )

        assert isinstance(block.spatial_index, GeoQuery)


class TestGeoMapBlock(BaseTestBlock):
    @pytest.fixture
    def block(self, entity_group, state):
        target_entity_group = EntityGroupBlock("my_dataset", "other_entities", "point")
        entity_group.setup(state=state)
        target_entity_group.setup(state=state)
        return GeoMapBlock(source=entity_group, target=target_entity_group, function="nearest")

    def test_invalidates_missing_distance_field(self, block: GeoMapBlock):
        block.function = "distance"
        with pytest.raises(ValidationError):
            block.validate()

    def test_initialize_creates_mapping(self, block: GeoMapBlock, add_data):
        add_data(
            {"id": [0, 1], "geometry.x": [1, 0], "geometry.y": [1, 0]},
            is_initial=True,
        )
        add_data(
            {"id": [10], "geometry.x": [0], "geometry.y": [0]},
            entity_name=block.target.entity_name,
            is_initial=True,
        )
        block.initialize()
        assert np.array_equal(block.mapping.indices, [1])


class TestGeoReduceBlock(BaseTestBlock):
    @pytest.fixture
    def reduce_func(self):
        return "sum"

    @pytest.fixture
    def block(self, entity_group, reduce_func):
        source = InputBlock(entity_group=entity_group, attribute_name="some.attribute")
        target = GeoMapBlock(
            source=entity_group,
            target=EntityGroupBlock("my_dataset", "other_entitites", "polygon"),
            function="overlap",
        )
        return GeoReduceBlock(source, target, reduce_func)

    @pytest.fixture
    def initialized_block(self, block: GeoReduceBlock, state, add_data):
        block.setup(state=state)
        add_data(
            {
                "id": [0, 1],
                "geometry.x": [1, 0],
                "geometry.y": [1, 0],
                "some.attribute": [1.0, 2.0],
            },
            is_initial=True,
        )
        add_data(
            {
                "id": [10, 11],
                "geometry.polygon": [
                    [[-2, -2], [-2, 2], [2, 2], [2, -2], [-2, -2]],
                    [[3, 3], [3, 2], [2, 2], [2, 3], [3, 3]],
                ],
            },
            entity_name=block.target.target.entity_name,
            is_initial=True,
        )
        block.initialize()
        return block

    def test_invalidates_when_source_attribute_doesnt_match_geomap_source(self, block):
        source = block.target.source
        block.target.source = block.target.target
        block.target.target = source
        with pytest.raises(ValidationError):
            block.validate()

    @pytest.mark.parametrize(
        "reduce_func, expected",
        [
            ("min", [1, np.nan]),
            ("max", [2, np.nan]),
            ("sum", [3, 0]),
        ],
    )
    def test_update_calculates_result(self, initialized_block, reduce_func, expected):
        initialized_block.update()
        assert np.array_equal(initialized_block.data, expected, equal_nan=True)


class TestFunctionBlock(BaseTestBlock):
    @pytest.fixture
    def block(self, entity_group):
        return FunctionBlock(
            sources={"attr": InputBlock(entity_group, "some.attribute")}, expression="attr*2"
        )

    @pytest.fixture
    def initialized_block(self, state, block, add_data):
        block.setup(state=state)
        add_data(
            {
                "id": [0, 1],
                "geometry.x": [1, 0],
                "geometry.y": [1, 0],
                "some.attribute": [1.0, 2.0],
            },
            is_initial=True,
        )

        block.initialize()
        return block

    @pytest.mark.parametrize(
        "sources",
        [
            {
                "attr": InputBlock(
                    EntityGroupBlock("some_dataset", "some_entities", geometry="point"),
                    "some.attribute",
                ),
                "other": InputBlock(
                    EntityGroupBlock("other_dataset", "some_entities", geometry="point"),
                    "some.attribute",
                ),
            },
            {},
        ],
    )
    def test_invalidates_invalid_sources(self, block, sources):
        block.sources = sources
        with pytest.raises(ValidationError):
            block.validate()

    def test_calculates_result(self, initialized_block):
        initialized_block.update()
        assert np.array_equal(initialized_block.data, [2, 4])


class TestOutputBlock(BaseTestBlock):
    @pytest.fixture
    def block(self, entity_group, state):
        result = OutputBlock(
            source=InputBlock(entity_group, "some_attribute"), attribute_name="other_attribute"
        )
        result.setup(state=state)
        return result

    def test_setup_sets_up_state(self, block, state: TrackedState):
        assert isinstance(block.attribute_object, UniformAttribute)
        assert state.get_attribute("my_dataset", "my_entities", "other_attribute").flags == PUB

    def test_update_sets_data(self, block, state, add_data):
        add_data(
            {
                "id": [0, 1],
                "some_attribute": [1.0, 2.0],
            },
            is_initial=True,
        )
        block.initialize()
        block.update()

        attr = state.get_attribute("my_dataset", "my_entities", "other_attribute")
        assert np.array_equal(attr.array, [1.0, 2.0])
