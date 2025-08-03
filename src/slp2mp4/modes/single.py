import pathlib

from slp2mp4.modes.mode import Mode
from slp2mp4.output import Output
import slp2mp4.util as util


class Single(Mode):
    def iterator(self, _location, path):
        if (not path.exists()) or (not path.is_file()):
            raise FileNotFoundError(path.name)
        if path.suffix.lower() == ".slp":
            yield [path], util.get_parent_as_path(path), path.parent / path.stem, None
