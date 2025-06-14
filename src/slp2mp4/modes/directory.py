import pathlib

from slp2mp4.modes.mode import Mode
from slp2mp4.output import Output
import slp2mp4.util as util


class Directory(Mode):
    def __init__(self, paths, *args, **kwargs):
        super().__init__(paths, *args, **kwargs)
        self.lookups = {}
        self.paths = self._extract_helper(paths)

    def iterator(self, _root, path):
        yield self.lookups[path]

    def _extract_helper(self, paths):
        for path in paths:
            root = (
                pathlib.Path(path.absolute().name)
                if path.is_dir()
                else util.get_parent_as_path(path) / path.stem
            )
            self._recursive_find(root, path)
        return self.lookups.keys()

    def _recursive_find(self, location, path):
        if not path.is_dir():
            return
        self._add_slps(location, path)
        for child in path.iterdir():
            self._recursive_find(location / child.stem, child)

    def _add_slps(self, location, path):
        slps = list(sorted(path.glob("*.slp"), key=util.natsort))
        if len(slps) > 0:
            context_path = path / "context.json"
            context = context_path if context_path.exists() else None
            self.lookups[location] = (
                slps,
                location.parent,
                pathlib.Path(location.name),
                context,
            )
