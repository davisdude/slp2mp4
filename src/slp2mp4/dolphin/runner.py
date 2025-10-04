# Wrapper for running dolphin

import tempfile
import time
import pathlib
import subprocess

import slp2mp4.replay as replay
import slp2mp4.dolphin.comm as comm
import slp2mp4.dolphin.ini as ini
import slp2mp4.util as util


class DolphinRunner:
    def __init__(self, config, kill_event):
        self.kill_event = kill_event
        self.slippi_playback = config["paths"]["slippi_playback"]
        self.ssbm_iso = config["paths"]["ssbm_iso"]
        self.video_backend = config["dolphin"]["backend"]
        self.user_gfx = {
            "Settings": {
                "EFBScale": config["dolphin"]["resolution"],
                "BitrateKbps": str(config["dolphin"]["bitrate"]),
            },
        }
        # https://github.com/project-slippi/Ishiiruka/blob/3e5b185ae080e8dca5e939369572d94d20049fea/Data/Sys/GameSettings/GAL.ini#L21
        # Need to override this setting for non-integral scaling
        self.user_gal = {
            "Video_Settings": {
                "EFBScale": config["dolphin"]["resolution"],
            },
        }
        self.user_gecko = {
            "Gecko_Enabled": {
                key: None
                for key, value in config["dolphin"]["gecko_codes"].items()
                if value is True
            },
            "Gecko_Disabled": {
                key: None
                for key, value in config["dolphin"]["gecko_codes"].items()
                if value is False
            },
        }

    def run_dolphin(self, replay: replay.ReplayFile, dump_dir: pathlib.Path):
        with tempfile.TemporaryDirectory() as userdir_str:
            userdir = pathlib.Path(userdir_str)
            with (
                comm.make_temp_file(replay) as comm_file,
                ini.make_dolphin_file(userdir) as dolphin_file,
                ini.make_gfx_file(userdir, self.user_gfx) as gfx_file,
                ini.make_gal_file(userdir, self.user_gal) as gal_file,
                ini.make_hotkeys_file(userdir) as hotkeys_file,
                ini.make_gecko_file(userdir, self.user_gecko) as gecko_file,
            ):
                args = (
                    (self.slippi_playback,),
                    (
                        "--exec",
                        self.ssbm_iso,
                    ),
                    ("--batch",),
                    (
                        "--video_backend",
                        self.video_backend,
                    ),
                    (
                        "--slippi-input",
                        comm_file,
                    ),
                    ("--hide-seekbar",),
                    (
                        "--output-directory",
                        dump_dir,
                    ),
                    (
                        "--user",
                        userdir,
                    ),
                    ("--cout",),
                )
                dolphin_args = util.flatten_arg_tuples(args)
                try:
                    proc = subprocess.Popen(
                        args=dolphin_args, stdout=subprocess.PIPE, text=True
                    )
                    game_end_frame = -124
                    current_frame = -125

                    while (proc.poll() is None) and (not self.kill_event.is_set()):
                        line = proc.stdout.readline()
                        if not line:
                            break
                        strip_line = line.rstrip()

                        if strip_line.startswith("[GAME_END_FRAME] "):
                            game_end_frame = int(
                                strip_line.removeprefix("[GAME_END_FRAME] ")
                            )
                        elif strip_line.startswith("[CURRENT_FRAME] "):
                            current_frame = int(
                                strip_line.removeprefix("[CURRENT_FRAME] ")
                            )

                        if current_frame >= game_end_frame:
                            break

                    # Kills dolphin (if need be) when finished dumping
                    if current_frame != game_end_frame:
                        print("Dolphin terminated early")
                    time.sleep(2)
                    proc.terminate()
                    proc.wait(timeout=5)

                except subprocess.CalledProcessError as e:
                    print(f"Dolphin failed with error ${e}")
                    raise

        audio_file = dump_dir.joinpath("dspdump.wav")
        video_file = dump_dir.joinpath("framedump0.avi")
        return audio_file, video_file
