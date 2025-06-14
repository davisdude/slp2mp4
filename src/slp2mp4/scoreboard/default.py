import textwrap

from slp2mp4.scoreboard import scoreboard

# Assumes drawtext.fontsize is default
MAX_WIDTH = 28


def _wrap_line(line):
    return textwrap.wrap(line, MAX_WIDTH, subsequent_indent="\t")


def _wrap_lines(lines):
    wrapped_lines = []
    for line in lines:
        wrapped_lines.extend(_wrap_line(line))
    return wrapped_lines


# Assumes standard melee aspect ratio (73x60)
class DefaultScoreboard(scoreboard.Scoreboard):
    def __post_init__(self):
        super().__post_init__()
        self.drawtext_args = [
            {
                "x": "main_w/60",  # ~1 character's width
                "y": "(main_h-text_h)/2",
            }
        ]

    def make_drawtexts(self):
        # TODO: Handle challonge / manual data
        tournament_data = _wrap_lines(
            [
                self.context_data["startgg"]["tournament"]["name"],
                self.context_data["startgg"]["tournament"]["location"],
                self.context_data["startgg"]["event"]["name"],
                f"{self.context_data['startgg']['set']['fullRoundText']} (Bo{self.context_data['bestOf']})",
            ]
        )
        name_data = _wrap_lines(
            [
                scoreboard.get_name_from_slot_data(slot_data)
                for slot_data in self.context_data["scores"][self.game_index]["slots"]
            ]
        )
        lines = [*name_data, "", *tournament_data]
        return [scoreboard.DrawtextContainer(lines)]
