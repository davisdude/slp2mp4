import copy
import pathlib
import json

from slp2mp4 import util


class GameContextInfo:
    """Wraps around context.json to abstract data differences."""

    def __init__(self, context_json_path: pathlib.Path, game_index: int):
        self.game_index = game_index
        with open(context_json_path, "r") as f:
            self.context_data = json.load(f)
            self.context_data["unknown"] = {
                "tournament": {
                    "name": "Unknown",
                    "location": "Unknown",
                },
                "event": {
                    "name": "",
                },
                "phase": {
                    "name": "",
                },
                "set": {
                    "fullRoundText": "",
                },
            }
            self.platform_data = self.context_data["unknown"]
            util.update_dict(self.platform_data, self.context_data[self.platform])

    @property
    def platform(self):
        if "startgg" in self.context_data:
            return "startgg"
        if "challonge" in self.context_data:
            return "challonge"
        return "unknown"

    @property
    def tags(self):
        return [
            _get_tag_from_slot_data(slot_data)
            for slot_data in self.context_data["scores"][self.game_index]["slots"]
        ]

    @property
    def scores(self):
        return self.context_data["scores"][self.game_index]["slots"]["score"]

    @property
    def tournament_name(self):
        return self.platform_data["tournament"]["name"]

    @property
    def tournament_location(self):
        return self.platform_data["tournament"]["location"]

    @property
    def event_name(self):
        return self.platform_data["event"]["name"]

    @property
    def phase_name(self):
        return self.platform_data["phase"]["name"]

    @property
    def bracket_round_text(self):
        return self.platform_data["set"]["fullRoundText"]

    @property
    def bracket_round_text_shortened(self):
        return _shorten_round(self.platform_data["set"]["fullRoundText"])

    @property
    def best_of(self):
        return f"Best of {self.context_data['bestOf']}"

    @property
    def best_of_shortened(self):
        return f"Bo{self.context_data['bestOf']}"

    def get_mapping(self):
        return copy.copy(
            {
                "{TOURNAMENT_NAME}": self.tournament_name,
                "{TOURNAMENT_LOCATION}": self.tournament_location,
                "{EVENT_NAME}": self.event_name,
                "{PHASE_NAME}": self.phase_name,
                "{BRACKET_ROUND}": self.bracket_round_text,
                "{BRACKET_ROUND_SHORT}": self.bracket_round_text_shortened,
                "{BRACKET_SCORING}": self.best_of,
                "{BRACKET_SCORING_SHORT}": self.best_of_shortened,
                "{COMBATANT_1_TAG}": self.tags[0],
                "{COMBATANT_2_TAG}": self.tags[1],
                "{COMBATANT_1_SCORE}": self.scores[0],
                "{COMBATANT_2_SCORE}": self.scores[1],
            }
        )


# TODO: Add [L] for GFs
def _get_tag(tag, prefixes, pronouns, ports, is_singles=True):
    if is_singles:
        if prefixes:
            tag = f"{prefixes} | {tag}"
        if pronouns:
            tag = f"{tag} ({pronouns})"
    else:
        tag = f"{tag} (P{ports})"
    return tag


def _get_tag_from_slot_data(slot_data):
    is_singles = len(slot_data["displayNames"]) == 1
    tags = [
        _get_tag(tag, prefixes, pronouns, ports, is_singles)
        for tag, prefixes, pronouns, ports in zip(
            slot_data["displayNames"],
            slot_data["prefixes"],
            slot_data["pronouns"],
            slot_data["ports"],
        )
    ]
    return ("/").join(tags)


def _shorten_round(round_text):
    return util.translate(
        round_text,
        {
            "Winners": "W",
            "Losers": "L",
            "Grand": "G",
            "Semi": "S",
            "Quarter": "Q",
            "Round": "R",
            "Final": "F",
            "Reset": "R",
            " ": "",
            "-": "",
        },
    )
