import dataclasses
import pathlib

from slp2mp4.output import Output
import slp2mp4.orchestrator as orchestrator
import slp2mp4.config as config

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
        if self.conf["runtime"]["prepend_directory"]:
            prefix = (" ").join(prefix.parts)
        else:
            prefix = (" ").join(prefix.parts[1:])
        if prefix:
            name = f"{prefix} {name}"
        if self.conf["runtime"]["youtubify_names"]:
            # TODO: Change to dict replace in utils
            name = name.replace("-", "—")
            name = name.replace("(", "⟮")
            name = name.replace(")", "⟯")
            name = name.replace("_", "＿")
            name = name.replace("<", "＜")
            name = name.replace(">", "＞")
            name = name.replace(".", "．")
        name = name.removesuffix(".slp")
        name += ".mp4"
        sanitized = self.output_directory / pathvalidate.sanitize_filename(name)
        # Name too long; suffix got dropped
        if not sanitized.suffix:
            # Drop beginning of name since it's more likely to be duplicated
            sanitized = sanitized.parent / (sanitized.name[4:] + ".mp4")
        return sanitized

    def get_outputs(self) -> list[Output]:
        return [
            Output(slps, self.get_name(prefix, mp4), context)
            for path in self.paths
            for slps, prefix, mp4, context in self.iterator(pathlib.Path("."), path)
        ]

    def run(self, dry_run=False):
        self.conf = config.get_config()
        config.translate_and_validate_config(self.conf)
        products = self.get_outputs()
        if dry_run:
            out = ""
            for output in products:
                out += f"{output.output}\n"
                for component in output.components:
                    out += f"\t{component.slp}\n"
                if output.context:
                    out += f"\tcontext: {output.context}\n"
                out += "\n"
            return out
        else:
            self.output_directory.mkdir(parents=True, exist_ok=True)
            orchestrator.run(self.conf, products)


@dataclasses.dataclass
class ModeContainer:
    mode: Mode
    help: str
    description: str
