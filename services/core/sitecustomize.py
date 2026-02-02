import os
import sys


def _bootstrap_src_path() -> None:
    project_root = os.path.dirname(__file__)
    src_dir = os.path.join(project_root, "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


_bootstrap_src_path()
