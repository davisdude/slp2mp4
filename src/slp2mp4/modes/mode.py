import concurrent.futures
import contextlib
import dataclasses
import multiprocessing
import pathlib

from slp2mp4.output import Output
import slp2mp4.orchestrator as orchestrator
import slp2mp4.config as config
import slp2mp4.util as util

import pathvalidate


class Mode:
    def __init__(
        self,
        paths: list[pathlib.Path],
        output_directory: pathlib.Path,
    ):
        self.paths = paths
        self.output_directory = output_directory
        self.conf = None

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
            Output(slps, self.get_name(prefix, mp4), context)
            for path in self.paths
            for slps, prefix, mp4, context in self.iterator(pathlib.Path("."), path)
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
    def run(self, event: multiprocessing.Event, dry_run=False):
        self.conf = config.get_config()
        config.translate_and_validate_config(self.conf)
        products = self.get_outputs()
        with concurrent.futures.ThreadPoolExecutor(1) as executor:
            if dry_run:
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
