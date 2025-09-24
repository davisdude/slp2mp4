# An output is the collection of slp inputs comprising a single video output

import dataclasses
import pathlib

from slp2mp4.context_helper import GameContextInfo


@dataclasses.dataclass(eq=True, frozen=True)
class OutputComponent:
    slp: pathlib.Path
    index: int
    context: GameContextInfo | None


class Output:
    def __init__(
        self,
        slps: list[pathlib.Path],
        output: pathlib.Path,
        context_path: pathlib.Path | None,
    ):
        self.components = [
            OutputComponent(
                slp,
                game_index,
                GameContextInfo(context_path, game_index) if context_path else None,
            )
            for game_index, slp in enumerate(slps)
        ]
        self.output = output
        self.context = context_path
