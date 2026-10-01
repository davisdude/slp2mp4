# Collects files for rendering. Does NOT determine names, just inputs / outputs.

import dataclasses
import shutil
import tempfile
import time
import zipfile
from collections import deque
from collections.abc import Generator
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
            # TODO: Check event info; only append if directory or slp/zip file

    return MonitorEventHandler()


@dataclasses.dataclass(frozen=True)
class RenderRequest:
    """Request for a game to be rendered."""

    slp: SlippiArtifact


@dataclasses.dataclass(frozen=True)
class ConcatRequest:
    """Request for a set to be rendered."""

    final: Path
    slps: tuple[SlippiArtifact, ...]


@dataclasses.dataclass
class Collector:
    inputs: list[Path]
    stop_event: Event = dataclasses.field(default_factory=Event)
    monitor: bool = dataclasses.field(default=False)
    workdir: Path | None = dataclasses.field(default=None)

    created_dirs: list[Path] = dataclasses.field(default_factory=list, init=False)
    encountered: set[Path] = dataclasses.field(default_factory=set, init=False)
    to_concat: dict[Path, tuple[Path, Path]] = dataclasses.field(
        default_factory=dict, init=False
    )
    raw_monitor_inputs: deque = dataclasses.field(default_factory=deque, init=False)
    done: bool = dataclasses.field(default=False, init=False)

    def next(self) -> Generator[RenderRequest | ConcatRequest, None, None]:
        try:
            yield from self._next()
        finally:
            self.done = True

    def cleanup(self):
        for d in self.created_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _next(self):
        # Set up monitoring
        monitoring = []
        if self.monitor:
            observer = Observer()
            for i in self.inputs:
                if i.is_dir():
                    monitoring.append(i)
                    handler = create_monitor_event_handler(self, i)
                    observer.schedule(handler, i, recursive=True)
            observer.start()

        # Iterate like normal to catch files that exist before monitoring
        for i in self.inputs:
            yield from self._recurse(i, i)

        # Monitor files
        while self.monitor and not self.stop_event.is_set() and monitoring:
            batch = self._get_monitor_batch()
            if len(batch) == 0:
                time.sleep(1)
                continue
            for i in batch:
                yield from self._recurse(i, i)
        # Drain batch after monitoring is done
        batch = self._get_monitor_batch()
        for i in batch:
            yield from self._recurse(i, i)

        if self.monitor:
            observer.stop()
            observer.join()

        for root, (input_path, name) in self.to_concat.items():
            slps = self._get_dir_slps(root)
            if slps:
                yield input_path, ConcatRequest(name, slps)

        self.done = True

    def _get_monitor_batch(self):
        inputs = set()
        while True:
            try:
                inputs.add(self.raw_monitor_inputs.popleft())
            except IndexError:
                break
        return inputs

    def _recurse(
        self,
        input_path: Path,
        path: Path,
        relative: Path = Path("."),
        in_zip: bool = False,
        in_dir: bool = False,
    ):
        if not path.exists():
            raise RuntimeError(f"Input '{path}' does not exist!")
        if path.is_file():
            if path in self.encountered:
                return
            self.encountered.add(path)
            if zipfile.is_zipfile(path):
                tmpdir = Path(tempfile.mkdtemp(dir=self.workdir))
                self.created_dirs.append(tmpdir)
                with zipfile.ZipFile(path, "r") as archive:
                    archive.extractall(path=tmpdir)
                yield from self._recurse(
                    input_path, tmpdir, relative.parent / path.stem, True, in_dir
                )
            elif path.suffix == ".slp":
                parent = path.resolve().parent
                context = parent / "context.json"
                context_artifact = None
                slps = sorted(parent.glob("*.slp"), key=util.natsort)
                index = slps.index(path.resolve())
                if context.exists():
                    context_artifact = ContextArtifact(context)
                if relative == Path("."):
                    name = Path(path.with_suffix(".mp4").name)
                else:
                    name = relative.parent / path.with_suffix(".mp4").name
                slp = SlippiArtifact(path, index, context_artifact)
                yield input_path, RenderRequest(slp)
                if not in_dir:
                    yield input_path, ConcatRequest(name, (slp,))
        else:
            if relative == Path("."):
                name = Path(path.name + ".mp4")
            else:
                name = relative.parent / (relative.name + ".mp4")

            for p in path.iterdir():
                yield from self._recurse(input_path, p, relative / p.name, in_zip, True)

            if in_zip or not self.monitor:
                slps = self._get_dir_slps(path)
                if slps:
                    yield input_path, ConcatRequest(name, slps)
            else:
                self.to_concat[path] = (input_path, name)

    def _get_dir_slps(self, path: Path):
        slp_paths = tuple(sorted(path.glob("*.slp"), key=util.natsort))
        context = path / "context.json"
        context_artifact = None
        if context.exists():
            context_artifact = ContextArtifact(context)
        return tuple(
            SlippiArtifact(slp_path, i, context_artifact)
            for i, slp_path in enumerate(slp_paths)
        )
