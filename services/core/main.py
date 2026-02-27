import os
import sys


def _load_env_file(path: str) -> None:
    """Minimal dotenv loader.

    Loads KEY=VALUE pairs into os.environ (does not override existing vars).
    """

    if not os.path.exists(path):
        return

    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if not key:
                    continue
                os.environ.setdefault(key, value)
    except OSError:
        # Non-fatal: running without .env is OK.
        return


PROJECT_ROOT = os.path.dirname(__file__)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Auto-load local env defaults for development.
_load_env_file(os.path.join(PROJECT_ROOT, ".env"))


from core.main import app  # noqa: E402


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
