# Commonizes the batching / concatenating of slippi files
#
# This renders by "set," which will be slightly slower on average than rendering
# all videos then concat-ing when the set is finished, but has a few upsides:
#
#   1. Reduces memory usage
#   2. Simplifies implementation

import concurrent.futures
import dataclasses
import enum
import pathlib
import tempfile
import multiprocessing

from slp2mp4.dolphin.runner import DolphinRunner
from slp2mp4.ffmpeg import FfmpegRunner

import slp2mp4.video as video
from slp2mp4.output import Output, OutputComponent


def render_and_concat(
    kill_event: multiprocessing.Event,
    executor: concurrent.futures.Executor,
    conf: dict,
    output: Output,
):
    ffmpeg_runners = [FfmpegRunner(conf) for _ in output.components]
    dolphin_runners = [DolphinRunner(conf, kill_event) for _ in output.components]
    futures = {
        c: executor.submit(render, fr, dr, c)
        for fr, dr, c in zip(ffmpeg_runners, dolphin_runners, output.components)
    }
    concurrent.futures.wait(futures.values())
    tmp_paths = [futures[c].result() for c in output.components]
    concat(conf, output, tmp_paths)


def render(ffmpeg_runner, dolphin_runner, component: OutputComponent):
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_path = pathlib.Path(tmp.name)
    video.render(ffmpeg_runner, dolphin_runner, component, tmp_path)
    tmp.close()
    return tmp_path


def concat(conf: dict, output: Output, renders: list[pathlib.Path]):
    Ffmpeg = FfmpegRunner(conf)
    output.output.parent.mkdir(parents=True, exist_ok=True)
    if output.context:
        for index, component in enumerate(output.components):
            render = renders[index]
            component = output.components[index]
            new_render = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            new_render.close()
            new_render_path = pathlib.Path(new_render.name)
            Ffmpeg.add_scoreboard(render, component.context, new_render_path)
            render.unlink()
            renders[index] = new_render_path
    Ffmpeg.concat_videos(renders, output.output)
    for render in renders:
        render.unlink()


def run(event: multiprocessing.Event, conf: dict, outputs: list[Output]):
    num_procs = conf["runtime"]["parallel"]
    with concurrent.futures.ProcessPoolExecutor(num_procs) as executor:
        for output in outputs:
            render_and_concat(event, executor, conf, output)
