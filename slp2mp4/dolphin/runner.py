# Wrapper for running dolphin

import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Event
from pathlib import Path
from queue import Empty, Queue

from slp2mp4 import log, util
from slp2mp4.dolphin import comm, ini

GAME_END_PREFIX = "[GAME_END_FRAME] "
CURRENT_FRAME_PREFIX = "[CURRENT_FRAME] "


def _read(proc: subprocess.Popen, queue: Queue[str | None]):
    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                queue.put(line)
    finally:
        queue.put(None)


class DolphinRunner:
    def __init__(self, config):
        self.log = log.get_logger()
        self.slippi_playback = config.paths.slippi_playback.expanduser()
        self.ssbm_iso = config.paths.ssbm_iso.expanduser()
        self.video_backend = config.dolphin.backend.value
        self.user_gfx = {
            "Settings": {
                "MSAA": str(config.dolphin.msaa),
                "SSAA": "True" if config.dolphin.ssaa else "False",
                "EFBScale": config.dolphin.resolution.dolphin_value,
                "BitrateKbps": str(config.dolphin.bitrate),
            },
        }
        # https://github.com/project-slippi/Ishiiruka/blob/3e5b185ae080e8dca5e939369572d94d20049fea/Data/Sys/GameSettings/GAL.ini#L21
        # Need to override this setting for non-integral scaling
        self.user_gal = {
            "Video_Settings": {
                "EFBScale": config.dolphin.resolution.dolphin_value,
            },
        }

        gecko_codes = config.dolphin.gecko_codes
        custom_gecko_codes = util.split_by_blank_line(config.dolphin.custom_gecko_codes)
        custom_gecko_code_names = [
            re.match(r"^(\$[^\n\r\[]*).*$", code, re.MULTILINE).group(1).strip()
            for code in custom_gecko_codes
        ]

        enabled_gecko_codes = custom_gecko_code_names
        disabled_gecko_codes = []
        for name, enabled in gecko_codes.items():
            if enabled:
                enabled_gecko_codes.append(name)
            else:
                disabled_gecko_codes.append(name)

        self.user_gecko = {
            "Gecko_Enabled": {name: None for name in enabled_gecko_codes},
            "Gecko_Disabled": {name: None for name in disabled_gecko_codes},
            "Gecko": {code: None for code in custom_gecko_codes},
        }

    def run(self, path: Path, dump_dir: Path, kill_event: Event):
        with tempfile.TemporaryDirectory() as userdir_str:
            userdir = Path(userdir_str)
            with (
                comm.make_temp_file(path) as comm_file,
                ini.make_dolphin_file(userdir) as _dolphin_file,
                ini.make_gfx_file(userdir, self.user_gfx) as _gfx_file,
                ini.make_gal_file(userdir, self.user_gal) as _gal_file,
                ini.make_hotkeys_file(userdir) as _hotkeys_file,
                ini.make_gecko_file(userdir, self.user_gecko) as _gecko_file,
            ):
                args = (
                    self.slippi_playback,
                    "--exec",
                    self.ssbm_iso,
                    "--batch",
                    "--video_backend",
                    self.video_backend,
                    "--slippi-input",
                    comm_file,
                    "--hide-seekbar",
                    "--output-directory",
                    dump_dir,
                    "--user",
                    userdir,
                    "--cout",
                )
                self._run(args, kill_event)
        audio_file = dump_dir.joinpath("dspdump.wav")
        video_file = dump_dir.joinpath("framedump0.avi")
        return audio_file, video_file

    def _run(self, args: tuple[str, ...], kill_event: Event):
        with ThreadPoolExecutor(max_workers=1) as executor:
            proc = subprocess.Popen(
                args=args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env=util.get_env(),
            )
            queue = Queue()
            future = executor.submit(_read, proc, queue)

            game_end_frame = -124
            current_frame = -125

            try:
                while not kill_event.is_set():
                    try:
                        line = queue.get(timeout=1)
                    except Empty:
                        if future.done():
                            break
                        continue
                    if line is None:
                        break
                    line = line.rstrip()
                    if line.startswith(GAME_END_PREFIX):
                        game_end_frame = int(line.removeprefix(GAME_END_PREFIX))
                    elif line.startswith(CURRENT_FRAME_PREFIX):
                        current_frame = int(line.removeprefix(CURRENT_FRAME_PREFIX))
                    if current_frame >= game_end_frame:
                        break
                if current_frame < game_end_frame:
                    self.log.info("Dolphin terminated early!")
                else:
                    # Give time for "GAME!" to clear
                    time.sleep(2)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                future.result()
