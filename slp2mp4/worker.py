# Given a task, runs it

import dataclasses
from datetime import timedelta
from functools import singledispatchmethod
from logging import Logger
from multiprocessing import Event
from pathlib import Path
from tempfile import TemporaryDirectory

from slp2mp4 import log
from slp2mp4.artifact import Mp4Artifact, SlippiArtifact, TimestampArtifact
from slp2mp4.config import Config
from slp2mp4.dolphin.runner import DolphinRunner
from slp2mp4.ffmpeg import FfmpegRunner
from slp2mp4.task import ConcatVideosTask, RenderGameTask, Task


@dataclasses.dataclass
class Worker:
    conf: Config
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
        self.combine_mp4s(task.inputs, task.video, task.timestamp)

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

    def combine_mp4s(
        self,
        inputs: list[Mp4Artifact],
        output: Mp4Artifact,
        timestamp: TimestampArtifact | None,
    ):
        input_paths = [i.path for i in inputs]
        self.logger.info(f"Combining '{input_paths}' to '{output.path}'")
        success = self.ffmpeg.concat_videos(input_paths, output.path)
        if not success:
            raise RuntimeError(f"Failed to create '{output.path}'")
        if timestamp:
            current_time = 0.0
            with open(timestamp.path, "w") as f:
                for path in input_paths:
                    time_str = str(timedelta(seconds=int(current_time)))
                    f.write(f"{time_str} - {path.stem}\n")
                    current_time += self.ffmpeg.get_video_duration(path)
        self.logger.info(f"Done combining '{output.path}'")
