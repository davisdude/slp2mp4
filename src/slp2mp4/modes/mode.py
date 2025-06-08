import pathlib

from slp2mp4.output import Output
import slp2mp4.orchestrator as orchestrator
import slp2mp4.config as config


class Mode:
    def __init__(self, paths: list[pathlib.Path], output_directory: pathlib.Path):
        self.paths = paths
        self.output_directory = output_directory

    def iterator(self, root, path):
        raise NotImplementedError("Child must implement `iterator`")

    def get_name(self, path):
        parent_part = ("_").join(path.parent.parts)
        parent_prefix = f"{parent_part}_" if path.parent != pathlib.Path(".") else ""
        return self.output_directory / f"{parent_prefix}{path.stem}.mp4"

    def get_outputs(self) -> list[Output]:
        return [
            Output(slps, self.get_name(mp4))
            for path in self.paths
            for slps, mp4 in self.iterator(pathlib.Path("."), path)
        ]

    def run(self, dry_run=False):
        products = self.get_outputs()
        conf = config.get_config()
        config.validate_config(conf)
        config.translate_config(conf)
        if dry_run:
            out = ""
            for output in products:
                out += f"{output.output}\n"
                for i in output.inputs:
                    out += f"\t{i}\n"
            return out
        else:
            self.output_directory.mkdir(parents=True, exist_ok=True)
            orchestrator.run(conf, products)
