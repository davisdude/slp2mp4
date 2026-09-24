# Takes collections and creates tasks / schedules them

import concurrent.futures
import dataclasses
import json
import math
import shutil
import tempfile
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from functools import singledispatchmethod
from logging import Logger
from multiprocessing import Event
from pathlib import Path

import psutil

from slp2mp4 import log, util
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
    output_directory: Path | None = dataclasses.field(default=None)
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
        if self.output_directory is None:
            self.output_directory = Path(".")
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
        # TODO: Preserve directory structure
        if not self.conf.runtime.youtubify_names:
            return path
        name = util.translate(path.stem, self.conf.runtime.name_replacements)
        return path.resolve().parent / (name + ".mp4")

    def get_output_name(self, tasks: list[Task], path: Path):
        contexts = list({task.slp.context for task in tasks})
        if (len(contexts) != 1) or (contexts[0] is None):
            # I don't think this is possible currently, but better safe...
            return path
        context = contexts[0]
        try:
            # TODO: Customizable
            # TODO: parry / challonge
            with open(context.path, "rb") as f:
                data = json.load(f)
                separator = " + "
                conf = self.conf.runtime
                if conf.youtubify_names and "/" in conf.name_replacements:
                    separator = " / "
                name1 = separator.join(data["scores"][0]["slots"][0]["displayNames"])
                name2 = separator.join(data["scores"][0]["slots"][1]["displayNames"])
                tournament = data["startgg"]["tournament"]["name"]
                event = data["startgg"]["event"]["name"]
                phase = data["startgg"]["phase"]["name"]
                round_str = data["startgg"]["set"]["fullRoundText"]
                round_short = util.translate(
                    round_str,
                    {
                        "Winners": "W",
                        "Losers": "L",
                        "Grand": "G",
                        "Semi": "S",
                        "Quarter": "Q",
                        "Round": "R",
                        "Final": "F",
                        "Reset": "R",
                        " ": "",
                        "-": "",
                    },
                )
                name = f"{name1} vs {name2} - {tournament} - {event} - {phase} - {round_short}"
                return path.resolve().parent / name
        except Exception:  # noqa: BLE001
            return path

    def get_slp_name(self, artifact: Artifact):
        task = self.scheduler.get_producer(artifact)
        for _, leaf in self.scheduler.walk_tree(task):
            if isinstance(leaf, SlippiArtifact):
                return leaf

    def get_set_round_info(self, task: Task):
        try:
            slp = self.get_slp_name(task.video)
            with open(slp.context.path, "rb") as f:
                # TODO: parry / challonge / etc.
                data = json.load(f)
                tournament_name = data["startgg"]["tournament"]["name"]
                event_name = data["startgg"]["event"]["name"]
                phase_name = data["startgg"]["phase"]["name"]
                set_order = (
                    data["startgg"]["set"]["ordinal"] or data["startgg"]["set"]["round"]
                )
                return (tournament_name, event_name, phase_name, set_order)
        except:  # noqa: E722
            return ("", "", "", -math.inf)

    def sort_tasks_for_concat(self, tasks: list[Task]):
        return sorted(
            tasks, key=lambda task: (self.get_set_round_info(task), task.final_name)
        )

    def print_leaf(self, task: Task):
        indent = "    "
        for indent_level, leaf in self.scheduler.walk_tree(task):
            if isinstance(leaf, Task):
                pad = indent_level * indent
                self.log.info(f"{pad}{leaf.final_name} ({leaf.short_name})")
            elif isinstance(leaf, Artifact):
                pad = (indent_level + 1) * indent
                self.log.info(f"{pad}{leaf}")
                if context := getattr(leaf, "context", None):
                    self.log.info(f"{pad}{context} ({leaf.index + 1})")

    def write_timestamps(self, main_task):
        filename = main_task.video.path.with_suffix(".txt")
        for _, leaf in self.scheduler.walk_tree(main_task):
            if hasattr(leaf, "timestamps") and not self.dry_run:
                if leaf.timestamps:
                    with open(filename, "w") as f:
                        names = [self.scheduler.get_producer(i).final_name.stem for i in leaf.inputs]
                        times = [timedelta(seconds=int(t)) for t in leaf.timestamps]
                        f.writelines(f"{t} - {n}\n" for n, t in zip(names, times))
                break

    @singledispatchmethod
    def get_final_name(self, item):
        raise TypeError(f"Unsupported task type '{type(item)}'")

    @get_final_name.register
    def _(self, item: SlippiArtifact):
        return Path(f"Game {item.index + 1}.mp4")

    def next(self):
        """Iterator that returns <task>."""
        input_by_task: dict[Task, Path] = {}
        for input_item, final, artifacts in self.collector.next():
            tasks = []
            tmp_vids = []
            for slp in artifacts:
                _handle, tmp = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp))
                tmp_vids.append(vid)
                self.tmp_artifacts.append(vid)
                # Not using `final` here makes timestamps easier later
                name = self.get_final_name(slp)
                render_task = RenderGameTask(f"render {slp}", [slp], [vid], name)
                tasks.append(render_task)
                input_by_task[render_task] = input_item

            _handle, tmp_mp4 = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
            vid = Mp4Artifact(Path(tmp_mp4))
            self.tmp_artifacts.append(vid)
            concat_task = ConcatVideosTask(f"concat {vid}", tmp_vids, [vid], final)
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
                final = Path("all.mp4")
                concat_task = ConcatVideosTask("concat all", all_vids, [vid], final)
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
                if input_item.is_file():
                    final = Path(input_item.with_suffix(".mp4").name)
                else:
                    final = Path(input_item.name + ".mp4")
                concat_task = ConcatVideosTask(f"concat {vid}", all_vids, [vid], final)
                new_tasks.append(concat_task)
            yield new_tasks
        elif self.conf.runtime.combine_mode == CombineMode.BY_PHASE:
            tasks_by_phase: dict[tuple[str, str, str], list[Task]] = defaultdict(list)
            for task in leaves:
                round_info = self.get_set_round_info(task)
                tasks_by_phase[round_info[:3]].append(task)
            new_tasks = []
            for (
                tournament_name,
                event_name,
                phase_name,
            ), tasks in tasks_by_phase.items():
                sorted_tasks = self.sort_tasks_for_concat(tasks)
                all_vids = [task.video for task in sorted_tasks]
                if len(all_vids) == 1:
                    continue
                _handle, tmp_mp4 = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
                vid = Mp4Artifact(Path(tmp_mp4))
                self.tmp_artifacts.append(vid)
                final = Path(f"{tournament_name} - {event_name} - {phase_name}.mp4")
                concat_task = ConcatVideosTask(f"concat {vid}", all_vids, [vid], final)
                new_tasks.append(concat_task)
            yield new_tasks

        leaves = self.scheduler.get_leaves()
        tasks = []
        for task in leaves:
            # TODO: format name
            new_path = self.output_directory / task.final_name
            new_artifact = Mp4Artifact(new_path)
            tasks.append(
                MoveFileTask(
                    f"move {new_path}", [task.video], [new_artifact], new_artifact.path
                )
            )
        yield tasks

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
