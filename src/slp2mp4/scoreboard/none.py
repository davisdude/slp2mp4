from slp2mp4.scoreboard import scoreboard


class NoScoreboard(scoreboard.Scoreboard):
    def _get_scoreboard_panels(self, pad):
        return []

    def _get_scoreboard_args(self):
        return ()
