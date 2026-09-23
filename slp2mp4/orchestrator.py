# Takes collections and creates tasks / schedules them

import concurrent.futures
import dataclasses
import shutil
import tempfile
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from logging import Logger
from multiprocessing import Event
from pathlib import Path

import psutil

from slp2mp4 import log
from slp2mp4.artifact import Artifact, Mp4Artifact
from slp2mp4.collector import Collector
from slp2mp4.config import CombineMode, Config
from slp2mp4.scheduler import Scheduler
from slp2mp4.task import ConcatVideosTask, MoveFileTask, RenderGameTask, Task
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

    def get_output_path(self, path: Path):
        if path.is_file():
            name = path.with_suffix(".mp4")
        else:
            if path != Path("."):
                parent = path.parent
            else:
                parent = Path("..")
                path = path.expanduser().absolute()
            name = parent / path.with_suffix(".mp4")
        return self.format_output_name(name)

    def write_timestamps(self, main_task):
        filename = main_task.video.path.with_suffix(".txt")
        for task in self.scheduler.get_parent_tasks(main_task):
            if hasattr(task, "timestamps"):
                if task.timestamps:
                    with open(filename, "w") as f:
                        for i, t in zip(task.inputs, task.timestamps):
                            # TODO: Convert i from tmp name to real name
                            time_str = str(timedelta(seconds=int(t)))
                            f.write(f"{time_str} - {i}\n")
                break

    def next(self):
        """Iterator that returns <task>."""
        input_by_task: dict[Task, Path] = {}
        paths_by_task: dict[Task, Path] = {}
        for input_item, path, artifacts in self.collector.next():
            tasks = []
            tmp_vids = []
            for slp in artifacts:
                _handle, tmp = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp))
                tmp_vids.append(vid)
                self.tmp_artifacts.append(vid)
                inputs = [slp]
                render_task = RenderGameTask(f"render {slp}", inputs, [vid])
                paths_by_task[render_task] = slp.path
                tasks.append(render_task)

            if len(tmp_vids) > 1:
                _handle, tmp_mp4 = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp_mp4))
                self.tmp_artifacts.append(vid)
                concat_task = ConcatVideosTask(f"concat {vid}", tmp_vids, [vid])
                tasks.append(concat_task)
                input_by_task[concat_task] = input_item
                paths_by_task[concat_task] = path

            yield tasks

        leaves = self.scheduler.get_leaves()
        if self.conf.runtime.combine_mode == CombineMode.ALL:
            # TODO: Sorting
            all_vids = [task.video for task in leaves]
            if len(all_vids) > 1:
                _handle, tmp_mp4 = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp_mp4))
                self.tmp_artifacts.append(vid)
                concat_task = ConcatVideosTask("concat all", all_vids, [vid])
                paths_by_task[concat_task] = Path("all.mp4")
                yield [concat_task]
        elif self.conf.runtime.combine_mode == CombineMode.BY_INPUT:
            # TODO: Sorting
            tasks_by_input: dict[Path, list[Task]] = defaultdict(list)
            for task in leaves:
                tasks_by_input[input_by_task[task]].append(task)
            new_tasks = []
            for input_item, tasks in tasks_by_input.items():
                all_vids = [task.video for task in tasks]
                if len(all_vids) == 1:
                    continue
                _handle, tmp_mp4 = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp_mp4))
                self.tmp_artifacts.append(vid)
                concat_task = ConcatVideosTask(f"concat {vid}", all_vids, [vid])
                paths_by_task[concat_task] = Path(input_item)
                new_tasks.append(concat_task)
            yield new_tasks

        leaves = self.scheduler.get_leaves()
        tasks = []
        for task in leaves:
            path = paths_by_task[task]
            new_path = self.get_output_path(path)
            new_artifact = Mp4Artifact(new_path)
            tasks.append(MoveFileTask(f"move {new_path}", [task.video], [new_artifact]))
        yield tasks

    def _print_leaf(self, leaf: Task, indent_level=0):
        indent = "\t"
        outputs = (", ").join(
            str(o.path) if indent_level == 0 else str(o) for o in leaf.outputs
        )
        self.log.info(f"{indent * indent_level}{outputs} ({leaf.short_name})")
        for i in leaf.inputs:
            task = self.scheduler.get_producer(i)
            if task:
                self._print_leaf(task, indent_level + 1)
            else:
                self.log.info(f"{indent * (indent_level + 1)}{i}")
                if context := getattr(i, "context", ""):
                    index = i.index
                    self.log.info(
                        f"{indent * (indent_level + 1)}{context} ({index + 1})"
                    )

    def collect_tasks(self):
        for tasks in self.next():
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

        # Timestamps must be written after concat is done
        leaves = self.scheduler.get_leaves()
        for task in leaves:
            self.write_timestamps(task)

        self.collector.cleanup()
        self.cleanup()

    def cleanup(self):
        for d in self.created_dirs:
            shutil.rmtree(d)
        for artifact in self.tmp_artifacts:
            artifact.cleanup()


# TODO: Somtimes has issues when parallel > # inputs?
