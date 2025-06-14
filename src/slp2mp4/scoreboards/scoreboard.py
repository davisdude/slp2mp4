import contextlib
import dataclasses
import io
import json
import os
import pathlib
import tempfile

from slp2mp4 import ffmpeg


# Assumes this will be doing pillar-boxing
def _get_pad_args(aspect_ratio="16/9", align="right", color="black"):
    if align == "left":
        x = "0"
    elif align == "right":
        x = "(out_w-in_w-1)"
    elif aign == "center":
        x = "(out_w-in_w)/2"
    return (f"pad=aspect={aspect_ratio}:x={x}:color={color}",)


def _get_scale_args(height):
    return (f"scale=width=-2:height={height}",)


def _remove_invalid_utf8(line):
    return bytes(line, "utf-8").decode("utf-8", "ignore")


@dataclasses.dataclass
class DrawtextContainer:
    lines: list[str] = dataclasses.field(default_factory=list)
    textfile: io.TextIOBase = dataclasses.field(init=False)  # Set externally

    def write_lines(self):
        validated_lines = [_remove_invalid_utf8(line) for line in self.lines]
        self.textfile.write(("\n").join(validated_lines))
        self.textfile.flush()

    # Assumes text will not overlap
    def get_args(self, x, y, fontcolor="white", fontsize="trunc(main_h/32)"):
        settings = [
            f"textfile={self.textfile.name.replace(':', '\\:').replace(os.sep, '/')}",
            "font=Mono",  # Makes wrapping easier / prettier
            f"fontcolor={fontcolor}",
            f"fontsize={fontsize}",
            f"x={x}",
            f"y={y}",
        ]
        return f"drawtext={(':').join(settings)}"


@contextlib.contextmanager
def drawtext_manager(drawtexts: list[DrawtextContainer]):
    tempfiles = [tempfile.NamedTemporaryFile(mode="w", delete=False) for _ in drawtexts]
    for drawtext, tmp in zip(drawtexts, tempfiles):
        drawtext.textfile = tmp
        drawtext.write_lines()
    try:
        yield drawtexts
    finally:
        for tmpfile in tempfiles:
            tmpfile.close()
            pathlib.Path(tmpfile.name).unlink()


@dataclasses.dataclass
class Scoreboard:
    context_json_path: pathlib.Path
    game_index: int
    height: int
    pad_args: dict = dataclasses.field(default_factory=dict)
    drawtext_args: list[dict] = dataclasses.field(default_factory=list)
    context_data: dict = dataclasses.field(init=False)

    def __post_init__(self):
        with open(self.context_json_path) as json_data:
            self.context_data = json.load(json_data)

    def make_drawtexts(self) -> list[DrawtextContainer]:
        raise NotImplementedError

    @contextlib.contextmanager
    def get_args(self):
        try:
            drawtexts = self.make_drawtexts()
            scale_args = _get_scale_args(self.height)
            pad_args = _get_pad_args(**self.pad_args)
            with drawtext_manager(drawtexts) as drawtexts:
                drawtext_args = tuple(
                    drawtext.get_args(**args)
                    for drawtext, args in zip(drawtexts, self.drawtext_args)
                )
                vf_args = (",").join(scale_args + pad_args + drawtext_args)
                yield ("-vf", vf_args)
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


def get_name_from_slot_data(slot_data):
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
    name_str = ("/").join(names)
    return f"{name_str}: {slot_data['score']}"


# TODO: Widescreen scoreboard
