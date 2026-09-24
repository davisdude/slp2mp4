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
from slp2mp4.artifact import Artifact, Mp4Artifact, SlippiArtifact
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
            name = parent / (path.name + ".mp4")
        return self.format_output_name(name)

    def get_timestamp_names(self, input_items: list[Artifact]):
        producers = [self.scheduler.get_producer(i) for i in input_items]
        paths = [p.path for p in producers]
        names = [p.stem if p.is_file() else p.name for p in paths]
        if len(set(names)) != 1:
            return names
        names = []
        for task in producers:
            for _, leaf in self.scheduler.walk_tree(task):
                if isinstance(leaf, SlippiArtifact):
                    names.append(f"Game {leaf.index + 1}")
        return names

    def write_timestamps(self, main_task):
        filename = main_task.video.path.with_suffix(".txt")
        for _, leaf in self.scheduler.walk_tree(main_task):
            if hasattr(leaf, "timestamps"):
                if leaf.timestamps:
                    with open(filename, "w") as f:
                        names = self.get_timestamp_names(leaf.inputs)
                        deltas = [timedelta(seconds=int(t)) for t in leaf.timestamps]
                        f.writelines(
                            f"{delta} - {name}\n" for name, delta in zip(names, deltas)
                        )
                break

    def sort_tasks_for_concat(self, tasks: list[Task]):
        return sorted(tasks, key=lambda task: task.path)

    def next(self):
        """Iterator that returns <task>."""
        input_by_task: dict[Task, Path] = {}
        for input_item, path, artifacts in self.collector.next():
            tasks = []
            tmp_vids = []
            for slp in artifacts:
                _handle, tmp = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp))
                tmp_vids.append(vid)
                self.tmp_artifacts.append(vid)
                render_task = RenderGameTask(f"render {slp}", [slp], [vid], path)
                tasks.append(render_task)
                input_by_task[render_task] = input_item

            if len(tmp_vids) > 1:
                _handle, tmp_mp4 = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp_mp4))
                self.tmp_artifacts.append(vid)
                concat_task = ConcatVideosTask(f"concat {vid}", tmp_vids, [vid], path)
                tasks.append(concat_task)
                input_by_task[concat_task] = input_item

            yield tasks

        leaves = self.scheduler.get_leaves()
        if self.conf.runtime.combine_mode == CombineMode.ALL:
            sorted_tasks = self.sort_tasks_for_concat(leaves)
            all_vids = [task.video for task in sorted_tasks]
            if len(all_vids) > 1:
                _handle, tmp_mp4 = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp_mp4))
                self.tmp_artifacts.append(vid)
                path = Path("all")
                concat_task = ConcatVideosTask("concat all", all_vids, [vid], path)
                yield [concat_task]
        elif self.conf.runtime.combine_mode == CombineMode.BY_INPUT:
            tasks_by_input: dict[Path, list[Task]] = defaultdict(list)
            for task in leaves:
                tasks_by_input[input_by_task[task]].append(task)
            new_tasks = []
            for input_item, tasks in tasks_by_input.items():
                sorted_tasks = self.sort_tasks_for_concat(tasks)
                all_vids = [task.video for task in sorted_tasks]
                if len(all_vids) == 1:
                    continue
                _handle, tmp_mp4 = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp_mp4))
                self.tmp_artifacts.append(vid)
                path = self.get_output_path(input_item)
                concat_task = ConcatVideosTask(f"concat {vid}", all_vids, [vid], path)
                new_tasks.append(concat_task)
            yield new_tasks

        leaves = self.scheduler.get_leaves()
        tasks = []
        for task in leaves:
            new_path = self.get_output_path(task.path)
            new_artifact = Mp4Artifact(new_path)
            tasks.append(
                MoveFileTask(
                    f"move {new_path}", [task.video], [new_artifact], new_artifact.path
                )
            )
        yield tasks

    def _print_leaf(self, task: Task):
        indent = "    "
        for indent_level, leaf in self.scheduler.walk_tree(task):
            if isinstance(leaf, Task):
                outputs = [
                    str(o.path) if indent_level == 0 else str(o) for o in leaf.outputs
                ]
                output_str = (", ").join(outputs)
                self.log.info(
                    f"{indent_level * indent}{output_str} ({leaf.short_name})"
                )
            elif isinstance(leaf, Artifact):
                indent_str = (indent_level + 1) * indent
                self.log.info(f"{indent_str}{leaf}")
                if context := getattr(leaf, "context", None):
                    self.log.info(f"{indent_str}{context} ({leaf.index + 1})")

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
