import concurrent.futures
import dataclasses
import enum
import pathlib
import tempfile
import multiprocessing

from slp2mp4.dolphin.runner import DolphinRunner
from slp2mp4.ffmpeg import FfmpegRunner
from slp2mp4.output import Output

import slp2mp4.log as log
import slp2mp4.video as video


def render(conf: dict, slp_path: pathlib.Path, kill_event: multiprocessing.Event):
    logger = log.get_logger()
    if kill_event.is_set():
        return
    ffmpeg_runner = FfmpegRunner(conf)
    dolphin_runner = DolphinRunner(conf, kill_event)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_path = pathlib.Path(tmp.name)
    logger.info(f"Rendering '{slp_path}' to '{tmp_path}")
    success = video.render(ffmpeg_runner, dolphin_runner, slp_path, tmp_path)
    if not success:
        logger.error(f"Failed to render '{slp_path}'")
    else:
        logger.info(f"Done rendering '{slp_path}'")
    tmp.close()
    return tmp_path, success


def concat(
    conf: dict,
    output_path: pathlib.Path,
    renders: dict[tuple[concurrent.futures.Future[pathlib.Path], bool], int],
    kill_event: multiprocessing.Event,
):
    logger = log.get_logger()
    completed_renders = {
        renders[future]: future.result()
        for future in concurrent.futures.wait(renders.keys()).done
    }
    render_outputs = dict(sorted(completed_renders.items())).values()
    render_list, sucesses = zip(*render_outputs)
    error = False in sucesses
    if kill_event.is_set() or error:
        for render in render_list:
            if render is not None:
                render.unlink(missing_ok=True)
        return
    ffmpeg_runner = FfmpegRunner(conf)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    render_str = (", ").join([f"'{r}'" for r in render_list])
    logger.info(f"Combining {render_str} into '{output_path}'")
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
