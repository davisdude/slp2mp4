from slp2mp4.modes import mode
from slp2mp4.modes.single import Single
from slp2mp4.modes.directory import Directory
from slp2mp4.modes.zip import Zip

MODES = {
    "single": mode.ModeContainer(
        Single,
        "convert single replay files to videos",
        "input file(s)",
    ),
    "directory": mode.ModeContainer(
        Directory,
        "recursively convert all replay files in a directory to videos",
        "input directory/directories",
    ),
    "zip": mode.ModeContainer(
        Zip,
        "recursively convert all replay files in a zip to videos",
        "replay manager zip/directory",
    ),
}
