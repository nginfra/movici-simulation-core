import pathlib


def run_file(path):
    content = pathlib.Path(path).read_text()
    locals = {}
    exec(content, None, locals)
    return locals


EXAMPLES_DIR = pathlib.Path(__file__).parents[1].joinpath("examples")


def test_custom_datasource():
    path = EXAMPLES_DIR / "custom_datasource.py"
    result = run_file(path)
    assert result["dataset"]["data"]["point_entities"]["some_attribute"] == [3, 7]
