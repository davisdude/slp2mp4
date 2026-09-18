# An artifact is any input or output in the pipeline, even temporary

import dataclasses
import pathlib

@dataclasses.dataclass(frozen=True)
class Artifact:
    path: pathlib.Path

    def __post_init__(self):
        pass

    def __str__(self):
        return self.path.name

    def exists(self):
        return self.path.is_file()


@dataclasses.dataclass(frozen=True)
class ExistingFileArtifact(Artifact):
    def __post_init__(self):
        super().__post_init__()
        if not self.exists():
            raise RuntimeError(f"'{self.path}' does not exist.")


@dataclasses.dataclass(frozen=True)
class SlippiArtifact(ExistingFileArtifact):
    def __post_init__(self):
        super().__post_init__()
        if self.path.suffix != ".slp":
            raise RuntimeError(f"'{self.path}' has invalid file extension for a slippi file.")


@dataclasses.dataclass(frozen=True)
class Mp4Artifact(Artifact):
    def __post_init__(self):
        super().__post_init__()
        if self.path.suffix != ".mp4":
            raise RuntimeError(f"'{self.path}' has invalid file extension for an mp4 file.")
