import os, json, sys
import shutil
from paths import Paths

class Config:
    def __init__(self, check_paths=True):
        self.paths = Paths()
        with open(self.paths.config_json, 'r') as f:
            j = json.loads(f.read())
            self.melee_iso = os.path.expanduser(j['melee_iso'])
            self.read_slp = os.path.expanduser(j['read_slp'])
            self.dolphin_dir = os.path.expanduser(j['dolphin_dir'])
            self.paths.dolphin_dir = self.dolphin_dir
            try:
                self.ffmpeg = os.path.expanduser(shutil.which(j['ffmpeg']))
            except TypeError:
                self.ffmpeg = None
            self.resolution = j['resolution']
            self.video_backend = j['video_backend']
            self.widescreen = j['widescreen']
            self.bitrateKbps = j['bitrateKbps']
            self.parallel_games = j['parallel_games']
            self.remove_short = j['remove_short']
            self.combine = j['combine']
            self.remove_slps = j['remove_slps']

        self.dolphin_bin = self.paths.dolphin_bin

        # TODO: add more checking here
        if check_paths:
            self.check_path(self.melee_iso, 'Melee ISO')
            self.check_path(self.read_slp, 'Read slp files')
            self.check_path(self.dolphin_dir, 'Dolphin directory')
            self.check_path(self.ffmpeg, 'ffmpeg')
            self.check_path(self.dolphin_bin, 'Dolphin binary')

    def check_path(self, path, name):
        if path is None:
            raise RuntimeError(f'Invalid config for {name}')
        if not os.path.exists(path):
            raise RuntimeError(f'{path} does not exist')
