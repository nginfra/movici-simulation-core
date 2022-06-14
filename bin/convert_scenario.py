#! /usr/bin/env python3

import glob
import itertools
import json
from pathlib import Path
import traceback
import typing as t

import click
from movici_simulation_core.core.types import Extensible, Model, Plugin
from movici_simulation_core.core.utils import configure_global_plugins


class ScenarioConverter(Extensible):
    def __init__(self) -> None:
        self.model_types: t.Dict[str, t.Type[Model]] = {}

    def use(self, plugin: t.Type[Plugin]):
        plugin.install(self)

    def register_model_type(self, identifier: str, model_type: t.Type[Model]):
        self.model_types[identifier] = model_type

    def convert(self, scenario: dict, debug=False):
        converted = []
        for model_config in scenario.get("models", []):
            name, model_type = model_config.get("name"), model_config.get("type")

            try:
                cls = self.model_types[model_type]
            except KeyError:
                click.echo(f"Skipping model '{name}': unknown type '{model_type}'")
                result = model_config
            except Exception:  # noqa
                click.echo(f"Skipping model '{name}': Unknown failure")
                if debug:
                    traceback.print_exc()
                result = model_config

            else:
                click.echo(f"Converting '{model_type}/{name}'")
                result = cls(model_config).config
                result["name"] = name
                result["type"] = model_type
            finally:
                converted.append(result)

        scenario["models"] = converted
        return scenario


def convert_scenario_in_place(
    scenario_file: t.Union[str, Path], converter: ScenarioConverter, debug=False
):
    click.echo(f"converting scenario {str(scenario_file)}")
    scenario_file = Path(scenario_file)
    scenario = json.loads(scenario_file.read_text())
    result = converter.convert(scenario, debug)
    scenario_file.write_text(json.dumps(result, indent=2))


@click.command()
@click.argument("scenarios", nargs=-1)
@click.option("--debug", is_flag=True, default=False)
@click.option("--no-ignore-plugin-errors", is_flag=True, default=False)
def main(scenarios, debug, no_ignore_plugin_errors):
    converter = ScenarioConverter()
    configure_global_plugins(converter, ignore_missing_imports=(not no_ignore_plugin_errors))

    for file in itertools.chain.from_iterable(
        glob.iglob(path, recursive=True) for path in scenarios
    ):
        try:
            convert_scenario_in_place(file, converter, debug)
        except Exception:  # noqa
            click.echo(f"Error while converting file {file}. skipping...")
            if debug:
                traceback.print_exc()


if __name__ == "__main__":
    main()
