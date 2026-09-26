# Groups orchestrator inputs logically; handles file names

import dataclasses
import os
import tempfile
from collections import defaultdict
from pathlib import Path

from slp2mp4.artifact import Artifact, Mp4Artifact, SlippiArtifact
from slp2mp4.config import CombineMode
from slp2mp4.task import ConcatVideosTask, RenderGameTask, Task

Phase = tuple[str, str, str, int, int]
PhaseGroup = tuple[str, str, str]


@dataclasses.dataclass
class Pipeline:
    workdir: Path | None = dataclasses.field(default=None)
    output_directory: Path | None = dataclasses.field(default=None)

    tmp_artifacts: list[Artifact] = dataclasses.field(default_factory=list, init=False)

    def __post_init__(self):
        if self.output_directory is None:
            self.output_directory = Path(".")

    def _make_tmp_mp4(self):
        fd, tmp = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
        os.close(fd)
        artifact = Mp4Artifact(Path(tmp))
        self.tmp_artifacts.append(artifact)
        return artifact

    def _concat_task(self, task_name: str, videos: list[Mp4Artifact], final: Path):
        output = self._make_tmp_mp4()
        return ConcatVideosTask(task_name, videos, [output], final)

    def _get_concat_groups(
        self,
        tasks: list[Task],
        input_by_task: dict[Task, Path],
        phase_by_task: dict[Task, Phase],
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
            groups: dict[PhaseGroup, list[Task]] = defaultdict(list)
            for task in tasks:
                groups[phase_by_task[task][:3]].append(task)
            for round_info, group_tasks in groups.items():
                name = (" - ").join(round_info) + ".mp4"
                yield group_tasks, Path(name)
        else:
            raise ValueError(f"Unsupported combine mode '{combine_mode}'")

    def _get_sorting_func(self, phase_by_task: dict[Task, Phase]):
        def foo(task: Task):
            return (phase_by_task[task], task.final_name)

        return foo

    def _sort_tasks(self, tasks: list[Task], phase_by_task: dict[Task, Phase]):
        return sorted(tasks, key=self._get_sorting_func(phase_by_task))

    def get_render_tasks(self, slps: list[SlippiArtifact]):
        for slp in slps:
            output = self._make_tmp_mp4()
            name = slp.path.with_suffix(".mp4").name
            yield RenderGameTask(f"render {slp}", [slp], [output], Path(name))

    def get_concat_tasks(self, videos: list[Mp4Artifact], path: Path):
        if len(videos) > 1:
            yield self._concat_task(f"concat {path}", videos, path)

    def get_group_concat_tasks(
        self,
        tasks: list[Task],
        input_by_task: dict[Task, Path],
        phase_by_task: dict[Task, Phase],
        combine_mode: CombineMode,
    ):
        for group_tasks, final in self._get_concat_groups(
            tasks, input_by_task, phase_by_task, combine_mode
        ):
            sorted_tasks = self._sort_tasks(group_tasks, phase_by_task)
            videos = [task.video for task in sorted_tasks]
            yield [self._concat_task(f"concat {final}", videos, final)]

    def cleanup(self):
        for artifact in self.tmp_artifacts:
            artifact.cleanup()
