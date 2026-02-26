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


def render(conf: dict, component: pathlib.Path, kill_event: multiprocessing.Event):
    if kill_event.is_set():
        return
    ffmpeg_runner = FfmpegRunner(conf)
    dolphin_runner = DolphinRunner(conf, kill_event)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_path = pathlib.Path(tmp.name)
    video.render(ffmpeg_runner, dolphin_runner, component, tmp_path)
    tmp.close()
    if component.context:
        new_render = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        new_render.close()
        new_render_path = pathlib.Path(new_render.name)
        ffmpeg_runner.add_scoreboard(tmp_path, component.context, new_render_path)
        tmp_path.unlink()
        tmp_path = new_render_path
    return tmp_path


def concat(
    conf: dict,
    output: Output,
    renders: dict[concurrent.futures.Future[pathlib.Path], int],
    kill_event: multiprocessing.Event,
):
    if kill_event.is_set():
        return
    completed_renders = {
        renders[future]: future.result()
        for future in concurrent.futures.wait(renders.keys()).done
    }
    render_list = dict(sorted(completed_renders.items())).values()
    ffmpeg_runner = FfmpegRunner(conf)
    output.output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_runner.concat_videos(render_list, output.output)
    for render in render_list:
        render.unlink()


def run(kill_event: multiprocessing.Event, conf: dict, outputs: list[Output]):
    num_workers = conf["runtime"]["parallel"]
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as render_pool:
        with concurrent.futures.ThreadPoolExecutor() as concat_pool:
            for output in outputs:
                future_to_index = {
                    render_pool.submit(render, conf, component, kill_event): index
                    for index, component in enumerate(output.components)
                }
                concat_futures = concat_pool.submit(
                    concat, conf, output, future_to_index, kill_event
                )
                futures.extend(future_to_index.keys())
                futures.append(concat_futures)
            concurrent.futures.wait(futures)
            for future in futures:
                if future.exception():
                    raise future.exception()
