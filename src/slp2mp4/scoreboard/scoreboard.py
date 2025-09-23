import contextlib
import dataclasses
import html
import json
import pathlib
import tempfile
import typing

from slp2mp4 import util
from slp2mp4.context_helper import GameContextInfo

from html2image import Html2Image


@dataclasses.dataclass
class ScoreboardPanel:
    html_str: str
    css_str: str
    aspect_ratio: float

    def _get_width(self, height):
        return int(self.aspect_ratio * height)

    def render(self, png_path, height):
        width = self._get_width(height)
        hti = Html2Image(
            size=(width, height),
            output_path=png_path.parent,
        )
        hti.screenshot(
            html_str=self.html_str,
            css_str=self.css_str,
            save_as=png_path.name,
        )


@dataclasses.dataclass
class Scoreboard:
    game_context: GameContextInfo
    conf: dict
    height: int

    def _get_scoreboard_panels(self, num_teams: int) -> list[ScoreboardPanel]:
        raise NotImplementedError("_get_scoreboard_panels must be overridden by child")

    def _get_scoreboard_args(self):
        raise NotImplementedError("_get_scoreboard_args must be overridden by child")

    def _get_scale_args(self):
        return (f"[0]scale=width=-2:height={self.height}[scaled]",)

    def _update_panel_html(self, panel):
        mapping = self.game_context.get_mapping()
        for k, v in mapping.items():
            mapping[k] = html.escape(str(v))
        panel.html_str = panel.html_str.format_map(mapping)

    def _render_html(self, panels, png_paths):
        for png_path, panel in zip(png_paths, panels):
            self._update_panel_html(panel)
            panel.render(png_path, self.height)

    @contextlib.contextmanager
    def get_args(self):
        panels = self._get_scoreboard_panels(self.game_context.num_teams)
        try:
            with _scoreboard_panel_context_manager(panels) as png_paths:
                self._render_html(panels, png_paths)
                scale_args = self._get_scale_args()
                scoreboard_args = self._get_scoreboard_args()
                # Don't re-scale if not doing filtering
                if scoreboard_args:
                    filter_args = scale_args + scoreboard_args
                else:
                    filter_args = ()
                yield png_paths, filter_args
        finally:
            pass


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
