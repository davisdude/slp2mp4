import contextlib

from slp2mp4.scoreboards.scoreboard import Scoreboard


class NoneScoreboard(Scoreboard):
    @contextlib.contextmanager
    def get_args(self):
        try:
            yield ()
        finally:
            pass
