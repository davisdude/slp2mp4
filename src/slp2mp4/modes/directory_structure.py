import pathlib

import pathvalidate

from slp2mp4.modes.mode import Mode
from slp2mp4.output import Output
import slp2mp4.util as util


class DirectoryStructure(Mode):
    def __init__(self, paths, *args, **kwargs):
        super().__init__(paths, *args, **kwargs)
        self.lookups = {}
        self.paths = self._extract_helper(paths)

    # Override to preserve directory structure
    def get_name(self, prefix, path):
        name = path.name
        if self.conf["runtime"]["youtubify_names"]:
            name = name.replace("-", "—")
            name = name.replace("(", "⟮")
            name = name.replace(")", "⟯")
        name = name.removesuffix(".slp")
        name = name.removesuffix(".mp4")
        name += ".mp4"
        sanitized = pathvalidate.sanitize_filepath(
            self.output_directory / prefix / name
        )
        # Name too long; suffix got dropped
        if not sanitized.suffix:
            # Drop beginning of name since it's more likely to be duplicated
            sanitized = sanitized.parent / (sanitized.name[4:] + ".mp4")
        return sanitized

    def iterator(self, _root, path):
        yield self.lookups[path]

    def _extract_helper(self, paths):
        for path in paths:
            abs_path = path.absolute()
            root = (
                pathlib.Path(abs_path.name)
                if path.is_dir()
                else util.get_parent_as_path(path) / abs_path.name
            )
            self._recursive_find(root, path)
        return self.lookups.keys()

    def _recursive_find(self, location, path):
        if not path.is_dir():
            return
        self._add_slps(location, path)
        for child in path.iterdir():
            self._recursive_find(location / child.name, child)

    def _add_slps(self, location, path):
        for filename in path.glob("*.slp"):
            self.lookups[filename] = (
                [filename],
                location,
                pathlib.Path(filename),
            )
