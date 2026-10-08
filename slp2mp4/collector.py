# Collects files for rendering. Does NOT determine names, just inputs / outputs.

import dataclasses
import shutil
import tempfile
import time
import zipfile
from collections import deque
from collections.abc import Generator
from logging import Logger
from multiprocessing import Event
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from slp2mp4 import log, util
from slp2mp4.artifact import ContextArtifact, SlippiArtifact


def create_monitor_event_handler(collector, root: Path):
    class MonitorEventHandler(FileSystemEventHandler):
        def on_any_event(self, event: FileSystemEvent):
            # When a directory is created, a `DirCreatedEvent` and one `FileCreatedEvent` per file
            # are triggered. We don't actually care _what_ has been created; the recursive iterator
            # handles that for us. By returning just the root, we avoid processing files for
            # multiple events.
            # NOTE: This is very inefficient for very large directories. A better approach would be
            # to try to aggregate events to minimize recursive traversal. But that seems hard and
            # this is probably fine for now.
            path = Path(event.src_path)
            if event.is_directory or (path.suffix.lower() in (".slp", ".zip")):
                collector.raw_monitor_inputs.append(root)

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


@dataclasses.dataclass(frozen=True)
class RecurseState:
    relative: Path = dataclasses.field(default=Path("."))
    in_dir: bool = dataclasses.field(default=False)
    in_zip: bool = dataclasses.field(default=False)


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
    log: Logger | None = dataclasses.field(default=None, init=False)

    def __post_init__(self):
        self.log = log.get_logger()

    def next(self) -> Generator[tuple[Path, RenderRequest | ConcatRequest], None, None]:
        try:
            yield from self._next()
        finally:
            self.done = True

    def cleanup(self):
        for d in self.created_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _next(self):
        observer = None
        try:
            actually_monitoring, observer = self._start_monitoring()

            # Iterate like normal to catch files that exist before monitoring
            for i in self.inputs:
                yield from self._recurse(i, i)
            if actually_monitoring:
                yield from self._monitor()
        finally:
            if observer is not None:
                observer.stop()
                observer.join()

        # Since we have no way of knowing when directories in monitor mode are
        # finalized, they are deferred until monitoring is finished
        for root, (input_path, name) in self.to_concat.items():
            slps = self._get_dir_slps(root)
            if slps:
                yield input_path, ConcatRequest(name, slps)

    def _start_monitoring(self):
        actually_monitoring = False
        observer = None
        if self.monitor:
            observer = Observer()
            for i in self.inputs:
                if i.is_dir():
                    actually_monitoring = True
                    handler = create_monitor_event_handler(self, i)
                    observer.schedule(handler, i, recursive=True)
            observer.start()
        return actually_monitoring, observer

    def _monitor(self):
        while self.monitor and not self.stop_event.is_set():
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

    def _get_monitor_batch(self):
        inputs = set()
        while True:
            try:
                inputs.add(self.raw_monitor_inputs.popleft())
            except IndexError:
                break
        return inputs

    def _recurse(self, input_path: Path, path: Path, state: RecurseState | None = None):
        if state is None:
            state = RecurseState()
        if not path.exists():
            self.log.info(f"Input '{path}' does not exist! Skipping.")
            return
        if path.is_file():
            if path in self.encountered:
                return
            if zipfile.is_zipfile(path):
                self.encountered.add(path)
                yield from self._handle_zip(input_path, path, state)
            elif path.suffix.lower() == ".slp":
                # TODO: Check if it's actually a slippi file
                self.encountered.add(path)
                yield from self._handle_slp(input_path, path, state)
        else:
            yield from self._handle_dir(input_path, path, state)

    def _handle_zip(self, input_path: Path, path: Path, state: RecurseState):
        tmpdir = Path(tempfile.mkdtemp(dir=self.workdir))
        self.created_dirs.append(tmpdir)
        with zipfile.ZipFile(path, "r") as archive:
            archive.extractall(path=tmpdir)
        new_state = RecurseState(state.relative.parent / path.stem, state.in_dir, True)
        yield from self._recurse(input_path, tmpdir, new_state)

    def _handle_slp(self, input_path: Path, path: Path, state: RecurseState):
        slp = self._get_slp(path)
        if state.relative == Path("."):
            name = Path(path.with_suffix(".mp4").name)
        else:
            name = state.relative.parent / path.with_suffix(".mp4").name
        yield input_path, RenderRequest(slp)
        if not state.in_dir:
            yield input_path, ConcatRequest(name, (slp,))

    def _handle_dir(self, input_path: Path, path: Path, state: RecurseState):
        if state.relative == Path("."):
            name = Path(path.resolve().name + ".mp4")
        else:
            name = state.relative.parent / (state.relative.name + ".mp4")
        for p in path.iterdir():
            if p not in self.created_dirs:
                new_state = RecurseState(state.relative / p.name, True, state.in_zip)
                yield from self._recurse(input_path, p, new_state)
        if state.in_zip or not self.monitor:
            slps = self._get_dir_slps(path)
            if slps:
                yield input_path, ConcatRequest(name, slps)
        elif path not in self.created_dirs:
            self.to_concat[path] = (input_path, name)

    def _get_context(self, path: Path):
        context = path / "context.json"
        if context.exists():
            return ContextArtifact(context).data
        return None

    def _get_slp(self, path: Path):
        resolved = path.resolve()
        slp_paths = tuple(sorted(resolved.parent.glob("*.slp"), key=util.natsort))
        index = slp_paths.index(resolved)
        return SlippiArtifact(path, index, self._get_context(path.parent))

    def _get_dir_slps(self, path: Path):
        slp_paths = tuple(sorted(path.glob("*.slp"), key=util.natsort))
        context = self._get_context(path)
        return tuple(
            SlippiArtifact(slp_path, i, context) for i, slp_path in enumerate(slp_paths)
        )
