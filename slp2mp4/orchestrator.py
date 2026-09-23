# Takes collections and creates tasks / schedules them

import concurrent.futures
import dataclasses
import shutil
import tempfile
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from logging import Logger
from multiprocessing import Event
from pathlib import Path

import psutil

from slp2mp4 import log
from slp2mp4.artifact import Artifact, Mp4Artifact, TimestampArtifact
from slp2mp4.collector import Collection, Collector
from slp2mp4.config import Config
from slp2mp4.scheduler import Scheduler
from slp2mp4.task import ConcatVideosTask, RenderGameTask, Task
from slp2mp4.worker import Worker


@dataclasses.dataclass
class Orchestrator:
    inputs: list[Path]
    conf: Config
    kill_event: Event = dataclasses.field(default_factory=Event)
    monitor: bool = dataclasses.field(default=False)
    dry_run: bool = dataclasses.field(default=False)
    num_procs: int | None = dataclasses.field(default=None)
    workdir: Path | None = dataclasses.field(default=None)
    collector: Collector | None = dataclasses.field(default=None)
    worker: Worker | None = dataclasses.field(default=None)
    scheduler: Scheduler | None = dataclasses.field(default=None)
    log: Logger | None = dataclasses.field(default=None)
    created_dirs: list[Path] = dataclasses.field(default_factory=list, init=False)
    tmp_artifacts: list[Artifact] = dataclasses.field(default_factory=list, init=False)

    def __post_init__(self):
        if self.num_procs is None:
            self.num_procs = self.conf.runtime.parallel
        if self.num_procs == 0:
            self.num_procs = psutil.cpu_count(logical=False) or 1
        if self.workdir is None:
            self.workdir = Path(tempfile.mkdtemp())
            self.created_dirs.append(self.workdir)
        if self.collector is None:
            self.collector = Collector(
                self.inputs, self.kill_event, self.monitor, self.workdir
            )
        if self.worker is None:
            self.worker = Worker(self.conf, self.kill_event)
        if self.scheduler is None:
            self.scheduler = Scheduler({"cpu": self.num_procs})
        if self.log is None:
            self.log = log.get_logger()

    def format_output_name(self, path: Path):
        # TODO: pathvalidate
        # TODO: youtubify
        # TODO: Preserve directory structure
        return path

    def get_output_name(self, path: Path, _collection: Collection):
        # TODO: Rename using context.json
        if path.is_file():
            return self.format_output_name(path.with_suffix(".mp4"))
        if path != Path("."):
            parent = path.parent
        else:
            parent = Path("..")
            path = path.expanduser().absolute()
        return self.format_output_name(parent / (path.name + ".mp4"))

    def next(self):
        """Iterator that returns <input>, <task>."""
        tasks = []
        for input_item, path, collection in self.collector.next():
            tmp_vids = []
            for index, slp in enumerate(collection.slps):
                _handle, tmp = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp))
                tmp_vids.append(vid)
                self.tmp_artifacts.append(vid)
                inputs = [slp]
                if collection.context is not None:
                    inputs.append(collection.context)
                tasks.append(RenderGameTask(f"render {slp.path}", inputs, [vid], index))
            _handle, tmp = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
            vid_path = Path(tmp)
            vid = Mp4Artifact(vid_path)
            timestamps = TimestampArtifact(vid_path.with_suffix(".txt"))
            self.tmp_artifacts.extend([vid, timestamps])
            tasks.append(
                ConcatVideosTask(f"concat {vid.path}", tmp_vids, [vid, timestamps])
            )
            yield input_item, tasks

        # TODO: yield more concats based on config.combine_mode
        # leaves = self.scheduler.get_leaves()

        # TODO: Move final tmp files to real names

    def _print_leaf(self, leaf: Task, indent_level=0):
        indent = "\t"
        outputs = (", ").join(o.path.name for o in leaf.outputs)
        self.log.info(f"{indent * indent_level}{outputs}")
        for i in leaf.inputs:
            task = self.scheduler.get_producer(i)
            if task:
                self._print_leaf(task, indent_level + 1)
            else:
                self.log.info(f"{indent * (indent_level + 1)}{i.path.name}")

    def collect_tasks(self):
        tasks_by_input: dict[Path, list[Task]] = defaultdict(list)
        for input_item, tasks in self.next():
            tasks_by_input[input_item].extend(tasks)
            self.scheduler.submit(tasks)

        leaves = self.scheduler.get_leaves()
        if self.dry_run:
            for leaf in leaves:
                self._print_leaf(leaf)

    def do_work(self):
        while not self.kill_event.is_set():
            task = self.scheduler.get_work()
            if task is not None:
                try:
                    if not self.dry_run:
                        self.worker.submit(task)
                finally:
                    self.scheduler.finish(task)
            else:
                if self.collector.done:
                    break
                time.sleep(1)

    def run(self):
        # 1 do_work per num_proc, + 1 for collect_tasks
        with ThreadPoolExecutor(self.num_procs + 1) as executor:
            futures = [executor.submit(self.collect_tasks)]
            for _ in range(self.num_procs):
                futures.append(executor.submit(self.do_work))
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception:  # noqa: BLE001
                    self.log.error(
                        f"Orchestrator encountered exception: {traceback.format_exc()}"
                    )

        self.collector.cleanup()
        self.cleanup()

    def cleanup(self):
        for d in self.created_dirs:
            shutil.rmtree(d)
        for artifact in self.tmp_artifacts:
            artifact.cleanup()
