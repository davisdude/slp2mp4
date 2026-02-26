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

import pathvalidate


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

    def get_name(self, prefix, path):
        name = path.name
        if not self.conf["runtime"]["prepend_directory"]:
            prefix = pathlib.Path(*prefix.parts[1:])
        out_dir = self.output_directory
        if self.conf["runtime"]["preserve_directory_structure"]:
            out_dir /= prefix
        elif prefix.parts:
            name = f"{(' ').join(prefix.parts)} {name}"
        if self.conf["runtime"]["youtubify_names"]:
            name = util.translate(name, self.conf["runtime"]["name_replacements"])
        name = name.removesuffix(".slp")
        name += ".mp4"
        sanitized = pathlib.Path(pathvalidate.sanitize_filename(name))
        # Name too long; suffix got dropped
        if not sanitized.suffix:
            # Drop beginning of name since it's more likely to be duplicated
            sanitized = sanitized.parent / (sanitized.name[4:] + ".mp4")
        return out_dir / sanitized

    def get_outputs(self) -> list[Output]:
        return [
            Output(slps, self.get_name(prefix, mp4))
            for path in self.paths
            for slps, prefix, mp4 in self.iterator(pathlib.Path("."), path)
        ]

    def _get_output(self, products):
        return [
            f"{output.output}:\n{('\n').join(f"\t{i}" for i in output.inputs)}"
            for output in products
        ]

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
