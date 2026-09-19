import concurrent.futures
import tempfile
import multiprocessing

from slp2mp4.task import RenderGameTask, ConcatVideosTask


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
