# Handles configuration options

import dataclasses
import importlib.resources
import shutil
import tomllib
import typing
from enum import Enum
from pathlib import Path
from types import UnionType

import slp2mp4
from slp2mp4 import log, util

DEFAULT_CONFIG_PATH = importlib.resources.files(slp2mp4).joinpath("defaults.toml")
USER_CONFIG_PATH = Path("~/.slp2mp4.toml").expanduser()


# From https://github.com/project-slippi/Ishiiruka/tree/slippi/Source/Core/VideoBackends
class DolphinBackend(Enum):
    D3D12 = "D3D12"
    DX11 = "DX11"
    DX9 = "DX9"
    OGL = "OGL"
    SOFTWARE = "Software Renderer"
    VULKAN = "Vulkan"


# https://github.com/project-slippi/Ishiiruka/blob/3e5b185ae080e8dca5e939369572d94d20049fea/Source/Core/VideoCommon/VideoConfig.h#L40
# https://github.com/project-slippi/Ishiiruka/blob/3e5b185ae080e8dca5e939369572d94d20049fea/Source/Core/DolphinWX/VideoConfigDiag.cpp#L450
class DolphinResolution(Enum):
    P480 = ("480p", "2")
    P720 = ("720p", "3")
    P1080 = ("1080p", "5")
    P1440 = ("1440p", "6")
    P2160 = ("2160p", "8")

    @classmethod
    def from_display_name(cls, name: str):
        for resolution in cls:
            if resolution.display_name == name:
                return resolution
        raise ValueError(f"Unknown resolution '{name}'")

    @property
    def display_name(self):
        return self.value[0]

    @property
    def dolphin_value(self):
        return self.value[1]


class CombineMode(Enum):
    NONE = "None"
    ALL = "All"
    BY_INPUT = "By Input"
    BY_PHASE = "By Phase"


@dataclasses.dataclass
class PathsConfig:
    # Paths are un-altered so saving works properly
    ffmpeg: Path
    slippi_playback: Path
    ssbm_iso: Path
    ffprobe: Path | None = dataclasses.field(default=None)

    @classmethod
    def from_dict(cls, data):
        return cls(
            ffmpeg=Path(data["ffmpeg"]),
            slippi_playback=Path(data["slippi_playback"]),
            ssbm_iso=Path(data["ssbm_iso"]),
            ffprobe=data.get("ffprobe"),
        )

    def __post_init__(self):
        if self.ffprobe is not None:
            self.ffprobe = Path(self.ffprobe)

    def validate(self):
        assert shutil.which(self.ffmpeg) is not None
        assert self.slippi_playback.expanduser().is_file()
        assert self.ssbm_iso.expanduser().is_file()

    def get_ffprobe(self):
        if self.ffprobe is not None:
            return self.ffprobe
        # Assume it's relative to ffmpeg
        suffix = self.ffmpeg.suffix
        ffprobe = self.ffmpeg.parent / f"ffprobe{suffix}"
        if ffprobe.is_file():
            return ffprobe
        # Try to find in path
        ffprobe = shutil.which("ffprobe")
        if ffprobe is not None:
            return Path(ffprobe)
        raise RuntimeError("Could not find ffprobe.")


@dataclasses.dataclass
class DolphinConfig:
    backend: DolphinBackend
    resolution: DolphinResolution
    msaa: int
    ssaa: bool
    bitrate: int
    gecko_codes: dict[str, bool]
    custom_gecko_codes: str = dataclasses.field(
        metadata={
            "help": "Custom gecko codes; all are enabled. Cannot contain '='",
            "multiline": True,
        },
    )

    @classmethod
    def from_dict(cls, data):
        return cls(
            backend=DolphinBackend(data["backend"]),
            resolution=DolphinResolution.from_display_name(data["resolution"]),
            msaa=data["msaa"],
            ssaa=data["ssaa"],
            bitrate=data["bitrate"],
            gecko_codes=data["gecko_codes"],
            custom_gecko_codes=data["custom_gecko_codes"],
        )

    def validate(self):
        pass


@dataclasses.dataclass
class FfmpegConfig:
    audio_args: str
    volume: int

    @classmethod
    def from_dict(cls, data):
        return cls(audio_args=data["audio_args"], volume=data["volume"])

    def validate(self):
        if not (0 <= self.volume <= 100):
            raise RuntimeError(f"Invalid ffmpeg volume value '{self.volume}'")


@dataclasses.dataclass
class RuntimeConfig:
    parallel: int = dataclasses.field(
        metadata={"help": "Max # of slippi instances; 0 = # of logical CPU cores"}
    )
    preserve_directory_structure: bool = dataclasses.field(
        metadata={"help": "Recreate input directory structure instead of being 'flat'"}
    )
    youtubify_names: bool = dataclasses.field(
        metadata={"help": "Enable name replacements"}
    )
    name_replacements: dict[str, str] = dataclasses.field(
        metadata={"help": "Mapping of characters to replace in video titles"}
    )
    combine_mode: CombineMode = dataclasses.field(
        metadata={"help": "How to combine set videos; None = separate sets"}
    )
    use_context_json_for_naming: bool = dataclasses.field(
        metadata={"help": "Use context.json files (if found) when naming videos"}
    )

    @classmethod
    def from_dict(cls, data):
        return cls(
            parallel=data["parallel"],
            preserve_directory_structure=data["preserve_directory_structure"],
            youtubify_names=data["youtubify_names"],
            name_replacements=data["name_replacements"],
            combine_mode=CombineMode(data["combine_mode"]),
            use_context_json_for_naming=data["use_context_json_for_naming"],
        )

    def validate(self):
        if self.parallel < 0:
            raise RuntimeError(f"Invalid runtime parallel value '{self.parallel}'")


@dataclasses.dataclass
class Config:
    paths: PathsConfig
    dolphin: DolphinConfig
    ffmpeg: FfmpegConfig
    runtime: RuntimeConfig

    @classmethod
    def from_dict(cls, data):
        return cls(
            paths=PathsConfig.from_dict(data["paths"]),
            dolphin=DolphinConfig.from_dict(data["dolphin"]),
            ffmpeg=FfmpegConfig.from_dict(data["ffmpeg"]),
            runtime=RuntimeConfig.from_dict(data["runtime"]),
        )

    def to_dict(self):
        data = dataclasses.asdict(self)
        data["dolphin"]["backend"] = data["dolphin"]["backend"].value
        data["dolphin"]["resolution"] = data["dolphin"]["resolution"].display_name
        for k, v in data["paths"].items():
            data["paths"][k] = str(v) if (v is not None) else None
        return data

    def validate(self):
        for field in dataclasses.fields(self):
            attr = getattr(self, field.name)
            attr.validate()


@dataclasses.dataclass
class RuntimeOptions:
    dry_run: bool = dataclasses.field(
        default=False,
        metadata={
            "short": "n",
            "help": "Don't actually render videos; useful for testing",
        },
    )
    monitor: bool = dataclasses.field(
        default=False,
        metadata={"short": "m", "help": "Continuously watch input directories"},
    )
    temporary_directory: Path | None = dataclasses.field(
        default=None,
        metadata={
            "short": "t",
            "help": "Where to write temp videos; leave blank for system default",
        },
    )
    output_directory: Path = dataclasses.field(
        default=Path("."),
        metadata={
            "short": "o",
            "help": "Where to write output videos",
            "is_directory": True,
        },
    )
    debug: bool = dataclasses.field(default=False)


def _load_configs(config_files: list[Path]) -> Config:
    conf = {}
    logger = log.get_logger()
    for file in config_files:
        try:
            with open(file, "rb") as f:
                data = tomllib.load(f)
                util.update_dict(conf, data)
        except FileNotFoundError:
            logger.info(f"Could not find config file '{file}' - skipping")
        except tomllib.TOMLDecodeError:
            logger.error(f"Invalid toml in file '{file}' - skipping")
    return Config.from_dict(conf)


def get_default_config():
    return _load_configs([DEFAULT_CONFIG_PATH])


def get_config(config_files: list[Path] | None = None):
    if config_files is None:
        config_files = [DEFAULT_CONFIG_PATH, USER_CONFIG_PATH]
    return _load_configs(config_files)


def is_optional_type(field_type):
    t = typing.get_origin(field_type)
    return t in [typing.Union, UnionType]


def get_optional_type(field_type):
    # Assumes Unions are [X, None]
    args = typing.get_args(field_type)
    return next(filter(lambda x: x is not None, args))
