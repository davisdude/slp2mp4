import concurrent.futures
import dataclasses
import enum
import pathlib
import tempfile
import multiprocessing

from slp2mp4.dolphin.runner import DolphinRunner
from slp2mp4.ffmpeg import FfmpegRunner

import slp2mp4.video as video
from slp2mp4.output import Output


def render(conf: dict, slp_path: pathlib.Path, kill_event: multiprocessing.Event):
    ffmpeg_runner = FfmpegRunner(conf)
    dolphin_runner = DolphinRunner(conf, kill_event)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_path = pathlib.Path(tmp.name)
    video.render(ffmpeg_runner, dolphin_runner, slp_path, tmp_path)
    tmp.close()
    return tmp_path


def concat(
    conf: dict,
    output_path: pathlib.Path,
    renders: list[concurrent.futures.Future[pathlib.Path]],
):
    renders = list(renders)
    Ffmpeg = FfmpegRunner(conf)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Ffmpeg.concat_videos(renders, output_path)
    for render in renders:
        render.unlink()


def run(kill_event: multiprocessing.Event, conf: dict, outputs: list[Output]):
    num_workers = conf["runtime"]["parallel"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as render_pool:
        with concurrent.futures.ThreadPoolExecutor() as concat_pool:
            for output in outputs:
                confs = (conf for _ in output.inputs)
                kill_events = (kill_event for _ in output.inputs)
                render_futures = render_pool.map(
                    render, confs, output.inputs, kill_events
                )
                concat_futures = concat_pool.submit(
                    concat, conf, output.output, render_futures
                )
