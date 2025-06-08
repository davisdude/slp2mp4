from slp2mp4.modes import single
from slp2mp4.modes import directory
from slp2mp4.modes import replay_manager

MODES = {
    "single": single.Single,
    "directory": directory.Directory,
    "replay_manager": replay_manager.ReplayManager,
}
