import pathlib
import shutil
import tempfile
import zipfile

import pathlib

from slp2mp4.modes.directory import Directory
from slp2mp4.output import Output
import slp2mp4.util as util


class Zip(Directory):
    def __init__(self, *args, **kwargs):
        self.tmpdirs = []
        super().__init__(*args, **kwargs)

    def _recursive_find(self, location, path, fromzip=False):
        if zipfile.is_zipfile(path):
            tmpdir = pathlib.Path(tempfile.mkdtemp())
            self.tmpdirs.append(tmpdir)
            with zipfile.ZipFile(path, "r") as zfile:
                zfile.extractall(path=tmpdir)
            name = location.name
            if location.suffix.lower() == ".zip":
                name = location.stem
            self._recursive_find(location.parent / name, tmpdir, True)
        else:
            self._add_slps(location, path, fromzip)
            for child in path.iterdir():
                if child.is_dir():
                    self._recursive_find(location / child.name, child, fromzip)
                elif zipfile.is_zipfile(child):
                    name = child.name
                    if child.suffix.lower() == ".zip":
                        name = child.stem
                    self._recursive_find(location / name, child, fromzip)

    def _add_slps(self, location, path, fromzip):
        if not fromzip:
            return
        super()._add_slps(location, path)

    def cleanup(self):
        for tmpdir in self.tmpdirs:
            shutil.rmtree(tmpdir)
        self.tmpdirs = []
