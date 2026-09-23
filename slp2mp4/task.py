# Tasks are jobs that take artifacts as inputs and outputs

import dataclasses

from slp2mp4.artifact import Artifact, Mp4Artifact, TimestampArtifact


@dataclasses.dataclass(eq=False)
class Task:
    name: str
    inputs: list[Artifact]
    outputs: list[Artifact]

    def __post_init__(self):
        pass

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
class RenderGameTask(Task):
    def __post_init__(self):
        super().__post_init__()
        assert len(self.inputs) == len(self.outputs)

    @property
    def resources(self):
        return {"cpu": 1.0}


@dataclasses.dataclass(eq=False)
class ConcatVideosTask(Task):
    video: Mp4Artifact = dataclasses.field(init=False)
    timestamp: TimestampArtifact | None = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        videos = [o for o in self.outputs if isinstance(o, Mp4Artifact)]
        timestamps = [o for o in self.outputs if isinstance(o, TimestampArtifact)]
        assert len(videos) == 1
        assert len(timestamps) <= 1
        self.video = videos[0]
        if timestamps:
            self.timestamp = timestamps[0]

    @property
    def resources(self):
        # TODO: GPU concat via ffmpeg
        # TODO: This uses multiple cores; 1 is unrealistic. Changing it to reflect 100% util would
        #       require a smarter scheduler/some priority system, otherwise concats will be
        #       preempted by lower priorty tasks. It's quick enough that I think it's okay.
        return {"cpu": 1.0}
