from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LogItem:
    ts_ms: int
    level: str
    message: str
    stage: str


@dataclass(frozen=True)
class LogsPage:
    items: list[LogItem]
    next_cursor: str | None


def _default_data_dir() -> Path:
    data_dir = os.environ.get("DATA_DIR")
    if data_dir:
        return Path(data_dir)

    # repo-root/data (repo root is 4 levels above core/app/logs)
    return Path(__file__).resolve().parents[4] / "data"


def _job_log_path(job_id: str) -> Path:
    return _default_data_dir() / "logs" / "jobs" / f"{job_id}.log"


def _cursor_secret() -> bytes:
    # This is not intended as a security boundary; it's for tamper-detection and opacity.
    return os.environ.get("LOG_CURSOR_SECRET", "dev-log-cursor-secret").encode("utf-8")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(token: str) -> bytes:
    padded = token + "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def encode_cursor(job_id: str, offset: int) -> str:
    payload = json.dumps({"v": 1, "o": int(offset)}, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_cursor_secret(), job_id.encode("utf-8") + b"." + payload, hashlib.sha256).digest()[:16]
    return f"{_b64url_encode(payload)}.{_b64url_encode(sig)}"


def decode_cursor(job_id: str, cursor: str) -> int:
    try:
        payload_b64, sig_b64 = cursor.split(".", 1)
        payload = _b64url_decode(payload_b64)
        sig = _b64url_decode(sig_b64)
    except Exception as e:  # noqa: BLE001
        raise ValueError("invalid cursor") from e

    expected = hmac.new(_cursor_secret(), job_id.encode("utf-8") + b"." + payload, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(sig, expected):
        raise ValueError("invalid cursor")

    data = json.loads(payload.decode("utf-8"))
    if data.get("v") != 1:
        raise ValueError("invalid cursor")

    offset = int(data.get("o"))
    if offset < 0:
        raise ValueError("invalid cursor")

    return offset


def _tail_lines(path: Path, limit: int, max_bytes: int = 512 * 1024) -> tuple[list[str], int]:
    with path.open("rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        if file_size == 0:
            return [], 0

        remaining = file_size
        chunks: list[bytes] = []
        read_bytes = 0

        while remaining > 0 and read_bytes < max_bytes:
            to_read = min(8192, remaining)
            remaining -= to_read
            f.seek(remaining)
            chunk = f.read(to_read)
            chunks.append(chunk)
            read_bytes += to_read

            data = b"".join(reversed(chunks))
            if data.count(b"\n") >= limit + 1:
                break

        data = b"".join(reversed(chunks))
        lines = data.splitlines()
        # Keep the last `limit` lines.
        tail = lines[-limit:] if limit > 0 else []
        return [l.decode("utf-8", errors="replace") for l in tail], file_size


def _parse_line(line: str, default_stage: str) -> LogItem:
    s = line.strip("\r\n")
    if not s:
        return LogItem(ts_ms=0, level="info", message="", stage=default_stage)

    try:
        obj = json.loads(s)
        ts_ms = int(obj.get("tsMs") or obj.get("ts_ms") or 0)
        level = str(obj.get("level") or "info")
        message = str(obj.get("message") or "")
        stage = str(obj.get("stage") or default_stage)
        return LogItem(ts_ms=ts_ms, level=level, message=message, stage=stage)
    except Exception:
        return LogItem(ts_ms=0, level="info", message=s, stage=default_stage)


def read_job_logs_page(job_id: str, limit: int, cursor: str | None, default_stage: str) -> LogsPage:
    path = _job_log_path(job_id)

    if not path.exists():
        return LogsPage(items=[], next_cursor=None)

    try:
        if cursor is None:
            lines, end_offset = _tail_lines(path, limit=limit)
            items = [_parse_line(line, default_stage=default_stage) for line in lines if line.strip()]
            next_cursor = encode_cursor(job_id, end_offset)
            return LogsPage(items=items, next_cursor=next_cursor)

        start_offset = decode_cursor(job_id, cursor)
        with path.open("rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
            if start_offset > file_size:
                start_offset = file_size

            f.seek(start_offset)
            items: list[LogItem] = []
            while len(items) < limit:
                line = f.readline()
                if not line:
                    break
                items.append(_parse_line(line.decode("utf-8", errors="replace"), default_stage=default_stage))

            next_cursor = encode_cursor(job_id, f.tell())
            return LogsPage(items=items, next_cursor=next_cursor)

    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("logs unavailable") from e
