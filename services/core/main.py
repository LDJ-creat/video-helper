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


def _should_enable_reload() -> bool:
    """Enable reload in local development, but keep container/runtime defaults off.

    CORE_RELOAD can override the default explicitly.
    """

    raw_reload = os.environ.get("CORE_RELOAD")
    if raw_reload is not None:
        return raw_reload.strip().lower() in {"1", "true", "yes", "y", "on"}

    # The packaged Docker runtime sets DATA_DIR=/app/data.
    # Treat that as a production-like environment and avoid auto-reload there.
    return os.environ.get("DATA_DIR") != "/app/data"


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    reload_enabled = _should_enable_reload()
    reload_dirs = [PROJECT_ROOT] if reload_enabled else None
    reload_excludes = [".venv", "build", "data", "__pycache__"] if reload_enabled else None

    uvicorn.run(
        "core.main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
        reload_dirs=reload_dirs,
        reload_excludes=reload_excludes,
        app_dir=SRC_DIR,
    )


if __name__ == "__main__":
    main()
