import contextlib
import dataclasses
import html
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
    pad: tuple[int]

    def _get_width(self, height):
        return int(self.aspect_ratio * height)

    def get_crop_args(self, stream_id, height):
        width = self._get_width(height)
        return f"[{stream_id}]crop=w={width}:h={height}:x=0:y=0:exact=1[{stream_id}_cropped]"

    def render(self, png_path, height):
        width = self._get_width(height)
        hti = Html2Image(
            size=(width + self.pad[0], height + self.pad[1]),
            output_path=png_path.parent,
        )
        hti.screenshot(
            html_str=self.html_str,
            css_str=self.css_str,
            save_as=png_path.name,
        )


@dataclasses.dataclass
class Scoreboard:
    conf: dict
    context_json_path: pathlib.Path
    game_index: int
    height: int

    def _get_context_data(self):
        with open(self.context_json_path) as json_data:
            return json.load(json_data)

    def _get_scoreboard_panels(self, pad: tuple[int]) -> list[ScoreboardPanel]:
        raise NotImplementedError("_get_scoreboard_panels must be overridden by child")

    # In the ffmpeg command (ffmpeg.py:merge_audio_and_video()), input 0 =
    # the audio, input 1 = the video. Remaining inputs are scoreboard images.
    def _get_scoreboard_args(self):
        raise NotImplementedError("_get_scoreboard_args must be overridden by child")

    def _get_scale_args(self):
        return (f"[1]scale=width=-2:height={self.height}[scaled]",)

    def _update_html(self, panels, context_data):
        for panel in panels:
            if "startgg" in context_data:
                platform_specific_data = context_data["startgg"]
            elif "challonge" in context_data:
                platform_specific_data = context_data["challonge"]
            else:
                platform_specific_data = {
                    "tournament": {"name": "Unknown"},
                    "set": {"fullRoundText": "Unknown"},
                }
            names = [
                _get_name_from_slot_data(slot_data)
                for slot_data in context_data["scores"][self.game_index]["slots"]
            ]
            scores = [
                str(slot_data["score"])
                for slot_data in context_data["scores"][self.game_index]["slots"]
            ]
            panel.html_str = panel.html_str.replace(
                "{TOURNAMENT_NAME}", html.escape(platform_specific_data["tournament"]["name"])
            )
            panel.html_str = panel.html_str.replace(
                "{EVENT_NAME}", html.escape(platform_specific_data["event"]["name"])
            )
            panel.html_str = panel.html_str.replace(
                "{PHASE_NAME}", html.escape(platform_specific_data["phase"]["name"])
            )
            panel.html_str = panel.html_str.replace(
                "{BRACKET_ROUND}", html.escape(platform_specific_data["set"]["fullRoundText"])
            )
            panel.html_str = panel.html_str.replace("{BRACKET_SCORING}", f"Bo{context_data['bestOf']}")
            panel.html_str = panel.html_str.replace("{COMBATANT_1_NAME}", html.escape(names[0]))
            panel.html_str = panel.html_str.replace("{COMBATANT_2_NAME}", html.escape(names[1]))
            panel.html_str = panel.html_str.replace("{COMBATANT_1_SCORE}", scores[0])
            panel.html_str = panel.html_str.replace("{COMBATANT_2_SCORE}", scores[1])

    def _render_html(self, panels, png_paths):
        for png_path, panel in zip(png_paths, panels):
            panel.render(png_path, self.height)

    def _get_pad(self):
        return (self.conf["scoreboard"]["crop_x"], self.conf["scoreboard"]["crop_y"])

    def _get_crop_args(self, panels):
        return tuple(
            (
                panel.get_crop_args(stream_id, self.height)
                for stream_id, panel in enumerate(panels, start=2)
            )
        )

    @contextlib.contextmanager
    def get_args(self):
        pad = self._get_pad()
        panels = self._get_scoreboard_panels(pad)
        context_data = self._get_context_data()
        self._update_html(panels, context_data)
        try:
            with _scoreboard_panel_context_manager(panels) as png_paths:
                self._render_html(panels, png_paths)
                scale_args = self._get_scale_args()
                crop_args = self._get_crop_args(panels)
                scoreboard_args = self._get_scoreboard_args()
                # Don't re-scale if not doing filtering
                if scoreboard_args:
                    filter_args = scale_args + crop_args + scoreboard_args
                else:
                    filter_args = ()
                yield png_paths, filter_args
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
        tempfile.NamedTemporaryFile(suffix=".png", delete=False) for _ in panels
    ]
    png_paths = []
    for png_temp in png_temps:
        png_paths.append(pathlib.Path(png_temp.name))
        png_temp.close()
    try:
        yield png_paths
    finally:
        for tmpfile in png_paths:
            tmpfile.unlink()


# TODO: Widescreen scoreboard
