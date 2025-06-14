import contextlib

from slp2mp4.scoreboard import scoreboard

class NoneScoreboard(scoreboard.Scoreboard):
    @contextlib.contextmanager
    def get_args(self):
        try:
            yield ()
        finally:
            pass
