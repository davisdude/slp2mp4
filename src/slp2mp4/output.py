# An output is the collection of slp inputs comprising a single video output

import dataclasses
import pathlib

import pathvalidate

from slp2mp4.context_helper import GameContextInfo
import slp2mp4.util as util


@dataclasses.dataclass(eq=True, frozen=True)
class OutputComponent:
    slp: pathlib.Path
    context: GameContextInfo | None


class Output:
    def __init__(
        self,
        conf: dict,
        output_directory: pathlib.Path,
        slps: list[pathlib.Path],
        prefix: pathlib.Path,
        path: pathlib.Path,
        context_path: pathlib.Path | None,
        game_indices: list[int],
    ):
        self.conf = conf
        self.components = [
            OutputComponent(
                slp,
                GameContextInfo(context_path, game_index) if context_path else None,
            )
            for game_index, slp in zip(game_indices, slps)
        ]
        self.context = context_path
        self.game_indices = game_indices
        self.output = self._get_name(output_directory, prefix, path)

    def _get_name(self, output_directory, prefix, path):
        if self.conf["runtime"]["preserve_directory_structure"]:
            output_directory /= prefix
        name = (
            self._get_name_context()
            if self.context is not None
            else self.get_name_no_context(prefix, path)
        )
        if self.conf["runtime"]["youtubify_names"]:
            name = util.translate(name, self.conf["runtime"]["name_replacements"])
        name += ".mp4"
        sanitized = pathlib.Path(pathvalidate.sanitize_filename(name))
        # Name too long; suffix got dropped
        if not sanitized.suffix:
            # Drop beginning of name since it's more likely to be duplicated
            sanitized = sanitized.parent / (sanitized.name[4:] + ".mp4")
        return output_directory / sanitized

    def _get_name_context(self):
        # Assumes first index is representative of entire set
        index = self.game_indices[0]
        comp = self.components[0].context
        team_1 = ("/").join(comp.slot_data[0]["displayNames"])
        team_2 = ("/").join(comp.slot_data[1]["displayNames"])
        tournament = comp.tournament_name
        round_info = comp.bracket_round_text
        suffix = f" - Game {index + 1}" if len(self.game_indices) == 1 else ""
        return f"{team_1} vs {team_2} - {tournament} - {round_info}{suffix}"

    def _get_name_no_context(self, prefix, path):
        name = path.name
        if not self.conf["runtime"]["prepend_directory"]:
            prefix = pathlib.Path(*prefix.parts[1:])
        if prefix.parts:
            name = f"{(' ').join(prefix.parts)} {name}"
        return name.removesuffix(".slp")
