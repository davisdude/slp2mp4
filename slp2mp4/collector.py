# Collects files for rendering. Does NOT determine names, just inputs / outputs.

import dataclasses
import tempfile
import time
import zipfile
from collections import deque
from multiprocessing import Event
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from slp2mp4 import util
from slp2mp4.artifact import ContextArtifact, SlippiArtifact


def create_monitor_event_handler(collector, root: Path):
    class MonitorEventHandler(FileSystemEventHandler):
        def on_created(self, _event: FileSystemEvent):
            # When a directory is created, a `DirCreatedEvent` and one `FileCreatedEvent` per file
            # is triggered. We don't actually care _what_ has been created; the recursive iterator
            # handles that for us. By returning just the root, we avoid processing files for
            # multiple events.
            # NOTE: This is very inefficient for very large directories. A better approach would be
            # to try to aggregate events to minimize recursive traversal. But that seems hard and
            # this is probably fine for now.
            collector.raw_monitor_inputs.append(root)

    return MonitorEventHandler()


@dataclasses.dataclass
class Collection:
    slps: list[SlippiArtifact]
    context: ContextArtifact | None = dataclasses.field(default=None)


@dataclasses.dataclass
class Collector:
    inputs: list[Path]
    kill_event: Event = dataclasses.field(default_factory=Event)
    monitor: bool = dataclasses.field(default=False)
    workdir: Path | None = dataclasses.field(default=None)
    yielded: dict[Path, set] = dataclasses.field(default_factory=dict)
    raw_monitor_inputs: deque = dataclasses.field(default_factory=deque)

    def __post_init__(self):
        if self.workdir is None:
            self.workdir = Path(tempfile.mkdtemp())

    def next(self):
        """Iterator that returns <input>, <collection root>, <collection>."""
        # Set up monitoring
        for i in self.inputs:
            self.yielded[i] = set()
        if self.monitor:
            observer = Observer()
            for i in self.inputs:
                if i.is_dir():
                    handler = create_monitor_event_handler(self, i)
                    observer.schedule(handler, i, recursive=True)
            observer.start()

        # Iterate like normal to catch files that exist before monitoring
        for i in self.inputs:
            for path, artifacts in self._recurse(i, i):
                yield path, artifacts

        # Monitor files
        while self.monitor and not self.kill_event.is_set():
            batch = self._get_monitor_batch()
            if len(batch) == 0:
                time.sleep(1)
                continue
            for i in batch:
                for path, artifacts in self._recurse(i, i):
                    yield path, artifacts
        if self.monitor:
            observer.stop()
            observer.join()

    def _get_monitor_batch(self):
        inputs = set()
        while True:
            try:
                inputs.add(self.raw_monitor_inputs.popleft())
            except IndexError:
                break
        return inputs

    def _recurse(self, key: Path, path: Path, relative: Path | None = None):
        if relative is None:
            relative = path
        if path.is_file():
            # TODO: Don't re-parse files
            if zipfile.is_zipfile(path):
                tmpdir = Path(tempfile.mkdtemp(dir=self.workdir))
                with zipfile.ZipFile(path, "r") as archive:
                    archive.extractall(path=tmpdir)
                yield from self._recurse(key, tmpdir, relative.parent / path.stem)
            elif path.suffix == ".slp" and path not in self.yielded[key]:
                self.yielded[key].add(path)
                yield relative, Collection([SlippiArtifact(path)])
        elif path.is_dir():
            slps = sorted(path.glob("*.slp"), key=util.natsort)
            slp_artifacts = [SlippiArtifact(slp) for slp in slps]
            if (len(slps) > 0) and (len(set(slps) & self.yielded[key]) != len(slps)):
                self.yielded[key].update(slps)
                context = path / "context.json"
                context_artifact = None
                if context.is_file():
                    self.yielded[key].add(context)
                    context_artifact = ContextArtifact(context)
                yield relative, Collection(slp_artifacts, context_artifact)
            for p in path.iterdir():
                yield from self._recurse(key, p, relative / p.name)
