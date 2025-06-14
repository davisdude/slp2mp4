import contextlib
import dataclasses
import io
import json
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


def _remove_invalid_utf8(line):
    return bytes(line, "utf-8").decode("utf-8", "ignore")


# TODO: Support x, y, w, h, alignment, etc.
@dataclasses.dataclass
class DrawtextContainer:
    lines: list[str] = dataclasses.field(default_factory=list)
    textfile: io.TextIOBase = dataclasses.field(init=False)  # Set externally

    def write_lines(self):
        validated_lines = [_remove_invalid_utf8(line) for line in self.lines]
        self.textfile.write(("\n").join(validated_lines))
        self.textfile.flush()

    # Assumes text will not overlap
    def get_args(self, fontcolor="white", fontsize="trunc(main_h/32)"):
        settings = [
            f"textfile={self.textfile.name}",
            "font=Mono",  # Makes wrapping easier / prettier
            f"fontcolor={fontcolor}",
            f"fontsize={fontsize}",
            f"y=(main_h-text_h)/2",
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
    conf: dict
    gameplay_video_path: pathlib.Path
    context_json_path: pathlib.Path
    output_video_path: pathlib.Path
    game_index: int
    pad_args: dict = dataclasses.field(default_factory=dict)
    drawtext_args: dict = dataclasses.field(default_factory=dict)
    context_data: dict = dataclasses.field(init=False)
    Ffmpeg: ffmpeg.FfmpegRunner = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        self.Ffmpeg = ffmpeg.FfmpegRunner(self.conf)
        with open(self.context_json_path) as json_data:
            self.context_data = json.load(json_data)

    def make_drawtexts(self) -> list[DrawtextContainer]:
        raise NotImplementedError

    def render(self):
        drawtexts = self.make_drawtexts()
        pad_args = _get_pad_args(**self.pad_args)
        with drawtext_manager(drawtexts) as drawtexts:
            drawtext_args = tuple(
                drawtext.get_args(**self.drawtext_args) for drawtext in drawtexts
            )
            vf_args = (",").join(pad_args + drawtext_args)
            args = (
                ("-y",),
                (
                    "-i",
                    self.gameplay_video_path,
                ),
                (
                    "-vf",
                    vf_args,
                ),
                ("-xerror",),
                (self.output_video_path,),
            )
            self.Ffmpeg.run(args)


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
