# Groups orchestrator inputs logically; handles file names

import dataclasses
import math
import os
import tempfile
from collections import defaultdict
from pathlib import Path

from slp2mp4.artifact import Artifact, Mp4Artifact, SlippiArtifact
from slp2mp4.config import CombineMode, ScoreboardConfig, ScoreboardType
from slp2mp4.context import ContextData
from slp2mp4.task import ConcatVideosTask, RenderGameTask, RenderScoreboardTask, Task

DEFAULT_PHASE_GROUP = ("", "", "")
DEFAULT_SET_ORDER = (-math.inf, 0, 0)


def _get_task_key(task: Task):
    if (context := task.video.context) is not None:
        return context.phase_group, context.set_order, task.final_name
    return DEFAULT_PHASE_GROUP, DEFAULT_SET_ORDER, task.final_name


@dataclasses.dataclass
class Pipeline:
    workdir: Path | None = dataclasses.field(default=None)
    output_directory: Path | None = dataclasses.field(default=None)

    tmp_artifacts: list[Artifact] = dataclasses.field(default_factory=list, init=False)

    def __post_init__(self):
        if self.output_directory is None:
            self.output_directory = Path(".")

    def _make_tmp_mp4(self, contexts: set[ContextData] | None = None):
        if contexts is None:
            contexts = {}
        fd, tmp = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
        os.close(fd)
        artifact = Mp4Artifact(Path(tmp), frozenset(contexts))
        self.tmp_artifacts.append(artifact)
        return artifact

    def _concat_task(self, task_name: str, videos: list[Mp4Artifact], final: Path):
        contexts = {context for video in videos for context in video.contexts}
        output = self._make_tmp_mp4(contexts)
        return ConcatVideosTask(task_name, videos, [output], final)

    def _get_concat_groups(
        self,
        tasks: list[Task],
        input_by_task: dict[Task, Path],
        combine_mode: CombineMode,
    ):
        if combine_mode == CombineMode.NONE:
            return None
        elif combine_mode == CombineMode.ALL:
            yield tasks, Path("all.mp4")
        elif combine_mode == CombineMode.BY_INPUT:
            groups: dict[Path, list[Task]] = defaultdict(list)
            for task in tasks:
                groups[input_by_task[task]].append(task)
            for input_item, group_tasks in groups.items():
                name = (
                    input_item.with_suffix(".mp4").name
                    if input_item.is_file()
                    else f"{input_item.name}.mp4"
                )
                yield group_tasks, Path(name)
        elif combine_mode == CombineMode.BY_PHASE:
            groups: dict[tuple | None, list[Task]] = defaultdict(list)
            for task in tasks:
                if context := task.video.context:
                    groups[context.phase_group].append(task)
                else:
                    groups[DEFAULT_PHASE_GROUP].append(task)
            for group_info, group_tasks in groups.items():
                name = (" - ").join(group_info) + ".mp4"
                yield group_tasks, Path(name)
        else:
            raise ValueError(f"Unsupported combine mode '{combine_mode}'")

    def get_render_task(self, slp: SlippiArtifact):
        context_data = None if slp.context is None else slp.context.data
        output = self._make_tmp_mp4({context_data})
        name = slp.path.with_suffix(".mp4")
        yield RenderGameTask(f"render {slp}", [slp], [output], name)

    def get_scoreboard_tasks(
        self,
        conf: ScoreboardConfig,
        slps: list[SlippiArtifact],
        videos: list[Mp4Artifact],
    ):
        if conf.type == ScoreboardType.NONE:
            return
        for slp, video in zip(slps, videos):
            context_data = None if slp.context is None else slp.context.data
            out = self._make_tmp_mp4({context_data})
            name = slp.path.with_suffix(".mp4").name
            yield RenderScoreboardTask(
                f"scoreboard {video}", [slp, video], [out], Path(name)
            )

    def get_concat_task(self, videos: list[Mp4Artifact], path: Path):
        if len(videos) > 0:
            yield self._concat_task(f"concat {path}", videos, path)

    def get_group_concat_tasks(
        self,
        tasks: list[Task],
        input_by_task: dict[Task, Path],
        combine_mode: CombineMode,
    ):
        for group_tasks, final in self._get_concat_groups(
            tasks, input_by_task, combine_mode
        ):
            sorted_tasks = sorted(group_tasks, key=_get_task_key)
            videos = [task.video for task in sorted_tasks]
            yield [self._concat_task(f"concat {final}", videos, final)]

    def cleanup(self):
        for artifact in self.tmp_artifacts:
            artifact.cleanup()
