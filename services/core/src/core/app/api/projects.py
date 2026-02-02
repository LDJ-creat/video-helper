import shutil

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.db.models.job import Job
from core.db.models.project import Project
from core.db.repositories.projects import get_project_by_id, list_projects_page
from core.db.session import get_db_session
from core.schemas.projects import DeleteProjectResponseDTO, ProjectDTO, ProjectsPageDTO
from core.storage.safe_paths import PathTraversalBlockedError, resolve_under_data_dir, validate_single_dir_name


router = APIRouter(tags=["projects"])


def _project_to_dto(project: Project) -> ProjectDTO:
    return ProjectDTO(
        projectId=project.project_id,
        title=project.title,
        sourceType=project.source_type,
        updatedAtMs=project.updated_at_ms,
        latestResultId=project.latest_result_id,
    )


@router.get("/projects", response_model=ProjectsPageDTO)
def list_projects(
    request: Request,
    limit: int = 50,
    cursor: str | None = None,
    session: Session = Depends(get_db_session),
):
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    projects, next_cursor = list_projects_page(session, limit=limit, cursor=cursor)
    items = [_project_to_dto(p) for p in projects]
    return ProjectsPageDTO(items=items, nextCursor=next_cursor)


@router.get("/projects/{project_id}", response_model=ProjectDTO)
def get_project(project_id: str, request: Request, session: Session = Depends(get_db_session)):
    project = get_project_by_id(session, project_id)
    if project is None:
        return JSONResponse(
            status_code=404,
            content=build_error_envelope(
                code=ErrorCode.PROJECT_NOT_FOUND,
                message="Project does not exist",
                details={"projectId": project_id},
                request_id=getattr(request.state, "request_id", None),
            ),
        )
    return _project_to_dto(project)


@router.delete("/projects/{project_id}", response_model=DeleteProjectResponseDTO)
def delete_project(project_id: str, request: Request, session: Session = Depends(get_db_session)):
    project = get_project_by_id(session, project_id)
    if project is None:
        return JSONResponse(
            status_code=404,
            content=build_error_envelope(
                code=ErrorCode.PROJECT_NOT_FOUND,
                message="Project does not exist",
                details={"projectId": project_id},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    # DB cascade (best-effort for current minimal schema)
    session.execute(delete(Job).where(Job.project_id == project_id))
    session.execute(delete(Project).where(Project.project_id == project_id))
    session.commit()

    # File cleanup: only allow DATA_DIR/<projectId>
    try:
        validate_single_dir_name(project_id)
        project_dir = resolve_under_data_dir(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)
    except PathTraversalBlockedError:
        return JSONResponse(
            status_code=400,
            content=build_error_envelope(
                code=ErrorCode.PATH_TRAVERSAL_BLOCKED,
                message="Unsafe project path",
                details={"projectId": project_id},
                request_id=getattr(request.state, "request_id", None),
            ),
        )
    except PermissionError as e:
        code = ErrorCode.FILESYSTEM_PERMISSION_DENIED
        if getattr(e, "winerror", None) == 32:
            code = ErrorCode.FILESYSTEM_BUSY
        return JSONResponse(
            status_code=500,
            content=build_error_envelope(
                code=code,
                message="Failed to delete project files",
                details={"projectId": project_id},
                request_id=getattr(request.state, "request_id", None),
            ),
        )
    except OSError:
        return JSONResponse(
            status_code=500,
            content=build_error_envelope(
                code=ErrorCode.FILESYSTEM_PERMISSION_DENIED,
                message="Failed to delete project files",
                details={"projectId": project_id},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    return DeleteProjectResponseDTO(ok=True)
