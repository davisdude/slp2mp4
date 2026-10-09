# Handles configuration options
# Each config group is a dataclass composed of types that serialize to/from TOML in a
# straightforward manner, esp from the GUI / CLI. More complex types / transformations
# are exposed via class properties.

import dataclasses
import importlib.resources
import shlex
import shutil
import tomllib
from datetime import datetime
from enum import Enum
from functools import cached_property
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

import psutil

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


@dataclasses.dataclass
class ConfigBase:
    @classmethod
    def from_dict(cls, data: dict):
        kwargs = {}
        for field in dataclasses.fields(cls):
            if dataclasses.is_dataclass(field.type):
                kwargs[field.name] = field.type.from_dict(data.get(field.name, {}))
            else:
                kwargs[field.name] = data.get(field.name)
        return cls(**kwargs)

    @classmethod
    def dict_from_namespace(cls, namespace, prefix=None):
        if prefix is None:
            prefix = ()
        data = {}
        for field in dataclasses.fields(cls):
            new_prefix = prefix + (field.name,)
            # Assumes argparse-like flat namespace
            name = ("_").join(new_prefix)
            if dataclasses.is_dataclass(field.type):
                nested = field.type.dict_from_namespace(namespace, new_prefix)
                if nested:
                    data[field.name] = nested
            else:
                if (value := getattr(namespace, name, None)) is not None:
                    data[field.name] = value
        return data

    def to_dict(self):
        data = {}
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if dataclasses.is_dataclass(field.type):
                data[field.name] = value.to_dict()
            else:
                data[field.name] = value
        return data

    def validate(self):
        for field in dataclasses.fields(self):
            if dataclasses.is_dataclass(field.type):
                getattr(self, field.name).validate()

    def override(self, data: dict):
        for field in dataclasses.fields(self):
            if dataclasses.is_dataclass(field.type):
                getattr(self, field.name).override(data.get(field.name, {}))
            else:
                value = data.get(field.name)
                if (value is not None) and (value is not dataclasses.MISSING):
                    setattr(self, field.name, value)


@dataclasses.dataclass
class PathsConfig(ConfigBase):
    # Paths are un-altered so saving works properly
    ffmpeg: str = dataclasses.field(metadata={"is_path": True})
    slippi_playback: str = dataclasses.field(metadata={"is_path": True})
    ssbm_iso: str = dataclasses.field(metadata={"is_path": True})
    ffprobe: str = dataclasses.field(metadata={"is_path": True})
    chrome: str = dataclasses.field(metadata={"is_path": True})
    # TODO: Make this just `browser` if html2image accepts that

    @cached_property
    def ffmpeg_path(self):
        path = shutil.which(self.ffmpeg)
        return Path(path) if path is not None else path

    @property
    def slippi_playback_path(self):
        return Path(self.slippi_playback)

    @property
    def ssbm_iso_path(self):
        return Path(self.ssbm_iso)

    @cached_property
    def ffprobe_path(self):
        if self.ffprobe != "":
            return Path(self.ffprobe)
        # Assume it's relative to ffmpeg
        suffix = self.ffmpeg_path.suffix
        ffprobe = self.ffmpeg_path.parent / f"ffprobe{suffix}"
        if util.check_file(ffprobe):
            return ffprobe
        # Try to find in path
        ffprobe = shutil.which("ffprobe")
        if ffprobe is not None:
            return Path(ffprobe)
        raise RuntimeError("Could not find ffprobe.")

    @property
    def chrome_path(self):
        if self.chrome != "":
            return Path(self.chrome)
        return None

    def validate(self):
        assert self.ffmpeg_path is not None
        assert util.check_file(self.ffmpeg_path)
        assert util.check_file(self.slippi_playback_path)
        assert util.check_file(self.ssbm_iso_path)
        assert self.ffprobe_path is not None
        assert util.check_file(self.ffprobe_path)
        assert (self.chrome_path is None) or util.check_file(self.chrome_path)


@dataclasses.dataclass
class DolphinConfig(ConfigBase):
    backend: str = dataclasses.field(
        metadata={"choices": util.get_enum_display_values(DolphinBackend)}
    )
    resolution: str = dataclasses.field(
        metadata={"choices": util.get_enum_display_values(DolphinResolution)}
    )
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

    @property
    def backend_enum(self):
        return DolphinBackend(self.backend)

    @property
    def resolution_enum(self):
        return DolphinResolution.from_display_name(self.resolution)


@dataclasses.dataclass
class FfmpegConfig(ConfigBase):
    audio_args: str
    volume: int = dataclasses.field(metadata={"min": 0, "max": 100})

    @cached_property
    def split_audio_args(self):
        return shlex.split(self.audio_args)

    def validate(self):
        if not (0 <= self.volume <= 100):
            raise RuntimeError(f"Invalid ffmpeg volume value '{self.volume}'")


@dataclasses.dataclass
class RuntimeConfig(ConfigBase):
    parallel: int = dataclasses.field(
        metadata={
            "help": "Max # of slippi instances; 0 = # of logical CPU cores",
            "min": 0,
        },
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

    @cached_property
    def parallel_procs(self):
        if self.parallel != 0:
            return self.parallel
        return psutil.cpu_count(logical=False) or 1

    def validate(self):
        assert self.parallel_procs > 0


@dataclasses.dataclass(kw_only=True)
class BasicScoreboardConfig(ConfigBase):
    @classmethod
    def get_properties(cls):
        return ()


@dataclasses.dataclass(kw_only=True)
class LogoScoreboardConfig(BasicScoreboardConfig):
    logo: str = dataclasses.field(metadata={"is_path": True})

    @classmethod
    def get_properties(cls):
        return super().get_properties() + ("logo",)

    @property
    def logo_path(self):
        if self.logo == "":
            return None
        return Path(self.logo)

    def validate(self):
        assert (self.logo_path is None) or util.check_file(self.logo_path)


@dataclasses.dataclass
class SharedScoreboardConfig(LogoScoreboardConfig):
    left: bool
    checkbox: bool

    @classmethod
    def get_properties(cls):
        return super().get_properties() + ("left", "checkbox")


@dataclasses.dataclass
class SplitScoreboardConfig(LogoScoreboardConfig):
    checkbox: bool

    @classmethod
    def get_properties(cls):
        return super().get_properties() + ("checkbox")


@dataclasses.dataclass(kw_only=True)
class MinimalScoreboardConfig(BasicScoreboardConfig):
    pass


@dataclasses.dataclass
class CustomScoreboardConfig(ConfigBase):
    alignment: str
    ratio: float = dataclasses.field(
        metadata={"help": "Output aspect ratio; 0 = pass-through"}
    )
    html: str = dataclasses.field(metadata={"is_path": True})
    css: str = dataclasses.field(metadata={"is_path": True})

    @property
    def html_path(self):
        return Path(self.html)

    @property
    def css_path(self):
        return Path(self.css)

    def validate(self):
        assert self.html_path is not None
        assert util.check_file(self.html_path)
        assert self.css_path is not None
        assert util.check_file(self.css_path)


@dataclasses.dataclass
class ScoreboardUserData(ConfigBase):
    font_spec: str
    primary_color: str
    secondary_color: str
    background_color: str


@dataclasses.dataclass
class ScoreboardConfig(ConfigBase):
    type: str
    timezone: str = dataclasses.field(
        metadata={
            "help_all": True,
            "help_all_metavar": "timezone; see --help-all",
            "help": "IANA timezone; Used for to get date for scoreboards; blank = local timezone",
            "choices": util.get_enum_display_values(TzEnum),
        }
    )
    theme: ScoreboardUserData
    shared: SharedScoreboardConfig
    split: SplitScoreboardConfig
    minimal: MinimalScoreboardConfig
    custom: CustomScoreboardConfig
    # TODO: [L] indicator for GFs

    @property
    def type_enum(self):
        return ScoreboardType(self.type)

    @property
    def timezone_enum(self):
        return TzEnum(self.timezone)

    @property
    def scoreboard(self):
        if self.type_enum == ScoreboardType.SHARED:
            return self.shared
        elif self.type_enum == ScoreboardType.SPLIT:
            return self.split
        elif self.type_enum == ScoreboardType.MINIMAL:
            return self.minimal
        elif self.type_enum == ScoreboardType.CUSTOM:
            return self.custom

    def validate(self):
        self.theme.validate()
        self.scoreboard.validate()


@dataclasses.dataclass
class Config(ConfigBase):
    paths: PathsConfig
    dolphin: DolphinConfig
    ffmpeg: FfmpegConfig
    runtime: RuntimeConfig
    scoreboard: ScoreboardConfig


@dataclasses.dataclass
class RuntimeOptions(ConfigBase):
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
    temporary_directory: str = dataclasses.field(
        default="",
        metadata={
            "short": "t",
            "help": "Where to write temp videos; leave blank for system default",
            "is_directory": True,
        },
    )
    output_directory: str = dataclasses.field(
        default=".",
        metadata={
            "short": "o",
            "help": "Where to write output videos",
            "is_directory": True,
        },
    )
    combine_mode: str = dataclasses.field(
        default="None",
        metadata={
            "help": "How to combine set videos; None = separate sets",
            "choices": util.get_enum_display_values(CombineMode),
        },
    )

    @property
    def temporary_directory_path(self):
        if self.temporary_directory == "":
            return None
        return Path(self.temporary_directory)

    @property
    def output_directory_path(self):
        return Path(self.output_directory)

    @property
    def combine_mode_enum(self):
        return CombineMode(self.combine_mode)


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
