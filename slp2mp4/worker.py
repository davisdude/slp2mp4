# Given a task, runs it

import dataclasses
import itertools
from functools import singledispatchmethod
from logging import Logger
from multiprocessing import Event
from pathlib import Path
from tempfile import TemporaryDirectory

from slp2mp4 import log
from slp2mp4.artifact import Mp4Artifact, SlippiArtifact
from slp2mp4.config import Config
from slp2mp4.dolphin.runner import DolphinRunner
from slp2mp4.ffmpeg import FfmpegRunner
from slp2mp4.scoreboard import SCOREBOARD_MAPPING
from slp2mp4.task import (
    ConcatVideosTask,
    MoveFileTask,
    RenderGameTask,
    RenderScoreboardTask,
    Task,
)


@dataclasses.dataclass
class Worker:
    conf: Config
    kill_event: Event
    log: Logger = dataclasses.field(default=None, init=False)
    ffmpeg: FfmpegRunner = dataclasses.field(default=None, init=False)
    dolphin: DolphinRunner = dataclasses.field(default=None, init=False)

    def __post_init__(self):
        self.log = log.get_logger()
        self.ffmpeg = FfmpegRunner(self.conf)
        self.dolphin = DolphinRunner(self.conf)

    def submit(self, task: Task):
        if self.kill_event.is_set():
            return
        task.check_inputs()
        self._submit(task)

    @singledispatchmethod
    def _submit(self, task):
        raise TypeError(f"Unsupported task type '{type(task)}'")

    @_submit.register
    def _(self, task: RenderGameTask):
        for i, o in zip(task.inputs, task.outputs):
            self.render_slp(i, o)

    @_submit.register
    def _(self, task: RenderScoreboardTask):
        self.render_scoreboard(task.slp, task.video_in, task.video)

    @_submit.register
    def _(self, task: ConcatVideosTask):
        self.combine_mp4s(task.inputs, task.video, task)

    @_submit.register
    def _(self, task: MoveFileTask):
        for i, o in zip(task.inputs, task.outputs):
            self.log.info(f"Moving '{i.path}' to '{o.path}'")
            o.path.parent.mkdir(parents=True, exist_ok=True)
            i.path.replace(o.path)

    def render_slp(self, slp: SlippiArtifact, mp4: Mp4Artifact):
        self.log.info(f"Rendering '{slp.path}' to '{mp4.path}'")
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
            self.log.info(f"Done rendering '{slp.path}'")

    def render_scoreboard(
        self, slp: SlippiArtifact, video_in: Mp4Artifact, video_out: Mp4Artifact
    ):
        self.log.info(f"Scoreboarding '{video_in.path}' to '{video_out.path}'")
        conf_data = dataclasses.asdict(self.conf.scoreboard.scoreboard)
        sb_class = SCOREBOARD_MAPPING[self.conf.scoreboard.type]
        video_in_dims = self.ffmpeg.get_video_dimensions(video_in.path)
        resolution = self.conf.dolphin.resolution.display_name
        video_out_height = int(resolution.removesuffix("p"))
        scoreboard = sb_class(
            slp=slp,
            input_video=video_in,
            output_video=video_out,
            input_video_dimensions=video_in_dims,
            output_video_height=video_out_height,
            user_data=self.conf.scoreboard.user_data,
            **conf_data,
        )
        scoreboard.render_image()
        cmd = scoreboard.get_ffmpeg_command()
        proc = self.ffmpeg.run(cmd)
        if not proc.returncode == 0:
            raise RuntimeError(f"Failed to scoreboard '{video_in.path}'")
        self.log.info(f"Done scoreboarding '{slp.path}'")

    def combine_mp4s(
        self,
        inputs: list[Mp4Artifact],
        output: Mp4Artifact,
        task: Task | None = None,
    ):
        input_paths = [i.path for i in inputs]
        self.log.info(f"Combining '{input_paths}' to '{output.path}'")
        success = self.ffmpeg.concat_videos(input_paths, output.path)
        if not success:
            raise RuntimeError(f"Failed to create '{output.path}'")
        self.log.info(f"Done combining '{output.path}'")
        if task:
            self.log.info(f"Getting timestamps for '{output.path}'")
            durations = [self.ffmpeg.get_video_duration(path) for path in input_paths]
            task.timestamps = itertools.accumulate(durations[:-1], initial=0)
