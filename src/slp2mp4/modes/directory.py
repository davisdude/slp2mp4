import pathlib

from slp2mp4.modes.mode import Mode
from slp2mp4.output import Output
import slp2mp4.util as util


class Directory(Mode):
    def iterator(self, root, path):
        if (not path.exists()) or (not path.is_dir()):
            raise FileNotFoundError(path.name)
        slps = list(sorted(path.glob("*.slp"), key=util.natsort))
        if len(slps) > 0:
            yield slps, root
        for child in path.iterdir():
            if child.is_dir():
                yield from self.iterator(root / child.name, child)
