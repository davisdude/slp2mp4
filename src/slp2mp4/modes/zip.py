import atexit
import pathlib
import shutil
import tempfile
import zipfile

import pathlib

from slp2mp4.modes.directory import Directory
from slp2mp4.output import Output
import slp2mp4.util as util


# TODO: Use context.json to get names?
def _make_tmpdir():
    tmpdir = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, tmpdir)
    return pathlib.Path(tmpdir)


class Zip(Directory):
    def _recursive_find(self, location, path, fromzip=False):
        if zipfile.is_zipfile(path):
            tmpdir = _make_tmpdir()
            with zipfile.ZipFile(path, "r") as zfile:
                zfile.extractall(path=tmpdir)
            self._recursive_find(location, tmpdir, True)
        else:
            self._add_slps(location, path, fromzip)
            for child in path.iterdir():
                if child.is_dir() or zipfile.is_zipfile(child):
                    self._recursive_find(location / child, child, fromzip)

    def _add_slps(self, location, path, fromzip):
        if not fromzip:
            return
        super()._add_slps(location, path)
