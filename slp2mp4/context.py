import dataclasses
import json
import math
from enum import Enum
from pathlib import Path

import frozendict

# https://github.com/jmlee337/replay-manager-for-slippi/blob/46fcbcd9aa5ae51702cdab45f75e343a27e56f9c/src/common/constants.ts#L7
_EXTERNAL_CHARACTER_IDS = {
    "Falcon": 0,
    "DK": 1,
    "Fox": 2,
    "GW": 3,
    "Kirby": 4,
    "Bowser": 5,
    "Link": 6,
    "Luigi": 7,
    "Mario": 8,
    "Marth": 9,
    "Mewtwo": 10,
    "Ness": 11,
    "Peach": 12,
    "Pikachu": 13,
    "ICs": 14,
    "Puff": 15,
    "Samus": 16,
    "Yoshi": 17,
    "Zelda": 18,
    "Sheik": 19,
    "Falco": 20,
    "YL": 21,
    "Doc": 22,
    "Roy": 23,
    "Pichu": 24,
    "Ganon": 25,
}


class CharacterEnum:
    @classmethod
    def from_string(cls, data: str):
        val = _EXTERNAL_CHARACTER_IDS.get(data)
        if val is None:
            return None
        return cls(val)


Character = Enum("Character", _EXTERNAL_CHARACTER_IDS, type=CharacterEnum)


@dataclasses.dataclass(frozen=True)
class CharacterData:
    id: int
    costume: int

    @classmethod
    def from_dict(cls, data: dict):
        return cls(id=data["id"], costume=data["costume"])


@dataclasses.dataclass(frozen=True)
class SlotData:
    display_names: tuple[str]
    ports: tuple[int]
    prefixes: tuple[str]
    pronouns: tuple[str]
    score: int
    characters: tuple[CharacterData] | None = dataclasses.field(default=None)
    team_id: int | None = dataclasses.field(default=None)
    losers: bool | None = dataclasses.field(default=None)

    def __post_init__(self):
        if isinstance(self.characters, list):
            characters = tuple(
                CharacterData.from_dict(char) for char in self.characters
            )
            object.__setattr__(self, "characters", characters)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            display_names=tuple(data["displayNames"]),
            ports=tuple(data["ports"]),
            prefixes=tuple(data["prefixes"]),
            pronouns=tuple(data["pronouns"]),
            score=data["score"],
            characters=data.get("characters"),
            team_id=data.get("team_id"),
            losers=data.get("losers"),
        )


@dataclasses.dataclass(frozen=True)
class ScoreData:
    slots: tuple[SlotData]

    @classmethod
    def from_dict(cls, data: dict):
        return cls(slots=tuple(SlotData.from_dict(slot) for slot in data["slots"]))


@dataclasses.dataclass(frozen=True)
class EntrantData:
    name: str
    characters: tuple[Character]

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            name=data["name"],
            characters=tuple(
                Character.from_string(char) for char in data["characters"]
            ),
        )


@dataclasses.dataclass(frozen=True)
class PlayerData:
    entrant_1: tuple[EntrantData]
    entrant_2: tuple[EntrantData]

    @classmethod
    def from_dict(cls, data: dict):
        entrant_1 = tuple(EntrantData.from_dict(e) for e in data["entrant1"])
        entrant_2 = tuple(EntrantData.from_dict(e) for e in data["entrant2"])
        return cls(entrant_1=entrant_1, entrant_2=entrant_2)


@dataclasses.dataclass(frozen=True)
class PlatformData:
    data: frozendict.frozendict

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
    scores: tuple[ScoreData]
    final_score: ScoreData
    start_ms: int  # UTC time

    players: PlayerData | None = dataclasses.field(default=None)
    startgg: StartggData | None = dataclasses.field(default=None)

    def __post_init__(self):
        if isinstance(self.players, dict):
            players = PlayerData.from_dict(self.players)
            object.__setattr__(self, "players", players)
        if isinstance(self.startgg, dict):
            startgg = StartggData(frozendict.deepfreeze(self.startgg))
            object.__setattr__(self, "startgg", startgg)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            best_of=data["bestOf"],
            duration_ms=data["durationMs"],
            scores=tuple(ScoreData.from_dict(score) for score in data["scores"]),
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
    def phase_group(self):
        return (self.tournament_name, self.event_name, self.phase_name)

    @property
    def set_order(self):
        ordinal = self.ordinal if self.ordinal is not None else -math.inf
        return (ordinal, self.round, self.start_ms)

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
