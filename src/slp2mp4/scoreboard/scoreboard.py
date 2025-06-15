import contextlib
import dataclasses
import json
import pathlib
import tempfile
import typing

from slp2mp4 import ffmpeg

from html2image import Html2Image


@dataclasses.dataclass
class ScoreboardPanel:
    html_str: str
    css_str: str
    aspect_ratio: float
    png_path: typing.BinaryIO = dataclasses.field(init=False)

    def render(self, height):
        width = self.aspect_ratio * height
        hti = Html2Image(
            size=(int(width), int(height)),
            output_path=self.png_path.parent,
        )
        hti.screenshot(
            html_str=self.html_str,
            css_str=self.css_str,
            save_as=self.png_path.name,
        )
        return self.png_path.name


# TODO: Pass conf to constructor to allow customization
@dataclasses.dataclass
class Scoreboard:
    context_json_path: pathlib.Path
    game_index: int
    height: int

    def _get_context_data(self):
        with open(self.context_json_path) as json_data:
            return json.load(json_data)

    def _get_scoreboard_panels(self) -> list[ScoreboardPanel]:
        raise NotImplementedError("_get_scoreboard_panels must be overridden by child")

    # In the ffmpeg command (ffmpeg.py:merge_audio_and_video()), input 0 =
    # the audio, input 1 = the video. Remaining inputs are scoreboard images.
    def _get_scoreboard_args(self):
        raise NotImplementedError("_get_scoreboard_args must be overridden by child")

    def _get_scale_args(self):
        return (f"[1]scale=width=-2:height={self.height}[scaled]",)

    def _update_html(self, panels, context_data):
        for panel in panels:
            # TODO: Support challonge
            html = panel.html_str
            names = [
                _get_name_from_slot_data(slot_data)
                for slot_data in context_data["scores"][self.game_index]["slots"]
            ]
            scores = [
                str(slot_data["score"])
                for slot_data in context_data["scores"][self.game_index]["slots"]
            ]
            html = html.replace(
                "{TOURNAMENT_NAME}", context_data["startgg"]["tournament"]["name"]
            )
            html = html.replace(
                "{BRACKET_ROUND}", context_data["startgg"]["set"]["fullRoundText"]
            )
            html = html.replace("{BRACKET_SCORING}", f"Bo{context_data['bestOf']}")
            html = html.replace("{COMBATANT_1_NAME}", names[0])
            html = html.replace("{COMBATANT_2_NAME}", names[1])
            html = html.replace("{COMBATANT_1_SCORE}", scores[0])
            html = html.replace("{COMBATANT_2_SCORE}", scores[1])
            panel.html_str = html

    def _render_html(self, panels):
        for panel in panels:
            panel.render(self.height)

    @contextlib.contextmanager
    def get_args(self):
        panels = self._get_scoreboard_panels()
        context_data = self._get_context_data()
        self._update_html(panels, context_data)
        try:
            with _scoreboard_panel_context_manager(panels) as png_files:
                self._render_html(panels)
                scale_args = self._get_scale_args()
                scoreboard_args = self._get_scoreboard_args()
                # Don't re-scale if not doing filtering
                if scoreboard_args:
                    filter_args = (
                        "-filter_complex",
                        (";").join(scale_args + scoreboard_args),
                    )
                else:
                    filter_args = ()
                yield png_files, filter_args
        finally:
            pass


def _get_name(name, prefixes, pronouns, ports, is_singles=True):
    if is_singles:
        if prefixes:
            name = f"{prefixes} | {name}"
        if pronouns:
            name = f"{name} ({pronouns})"
    else:
        name = f"{name} (P{ports})"
    return name


def _get_name_from_slot_data(slot_data):
    is_singles = len(slot_data["displayNames"]) == 1
    names = [
        _get_name(name, prefixes, pronouns, ports, is_singles)
        for name, prefixes, pronouns, ports in zip(
            slot_data["displayNames"],
            slot_data["prefixes"],
            slot_data["pronouns"],
            slot_data["ports"],
        )
    ]
    return ("/").join(names)


@contextlib.contextmanager
def _scoreboard_panel_context_manager(panels: list[ScoreboardPanel]):
    png_temps = [
        tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        for _ in panels
    ]
    png_paths = []
    for png_temp in png_temps:
        png_paths.append(pathlib.Path(png_temp.name))
        png_temp.close()
    try:
        for panel, png_path in zip(panels, png_paths):
            panel.png_path = png_path
        yield png_paths
    finally:
        for tmpfile in png_paths:
            tmpfile.unlink()


# TODO: Widescreen scoreboard
