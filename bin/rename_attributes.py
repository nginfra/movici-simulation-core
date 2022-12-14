#! /usr/bin/env python3
import csv
import shutil
import typing as t
from pathlib import Path

import click

from movici_simulation_core.core.data_format import data_keys
from movici_simulation_core.core.state import parse_special_values

try:
    import orjson as _orjson

    loads = _orjson.loads

    def dumps(data, indent=None):
        option = 0 if indent is None else _orjson.OPT_INDENT_2
        return _orjson.dumps(data, option=option)

except ImportError:
    import json as _json

    def dumps(*args, **kwargs):
        return _json.dumps(*args, **kwargs).encode()

    loads = _json.loads

DEFAULT_ATTRIBUTE_MAPPING_FILE = Path(__file__).parent.joinpath("attribute_mapping.csv")


def iter_attributes(data_section, component=None):
    for key, val in data_section.items():
        if isinstance(val, dict):
            yield from iter_attributes(val, component=key)
        else:
            yield ((component, key), val)


def parse_attribute_csv(filename, skip_headers=True):
    with open(filename, newline="") as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=("old_component", "old_name", "new_name"))
        if skip_headers:
            next(reader)
        return {
            (row["old_component"] or None, row["old_name"]): row["new_name"]
            for row in reader
            if row["new_name"]
        }


class Converter:
    def __init__(
        self, attribute_mapping, pretty, save_original, special_key, glob_pattern="*.json"
    ):
        self.mapping = parse_attribute_csv(attribute_mapping)
        self.pretty = pretty
        self.save_original = save_original
        self.glob_pattern = glob_pattern
        self.special_key = special_key

    def convert(self, path: Path):
        path = Path(path).expanduser()
        if path.is_dir():
            files = path.glob(self.glob_pattern)
            self.try_convert_multiple(file for file in files if file.is_file())
        elif path.is_file():
            self.try_convert_file(path)
        else:
            raise FileNotFoundError(f"{str(path)} is not a valid file or directory")

    def try_convert_multiple(self, files: t.Iterable[Path]):
        for file in files:
            self.try_convert_file(file)

    def try_convert_file(self, file: Path):
        try:
            click.echo(f"converting {str(file)}... ", nl=False)
            changed = self.convert_file(file)
        except (ValueError, TypeError) as e:
            click.echo("ERROR")
            click.echo(f"{str(e)}")
        else:
            click.echo("SUCCESS" if changed else "SKIPPED")

    def convert_file(self, file: Path):
        dataset_file = Path(file)
        dataset_dict: dict = loads(dataset_file.read_bytes())
        changed = False
        for key in data_keys(dataset_dict):
            result, changed_ = self.convert_data_section(dataset_dict[key])
            dataset_dict[key] = result
            changed |= changed_

        if is_tabular(dataset_dict):
            key = "data"
            result, changed_ = self.convert_tabular(dataset_dict[key])
            dataset_dict[key] = result
            changed |= changed_

        general_key = "general"
        if general_section := dataset_dict.get(general_key):
            result, changed_ = self.convert_general_section(general_section)
            dataset_dict[general_key] = result
            changed |= changed_

        if changed:
            if self.save_original:
                shutil.copyfile(dataset_file, str(dataset_file) + ".orig")
            dataset_file.write_bytes(dumps(dataset_dict, indent=2 if self.pretty else None))
        return changed

    def convert_tabular(self, data_section):
        data_series = data_section.get("data_series")
        changed = False

        if not isinstance(data_series, list):
            return data_section, changed

        new_data_series = []
        for sub_data in data_series:
            result, changed_ = self.convert_data_section(sub_data)
            new_data_series.append(result)
            changed |= changed_
        data_section["data_series"] = new_data_series
        return data_section, changed

    def convert_data_section(self, data_section: dict):
        rv = {}
        changed = False
        for entity_group, attribute_data in data_section.items():
            entity_data = {}
            for key, data in iter_attributes(attribute_data):
                new_name, changed_ = self.get_new_attribute_name(key, scope=f"data/{entity_group}")
                changed |= changed_

                entity_data[new_name] = data

            rv[entity_group] = entity_data
        return rv, changed

    def get_new_attribute_name(self, comp_attr, scope=""):
        component, attribute = comp_attr
        if (new_name := self.mapping.get(comp_attr)) is not None:
            return new_name, True
        elif component is None:
            return attribute, False

        error_prefix = "Non-mapped attribute found" + (f" in {scope}" if scope else "")
        raise ValueError(f"{error_prefix}: {component}/{attribute}")

    def convert_general_section(self, general_section: dict):
        all_special_keys = {"no_data", "special"}
        changed = False
        special_values = parse_special_values(general_section, special_keys=all_special_keys)
        flattened = (
            (entity_group, key, value)
            for entity_group, e_section in special_values.items()
            for key, value in e_section.items()
        )
        new_special_values = {}
        for entity_group, key, value in flattened:
            new_name, changed_ = self.get_new_attribute_name(key, scope="general section")
            changed |= changed_
            new_special_values[f"{entity_group}.{new_name}"] = value

        for key in all_special_keys - {self.special_key}:
            if key in general_section:
                del general_section[key]
                changed = True
        general_section[self.special_key] = new_special_values

        return general_section, changed


def is_tabular(dataset_dict):
    return dataset_dict.get("type") == "tabular" and isinstance(dataset_dict.get("data"), dict)


@click.command()
@click.argument("path")
@click.option(
    "-a",
    "--attribute-mapping",
    help="path the attribute mapping csv",
    type=click.Path(),
    default=DEFAULT_ATTRIBUTE_MAPPING_FILE,
)
@click.option("--pretty/--no-pretty", "-p/", default=False)
@click.option("--save-original/--no-save-original", "-o/", default=False)
@click.option(
    "--special-key",
    type=click.Choice(["special", "no_data"], case_sensitive=False),
    default="no_data",
)
def main(path, attribute_mapping, pretty, save_original, special_key):
    path = Path(path)
    converter = Converter(attribute_mapping, pretty, save_original, special_key)
    converter.convert(path)


if __name__ == "__main__":
    main()
