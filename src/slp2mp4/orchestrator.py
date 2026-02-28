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


def render(conf: dict, component: pathlib.Path, kill_event: multiprocessing.Event):
    logger = log.get_logger()
    if kill_event.is_set():
        return
    ffmpeg_runner = FfmpegRunner(conf)
    dolphin_runner = DolphinRunner(conf, kill_event)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_path = pathlib.Path(tmp.name)
    logger.info(f"Rendering '{component.slp}' to '{tmp_path}")
    success = video.render(ffmpeg_runner, dolphin_runner, component, tmp_path) and not kill_event.is_set()
    tmp.close()
    if not success:
        logger.error(f"Failed to render '{component.slp}'")
    else:
        logger.info(f"Done rendering '{component.slp}'")
    if success and component.context:
        new_render = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        new_render.close()
        new_render_path = pathlib.Path(new_render.name)
        logger.info(f"Adding scoreboard to '{tmp_path}' as '{new_render_path}'")
        success = ffmpeg_runner.add_scoreboard(tmp_path, component.context, new_render_path)
        if not success:
            logger.error(f"Failed to add scoreboard to '{new_render_path}'")
        else:
            logger.info(f"Finished scoreboard for '{new_render_path}'")
        tmp_path.unlink()
        tmp_path = new_render_path
    return tmp_path, success


def concat(
    conf: dict,
    output: Output,
    renders: dict[concurrent.futures.Future[tuple[pathlib.Path, bool]], int],
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
    output.output.parent.mkdir(parents=True, exist_ok=True)
    render_str = (", ").join([f"'{r}'" for r in render_list])
    logger.info(f"Combining {render_str} into '{output.output}'")
    success = ffmpeg_runner.concat_videos(render_list, output.output)
    if not success:
        logger.error(f"Failed to combine '{output.output}'")
    else:
        logger.info(f"Done combining '{output.output}'")
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
