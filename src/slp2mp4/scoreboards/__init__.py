from slp2mp4.scoreboards import scoreboard
from slp2mp4.scoreboards.none import NoneScoreboard
from slp2mp4.scoreboards.default import DefaultScoreboard

SCOREBOARDS = {
    "none": none.NoneScoreboard,
    "default": default.DefaultScoreboard,
}
