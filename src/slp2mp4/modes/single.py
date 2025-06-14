import pathlib

from slp2mp4.modes.mode import Mode
from slp2mp4.output import Output
import slp2mp4.util as util


class Single(Mode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, supports_scoreboard=False)

    def iterator(self, _location, path):
        if (not path.exists()) or (not path.is_file()):
            raise FileNotFoundError(path.name)
        yield [path], util.get_parent_as_path(path), path, None
