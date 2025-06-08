import atexit
import pathlib
import shutil
import tempfile
import zipfile

import pathlib

from slp2mp4.modes.mode import Mode
from slp2mp4.output import Output
from slp2mp4.modes.directory import Directory
import slp2mp4.util as util


# TODO: Use context.json to get names?


def _recursive_extract(tmpdir, path):
    newdir = tmpdir / path.stem
    newdir.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, "r") as zfile:
            zfile.extractall(path=newdir)
    for zfile in newdir.glob("*.zip"):
        _recursive_extract(newdir, zfile)


def _extract(file):
    tmpdir = pathlib.Path(tempfile.mkdtemp())
    atexit.register(shutil.rmtree, tmpdir)
    _recursive_extract(tmpdir, file)
    return tmpdir


class ReplayManager(Directory):
    def __init__(self, paths: list[pathlib.Path], output_directory: pathlib.Path):
        self.paths = [_extract(path) for path in paths]
        self.output_directory = output_directory
