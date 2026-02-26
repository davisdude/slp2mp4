import concurrent.futures
import contextlib
import dataclasses
import multiprocessing
import pathlib

from slp2mp4.output import Output
import slp2mp4.orchestrator as orchestrator
import slp2mp4.config as config


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
        out = ""
        for output in products:
            out += f"{output.output}\n"
            for component in output.components:
                out += f"\t{component.slp}\n"
            if output.context:
                out += f"\tcontext: {output.context}\n"
            out += "\n"
        return out

    @contextlib.contextmanager
    def run(self, event: multiprocessing.Event):
        self.conf = config.get_config()
        config.translate_and_validate_config(self.conf)
        products = self.get_outputs()
        with concurrent.futures.ThreadPoolExecutor(1) as executor:
            if self.dry_run:
                future = executor.submit(self._get_output, products)
            else:
                self.output_directory.mkdir(parents=True, exist_ok=True)
                future = executor.submit(orchestrator.run, event, self.conf, products)
            yield executor, future


@dataclasses.dataclass
class ModeContainer:
    mode: Mode
    help: str
    description: str
