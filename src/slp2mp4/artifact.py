# An artifact is any input or output in the pipeline, even temporary

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Artifact:
    path: Path

    def __post_init__(self):
        pass

    def __str__(self):
        return self.path.name

    def exists(self):
        return self.path.is_file()


@dataclass(frozen=True)
class ExistingFileArtifact(Artifact):
    def __post_init__(self):
        super().__post_init__()
        if not self.exists():
            raise RuntimeError(f"'{self.path}' does not exist.")


@dataclass(frozen=True)
class SlippiArtifact(ExistingFileArtifact):
    def __post_init__(self):
        super().__post_init__()
        if self.path.suffix != ".slp":
            raise RuntimeError(f"'{self.path}' has invalid file extension for a slippi file.")


@dataclass(frozen=True)
class Mp4Artifact(Artifact):
    def __post_init__(self):
        super().__post_init__()
        if self.path.suffix != ".mp4":
            raise RuntimeError(f"'{self.path}' has invalid file extension for an mp4 file.")
