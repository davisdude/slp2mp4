# Tasks are jobs that take artifacts as inputs and outputs

from dataclasses import dataclass
from pathlib import Path
from multiprocessing import Event
from tempfile import TemporaryDirectory

import slp2mp4.log as log
from slp2mp4.artifact import Artifact, Mp4Artifact, SlippiArtifact
from slp2mp4.dolphin.runner import DolphinRunner
from slp2mp4.ffmpeg import FfmpegRunner


def render_slp(kill_event: Event, conf: dict, slp: SlippiArtifact, mp4: Mp4Artifact):
    logger = log.get_logger()
    ffmpeg = FfmpegRunner(conf)
    dolphin = DolphinRunner(conf)
    logger.info(f"Rendering '{slp.path}' to '{mp4.path}")
    with TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        audio_file, video_path = dolphin.run(slp.path, tmpdir, kill_event)
        reencoded_audio_file = ffmpeg.reencode_audio(audio_file)
        if reencoded_audio_file is None:
            return False
        return ffmpeg.merge_audio_and_video(
            reencoded_audio_file,
            video_path,
            mp4.path,
        )
    if not success:
        raise RuntimeError(f"Failed to render '{slp.path}'")
    logger.info(f"Done rendering '{slp.path}'")


def combine_mp4s(
    kill_event: Event, conf: dict, inputs: list[Mp4Artifact], output: Mp4Artifact
):
    logger = log.get_logger()
    input_paths = [i.path for i in inputs]
    logger.info(f"Combining '{input_paths}' to '{output.path}")
    ffmpeg = FfmpegRunner(conf)
    success = ffmpeg.concat_videos(input_paths, output.path)
    if not success:
        raise RuntimeError(f"Failed to create '{output.path}'")
    logger.info(f"Done combining '{output.path}")


@dataclass(eq=False)
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

    def work(self, kill_event: Event):
        raise NotImplementedError


@dataclass(eq=False)
class RenderGameTask(Task):
    def __post_init__(self):
        super().__post_init__()
        assert len(self.inputs) == len(self.outputs)

    @property
    def resources(self):
        return {"cpu": 1.0}

    def work(self, kill_event: Event, conf: dict):
        if kill_event.is_set():
            return
        self.check_inputs()
        for i, o in zip(self.inputs, self.outputs):
            render_slp(kill_event, conf, i, o)


@dataclass(eq=False)
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

    def work(self, kill_event: Event, conf: dict):
        if kill_event.is_set():
            return
        self.check_inputs()
        combine_mp4s(kill_event, conf, self.inputs, self.outputs[0])
