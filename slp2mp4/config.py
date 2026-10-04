# Handles configuration options

import dataclasses
import importlib.resources
import shlex
import shutil
import tomllib
import typing
from datetime import datetime
from enum import Enum
from functools import cached_property
from pathlib import Path
from types import UnionType
from zoneinfo import ZoneInfo, available_timezones

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


class ScoreboardType(Enum):
    NONE = "None"
    SHARED = "Shared"
    SPLIT = "Split"
    MINIMAL = "Minimal"
    CUSTOM = "Custom"


class _ZoneInfo(Enum):
    @cached_property
    def tzinfo(self):
        if self.value == "local":
            return datetime.now().astimezone().tzinfo
        return ZoneInfo(self.value)

    def __str__(self):
        return self.value


_values = {name: name for name in ["local"] + sorted(available_timezones())}
TzEnum = Enum("TzEnum", _values, type=_ZoneInfo)


def _check_file(path: Path):
    p = path.expanduser().resolve()
    return p.is_file() and p.exists()


@dataclasses.dataclass
class PathsConfig:
    # Paths are un-altered so saving works properly
    ffmpeg: Path
    slippi_playback: Path
    ssbm_iso: Path
    ffprobe: Path | None = dataclasses.field(default=None)
    chrome: Path | None = dataclasses.field(default=None)
    # TODO: Make this just `browser` if html2image accepts that

    @cached_property
    def ffmpeg_path(self):
        return Path(shutil.which(self.ffmpeg))

    @cached_property
    def ffprobe_path(self):
        if self.ffprobe is not None:
            return self.ffprobe
        # Assume it's relative to ffmpeg
        suffix = self.ffmpeg.suffix
        ffprobe = self.ffmpeg_path.parent / f"ffprobe{suffix}"
        if _check_file(ffprobe):
            return ffprobe
        # Try to find in path
        ffprobe = shutil.which("ffprobe")
        if ffprobe is not None:
            return Path(ffprobe)
        raise RuntimeError("Could not find ffprobe.")

    @classmethod
    def from_dict(cls, data):
        return cls(
            ffmpeg=Path(data["ffmpeg"]),
            slippi_playback=Path(data["slippi_playback"]),
            ssbm_iso=Path(data["ssbm_iso"]),
            ffprobe=data.get("ffprobe"),
            chrome=data.get("chrome"),
        )

    def __post_init__(self):
        if self.ffprobe is not None:
            self.ffprobe = Path(self.ffprobe)
        if self.chrome is not None:
            self.chrome = Path(self.chrome)

    def validate(self):
        assert _check_file(self.ffmpeg_path)
        assert _check_file(self.slippi_playback)
        assert _check_file(self.ssbm_iso)
        assert _check_file(self.ffprobe_path)
        assert (self.chrome is None) or _check_file(self.chrome)


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
            custom_gecko_codes=data["custom_gecko_codes"].strip(),
        )

    def validate(self):
        pass


@dataclasses.dataclass
class FfmpegConfig:
    audio_args: str
    volume: int

    @cached_property
    def split_audio_args(self):
        return shlex.split(self.audio_args)

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
    use_context_json: bool = dataclasses.field(
        metadata={
            "help": "Use context.json files (if found) when naming / sorting videos"
        }
    )
    exclude_streamed_sets: bool = dataclasses.field(
        metadata={
            "help": "Exclude sets marked with stream metadata (requires context.json)"
        }
    )

    @classmethod
    def from_dict(cls, data):
        return cls(
            parallel=data["parallel"],
            preserve_directory_structure=data["preserve_directory_structure"],
            youtubify_names=data["youtubify_names"],
            name_replacements=data["name_replacements"],
            use_context_json=data["use_context_json"],
            exclude_streamed_sets=data["exclude_streamed_sets"],
        )

    def validate(self):
        if self.parallel < 0:
            raise RuntimeError(f"Invalid runtime parallel value '{self.parallel}'")


@dataclasses.dataclass(kw_only=True)
class BasicScoreboardConfig:
    logo: Path | None = dataclasses.field(default=None)

    @classmethod
    def from_dict(cls, data):
        return cls(logo=data.get("logo"))

    def __post_init__(self):
        if self.logo is not None:
            self.logo = Path(self.logo)

    def validate(self):
        assert (self.logo is None) or self.logo.exists()


@dataclasses.dataclass
class SharedScoreboardConfig(BasicScoreboardConfig):
    left: bool

    @classmethod
    def from_dict(cls, data):
        return cls(left=data["left"], logo=data.get("logo"))


@dataclasses.dataclass(kw_only=True)
class MinimalScoreboardConfig:
    @classmethod
    def from_dict(cls, _data):
        return cls()

    def validate(self):
        pass


@dataclasses.dataclass
class CustomScoreboardConfig:
    alignment: str
    ratio: float | None = dataclasses.field(default=None)
    html_path: Path | None = dataclasses.field(default=None)
    css_path: Path | None = dataclasses.field(default=None)

    @classmethod
    def from_dict(cls, data):
        return cls(
            alignment=data["alignment"],
            ratio=data.get("ratio"),
            html_path=data.get("html_path"),
            css_path=data.get("css_path"),
        )

    def __post_init__(self):
        if self.html_path is not None:
            self.html_path = Path(self.html_path)
        if self.css_path is not None:
            self.css_path = Path(self.css_path)

    def validate(self):
        print(self.html_path)
        assert self.html_path is not None
        assert self.html_path.expanduser().exists()
        assert self.css_path is not None
        assert self.css_path.expanduser().exists()


@dataclasses.dataclass
class ScoreboardUserData:
    font_spec: str
    primary_color: str
    secondary_color: str
    background_color: str

    @classmethod
    def from_dict(cls, data):
        return cls(
            font_spec=data["font_spec"],
            primary_color=data["primary_color"],
            secondary_color=data["secondary_color"],
            background_color=data["background_color"],
        )

    def validate(self):
        pass


@dataclasses.dataclass
class ScoreboardConfig:
    type: ScoreboardType
    timezone: TzEnum = dataclasses.field(
        metadata={
            "help_all": True,
            "help_all_metavar": "timezone; see --help-all",
            "help": "IANA timezone; Used for to get date for scoreboards; blank = local timezone",
        }
    )
    theme: ScoreboardUserData
    shared: SharedScoreboardConfig
    split: BasicScoreboardConfig  # TODO: checkbox option (remove boX text)
    minimal: MinimalScoreboardConfig
    custom: CustomScoreboardConfig
    # TODO: [L] indicator for GFs

    @classmethod
    def from_dict(cls, data):
        return cls(
            type=ScoreboardType(data["type"]),
            timezone=TzEnum(data["timezone"]),
            theme=ScoreboardUserData.from_dict(data["theme"]),
            shared=SharedScoreboardConfig.from_dict(data["shared"]),
            split=BasicScoreboardConfig.from_dict(data["split"]),
            minimal=MinimalScoreboardConfig.from_dict(data["minimal"]),
            custom=CustomScoreboardConfig.from_dict(data["custom"]),
        )

    @property
    def scoreboard(self):
        if self.type == ScoreboardType.SHARED:
            return self.shared
        elif self.type == ScoreboardType.SPLIT:
            return self.split
        elif self.type == ScoreboardType.MINIMAL:
            return self.minimal
        elif self.type == ScoreboardType.CUSTOM:
            return self.custom

    def validate(self):
        self.theme.validate()
        self.scoreboard.validate()


@dataclasses.dataclass
class Config:
    paths: PathsConfig
    dolphin: DolphinConfig
    ffmpeg: FfmpegConfig
    runtime: RuntimeConfig
    scoreboard: ScoreboardConfig

    @classmethod
    def from_dict(cls, data):
        return cls(
            paths=PathsConfig.from_dict(data["paths"]),
            dolphin=DolphinConfig.from_dict(data["dolphin"]),
            ffmpeg=FfmpegConfig.from_dict(data["ffmpeg"]),
            runtime=RuntimeConfig.from_dict(data["runtime"]),
            scoreboard=ScoreboardConfig.from_dict(data["scoreboard"]),
        )

    def to_dict(self):
        data = dataclasses.asdict(self)
        data["dolphin"]["backend"] = data["dolphin"]["backend"].value
        data["dolphin"]["resolution"] = data["dolphin"]["resolution"].display_name
        data["scoreboard"]["type"] = data["scoreboard"]["type"].value
        data["scoreboard"]["timezone"] = data["scoreboard"]["timezone"].value
        self._convert_paths_to_strs(data)
        return data

    def validate(self):
        for field in dataclasses.fields(self):
            attr = getattr(self, field.name)
            attr.validate()

    def _convert_paths_to_strs(self, data: dict, obj=None):
        if obj is None:
            obj = self
        for field in dataclasses.fields(obj):
            if dataclasses.is_dataclass(field.type):
                self._convert_paths_to_strs(data[field.name], field.type)
            else:
                val = data[field.name]
                if field.type is Path:
                    data[field.name] = str(val)
                elif is_optional_type(field.type) and (
                    get_optional_type(field.type) is Path
                ):
                    data[field.name] = str(val) if (val is not None) else None


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
    debug: bool = dataclasses.field(
        default=False, metadata={"help": "Enables extra logging; saves temporary files"}
    )
    temporary_directory: Path | None = dataclasses.field(
        default=None,
        metadata={
            "short": "t",
            "help": "Where to write temp videos; leave blank for system default",
            "is_directory": True,
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
    combine_mode: CombineMode = dataclasses.field(
        default=CombineMode.NONE,
        metadata={"help": "How to combine set videos; None = separate sets"},
    )


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
    return (t in [typing.Union, UnionType]) and (
        type(None) in typing.get_args(field_type)
    )


def get_optional_type(field_type):
    # Assumes Unions are [X, None]
    args = typing.get_args(field_type)
    return next(filter(lambda x: x is not None, args))


# TODO: From dict + merge to unify CLI / GUI
