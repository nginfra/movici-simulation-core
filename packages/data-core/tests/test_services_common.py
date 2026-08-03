import pathlib

import pytest

from movici_data_core.services.common import tempfile_delete_on_error


def test_can_write_and_read_tempfile_delete_on_error(tmp_path):
    with tempfile_delete_on_error(suffix=".suff", prefix="prefpref", dir=tmp_path) as file:
        file.write(b"asdfasdf")

    assert pathlib.Path(file.name).read_bytes() == b"asdfasdf"


def test_tempfile_delete_on_error_sets_prefix_and_suffix(tmp_path):
    with tempfile_delete_on_error(suffix=".suff", prefix="prefpref", dir=tmp_path) as file:
        pass

    path = pathlib.Path(file.name)
    assert path.parent == tmp_path
    assert path.name.startswith("prefpref")
    assert path.suffix == ".suff"


def test_tempfile_delete_on_error_deletes_file_after_exception(tmp_path):
    with (
        pytest.raises(RuntimeError),
        tempfile_delete_on_error(suffix=".suff", prefix="prefpref", dir=tmp_path) as file,
    ):
        file.write(b"somedata")
        raise RuntimeError
    assert not pathlib.Path(file.name).exists()
