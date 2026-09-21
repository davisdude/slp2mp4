# Collects files for rendering. Does NOT determine names, just inputs / outputs.

import dataclasses
import tempfile
import zipfile
from multiprocessing import Event
from pathlib import Path

from slp2mp4 import util
from slp2mp4.artifact import Artifact, ContextArtifact, SlippiArtifact


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
            self.workdir = tempfile.mkdtemp()

    def next(self):
        """Iterator that returns <input>, <collection root>, <collection>."""
        for i in self.inputs:
            self.yielded[i] = set()
            for path, artifacts in self._recurse(i, i):
                yield i, path, Collection(artifacts)

    def _recurse(self, key: Path, path: Path, relative: Path | None=None):
        if relative is None:
            relative = path
        if path.is_file():
            if zipfile.is_zipfile(path):
                tmpdir = Path(tempfile.mkdtemp(dir=self.workdir))
                with zipfile.ZipFile(path, "r") as archive:
                    archive.extractall(path=tmpdir)
                yield from self._recurse(key, tmpdir, relative.parent / path.stem)
            elif path.suffix == ".slp" and path not in self.yielded[key]:
                self.yielded[key].add(path)
                yield relative, [SlippiArtifact(path)]
        elif path.is_dir():
            slps = list(sorted(path.glob("*.slp"), key=util.natsort))
            self.yielded[key].update(slps)
            artifacts = [SlippiArtifact(slp) for slp in slps]
            if len(slps) > 0:
                context = path / "context.json"
                if context.is_file():
                    self.yielded[key].add(context)
                    artifacts.append(ContextArtifact(context))
                yield relative, artifacts
            for p in path.iterdir():
                yield from self._recurse(key, p, relative / p.name)

# TODO: monitor (snapshot on call + watchdog.observer)
