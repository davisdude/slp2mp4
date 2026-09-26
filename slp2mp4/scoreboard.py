import dataclasses
import importlib
import os
import tempfile
from enum import Enum
from pathlib import Path

from html2image import Html2Image

import slp2mp4
from slp2mp4.artifact import Mp4Artifact, SlippiArtifact

DEFAULT_LOGO_PATH = importlib.resources.files(slp2mp4).joinpath("logo.svg")


class ScoreboardType(Enum):
    NONE = "None"
    SHARED = "Shared"
    SPLIT = "Split"
    MINIMAL = "Minimal"
    CUSTOM = "Custom"


@dataclasses.dataclass
class ScoreboardBase:
    slp: SlippiArtifact
    input_video: Mp4Artifact
    output_video: Mp4Artifact
    workdir: Path | None = dataclasses.field(default=None)
    image_path: Path | None = dataclasses.field(default=None)

    tmp_paths: list[Path] = dataclasses.field(default_factory=list, init=False)

    def __post_init__(self):
        if self.image_path is None:
            fd, tmp = tempfile.mkstemp(suffix=".mp4", dir=self.workdir)
            os.close(fd)
            self.image_path = Path(tmp)
            self.tmp_paths.append(self.image_path)

    @property
    def size(self) -> tuple[int, int]:
        # TODO: get size based on input image
        return (1280, 720)

    @property
    def html(self):
        return (
            self.html_header
            + (
                self.html_body_singles
                if self.slp.context.data.is_singles
                else self.html_body_doubles
            )
            + self.html_footer
        )

    @property
    def video_alignment(self) -> str:
        raise NotImplementedError

    @property
    def html_header(self) -> str:
        raise NotImplementedError

    @property
    def html_footer(self) -> str:
        raise NotImplementedError

    @property
    def html_body_singles(self) -> str:
        raise NotImplementedError

    @property
    def html_body_doubles(self) -> str:
        raise NotImplementedError

    @property
    def css(self) -> str:
        # TODO: Custom color, font, etc
        raise NotImplementedError

    def _render_image(self):
        # TODO: provide browser_executable
        hti = Html2Image(
            custom_flags=[
                "--no-sandbox",
                "--default-background-color=00000000",
                "--hide-scrollbars",
            ],
            output_path=self.image_path.parent,
        )
        hti.screenshot(
            html_str=self.html,
            css_str=self.css,
            save_as=self.image_path.name,
            size=self.size,
        )

    def get_ffmpeg_command(self) -> list[str]:
        self._render_image()
        return [
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
    logo: Path = dataclasses.field(default=DEFAULT_LOGO_PATH)
    left: bool = dataclasses.field(default=True)

    @property
    def video_alignment(self):
        if self.left:
            return "x=(ow-iw):y=0"
        return "x=0:y=0"

    @property
    def html_header(self):
        return f"""
<!DOCTYPE html>
<html lang="en">
    <body>
        <div id="container">
            <div class="tournament">
                <div class="tournament-name">{self.slp.context.data.tournament_name}</div>
                <div class="rule"><hr></div>
                <div class="tournament-location">{self.slp.context.data.tournament_date.strftime("%B %d, %Y").replace(" 0", " ")}</div>
                <div class="tournament-location">{self.slp.context.data.tournament_location}</div>
                <div class="rule"><hr></div>
            </div>
            <div class="filler"></div>
            <img src="{self.logo}" width=80%></img>
            <div class="filler"></div>
"""

    @property
    def html_footer(self):
        return f"""
            <div class="bracket">
                <div class="rule"><hr></div>
                <div class="bracket-info">
                    <span class="bracket-data">{self.slp.context.data.event_name}</span>
                    <span class="bracket-data">{self.slp.context.data.phase_name}</span>
                    <span class="bracket-data">{self.slp.context.data.round_name_short}</span>
                    <span class="bracket-data">Bo{self.slp.context.data.best_of}</span>
                </div>
            </div>
        </div>
    </body>
</html>
"""

    @property
    def html_body_singles(self):
        return f"""
            <div class="combatants">
                <div class="rule"><hr></div>
                <div class="combatant">
                    <div class="combatant-team">
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[0].prefixes[0]}</span>
                            <span class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[0].display_names[0]}</span>
                            <span class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[0].pronouns[0]}</span>
                        </div>
                    </div>
                    <span class="combatant-score">{self.slp.context.data.scores[self.slp.index].slots[0].score}</span>
                </div>
                <div class="combatant">
                    <div class="combatant-team">
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[1].prefixes[0]}</span>
                            <span class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[1].display_names[0]}</span>
                            <span class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[1].pronouns[0]}</span>
                        </div>
                    </div>
                    <span class="combatant-score">{self.slp.context.data.scores[self.slp.index].slots[1].score}</span>
                </div>
            </div>
"""

    @property
    def html_body_doubles(self):
        return f"""
            <div class="combatants">
                <div class="rule"><hr></div>
                <div class="combatant">
                    <div class="combatant-team">
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[0].prefixes[0]}</span>
                            <span class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[0].display_names[0]}</span>
                            <span class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[0].pronouns[0]}</span>
                        </div>
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[0].prefixes[1]}</span>
                            <span class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[0].display_names[1]}</span>
                            <span class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[0].pronouns[1]}</span>
                        </div>
                    </div>
                    <span class="combatant-score">{self.slp.context.data.scores[self.slp.index].slots[0].score}</span>
                </div>
                <div class="combatant">
                    <div class="combatant-team">
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[1].prefixes[0]}</span>
                            <span class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[1].display_names[0]}</span>
                            <span class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[1].pronouns[0]}</span>
                        </div>
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[1].prefixes[1]}</span>
                            <span class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[1].display_names[1]}</span>
                            <span class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[1].pronouns[1]}</span>
                        </div>
                    </div>
                    <span class="combatant-score">{self.slp.context.data.scores[self.slp.index].slots[1].score}</span>
                </div>
            </div>
"""

    @property
    def css(self):
        return f"""
* {{
    box-sizing: border-box;
}}
html, body {{
    position: absolute;
    {"left: 0px;" if self.left else "right: 0px;"}
    color: white;
    font-family: "Inconsolata", "Consolas", "monospace";
    height: 100%;
    width: {606 / 1080 * self.size[1]}px;
    margin: 0 0 0 0;
    padding: 0.5vh 0.5vh 0.5vh 0.5vh;
}}
#container {{
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
}}
.tournament {{
    display: flex;
    flex-direction: column;
    flex-wrap: wrap;
    align-items: center;
    align-self: stretch;
}}
.rule {{
    align-self: stretch;
    flex-grow: 1;
}}
.tournament-name, .tournament-location {{
    display: flex;
    text-align: center;
}}
.tournament-name {{
    font-size: 6vh;
}}
.tournament-location {{
    font-size: 3vh;
}}
.filler {{
    flex-grow: 1;
}}
.combatants {{
    display: flex;
    flex-direction: column;
    align-self: stretch;
}}
.combatant {{
    font-size: 4vh;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: baseline;
}}
.combatant-team {{
    flex-direction: column;
}}
.combatant-info {{
    flex-direction: row;
}}
.combatant-sponsor, .combatant-tag, .combatant-pronouns {{
    text-align: center;
}}
.combatant-sponsor, .combatant-pronouns {{
    font-size: 60%;
    color: LightGray;
}}
.combatant-score {{
    padding-left: 1vh;
    text-align: right;
    flex: 1;
    align-self: center;
}}
.bracket {{
    font-size: 3vh;
    display: flex;
    flex-direction: column;
    align-self: stretch;
}}
.bracket-info {{
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: baseline;
}}
.bracket-data {{
    text-align: center;
}}
"""


@dataclasses.dataclass
class SplitScoreboard(ScoreboardBase):
    logo: Path = dataclasses.field(default=DEFAULT_LOGO_PATH)
    logo_right: Path = dataclasses.field(default=DEFAULT_LOGO_PATH)

    @property
    def video_alignment(self):
        return "x=(ow-iw)/2:y=0"

    @property
    def html_header(self):
        return """
<!DOCTYPE html>
<html lang="en">
    <body>
"""

    @property
    def html_footer(self):
        return """
    </body>
</html>
"""

    @property
    def html_body_singles(self):
        return f"""
        <div class="stage">
            <section class="side left">
                <div class="info row1">
                    <div class="info-big">{self.slp.context.data.tournament_name}</div>
                </div>
                <div class="row2"><hr></div>
                <div class="info row3">
                    <div class="info-medium">{self.slp.context.data.tournament_date.strftime("%B %d, %Y").replace(" 0", " ")}</div>
                    <div class="info-medium">{self.slp.context.data.tournament_location}</div>
                </div>
                <div class="row4"><hr></div>
                <table class="row5">
                    <tr>
                        <td class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[0].prefixes[0]}</td>
                        <td class="combatant-score" rowspan="3">{self.slp.context.data.scores[self.slp.index].slots[0].score}</td>
                    </tr>
                    <tr>
                        <td class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[0].display_names[0]}</td>
                    </tr>
                    <tr>
                        <td class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[0].pronouns[0]}</td>
                    </tr>
                </table>
                <div class="row6"><hr></div>
                <img src="{self.logo}" class="row7">
            </section>

            <section class="side right">
                <div class="info row1">
                    <div class="info-medium">{self.slp.context.data.event_name}</div>
                    <div class="info-medium">{self.slp.context.data.phase_name}</div>
                </div>
                <div class="row2"><hr></div>
                <div class="info row3">
                    <div class="info-medium">{self.slp.context.data.round_name}</div>
                    <div class="info-medium">Best of {self.slp.context.data.best_of}</div>
                </div>
                <div class="row4"><hr></div>
                <table class="row5">
                    <tr>
                        <td class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[1].prefixes[0]}</td>
                        <td class="combatant-score" rowspan="3">{self.slp.context.data.scores[self.slp.index].slots[1].score}</td>
                    </tr>
                    <tr>
                        <td class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[1].display_names[0]}</td>
                    </tr>
                    <tr>
                        <td class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[1].pronouns[0]}</td>
                    </tr>
                </table>
                <div class="row6"><hr></div>
                <img src="{self.logo_right}" class="row7">
            </section>
        </div>
"""

    @property
    def html_body_doubles(self):
        return f"""
        <div class="stage">
            <section class="side left">
                <div class="info row1">
                    <div class="info-big">{self.slp.context.data.tournament_name}</div>
                </div>
                <div class="row2"><hr></div>
                <div class="info row3">
                    <div class="info-medium">{self.slp.context.data.tournament_date.strftime("%B %d, %Y").replace(" 0", " ")}</div>
                    <div class="info-medium">{self.slp.context.data.tournament_location}</div>
                </div>
                <div class="row4"><hr></div>
                <table class="row5">
                    <tr>
                        <td class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[0].prefixes[0]}</td>
                        <td class="combatant-score" rowspan="6">{self.slp.context.data.scores[self.slp.index].slots[0].score}</td>
                    </tr>
                    <tr>
                        <td class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[0].display_names[0]}</td>
                    </tr>
                    <tr>
                        <td class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[0].pronouns[0]}</td>
                    </tr>
                    <tr>
                        <td class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[0].prefixes[1]}</td>
                    </tr>
                    <tr>
                        <td class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[0].display_names[1]}</td>
                    </tr>
                    <tr>
                        <td class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[0].pronouns[1]}</td>
                </table>
                <div class="row6"><hr></div>
                <img src="{self.logo}" class="row7">
            </section>

            <section class="side right">
                <div class="info row1">
                    <div class="info-medium">{self.slp.context.data.event_name}</div>
                    <div class="info-medium">{self.slp.context.data.phase_name}</div>
                </div>
                <div class="row2"><hr></div>
                <div class="info row3">
                    <div class="info-medium">{self.slp.context.data.round_name}</div>
                    <div class="info-medium">Best of {self.slp.context.data.best_of}</div>
                </div>
                <div class="row4"><hr></div>
                <table class="row5">
                    <tr>
                        <td class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[1].prefixes[0]}</td>
                        <td class="combatant-score" rowspan="6">{self.slp.context.data.scores[self.slp.index].slots[1].score}</td>
                    </tr>
                    <tr>
                        <td class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[1].display_names[0]}</td>
                    </tr>
                    <tr>
                        <td class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[1].pronouns[0]}</td>
                    </tr>
                    <tr>
                        <td class="combatant-sponsor">{self.slp.context.data.scores[self.slp.index].slots[1].prefixes[1]}</td>
                    </tr>
                    <tr>
                        <td class="combatant-tag">{self.slp.context.data.scores[self.slp.index].slots[1].display_names[1]}</td>
                    </tr>
                    <tr>
                        <td class="combatant-pronouns">{self.slp.context.data.scores[self.slp.index].slots[1].pronouns[1]}</td>
                    </tr>
                </table>
                <div class="row6"><hr></div>
                <img src="{self.logo_right}" class="row7">
            </section>
        </div>
"""

    @property
    def css(self):
        return f"""
* {{
    box-sizing: border-box;
}}

html, body {{
    height: 100%;
    margin: 0;
    padding: 0.5vh;
    color: white;
    font-family: "Inconsolata", "Consolas", monospace;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}}

td {{
    padding: 0;
    vertical-align: middle;
}}

img {{
    width: 80%;
    height: auto;
    justify-self: center;
    align-self: end;
}}

.stage {{
    width: 100%;
    height: 100%;
    display: grid;
    grid-template-columns: calc({303 / 1080 * self.size[1] - 2}px - 1vh) calc({303 / 1080 * self.size[1] - 2}px - 1vh);
    grid-template-rows: auto auto auto auto auto auto auto;
    justify-content: space-between;
}}

.side {{
    display: contents;
}}

.left > * {{
    grid-column: 1;
}}
.right > * {{
    grid-column: 2;
}}
.side > * {{
    align-self: center;
}}

.info {{
    width: 100%;
    text-align: center;
}}

.row1 {{
    grid-row: 1;
}}
.row2 {{
    grid-row: 2;
}}
.row3 {{
    grid-row: 3;
}}
.row4 {{
    grid-row: 4;
}}
.row5 {{
    grid-row: 5;
}}
.row6 {{
    grid-row: 6;
}}
.row7 {{
    grid-row: 7;
}}

.info-big {{
    font-size: 6vh;
}}

.info-medium {{
    font-size: 3vh;
}}

.combatant-sponsor,
.combatant-score,
.combatant-tag,
.combatant-pronouns {{
    font-size: 3vh;
}}
.combatant-score {{
    width: 2em;
}}
.combatant-sponsor,
.combatant-pronouns {{
    color: lightgray;
}}

.left table {{
    direction: ltr;
}}
.left .combatant-sponsor,
.left .combatant-tag,
.left .combatant-pronouns,
.left .combatant-score {{
    text-align: right;
}}

.right table {{
    direction: rtl;
}}
.right .combatant-sponsor,
.right .combatant-tag,
.right .combatant-pronouns,
.right .combatant-score {{
    text-align: left;
}}
"""


# TODO: some scoreboards should enforce widescreen expectations
