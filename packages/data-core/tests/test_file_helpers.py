import pathlib
import tempfile

import pytest

from movici_data_core.file_helpers import (
    get_mimetype,
    infer_filetype_from_filename_or_mimetype,
    store_file_to_disk,
    tempfile_delete_on_error,
)
from movici_simulation_core.types import FileType


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


async def test_store_file_to_disk(tmp_path):
    data = b"asdfasdfasdf"
    with tempfile.TemporaryFile("w+b") as file:
        file.write(data)
        file.seek(0)

        path = await store_file_to_disk(
            file, tmp_path, filetype=FileType.OTHER, prefix="some-prefix-"
        )
        assert path.suffix == FileType.OTHER.default_extension
        assert path.name.startswith("some-prefix-")
        assert path.read_bytes() == data


async def test_raises_on_non_existing_directory(tmp_path):
    with tempfile.TemporaryFile("w+b") as file:
        with pytest.raises(ValueError, match="path must be an existing directory"):
            await store_file_to_disk(file, tmp_path / "nonexisting", filetype=FileType.OTHER)


async def test_raises_on_file_instead_of_directory(tmp_path):
    path = tmp_path / "afile"
    path.touch()
    assert path.exists()

    with tempfile.TemporaryFile("w+b") as file:
        with pytest.raises(ValueError, match="path must be an existing directory"):
            await store_file_to_disk(file, path, filetype=FileType.OTHER)


@pytest.mark.parametrize(
    "filename, mimetype,expected",
    [
        ("somefile.json", None, FileType.JSON),
        ("somefile", "application/json", FileType.JSON),
        ("somefile.msgpack", "application/json", FileType.JSON),
        ("somefile.msgpack", None, FileType.MSGPACK),
        ("somefile", "application/msgpack", FileType.MSGPACK),
        ("somefile", "application/x-msgpack", FileType.MSGPACK),
        ("somefile.csv", None, FileType.CSV),
        ("somefile", "text/csv", FileType.CSV),
        ("somefile.nc", None, FileType.NETCDF),
        ("somefile", "application/netcdf", FileType.NETCDF),
        ("somefile", "application/x-netcdf", FileType.NETCDF),
        ("somefile.dat", "application/unknown", FileType.OTHER),
        ("somefile.dat", None, FileType.OTHER),
        ("somefile.bin", None, FileType.OTHER),
        ("somefile.asdf", None, FileType.OTHER),
        ("somefile", None, FileType.OTHER),
        ("", None, FileType.OTHER),
        ("", "application/json", FileType.JSON),
        ("", "application/x-msgpack", FileType.MSGPACK),
    ],
)
def test_infer_filetype_from_filename_or_mimetype(filename, mimetype, expected):
    assert infer_filetype_from_filename_or_mimetype(filename, mimetype) == expected


@pytest.mark.parametrize(
    "filetype, mimetype",
    [
        (FileType.JSON, "application/json"),
        (FileType.MSGPACK, "application/x-msgpack"),
        (FileType.CSV, "text/csv"),
        (FileType.NETCDF, "application/x-netcdf"),
        (FileType.OTHER, None),
    ],
)
def test_get_mimetype(filetype, mimetype):
    assert get_mimetype(filetype) == mimetype
