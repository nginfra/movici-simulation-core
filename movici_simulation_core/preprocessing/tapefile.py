"""
Create a tapefile from one or more CSV files that contain a yearly changing attribute. The csv
files should be in the form "<key> <year_1> <year_2>, ..." such as:
name, 2020, 2025, 2030
e1  ,  100,  110,  120
e2  ,  100,   90,   85

One or more of these csv files can then be linked to an Attribute and a tapefile can be created
that outputs a value for every year (linearly interpolating between years that do not exist in the
csv files). The entities are matched based on a `reference_attribute` and the `<key>` column in the
csv files.

If multiple csv files are given, every update will contain the interpolated values for all time
dependent attributes, even if the corresponding timestamp is not defined for that tapefile. For
example if csv file "a" defines 2020 as a year, but csv file "b" starts at 2025, then a tapefile
will be generated starting from the timestamp at 2020. The values from csv file "b" will be taken
as the values at 2025 for all years earlier than 2025
"""

from __future__ import annotations

import dataclasses
import datetime
import functools
import json
import typing as t
from pathlib import Path

import pandas as pd


@dataclasses.dataclass
class InterpolatingTapefile:
    entity_data: dict
    dataset_name: str
    entity_group_name: str
    reference: str
    tapefile_name: str
    tapefile_display_name: t.Optional[str] = None
    metadata: dict = None
    attributes: t.List[TimeDependentAttribute] = dataclasses.field(default_factory=list)
    init_data: pd.DataFrame = dataclasses.field(init=False)

    def __post_init__(self):
        self.init_data = self.read_initial_data()

        self.tapefile_display_name = (
            self.tapefile_display_name
            if self.tapefile_display_name is not None
            else self.tapefile_name
        )

    def read_initial_data(self) -> pd.DataFrame:
        all_fields = ("id", self.reference)
        for field in all_fields:
            if field not in self.entity_data:
                raise ValueError(f"field '{field}' not available")

        return pd.DataFrame.from_dict({field: self.entity_data[field] for field in all_fields})

    def add_attribute(self, attribute: TimeDependentAttribute):
        self.attributes.append(attribute)

    def dump(self, file: t.Union[str, Path]):
        if not self.attributes:
            return

        self.ensure_csv_completeness()
        Path(file).write_text(json.dumps(self.dump_dict()))

    def ensure_csv_completeness(self):
        incomplete = {}
        for attr in self.attributes:
            if missing := (set(self.init_data[self.reference]) - set(attr.dataframe[attr.name])):
                incomplete[str(attr.csv_file)] = missing
        if incomplete:
            entities = ((key, name) for key in incomplete for name in incomplete[key])
            raise ValueError(
                "Missing entities in CSV files:\n"
                + "\n".join(f"{csv}: {name}" for csv, name in entities)
            )

    def dump_dict(self):
        interpolators = self.get_interpolators()
        return self.create_content(interpolators)

    def get_interpolators(self):
        return {attr.name: Interpolator(self.get_merged_df(attr)) for attr in self.attributes}

    def get_merged_df(self, attribute: TimeDependentAttribute):
        return self.init_data.merge(
            attribute.dataframe, left_on=self.reference, right_on=attribute.key
        )

    def create_content(self, interpolators: t.Dict[str, Interpolator]):
        tapefile = self.get_scaffold()
        if not interpolators:
            return tapefile
        min_year = min(ip.min_year for ip in interpolators.values())
        max_year = max(ip.max_year for ip in interpolators.values())
        for year in range(min_year, max_year + 1):
            seconds = self.get_seconds(year, min_year)
            tapefile["data"]["time_series"].append(seconds)
            tapefile["data"]["data_series"].append(
                self.create_update(
                    {
                        name: ip.interpolate(year).values.tolist()
                        for name, ip in interpolators.items()
                    },
                )
            )
        return tapefile

    def get_scaffold(self):
        return {
            **(self.metadata.copy() if self.metadata is not None else {}),
            **{
                "name": self.tapefile_name,
                "display_name": self.tapefile_display_name,
                "data": {
                    "tabular_data_name": self.dataset_name,
                    "time_series": [],
                    "data_series": [],
                },
            },
        }

    @staticmethod
    def get_seconds(year: int, reference: int):
        """
        :param year: eg: 2024
        :param reference: 2019

        :return: seconds since reference
        """
        return (datetime.datetime(year, 1, 1) - datetime.datetime(reference, 1, 1)).total_seconds()

    def create_update(self, values: t.Dict[str, list]):
        """
        example:

        .. highlight:: json
        .. code-block:: json

            {
            "entity_group_name": {
                "id": [4, 5, 6],
                "some_attribute": [102, 40, 201]
                "some_other_attribute": [7, 6, 21]
            }
            }

        """
        return {self.entity_group_name: {**{"id": self.init_data["id"].values.tolist()}, **values}}


@dataclasses.dataclass
class TimeDependentAttribute:
    name: str
    csv_file: t.Union[Path, str]
    key: str

    def __post_init__(self):
        self.csv_file = Path(self.csv_file)

    @functools.cached_property
    def dataframe(self):
        return pd.read_csv(self.csv_file)


class Interpolator:
    years: t.List[int]
    min_year: int
    max_year: int

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.infer_years()

    def infer_years(self):
        self.max_year = -1
        self.min_year = 1e14
        self.years = []
        for col in self.df.columns:
            try:
                year = int(col)
            except ValueError:
                continue
            if year < self.min_year:
                self.min_year = year
            if year > self.max_year:
                self.max_year = year

            self.years.append(year)
        self.years.sort()

    def _get_col(self, year: int):
        return self.df[str(year)]

    def interpolate(self, year):
        if year in self.df:
            return self._get_col(year)
        if year <= self.min_year:
            return self._get_col(self.min_year)
        if year >= self.max_year:
            return self._get_col(self.max_year)

        for idx, candidate in enumerate(self.years):
            if candidate > year:
                lower_year = self.years[idx - 1]
                lower_col = self._get_col(lower_year)
                higher_col = self._get_col(candidate)

                return lower_col + (higher_col - lower_col) / (candidate - lower_year) * (
                    year - lower_year
                )
        raise RuntimeError("shouldn't get here")
