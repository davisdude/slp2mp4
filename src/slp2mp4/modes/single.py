import pathlib

from slp2mp4.modes.mode import Mode
from slp2mp4.output import Output


class Single(Mode):
    def iterator(self, root, path):
        if (not path.exists()) or (not path.is_file()):
            raise FileNotFoundError(path.name)
        yield [path], root / path.parent.name / path.name
