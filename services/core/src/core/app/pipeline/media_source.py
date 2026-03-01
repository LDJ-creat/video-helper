from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.db.models.project import Project
from core.db.session import get_data_dir
from core.storage.safe_paths import PathTraversalBlockedError, resolve_under_data_dir


@dataclass(frozen=True)
class MediaSourcePlan:
	"""Plan how to obtain a media file for a project.

	- For uploads, the media is already present at project.source_path.
	- For URL sources, the media may need to be downloaded (yt-dlp) to a stable
	  location under DATA_DIR/<projectId>/downloads/.
	"""

	kind: str  # "upload" | "url"
	source_type: str
	project_id: str
	source_url: str | None
	media_rel_path: str | None
	media_abs_path: Path | None
	requires_download: bool
	download_dir_abs: Path | None


_URL_SOURCE_TYPES: set[str] = {"youtube", "bilibili", "url"}


def plan_media_source(project: Project) -> MediaSourcePlan:
	"""Return a plan for locating/downloading the project's media file.

	Raises ValueError / PathTraversalBlockedError when the project source fields
	are inconsistent.
	"""

	source_type = (project.source_type or "").strip().lower()
	project_id = project.project_id

	if source_type == "upload":
		rel = project.source_path
		if not isinstance(rel, str) or not rel:
			raise ValueError("upload project requires source_path")
		abs_path = resolve_under_data_dir(rel)
		return MediaSourcePlan(
			kind="upload",
			source_type=source_type,
			project_id=project_id,
			source_url=None,
			media_rel_path=rel,
			media_abs_path=abs_path,
			requires_download=False,
			download_dir_abs=None,
		)

	if source_type in _URL_SOURCE_TYPES:
		url = project.source_url
		if not isinstance(url, str) or not url:
			raise ValueError("url project requires source_url")

		# If previously downloaded, we can reuse it.
		rel = project.source_path
		abs_path: Path | None = None
		requires_download = True
		if isinstance(rel, str) and rel:
			try:
				abs_path = resolve_under_data_dir(rel)
				requires_download = False
			except PathTraversalBlockedError:
				# Treat invalid path as missing; force re-download.
				abs_path = None
				requires_download = True
				rel = None

		download_dir = (get_data_dir() / project_id / "downloads").resolve()
		# Ensure download_dir remains under DATA_DIR.
		if not download_dir.is_relative_to(get_data_dir().resolve()):
			raise PathTraversalBlockedError("download_dir escapes DATA_DIR")

		return MediaSourcePlan(
			kind="url",
			source_type=source_type,
			project_id=project_id,
			source_url=url,
			media_rel_path=rel,
			media_abs_path=abs_path,
			requires_download=requires_download,
			download_dir_abs=download_dir,
		)

	raise ValueError("unsupported project.source_type")
