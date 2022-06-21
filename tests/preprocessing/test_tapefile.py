import typing as t
from pathlib import Path

import pytest

from movici_simulation_core.preprocessing.tapefile import (
    InterpolatingTapefile,
    TimeDependentAttribute,
)


def write_csv(content: t.List[t.List[t.Any]], path: Path):
    path.write_text("\n".join(",".join(item for item in row) for row in content))
    return path


@pytest.fixture
def csv_a(tmp_path):
    file = tmp_path / "a.csv"
    return write_csv(
        [
            ["Name", "2021", "2023"],
            ["A", "100", "120"],
            ["B", "100", "80"],
            ["C", "100", "70"],
        ],
        file,
    )


@pytest.fixture
def csv_b(tmp_path):
    file = tmp_path / "b.csv"
    return write_csv(
        [
            ["Name", "2021", "2023"],
            ["A", "1", "3"],
            ["B", "1", "5"],
            ["C", "1", "7"],
        ],
        file,
    )


@pytest.fixture
def init_data():
    return {
        "id": [1, 2, 3],
        "reference": ["A", "B", "C"],
    }


def test_create_empty_tapefile(init_data):
    tapefile = InterpolatingTapefile(
        entity_data=init_data,
        dataset_name="dataset",
        entity_group_name="some_entities",
        reference="reference",
        tapefile_name="some_name",
    )
    assert tapefile.dump_dict() == {
        "name": "some_name",
        "display_name": "some_name",
        "data": {"tabular_data_name": "dataset", "time_series": [], "data_series": []},
    }


def test_create_tapefile(csv_a, csv_b, init_data):
    a1 = TimeDependentAttribute("a", csv_a, "Name")
    a2 = TimeDependentAttribute("b", csv_b, "Name")

    tapefile = InterpolatingTapefile(
        entity_data=init_data,
        dataset_name="dataset",
        entity_group_name="some_entities",
        reference="reference",
        attributes=[a1, a2],
        tapefile_name="some_name",
    )
    seconds = [
        tapefile.get_seconds(2021, 2021),
        tapefile.get_seconds(2022, 2021),
        tapefile.get_seconds(2023, 2021),
    ]
    result = tapefile.dump_dict()
    assert result["data"] == {
        "tabular_data_name": "dataset",
        "time_series": seconds,
        "data_series": [
            {
                "some_entities": {
                    "id": [1, 2, 3],
                    "a": [100, 100, 100],
                    "b": [1, 1, 1],
                }
            },
            {
                "some_entities": {
                    "id": [1, 2, 3],
                    "a": [110, 90, 85],
                    "b": [2, 3, 4],
                }
            },
            {
                "some_entities": {
                    "id": [1, 2, 3],
                    "a": [120, 80, 70],
                    "b": [3, 5, 7],
                }
            },
        ],
    }


def test_out_of_bounds(tmp_path):
    init_data = {
        "id": [1],
        "reference": ["A"],
    }
    csv_a = write_csv([["Name", "2020"], ["A", "1"]], tmp_path / "a.csv")
    csv_b = write_csv([["Name", "2021"], ["A", "2"]], tmp_path / "b.csv")
    a1 = TimeDependentAttribute("a", csv_a, "Name")
    a2 = TimeDependentAttribute("b", csv_b, "Name")
    tapefile = InterpolatingTapefile(
        entity_data=init_data,
        dataset_name="dataset",
        entity_group_name="some_entities",
        reference="reference",
        attributes=[a1, a2],
        tapefile_name="some_name",
    )
    seconds = [
        tapefile.get_seconds(2020, 2020),
        tapefile.get_seconds(2021, 2020),
    ]
    result = tapefile.dump_dict()
    assert result["data"] == {
        "tabular_data_name": "dataset",
        "time_series": seconds,
        "data_series": [
            {
                "some_entities": {
                    "id": [1],
                    "a": [1],
                    "b": [2],
                }
            },
            {
                "some_entities": {
                    "id": [1],
                    "a": [1],
                    "b": [2],
                }
            },
        ],
    }
