# Tasks are jobs that take artifacts as inputs and outputs

import dataclasses

from slp2mp4.artifact import (
    Artifact,
    ContextArtifact,
    Mp4Artifact,
    SlippiArtifact,
)


@dataclasses.dataclass(eq=False)
class Task:
    name: str
    inputs: list[Artifact]
    outputs: list[Artifact]

    @property
    def resources(self) -> dict[str, float]:
        raise NotImplementedError

    def check_inputs(self):
        for i in self.inputs:
            if not i.exists():
                raise RuntimeError(f"Input {i} does not exist.")

    def cleanup(self):
        for i in self.inputs:
            i.cleanup()

@dataclasses.dataclass(eq=False)
class VideoTask(Task):
    def __post_init__(self):
        videos = [o for o in self.outputs if isinstance(o, Mp4Artifact)]
        assert len(videos) == 1
        self.video = videos[0]


@dataclasses.dataclass(eq=False)
class RenderGameTask(VideoTask):
    index: int = dataclasses.field(default=0)
    slp: SlippiArtifact = dataclasses.field(init=False)
    context: ContextArtifact | None = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        super().__post_init__()

        slps = [i for i in self.inputs if isinstance(i, SlippiArtifact)]
        assert len(slps) == 1
        self.slp = slps[0]

        contexts = [i for i in self.inputs if isinstance(i, ContextArtifact)]
        assert len(contexts) <= 1
        if contexts:
            self.context = contexts[0]

    @property
    def resources(self):
        return {"cpu": 1.0}


@dataclasses.dataclass(eq=False)
class ConcatVideosTask(VideoTask):
    timestamps: list[int] = dataclasses.field(init=False, default_factory=list)

    @property
    def resources(self):
        # TODO: GPU concat via ffmpeg
        # TODO: This uses multiple cores; 1 is unrealistic. Changing it to reflect 100% util would
        #       require a smarter scheduler/some priority system, otherwise concats will be
        #       preempted by lower priorty tasks. It's quick enough that I think it's okay.
        return {"cpu": 1.0}


# TODO: Copy task
