# Logic for dolphin comm configuration
# https://github.com/project-slippi/slippi-wiki/blob/master/COMM_SPEC.md

import contextlib
import json
import os
import tempfile
import uuid
from pathlib import Path


@contextlib.contextmanager
def make_temp_file(path: Path):
    config = {
        # Use queue mode because the NO_GAME message it emits can be used to detect end
        # of game. GAME_END_FRAME is when slippi data stops, so it isn't reliable.
        "mode": "queue",
        "isRealTimeMode": False,
        "commandId": str(uuid.uuid4()),
        "queue": [
            {
                "path": str(path.absolute()),
            },
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as file:
        file.write(json.dumps(config))
        file.close()
        try:
            yield file.name
        finally:
            os.unlink(file.name)
