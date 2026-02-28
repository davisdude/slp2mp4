import concurrent.futures
import contextlib
import dataclasses
import multiprocessing
import pathlib

from slp2mp4.output import Output
import slp2mp4.orchestrator as orchestrator
import slp2mp4.config as config
import slp2mp4.log as log
import slp2mp4.util as util


class Mode:
    def __init__(
        self,
        paths: list[pathlib.Path],
        output_directory: pathlib.Path,
        dry_run: bool,
    ):
        self.paths = paths
        self.output_directory = output_directory
        self.dry_run = dry_run
        self.conf = None
        self.log = log.get_logger()

    def iterator(self, location, path):
        raise NotImplementedError("Child must implement `iterator`")

    def get_outputs(self) -> list[Output]:
        return [
            Output(
                self.conf, self.output_directory, slps, prefix, mp4, context, indices
            )
            for path in self.paths
            for slps, prefix, mp4, context, indices in self.iterator(
                pathlib.Path("."), path
            )
        ]

    def _get_output(self, products):
        text = []
        for output in products:
            text.append(f"{output.output}:")
            for component in output.components:
                text.append(f"\t{component.slp}")
            if output.context:
                text.append(f"\tcontext: {output.context}")
        return text

    @contextlib.contextmanager
    def run(self, event: multiprocessing.Event):
        self.conf = config.get_config()
        try:
            config.translate_and_validate_config(self.conf)
        except Exception as e:
            self.log.error(f"Error during config validation: {e}")
            yield None, None
            return
        products = self.get_outputs()
        if self.dry_run:
            outputs = self._get_output(products)
            for output in outputs:
                self.log.info(output)
            yield None, None
            return
        with concurrent.futures.ThreadPoolExecutor(1) as executor:
            self.output_directory.mkdir(parents=True, exist_ok=True)
            future = executor.submit(orchestrator.run, event, self.conf, products)
            yield executor, future

    def cleanup(self):
        pass


@dataclasses.dataclass
class ModeContainer:
    mode: Mode
    help: str
    description: str
