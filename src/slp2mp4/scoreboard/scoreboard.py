import contextlib
import dataclasses
import json
import pathlib
import shutil
import tempfile
import typing

from slp2mp4 import ffmpeg

from PIL import Image


@dataclasses.dataclass
class ScoreboardPanel:
    aspect_ratio: float
    name: str = dataclasses.field(init=False, default=None)
    image: Image = dataclasses.field(init=False, default=None)

    def get_width(self, height):
        return int(self.aspect_ratio * height)

    def draw(self, height, name, context_data, game_index):
        raise NotImplementedError("draw must be overridden by child")

    def save(self):
        self.image.save(self.name)


# TODO: Pass conf to constructor to allow customization
@dataclasses.dataclass
class Scoreboard:
    context_json_path: pathlib.Path
    game_index: int
    height: int

    def _get_context_data(self):
        with open(self.context_json_path) as json_data:
            return json.load(json_data)

    def _get_scale_args(self):
        return (f"[1]scale=width=-2:height={self.height}[scaled]",)

    def _get_scoreboard_panels(self):
        raise NotImplementedError("_get_scoreboard_panels must be overridden by child")

    def _get_scoreboard_args(self):
        raise NotImplementedError("_get_scoreboard_args must be overridden by child")

    @contextlib.contextmanager
    def get_args(self):
        context_data = self._get_context_data()
        try:
            panels = self._get_scoreboard_panels()
            with _scoreboard_panel_context_manager(panels) as png_paths:
                for panel, png_path in zip(panels, png_paths):
                    panel.draw(png_path, self.height, context_data, self.game_index)
                    panel.save()
                    shutil.copyfile(png_path, f"scoreboard_{self.game_index}.png")
                scale_args = self._get_scale_args()
                scoreboard_args = self._get_scoreboard_args()
                # Don't re-scale if not doing filtering
                if scoreboard_args:
                    filter_args = (
                        "-filter_complex",
                        (",").join(scale_args + scoreboard_args),
                    )
                else:
                    filter_args = ()
                yield png_paths, filter_args
        finally:
            pass


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
        yield png_paths
    finally:
        for tmpfile in png_paths:
            tmpfile.unlink()


def _get_name(name, prefixes, pronouns, ports, is_singles=True):
    if is_singles:
        if prefixes:
            name = f"{prefixes} | {name}"
        if pronouns:
            name = f"{name} ({pronouns})"
    else:
        name = f"{name} (P{ports})"
    return name


def get_name_and_score_from_slot_data(slot_data):
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
    return f"{('/').join(names)}: {slot_data['score']}"


def get_wrapped_text(width, draw, text, font):
    words = text.split()
    lines = []
    current_line = words[0]
    xy = (0, 0)
    for word in words[1:]:
        new_text = f"{current_line} {word}"
        _, _, text_width, _ = draw.textbbox(xy, new_text, font=font)
        if text_width > width:
            lines.append(current_line)
            current_line = word
        else:
            current_line = new_text
    lines.append(current_line)
    text = ("\n").join(lines)
    bbox = draw.multiline_textbbox(xy, text, font=font)
    return text, bbox


def draw_multiline_text(y, padding, width, draw, text, align="center", anchor="top", **kwargs):
    max_width = width - 2 * padding
    text, bbox = get_wrapped_text(max_width, draw, text, kwargs["font"])
    _, _, text_width, text_height = bbox
    if align == "center":
        x = (width - text_width) // 2
    elif align == "left":
        x = padding
    elif align == "right":
        x = width - text_width - padding
    if anchor == "bottom":
        y = y - text_height
    pos = (x, y)
    draw.multiline_text(pos, text, align=align, **kwargs)
    return draw.multiline_textbbox(pos, text, font=kwargs["font"])


# TODO: Widescreen scoreboard
