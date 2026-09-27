import dataclasses
import importlib
import os
import tempfile
from enum import Enum
from pathlib import Path

from html2image import Html2Image
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

import slp2mp4
from slp2mp4.artifact import Mp4Artifact, SlippiArtifact

DEFAULT_LOGO_PATH = importlib.resources.files(slp2mp4).joinpath("logo.svg")
TEMPLATES_DIR = importlib.resources.files(slp2mp4).joinpath("templates")
MELEE_ASPECT_RATIO = 73 / 60


class ScoreboardType(Enum):
    NONE = "None"
    SHARED = "Shared"
    SPLIT = "Split"
    MINIMAL = "Minimal"
    CUSTOM = "Custom"


@dataclasses.dataclass(kw_only=True)
class ScoreboardBase:
    slp: SlippiArtifact
    input_video: Mp4Artifact
    output_video: Mp4Artifact
    input_video_dimensions: tuple[int, int]
    output_video_height: int
    workdir: Path | None = dataclasses.field(default=None)
    image_path: Path | None = dataclasses.field(default=None)

    tmp_paths: list[Path] = dataclasses.field(default_factory=list, init=False)

    def __post_init__(self):
        if self.image_path is None:
            fd, tmp = tempfile.mkstemp(suffix=".png", dir=self.workdir)
            os.close(fd)
            self.image_path = Path(tmp)
            self.tmp_paths.append(self.image_path)
        self.jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=select_autoescape(["html", "css"]),
            undefined=StrictUndefined,
        )

    @property
    def html(self):
        return self.html_template.render(sb=self)

    @property
    def css(self):
        return self.css_template.render(sb=self)

    @property
    def input_aspect_ratio(self):
        return self.input_video_dimensions[0] / self.input_video_dimensions[1]

    @property
    def size(self) -> tuple[int, int]:
        return (
            round(self.aspect_ratio * self.output_video_height / 2) * 2,
            self.output_video_height,
        )

    @property
    def aspect_ratio(self):
        raise NotImplementedError

    @property
    def video_alignment(self) -> str:
        raise NotImplementedError

    @property
    def html_template(self) -> str:
        raise NotImplementedError

    @property
    def css_template(self) -> str:
        # TODO: Custom color, font, etc
        raise NotImplementedError

    def render_image(self):
        # TODO: provide browser_executable
        hti = Html2Image(
            custom_flags=[
                "--no-sandbox",
                "--default-background-color=00000000",
                "--hide-scrollbars",
            ],
            output_path=self.image_path.parent,
            disable_logging=True,
        )
        hti.screenshot(
            html_str=self.html,
            css_str=self.css,
            save_as=self.image_path.name,
            size=self.size,
        )

    def get_ffmpeg_command(self) -> list[str]:
        return [
            "-y",
            "-i",
            str(self.input_video.path),
            "-framerate",
            "60",
            "-loop",
            "1",
            "-i",
            str(self.image_path),
            "-filter_complex",
            (
                # Scale video down
                f"[0]scale={self.size[0]}:{self.size[1]}:force_original_aspect_ratio=decrease,"
                # Pad to output resolution
                f"pad=w={self.size[0]}:h={self.size[1]}:{self.video_alignment}[scaled];"
                # Overlay
                "[scaled][1:v]overlay"
            ),
            "-c:v",
            "libx264",  # TODO
            "-c:a",
            "copy",
            "-shortest",
            str(self.output_video.path),
        ]

    def cleanup(self):
        for artifact in self.tmp_paths:
            artifact.unlink(missing_ok=True)


@dataclasses.dataclass
class SharedScoreboard(ScoreboardBase):
    logo: Path = dataclasses.field(default=None)
    left: bool = dataclasses.field(default=True)

    def __post_init__(self):
        super().__post_init__()
        if self.logo is None:
            self.logo = DEFAULT_LOGO_PATH
        if abs(self.input_aspect_ratio - MELEE_ASPECT_RATIO) > 1e-3:
            raise RuntimeError("Shared scoreboard must not be widescreen")

    @property
    def aspect_ratio(self):
        return 16 / 9

    @property
    def video_alignment(self):
        if self.left:
            return "x=(ow-iw):y=0"
        return "x=0:y=0"

    @property
    def html_template(self):
        return self.jinja_env.get_template("shared.html")

    @property
    def css_template(self):
        return self.jinja_env.get_template("shared.css")


@dataclasses.dataclass
class SplitScoreboard(ScoreboardBase):
    logo: Path = dataclasses.field(default=None)
    logo_right: Path = dataclasses.field(default=None)

    def __post_init__(self):
        super().__post_init__()
        if self.logo is None:
            self.logo = DEFAULT_LOGO_PATH
        if self.logo_right is None:
            self.logo_right = DEFAULT_LOGO_PATH
        if abs(self.input_aspect_ratio - MELEE_ASPECT_RATIO) > 1e-3:
            raise RuntimeError("Split scoreboard must not be widescreen")

    @property
    def aspect_ratio(self):
        return 16 / 9

    @property
    def video_alignment(self):
        return "x=(ow-iw)/2:y=0"

    @property
    def html_template(self):
        return self.jinja_env.get_template("split.html")

    @property
    def css_template(self):
        return self.jinja_env.get_template("split.css")


@dataclasses.dataclass
class MinimalScoreboard(ScoreboardBase):
    @property
    def aspect_ratio(self):
        return self.input_aspect_ratio

    @property
    def video_alignment(self):
        return "x=0:y=0"

    @property
    def html_template(self):
        return self.jinja_env.get_template("minimal.html")

    @property
    def css_template(self):
        return self.jinja_env.get_template("minimal.css")


@dataclasses.dataclass
class CustomScoreboard(ScoreboardBase):
    alignment: str
    ratio: float | None
    html_path: Path
    css_path: Path

    @property
    def aspect_ratio(self):
        return self.ratio or self.input_aspect_ratio

    @property
    def video_alignment(self):
        return self.alignment

    @property
    def html_template(self):
        html = self.html_path.resolve().read_text(encoding="utf-8")
        return self.jinja_env.from_string(html)

    @property
    def css_template(self):
        css = self.css_path.resolve().read_text(encoding="utf-8")
        return self.jinja_env.from_string(css)


SCOREBOARD_MAPPING = {
    ScoreboardType.SHARED: SharedScoreboard,
    ScoreboardType.SPLIT: SplitScoreboard,
    ScoreboardType.MINIMAL: MinimalScoreboard,
    ScoreboardType.CUSTOM: CustomScoreboard,
}
