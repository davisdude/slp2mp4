# Collects files for rendering. Does NOT determine names, just inputs / outputs.

import dataclasses
from tempfile import NamedTemporaryFile, TemporaryDirectory
from multiprocessing import Event
from pathlib import Path

from slp2mp4 import util
from slp2mp4.artifact import Artifact, SlippiArtifact


@dataclasses.dataclass
class Collection:
    inputs: list[Artifact]


@dataclasses.dataclass
class Collector:
    inputs: list[Path]
    workdir: Path | None = dataclasses.field(default=None)
    yielded: dict[Path, set] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        if self.workdir is None:
            self.workdir = TemporaryDirectory()

    def next(self):
        """Iterator that returns <input>, <collection root>, <collection>."""
        for i in self.inputs:
            self.yielded[i] = set()
            for path, slps in self._recurse(i, i):
                yield i, path, Collection([SlippiArtifact(s) for s in slps])

    def _recurse(self, key: Path, path: Path):
        if path.is_file() and path.suffix == ".slp" and path not in self.yielded[key]:
            self.yielded[key].add(path)
            yield path, [path]
        elif path.is_dir():
            slps = list(sorted(path.glob("*.slp"), key=util.natsort))
            if len(slps) > 0:
                self.yielded[key].update(slps)
                yield path, slps
            for p in path.iterdir():
                yield from self._recurse(key, p)

# TODO: zip
# TODO: monitor (snapshot on call + watchdog.observer)
