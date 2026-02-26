import pathlib

from slp2mp4.modes.mode import Mode
from slp2mp4.output import Output
import slp2mp4.util as util


class Single(Mode):
    def iterator(self, _location, path):
        if (not path.exists()) or (not path.is_file()):
            raise FileNotFoundError(path.name)
        if path.suffix.lower() == ".slp":
            context_path = path.parent / "context.json"
            context = context_path if context_path.exists() else None
            index = 0
            if context:
                slps = list(sorted(path.parent.glob("*.slp"), key=util.natsort))
                index = slps.index(path)
            yield [path], util.get_parent_as_path(path), path.parent / path.stem, context, [index]
