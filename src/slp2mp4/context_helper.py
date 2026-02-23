from datetime import datetime
import copy
import pathlib
import json

from slp2mp4 import util


# https://github.com/jmlee337/replay-manager-for-slippi/blob/efe8c246181a6251c268abd2194706db9b7c6c00/src/common/types.ts#L257
class GameContextInfo:
    """Wraps around context.json to abstract data differences."""

    def __init__(self, context_json_path: pathlib.Path, game_index: int):
        self.game_index = game_index
        with open(context_json_path, "r", encoding="utf-8") as f:
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
    def slot_data(self):
        return self.context_data["scores"][self.game_index]["slots"]

    @property
    def tournament_name(self):
        return self.platform_data["tournament"]["name"]

    @property
    def tournament_location(self):
        return self.platform_data["tournament"]["location"]

    @property
    def tournament_date(self):
        location_str = self.tournament_location
        start_time_ms = self.context_data["startMs"]
        # TODO: Add to config / add to context.json
        # Assume user's local timezone
        timezone = datetime.now().astimezone().tzinfo
        return datetime.fromtimestamp(start_time_ms / 1000, tz=timezone)

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

    @property
    def num_teams(self):
        # Assumes teams have an equal number of players
        return len(self.slot_data[0]["displayNames"])

    def get_mapping(self):
        # TODO: Add [L] for GFs
        replacements = {
            "TOURNAMENT_NAME": self.tournament_name,
            "TOURNAMENT_LOCATION": self.tournament_location,
            "EVENT_NAME": self.event_name,
            "PHASE_NAME": self.phase_name,
            "BRACKET_ROUND": self.bracket_round_text,
            "BRACKET_ROUND_SHORT": self.bracket_round_text_shortened,
            "BRACKET_SCORING": self.best_of,
            "BRACKET_SCORING_SHORT": self.best_of_shortened,
        }
        for team_id, slot_data in enumerate(self.slot_data, start=1):
            replacements.update({f"COMBATANT_{team_id}_SCORE": slot_data["score"]})
            for player_id in range(self.num_teams):
                replacements.update(
                    {
                        f"COMBATANT_{team_id}_{player_id + 1}_SPONSOR": slot_data[
                            "prefixes"
                        ][player_id],
                        f"COMBATANT_{team_id}_{player_id + 1}_TAG": slot_data[
                            "displayNames"
                        ][player_id],
                        f"COMBATANT_{team_id}_{player_id + 1}_PRONOUNS": slot_data[
                            "pronouns"
                        ][player_id],
                    }
                )
        return replacements


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
