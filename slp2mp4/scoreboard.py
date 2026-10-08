import dataclasses
import importlib
import os
import tempfile
from pathlib import Path

from html2image import Html2Image
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

import slp2mp4
from slp2mp4 import util
from slp2mp4.artifact import Mp4Artifact, SlippiArtifact
from slp2mp4.config import ScoreboardConfig, ScoreboardType

DEFAULT_LOGO_PATH = importlib.resources.files(slp2mp4).joinpath("logo.svg")
TEMPLATES_DIR = importlib.resources.files(slp2mp4).joinpath("templates")
MELEE_ASPECT_RATIO = 73 / 60


@dataclasses.dataclass(kw_only=True)
class ScoreboardBase:
    slp: SlippiArtifact
    input_video: Mp4Artifact
    output_video: Mp4Artifact
    input_video_dimensions: tuple[int, int]
    output_video_height: int
    config: ScoreboardConfig
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
    def tournament_date(self):
        return util.unix_ms_to_datetime(
            self.slp.context.start_ms, self.config.timezone.tzinfo
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
        raise NotImplementedError

    def render_image(self):
        # TODO: provide browser_executable
        if self.slp.context is not None:
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
        args = ["-y", "-i", str(self.input_video.path)]
        if self.slp.context:
            args.extend(["-i", str(self.image_path), "-framerate", "60", "-loop", "1"])

        filter_str = (
            # Scale video down
            f"[0]scale={self.size[0]}:{self.size[1]}:force_original_aspect_ratio=decrease,"
            # Pad to output resolution
            f"pad=w={self.size[0]}:h={self.size[1]}:{self.video_alignment}:color={self.config.theme.background_color}"
            # Overlay
            f"{'[scaled];[scaled][1:v]overlay,' if self.slp.context is not None else ','}"
            # Bookkeeping
            "setsar=1,setpts=PTS-STARTPTS"
        )
        args.extend(
            [
                "-filter_complex",
                filter_str,
                "-c:v",
                "libx264",  # TODO
                "-c:a",
                "copy",
                "-shortest",
                "-avoid_negative_ts",
                "make_zero",
                "-bf",
                "0",
                str(self.output_video.path),
            ]
        )
        return args

    def cleanup(self):
        for artifact in self.tmp_paths:
            artifact.unlink(missing_ok=True)


@dataclasses.dataclass
class SharedScoreboard(ScoreboardBase):
    logo_path: Path = dataclasses.field(default=None)
    left: bool = dataclasses.field(default=True)
    checkbox: bool = dataclasses.field(default=False)

    def __post_init__(self):
        super().__post_init__()
        if not self.logo_path:
            self.logo_path = DEFAULT_LOGO_PATH
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
    logo_path: Path = dataclasses.field(default=None)
    checkbox: bool = dataclasses.field(default=False)

    def __post_init__(self):
        super().__post_init__()
        if not self.logo_path:
            self.logo_path = DEFAULT_LOGO_PATH
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
    ratio: float
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
