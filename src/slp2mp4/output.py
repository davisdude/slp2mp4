# An output is the collection of slp inputs comprising a single video output

import dataclasses
import pathlib


@dataclasses.dataclass
class Output:
    inputs: list[pathlib.Path] = dataclasses.field(default_factory=list)  # slps
    output: pathlib.Path = dataclasses.field(default=pathlib.Path("."))
    context: pathlib.Path = dataclasses.field(default=None)
