# An output is the collection of slp inputs comprising a single video output

import dataclasses
import pathlib

from slp2mp4.context_helper import GameContextInfo


@dataclasses.dataclass
class Output:
    inputs: list[pathlib.Path] = dataclasses.field(default_factory=list)  # slps
    output: pathlib.Path = dataclasses.field(default=pathlib.Path("."))
    context_path: pathlib.Path
    contexts: list[GameContextInfo] = dataclasses.field(init=False)

    def __post_init__(self):
        self.contexts = [
            GameContextInfo(self.context_path, game_index) if self.context_path else None
            for game_index in range(1, len(self.inputs) + 1)
        ]
