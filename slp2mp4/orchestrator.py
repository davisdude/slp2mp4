# Takes collections and creates tasks / schedules them

import concurrent.futures
import dataclasses
import hashlib
import pickle
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from logging import Logger
from multiprocessing import Event
from pathlib import Path

import pathvalidate

from slp2mp4 import log, util
from slp2mp4.artifact import Artifact, Mp4Artifact
from slp2mp4.collector import Collector, ConcatRequest, RenderRequest
from slp2mp4.config import CombineMode, Config
from slp2mp4.pipeline import Pipeline
from slp2mp4.scheduler import Scheduler
from slp2mp4.task import MoveFileTask, Task
from slp2mp4.worker import Worker


def _hash_task(task: Task):
    return hashlib.sha1(pickle.dumps(task)).hexdigest()[:6]


@dataclasses.dataclass
class Orchestrator:
    conf: Config
    kill_event: Event
    collector: Collector
    combine_mode: CombineMode

    dry_run: bool = dataclasses.field(default=False)
    num_procs: int | None = dataclasses.field(default=None)
    output_directory: Path | None = dataclasses.field(default=None)
    workdir: Path | None = dataclasses.field(default=None)
    debug: bool = dataclasses.field(default=False)
    poll_interval_s: int = dataclasses.field(default=1)

    worker: Worker | None = dataclasses.field(default=None, init=False)
    scheduler: Scheduler | None = dataclasses.field(default=None, init=False)
    pipeline: Pipeline | None = dataclasses.field(default=None, init=False)
    log: Logger | None = dataclasses.field(default=None, init=False)

    def __post_init__(self):
        if self.num_procs is None:
            self.num_procs = self.conf.runtime.parallel_procs
        if self.output_directory is None:
            self.output_directory = Path(".")
        if self.workdir is not None:
            self.workdir.mkdir(exist_ok=True, parents=True)

        self.worker = Worker(self.conf, self.kill_event)
        self.scheduler = Scheduler({"cpu": self.num_procs})
        self.pipeline = Pipeline(self.workdir, self.output_directory)
        self.log = log.get_logger()

    def print_leaf(self, task: Task):
        indent = "    "
        for indent_level, leaf in self.scheduler.walk_tree(task):
            if isinstance(leaf, Task):
                pad = indent_level * indent
                self.log.info(f"{pad}{leaf.final_name} ({leaf.short_name})")
            elif isinstance(leaf, Artifact):
                pad = (indent_level + 1) * indent
                prefix = f"{pad}{leaf} ({leaf.index + 1})"
                suffix = " + context.json" if leaf.context is not None else ""
                self.log.info(f"{prefix}{suffix}")

    def get_timestamps(self, task):
        for _, child in self.scheduler.walk_tree(task):
            if hasattr(child, "timestamps") and not self.dry_run:
                if child.timestamps:
                    names = [
                        self.scheduler.get_producer(i).final_name.stem
                        for i in child.inputs
                    ]
                    times = [timedelta(seconds=int(t)) for t in child.timestamps]
                    return ("\n").join(f"{t} - {n}" for n, t in zip(names, times))
                return ""
        return ""

    def write_timestamps(self, task):
        filename = task.video.path.with_suffix(".txt")
        timestamp_str = self.get_timestamps(task)
        if timestamp_str:
            with open(filename, "w") as f:
                f.write(timestamp_str)

    def get_move_paths(self, tasks: list[Task]):
        paths: dict[Task, Path] = {}
        for task in tasks:
            parent_parts = task.final_name.parent.parts
            name = task.final_name.stem
            if self.conf.runtime.youtubify_names:
                name = util.translate(name, self.conf.runtime.name_replacements)
            output_directory = Path(self.output_directory)
            if self.conf.runtime.preserve_directory_structure:
                for parent in parent_parts:
                    output_directory /= parent
            name = pathvalidate.sanitize_filename(name, max_len=244)  # 255 - .mp4 - sha
            paths[task] = output_directory / name

        counts = Counter(paths.values())
        new_paths = []
        for task, path in paths.items():
            if counts[path] > 1:
                sha = _hash_task(task)
                path = path.parent / f"{path.name}-{sha}"
            output_path = path.parent / f"{path.name}.mp4"
            new_paths.append(output_path)
        return new_paths

    def get_move_tasks(self, tasks: list[Task]):
        new_paths = self.get_move_paths(tasks)
        for task, output_path in zip(tasks, new_paths):
            output_artifact = Mp4Artifact(output_path)
            yield [
                MoveFileTask(
                    f"move {output_path}", [task.video], [output_artifact], output_path
                )
            ]

    def get_final_name(self, request: ConcatRequest):
        if not self.conf.runtime.use_context_json:
            return request.final
        contexts = {slp.context for slp in request.slps}
        if (len(contexts) != 1) or (None in contexts):
            return request.final
        context = next(iter(contexts))
        player1 = (" + ").join(context.final_score.slots[0].display_names)
        player2 = (" + ").join(context.final_score.slots[1].display_names)
        tournament_name = context.tournament_name
        event_name = context.event_name
        phase_name = context.phase_name
        round_name = context.round_name
        name = f"{player1} vs {player2} - {tournament_name} - {event_name} - {phase_name} {round_name}.mp4"
        return request.final.parent / name

    def should_skip_request(self, request: RenderRequest | ConcatRequest):
        if not self.conf.runtime.exclude_streamed_sets:
            return False
        if isinstance(request, RenderRequest):
            if request.slp.context is None:
                return False
            return request.slp.context.stream is not None

    def next(self):
        """Iterator that returns <task>."""
        # Indexing by slp path lets us handle context/index changes
        task_by_slp_path: dict[Path, Task] = {}
        input_by_task: dict[Task, Path] = {}
        for input_path, request in self.collector.next():
            if self.should_skip_request(request):
                continue
            if isinstance(request, RenderRequest):
                for task in self.pipeline.get_render_task(request.slp):
                    task_by_slp_path[request.slp.path] = task
                    input_by_task[task] = input_path
                    yield [task]
            elif isinstance(request, ConcatRequest):
                name = self.get_final_name(request)
                videos = [
                    task_by_slp_path[slp.path].video
                    for slp in request.slps
                    if slp.path in task_by_slp_path
                ]

                sb = self.conf.scoreboard
                it = self.pipeline.get_scoreboard_tasks(sb, request.slps, videos)
                for i, task in enumerate(it):
                    input_by_task[task] = input_path
                    yield [task]
                    videos[i] = task.video

                for task in self.pipeline.get_concat_task(videos, name):
                    input_by_task[task] = input_path
                    yield [task]

        leaves = self.scheduler.get_leaves()
        yield from self.pipeline.get_group_concat_tasks(
            leaves, input_by_task, self.combine_mode
        )
        leaves = self.scheduler.get_leaves()
        yield from self.get_move_tasks(leaves)

    def collect_tasks(self):
        for tasks in self.next():
            self.scheduler.submit(tasks)

        leaves = self.scheduler.get_leaves()
        if self.dry_run:
            for leaf in leaves:
                self.print_leaf(leaf)

    def do_work(self):
        while not self.kill_event.is_set():
            task = self.scheduler.get_work()
            if task is None:
                if self.collector.done and self.scheduler.is_pipeline_empty():
                    break
                time.sleep(self.poll_interval_s)
                continue
            try:
                if not self.dry_run:
                    task_num = self.scheduler.num_tasks_completed + 1
                    submitted = self.scheduler.num_tasks_submitted
                    self.log.info(f"[{task_num}/{submitted}]: Starting {task.name}")
                    self.worker.submit(task)
                self.scheduler.finish(task)
            except Exception:  # noqa: BLE001
                tb = traceback.format_exc()
                self.log.error(f"Encountered exception in task '{task.name}': {tb}")
                self.scheduler.mark_failed(task)
            finally:
                if not self.debug:
                    task.cleanup()

    def run(self):
        self.log.info("Starting")

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

        if not self.debug:
            self.collector.cleanup()
            self.pipeline.cleanup()

        self.log.info("Done!")
