#!/usr/bin/env python3
"""
Video Analyzer - CLI tool to analyze videos via the video-helper backend API.

This script creates a video analysis job, polls for completion, and returns
the result links for viewing in the frontend.

Usage:
    python analyze_video.py <video_url_or_path> [--title "Video Title"] [--lang zh]
    python analyze_video.py --help

Examples:
    python analyze_video.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    python analyze_video.py "https://www.bilibili.com/video/BV1xx411c7mD" --lang zh
    python analyze_video.py "/path/to/local/video.mp4" --title "My Video"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Optional
from dataclasses import dataclass


# Configuration
DEFAULT_API_BASE = os.environ.get("VIDEO_HELPER_API_URL", "http://localhost:8000/api/v1")
DEFAULT_POLL_INTERVAL_S = 2.0
DEFAULT_TIMEOUT_S = 600.0  # 10 minutes max wait time

DEFAULT_AUTO_START_TIMEOUT_S = 20.0


def _repo_root_from_this_file() -> Path:
    # scripts/ -> video-analyzer/ -> skill/ -> repo root
    return Path(__file__).resolve().parents[3]


def _is_localhost_8000(api_base: str) -> bool:
    try:
        p = urlparse(api_base)
        host = (p.hostname or "").lower()
        port = int(p.port or 0)
        return host in {"localhost", "127.0.0.1"} and port == 8000
    except Exception:
        return False


def _find_backend_python(repo_root: Path) -> Path | None:
    venv_py = repo_root / "services" / "core" / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return venv_py
    return None


def ensure_backend_running(api_base: str, *, auto_start: bool, timeout_s: float = DEFAULT_AUTO_START_TIMEOUT_S) -> None:
    if check_health(api_base):
        return

    if not auto_start:
        raise RuntimeError(
            f"Backend service unavailable at {api_base}. "
            "Please ensure the video-helper backend is running."
        )

    # Only attempt auto-start for the default local dev URL.
    if not _is_localhost_8000(api_base):
        raise RuntimeError(
            f"Backend service unavailable at {api_base}. "
            "Auto-start is only supported for http://localhost:8000/api/v1. "
            "Start the backend manually or set VIDEO_HELPER_API_URL accordingly."
        )

    repo_root = _repo_root_from_this_file()
    backend_cwd = repo_root / "services" / "core"
    backend_main = backend_cwd / "main.py"
    if not backend_main.exists():
        raise RuntimeError(f"Cannot find backend entrypoint at {backend_main}")

    py = _find_backend_python(repo_root)
    if py is None:
        raise RuntimeError(
            "Backend service unavailable and auto-start could not find backend venv python. "
            "Expected services/core/.venv/Scripts/python.exe. "
            "Please create the backend venv or start the backend manually."
        )

    log_dir = repo_root / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "skill-backend-autostart.log"

    env = os.environ.copy()
    env.setdefault("WORKER_ENABLE", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]

    with open(log_path, "ab", buffering=0) as log_fp:
        try:
            subprocess.Popen(
                [str(py), str(backend_main)],
                cwd=str(backend_cwd),
                env=env,
                stdout=log_fp,
                stderr=log_fp,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
                close_fds=True,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to auto-start backend: {e}") from e

    # Wait until health endpoint becomes ready.
    deadline = time.time() + float(max(1.0, timeout_s))
    while time.time() < deadline:
        if check_health(api_base):
            return
        time.sleep(0.5)

    raise RuntimeError(
        f"Backend auto-start attempted but health check still failing after {timeout_s}s. "
        f"Check logs: {log_path}"
    )


@dataclass
class JobResult:
    """Result of a video analysis job."""
    job_id: str
    project_id: str
    status: str
    error: Optional[str] = None
    result_url: Optional[str] = None
    frontend_url: Optional[str] = None
    plan_request_url: Optional[str] = None


def get_api_base() -> str:
    """Get the API base URL from environment or default."""
    return os.environ.get("VIDEO_HELPER_API_URL", DEFAULT_API_BASE)


def get_frontend_base() -> str:
    """Get the frontend base URL for result links."""
    # Frontend typically runs on port 3000
    return os.environ.get("VIDEO_HELPER_FRONTEND_URL", "http://localhost:3000")


def http_request(
    url: str,
    method: str = "GET",
    data: Optional[bytes] = None,
    headers: Optional[dict] = None,
    timeout: float = 30.0,
) -> tuple[int, dict | bytes]:
    """Make an HTTP request and return (status_code, response_body)."""
    if headers is None:
        headers = {}
    
    headers.setdefault("Accept", "application/json")
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            body = response.read()
            
            if "application/json" in content_type:
                return status, json.loads(body.decode("utf-8"))
            return status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"error": body}
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}") from e


def check_health(api_base: str) -> bool:
    """Check if the backend service is healthy."""
    try:
        status, response = http_request(f"{api_base}/health", timeout=5.0)
        if status == 200:
            data = response if isinstance(response, dict) else {}
            return data.get("ok", True) or data.get("status") == "ok"
        return False
    except Exception:
        return False


def is_url(source: str) -> bool:
    """Check if the source is a URL."""
    return source.startswith("http://") or source.startswith("https://")


def infer_source_type(url: str) -> str:
    """Infer source type from URL."""
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    if "bilibili.com" in url_lower or "b23.tv" in url_lower:
        return "bilibili"
    return "url"


def create_job_from_url(
    api_base: str,
    source_url: str,
    title: Optional[str] = None,
    output_language: Optional[str] = None,
    llm_mode: Optional[str] = None,
) -> JobResult:
    """Create an analysis job from a video URL."""
    source_type = infer_source_type(source_url)
    
    payload = {
        "sourceUrl": source_url,
        "sourceType": source_type,
    }
    if title:
        payload["title"] = title
    if output_language:
        payload["outputLanguage"] = output_language
    if llm_mode:
        payload["llmMode"] = llm_mode
    
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    
    status, response = http_request(
        f"{api_base}/jobs",
        method="POST",
        data=data,
        headers=headers,
        timeout=30.0,
    )
    
    if status != 200:
        error_msg = "Unknown error"
        if isinstance(response, dict):
            error_data = response.get("error", {})
            error_msg = error_data.get("message", str(response))
        raise RuntimeError(f"Failed to create job: {error_msg}")
    
    return JobResult(
        job_id=response["jobId"],
        project_id=response["projectId"],
        status=response["status"],
    )


def create_job_from_file(
    api_base: str,
    file_path: str,
    title: Optional[str] = None,
    output_language: Optional[str] = None,
    llm_mode: Optional[str] = None,
) -> JobResult:
    """Create an analysis job from a local video file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")
    
    # Check file extension
    valid_extensions = {".mp4", ".mkv", ".webm", ".mov"}
    if path.suffix.lower() not in valid_extensions:
        raise ValueError(f"Unsupported file type: {path.suffix}. Supported: {valid_extensions}")
    
    # Read file content
    with path.open("rb") as f:
        file_content = f.read()
    
    # Build multipart form data
    boundary = f"----WebKitFormBoundary{int(time.time() * 1000)}"
    
    def encode_field(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode("utf-8")
    
    def encode_file(name: str, filename: str, content: bytes, content_type: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + content + b"\r\n"
    
    # Build body
    body_parts = []
    body_parts.append(encode_field("sourceType", "upload"))
    if title:
        body_parts.append(encode_field("title", title))
    if output_language:
        body_parts.append(encode_field("outputLanguage", output_language))
    if llm_mode:
        body_parts.append(encode_field("llmMode", llm_mode))
    
    # Guess content type
    content_type = "video/mp4"
    if path.suffix.lower() == ".mkv":
        content_type = "video/x-matroska"
    elif path.suffix.lower() == ".webm":
        content_type = "video/webm"
    elif path.suffix.lower() == ".mov":
        content_type = "video/quicktime"
    
    body_parts.append(encode_file("file", path.name, file_content, content_type))
    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    
    body = b"".join(body_parts)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    
    status, response = http_request(
        f"{api_base}/jobs",
        method="POST",
        data=body,
        headers=headers,
        timeout=60.0,  # Longer timeout for file upload
    )
    
    if status != 200:
        error_msg = "Unknown error"
        if isinstance(response, dict):
            error_data = response.get("error", {})
            error_msg = error_data.get("message", str(response))
        raise RuntimeError(f"Failed to create job: {error_msg}")
    
    return JobResult(
        job_id=response["jobId"],
        project_id=response["projectId"],
        status=response["status"],
    )


def get_job_status(api_base: str, job_id: str) -> dict:
    """Get the current status of a job."""
    status, response = http_request(f"{api_base}/jobs/{job_id}", timeout=10.0)
    
    if status != 200:
        error_msg = "Unknown error"
        if isinstance(response, dict):
            error_data = response.get("error", {})
            error_msg = error_data.get("message", str(response))
        raise RuntimeError(f"Failed to get job status: {error_msg}")
    
    return response


def poll_job_until_complete(
    api_base: str,
    job_id: str,
    poll_interval: float = DEFAULT_POLL_INTERVAL_S,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> JobResult:
    """Poll job status until it completes (succeeded, failed, or canceled)."""
    start_time = time.time()
    terminal_statuses = {"succeeded", "failed", "canceled", "blocked"}
    
    last_stage = None
    last_progress = None
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise TimeoutError(f"Job polling timed out after {timeout}s")
        
        job = get_job_status(api_base, job_id)
        status = job.get("status", "unknown")
        stage = job.get("stage", "unknown")
        progress = job.get("progress")
        error = job.get("error")
        
        # Print progress updates
        if stage != last_stage or progress != last_progress:
            progress_str = f" ({progress * 100:.0f}%)" if progress is not None else ""
            print(f"[{stage}]{progress_str} - status: {status}", file=sys.stderr)
            last_stage = stage
            last_progress = progress
        
        if status in terminal_statuses:
            result = JobResult(
                job_id=job_id,
                project_id=job.get("projectId", ""),
                status=status,
                error=error.get("message") if error else None,
            )
            
            if status == "succeeded":
                frontend_base = get_frontend_base()
                api_base_url = get_api_base()
                result.result_url = f"{api_base_url}/projects/{result.project_id}/results/latest"
                result.frontend_url = f"{frontend_base}/project/{result.project_id}"

            if status == "blocked":
                # External LLM flow: the backend is waiting for a plan to be submitted.
                result.plan_request_url = f"{api_base}/jobs/{job_id}/plan-request"
            
            return result
        
        time.sleep(poll_interval)


def analyze_video(
    source: str,
    title: Optional[str] = None,
    output_language: Optional[str] = None,
    llm_mode: Optional[str] = "external",
    auto_start_backend: bool = True,
    poll_interval: float = DEFAULT_POLL_INTERVAL_S,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> JobResult:
    """
    Analyze a video by creating a job and waiting for completion.
    
    Args:
        source: Video URL or local file path
        title: Optional video title
        output_language: Optional output language for analysis (e.g., "zh", "en")
        poll_interval: Seconds between status polls
        timeout: Maximum seconds to wait for completion
    
    Returns:
        JobResult with job status and result URLs
    """
    api_base = get_api_base()

    ensure_backend_running(api_base, auto_start=auto_start_backend)
    
    print(f"API Base: {api_base}", file=sys.stderr)
    
    # Create job
    if is_url(source):
        print(f"Creating analysis job for URL: {source}", file=sys.stderr)
        result = create_job_from_url(api_base, source, title, output_language, llm_mode=llm_mode)
    else:
        print(f"Creating analysis job for file: {source}", file=sys.stderr)
        result = create_job_from_file(api_base, source, title, output_language, llm_mode=llm_mode)
    
    print(f"Job created: job_id={result.job_id}, project_id={result.project_id}", file=sys.stderr)
    
    # Poll until complete
    print("Waiting for analysis to complete...", file=sys.stderr)
    result = poll_job_until_complete(
        api_base,
        result.job_id,
        poll_interval=poll_interval,
        timeout=timeout,
    )
    
    return result


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze a video using the video-helper backend API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  %(prog)s "https://www.bilibili.com/video/BV1xx411c7mD" --lang zh
  %(prog)s "/path/to/video.mp4" --title "My Video"

Environment Variables:
  VIDEO_HELPER_API_URL      Backend API URL (default: http://localhost:8000/api/v1)
  VIDEO_HELPER_FRONTEND_URL Frontend URL for result links (default: http://localhost:3000)
""",
    )
    
    parser.add_argument(
        "source",
        help="Video URL (YouTube, Bilibili, etc.) or local file path",
    )
    parser.add_argument(
        "--title", "-t",
        help="Video title (optional, auto-detected for URLs)",
    )
    parser.add_argument(
        "--lang", "-l",
        dest="language",
        help="Output language for analysis (e.g., 'zh' for Chinese)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL_S,
        help=f"Seconds between status polls (default: {DEFAULT_POLL_INTERVAL_S})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help=f"Maximum seconds to wait for completion (default: {DEFAULT_TIMEOUT_S})",
    )
    parser.add_argument(
        "--llm-mode",
        choices=["external", "backend"],
        default="external",
        help="LLM mode: 'external' (default) lets AI editor provide the plan; 'backend' requires backend LLM config",
    )
    parser.add_argument(
        "--no-auto-start-backend",
        action="store_true",
        help="Do not auto-start backend when it is not running",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )
    
    args = parser.parse_args()
    
    try:
        result = analyze_video(
            source=args.source,
            title=args.title,
            output_language=args.language,
            llm_mode=args.llm_mode,
            auto_start_backend=not args.no_auto_start_backend,
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )
        
        if args.json:
            output = {
                "jobId": result.job_id,
                "projectId": result.project_id,
                "status": result.status,
                "error": result.error,
                "resultUrl": result.result_url,
                "frontendUrl": result.frontend_url,
                "planRequestUrl": result.plan_request_url,
            }
            print(json.dumps(output, indent=2))
        else:
            if result.status == "succeeded":
                print(f"\nAnalysis completed successfully!")
                print(f"Project ID: {result.project_id}")
                print(f"Result API: {result.result_url}")
                print(f"View in browser: {result.frontend_url}")
            elif result.status == "blocked":
                print("\nAnalysis is waiting for external AI plan (blocked).")
                if result.plan_request_url:
                    print(f"Plan request: {result.plan_request_url}")
                print("Next: use your AI editor to generate plan JSON and POST it to /api/v1/jobs/{jobId}/plan, then rerun polling.")
            else:
                print(f"\nAnalysis {result.status}.")
                if result.error:
                    print(f"Error: {result.error}")
                sys.exit(1)
    
    except KeyboardInterrupt:
        print("\nCancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
