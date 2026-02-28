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
    if kill_event.is_set():
        return
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
    renders: dict[concurrent.futures.Future[pathlib.Path], int],
    kill_event: multiprocessing.Event,
):
    completed_renders = {
        renders[future]: future.result()
        for future in concurrent.futures.wait(renders.keys()).done
    }
    render_list = dict(sorted(completed_renders.items())).values()
    if kill_event.is_set():
        for render in render_list:
            render.unlink(missing_ok=True)
        return
    ffmpeg_runner = FfmpegRunner(conf)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_runner.concat_videos(render_list, output_path)
    for render in render_list:
        render.unlink()


def run(kill_event: multiprocessing.Event, conf: dict, outputs: list[Output]):
    num_workers = conf["runtime"]["parallel"]
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as render_pool:
        with concurrent.futures.ThreadPoolExecutor() as concat_pool:
            for output in outputs:
                future_to_index = {
                    render_pool.submit(render, conf, slp_path, kill_event): index
                    for index, slp_path in enumerate(output.inputs)
                }
                concat_futures = concat_pool.submit(
                    concat, conf, output.output, future_to_index, kill_event
                )
                futures.extend(future_to_index.keys())
                futures.append(concat_futures)
            concurrent.futures.wait(futures)
            for future in futures:
                if future.exception():
                    raise future.exception()
