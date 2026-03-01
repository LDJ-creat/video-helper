from __future__ import annotations

import os
from pathlib import Path

# Ensure src-layout imports work when running as a script.
import sys

HERE = Path(__file__).resolve()
CORE_DIR = HERE.parents[1]
SRC_DIR = CORE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from core.external.ytdlp import download_with_ytdlp  # noqa: E402


def main() -> None:
    os.environ.setdefault("YTDLP_COOKIES_FILE", "D:/video-helper/www.bilibili.com_cookies.txt")
    os.environ.setdefault("DATA_DIR", "D:/vh-wrapper-debug")
    data_dir = Path(os.environ["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)

    out_dir = data_dir / "dl"
    out_dir.mkdir(parents=True, exist_ok=True)

    url = "https://www.bilibili.com/video/BV1G4iMBeEWH/?spm_id_from=333.337.search-card.all.click"
    res = download_with_ytdlp(url=url, output_dir=out_dir, base_filename="source", timeout_s=600)

    print("OK", res.rel_path)
    print("FILES", sorted([p.name for p in out_dir.rglob('*') if p.is_file()]))


if __name__ == "__main__":
    main()
