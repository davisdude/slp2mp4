from slp2mp4.modes import single
from slp2mp4.modes import directory
from slp2mp4.modes import replay_manager
from slp2mp4.modes import mode

MODES = {
    "single": mode.ModeContainer(
        single.Single,
        "convert single replay files to videos",
        "input file(s)",
    ),
    "directory": mode.ModeContainer(
        directory.Directory,
        "recursively convert all replay files in a directory to videos",
        "input directory/directories",
    ),
    "replay_manager": mode.ModeContainer(
        replay_manager.ReplayManager,
        "recursively convert all replay files in a zip to videos",
        "replay manager zip/directory",
    ),
}
