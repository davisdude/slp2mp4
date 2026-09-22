# Tasks are jobs that take artifacts as inputs and outputs

import dataclasses
from functools import singledispatchmethod
from pathlib import Path
from logging import Logger
from multiprocessing import Event
from tempfile import TemporaryDirectory

import slp2mp4.log as log
from slp2mp4.artifact import Artifact, Mp4Artifact, SlippiArtifact
from slp2mp4.dolphin.runner import DolphinRunner
from slp2mp4.ffmpeg import FfmpegRunner


@dataclasses.dataclass(eq=False)
class Task:
    name: str
    inputs: list[Artifact]
    outputs: list[Artifact]

    def __post_init__(self):
        pass

    @property
    def resources(self) -> dict[str, float]:
        raise NotImplementedError

    def check_inputs(self):
        for i in self.inputs:
            if not i.exists():
                raise RuntimeError(f"Input {i} does not exist.")


@dataclasses.dataclass(eq=False)
class RenderGameTask(Task):
    def __post_init__(self):
        super().__post_init__()
        assert len(self.inputs) == len(self.outputs)

    @property
    def resources(self):
        return {"cpu": 1.0}


@dataclasses.dataclass(eq=False)
class ConcatVideosTask(Task):
    def __post_init__(self):
        super().__post_init__()
        assert len(self.outputs) == 1

    @property
    def resources(self):
        # TODO: GPU concat via ffmpeg
        # TODO: This uses multiple cores; 1 is unrealistic. Changing it to reflect 100% util would
        #       require a smarter scheduler/some priority system, otherwise concats will be
        #       preempted lower priorty tasks. It's quick enough that I think it's okay.
        return {"cpu": 1.0}


@dataclasses.dataclass
class Worker:
    conf: dict
    kill_event: Event
    logger: Logger = dataclasses.field(default=None, init=False)
    ffmpeg: FfmpegRunner = dataclasses.field(default=None, init=False)
    dolphin: DolphinRunner = dataclasses.field(default=None, init=False)

    def __post_init__(self):
        self.logger = log.get_logger()
        self.ffmpeg = FfmpegRunner(self.conf)
        self.dolphin = DolphinRunner(self.conf)

    def submit(self, task: Task):
        if self.kill_event.is_set():
            return
        task.check_inputs()
        self._submit(task)

    @singledispatchmethod
    def _submit(self, task: Task):
        raise TypeError(f"Unsupported task type '{type(task)}'")

    @_submit.register
    def _(self, task: RenderGameTask):
        for i, o in zip(task.inputs, task.outputs):
            self.render_slp(i, o)

    @_submit.register
    def _(self, task: ConcatVideosTask):
        self.combine_mp4s(task.inputs, task.outputs[0])

    def render_slp(self, slp: SlippiArtifact, mp4: Mp4Artifact):
        self.logger.info(f"Rendering '{slp.path}' to '{mp4.path}'")
        with TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            audio_file, video_path = self.dolphin.run(slp.path, tmpdir, self.kill_event)
            reencoded_audio_file = self.ffmpeg.reencode_audio(audio_file)
            if reencoded_audio_file is None:
                return False
            success = self.ffmpeg.merge_audio_and_video(
                reencoded_audio_file,
                video_path,
                mp4.path,
            )
            if not success:
                raise RuntimeError(f"Failed to render '{slp.path}'")
            self.logger.info(f"Done rendering '{slp.path}'")

    def combine_mp4s(self, inputs: list[Mp4Artifact], output: Mp4Artifact):
        input_paths = [i.path for i in inputs]
        self.logger.info(f"Combining '{input_paths}' to '{output.path}'")
        success = self.ffmpeg.concat_videos(input_paths, output.path)
        if not success:
            raise RuntimeError(f"Failed to create '{output.path}'")
        self.logger.info(f"Done combining '{output.path}")
