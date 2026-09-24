# An artifact is any input or output in the pipeline, even temporary

import dataclasses
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class Artifact:
    path: Path

    def __post_init__(self):
        pass

    def __str__(self):
        return self.path.name

    def exists(self):
        return self.path.exists()

    def cleanup(self):
        self.path.unlink(missing_ok=True)


@dataclasses.dataclass(frozen=True)
class ExistingFileArtifact(Artifact):
    def __post_init__(self):
        super().__post_init__()
        if not self.exists():
            raise RuntimeError(f"'{self.path}' does not exist.")

    def cleanup(self):
        pass


@dataclasses.dataclass(frozen=True)
class ContextArtifact(ExistingFileArtifact):
    def __post_init__(self):
        super().__post_init__()
        if self.path.suffix != ".json":
            raise RuntimeError(
                f"'{self.path}' has invalid file extension for a context file."
            )


@dataclasses.dataclass(frozen=True)
class SlippiArtifact(ExistingFileArtifact):
    index: int = dataclasses.field(default=0)
    context: ContextArtifact | None = dataclasses.field(default=None)

    def __post_init__(self):
        super().__post_init__()
        if self.path.suffix != ".slp":
            raise RuntimeError(
                f"'{self.path}' has invalid file extension for a slippi file."
            )


@dataclasses.dataclass(frozen=True)
class Mp4Artifact(Artifact):
    def __post_init__(self):
        super().__post_init__()
        if self.path.suffix != ".mp4":
            raise RuntimeError(
                f"'{self.path}' has invalid file extension for an mp4 file."
            )
