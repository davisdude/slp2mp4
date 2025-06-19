# Commonizes the batching / concatenating of slippi files
# There are to threads here:
#   1. The "render" thread, which runs dolphin / does frame dumps
#   2. The "concat" thread, which contatenates frame-dumps into a single mp4

import multiprocessing
import pathlib
import queue
import tempfile

import slp2mp4.ffmpeg as ffmpeg
import slp2mp4.video as video
from slp2mp4.output import Output


def _render(conf, slp_queue, video_queue):
    while True:
        data = slp_queue.get()
        if data is None:
            break
        output_name, slp_path, context, index = data
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        video.render(
            conf, slp_path, pathlib.Path(tmp.name), context, output_name, index
        )
        tmp.close()
        video_queue.put((output_name, tmp.name, index))


def _concat(conf, video_queue, outputs):
    Ffmpeg = ffmpeg.FfmpegRunner(conf)
    mp4s = {}
    while True:
        data = video_queue.get()
        if data is None:
            break
        output_name, mp4_path, index = data
        if output_name not in mp4s:
            mp4s[output_name] = {}
        mp4s[output_name][index] = mp4_path
        output = list(filter(lambda o: o.output == output_name, outputs))[0]
        if len(mp4s[output_name]) < len(output.inputs):
            continue
        tmpfiles = [
            pathlib.Path(mp4s[output_name][index])
            for index in range(len(output.inputs))
        ]
        Ffmpeg.concat_videos(tmpfiles, output_name)
        for tmp in tmpfiles:
            tmp.unlink()


def run(conf, outputs: list[Output]):
    num_procs = conf["runtime"]["parallel"]
    slp_queue = multiprocessing.Queue()
    video_queue = multiprocessing.Queue()
    slp_pool = multiprocessing.Pool(
        num_procs,
        _render,
        (
            conf,
            slp_queue,
            video_queue,
        ),
    )
    video_pool = multiprocessing.Pool(
        1,
        _concat,
        (
            conf,
            video_queue,
            outputs,
        ),
    )

    for output in outputs:
        for index, slp in enumerate(output.inputs):
            slp_queue.put(
                (
                    output.output,
                    slp,
                    output.context,
                    index,
                )
            )

    for i in range(num_procs):
        slp_queue.put(None)

    slp_queue.close()
    slp_queue.join_thread()

    slp_pool.close()
    slp_pool.join()

    video_queue.put(None)

    video_queue.close()
    video_queue.join_thread()

    video_pool.close()
    video_pool.join()
