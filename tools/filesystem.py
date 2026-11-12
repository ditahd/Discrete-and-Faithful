"""Clone immutable inputs efficiently, including across filesystem boundaries."""
import errno
import os
import shutil
from pathlib import Path

def link_or_copy(source, destination):
    source, destination = Path(source), Path(destination)
    if source.stat().st_dev == destination.parent.stat().st_dev:
        try:
            os.link(source, destination)
            return str(destination)
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
    return shutil.copy2(source, destination)
