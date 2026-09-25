import dataclasses
import json
from enum import Enum
from pathlib import Path


# https://github.com/jmlee337/replay-manager-for-slippi/blob/46fcbcd9aa5ae51702cdab45f75e343a27e56f9c/src/common/constants.ts#L7
class Character(Enum):
    FALCON = "Falcon"
    DK = "DK"
    FOX = "Fox"
    GW = "GW"
    KIRBY = "Kirby"
    BOWSER = "Bowser"
    LINK = "Link"
    LUIGI = "Luigi"
    MARIO = "Mario"
    MARTH = "Marth"
    MEWTWO = "Mewtwo"
    NESS = "Ness"
    PEACH = "Peach"
    PIKACHU = "Pikachu"
    ICS = "ICs"
    PUFF = "Puff"
    SAMUS = "Samus"
    YOSHI = "Yoshi"
    ZELDA = "Zelda"
    SHEIK = "Sheik"
    FALCO = "Falco"
    YL = "YL"
    DOC = "Doc"
    ROY = "Roy"
    PICHU = "Pichu"
    GANON = "Ganon"


@dataclasses.dataclass(frozen=True)
class SlotData:
    display_names: list[str]
    ports: list[int]
    prefixes: list[str]
    pronouns: list[str]
    score: int

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            display_names=data["displayNames"],
            ports=data["ports"],
            prefixes=data["prefixes"],
            pronouns=data["pronouns"],
            score=data["score"],
        )


@dataclasses.dataclass(frozen=True)
class ScoreData:
    slots: list[SlotData]

    @classmethod
    def from_dict(cls, data: dict):
        return cls(slots=[SlotData.from_dict(slot) for slot in data["slots"]])


@dataclasses.dataclass(frozen=True)
class EntrantData:
    name: str
    characters: list[Character]

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            name=data["name"],
            characters=[Character(char) for char in data["characters"]],
        )


@dataclasses.dataclass(frozen=True)
class PlayerData:
    entrant_1: list[EntrantData]
    entrant_2: list[EntrantData]

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            entrant_1=[EntrantData.from_dict(entrant) for entrant in data["entrant1"]],
            entrant_2=[EntrantData.from_dict(entrant) for entrant in data["entrant2"]],
        )


@dataclasses.dataclass(frozen=True)
class PlatformData:
    data: dict

    @property
    def tournament_name(self):
        raise NotImplementedError

    @property
    def tournament_location(self):
        raise NotImplementedError

    @property
    def event_name(self):
        raise NotImplementedError

    @property
    def phase_name(self):
        raise NotImplementedError

    @property
    def round_name(self):
        raise NotImplementedError

    @property
    def ordinal(self):
        raise NotImplementedError

    @property
    def round(self):
        raise NotImplementedError

    @property
    def stream(self):
        raise NotImplementedError


@dataclasses.dataclass(frozen=True)
class StartggData(PlatformData):
    @property
    def tournament_name(self):
        return self.data["tournament"]["name"]

    @property
    def tournament_location(self):
        return self.data["tournament"]["location"]

    @property
    def event_name(self):
        return self.data["event"]["name"]

    @property
    def phase_name(self):
        return self.data["phase"]["name"]

    @property
    def round_name(self):
        return self.data["set"]["fullRoundText"]

    @property
    def ordinal(self):
        return self.data["set"]["ordinal"]

    @property
    def round(self):
        return self.data["set"]["round"]

    @property
    def stream(self):
        return self.data["set"]["stream"]


@dataclasses.dataclass(frozen=True)
class ContextData:
    best_of: int
    duration_ms: int
    scores: list[ScoreData]
    final_score: ScoreData
    start_ms: int  # UTC time

    players: PlayerData | None = dataclasses.field(default=None)
    startgg: StartggData | None = dataclasses.field(default=None)

    def __post_init__(self):
        if isinstance(self.players, dict):
            players = PlayerData.from_dict(self.players)
            object.__setattr__(self, "players", players)
        if isinstance(self.startgg, dict):
            startgg = StartggData(self.startgg)
            object.__setattr__(self, "startgg", startgg)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            best_of=data["bestOf"],
            duration_ms=data["durationMs"],
            scores=[ScoreData.from_dict(score) for score in data["scores"]],
            final_score=ScoreData.from_dict(data["finalScore"]),
            start_ms=data["startMs"],
            players=data.get("players"),
            startgg=data.get("startgg"),
        )

    @classmethod
    def from_json(self, path: Path):
        with open(path, "rb") as f:
            return ContextData.from_dict(json.load(f))

    @property
    def platform(self):
        if self.startgg is not None:
            return self.startgg

    @property
    def tournament_name(self):
        return self.platform.tournament_name

    @property
    def tournament_location(self):
        return self.platform.tournament_location

    @property
    def event_name(self):
        return self.platform.event_name

    @property
    def phase_name(self):
        return self.platform.phase_name

    @property
    def round_name(self):
        return self.platform.round_name

    @property
    def ordinal(self):
        return self.platform.ordinal

    @property
    def round(self):
        return self.platform.round

    @property
    def stream(self):
        return self.platform.stream
