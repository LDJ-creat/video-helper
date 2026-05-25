import shutil

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.db.models.job import Job
from core.db.models.project import Project
from core.db.repositories.categories import get_category_by_id, get_category_names_by_ids
from core.db.repositories.projects import (
    batch_update_project_categories,
    get_project_by_id,
    list_projects_page,
    update_project_category,
)
from core.db.session import get_db_session
from core.schemas.projects import (
    BatchUpdateCategoryRequest,
    BatchUpdateCategoryResponse,
    DeleteProjectResponseDTO,
    PatchProjectRequest,
    ProjectDTO,
    ProjectsPageDTO,
)
from core.storage.safe_paths import PathTraversalBlockedError, resolve_under_data_dir, validate_single_dir_name


router = APIRouter(tags=["projects"])

BATCH_CATEGORY_MAX = 100


def _get_latest_job_id(session: Session, project_id: str) -> str | None:
    """Return the job_id of the most-recently updated job for a project."""
    row = (
        session.execute(
            select(Job.job_id)
            .where(Job.project_id == project_id)
            .order_by(Job.updated_at_ms.desc())
            .limit(1)
        )
        .first()
    )
    return row[0] if row else None


def _project_to_dto(
    project: Project,
    latest_job_id: str | None = None,
    category_meta: dict[str, tuple[str, str]] | None = None,
) -> ProjectDTO:
    category_id = project.category_id
    category_name: str | None = None
    category_slug: str | None = None
    if category_id and category_meta and category_id in category_meta:
        category_name, category_slug = category_meta[category_id]

    return ProjectDTO(
        projectId=project.project_id,
        title=project.title,
        sourceType=project.source_type,
        updatedAtMs=project.updated_at_ms,
        latestResultId=project.latest_result_id,
        latestJobId=latest_job_id,
        categoryId=category_id,
        categoryName=category_name,
        categorySlug=category_slug,
    )


def _build_category_meta(session: Session, projects: list[Project]) -> dict[str, tuple[str, str]]:
    category_ids = {p.category_id for p in projects if p.category_id}
    return get_category_names_by_ids(session, category_ids)


@router.get("/projects", response_model=ProjectsPageDTO)
def list_projects(
    request: Request,
    limit: int = 50,
    cursor: str | None = None,
    categoryId: str | None = None,
    session: Session = Depends(get_db_session),
):
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    if categoryId:
        if get_category_by_id(session, categoryId) is None:
            return JSONResponse(
                status_code=404,
                content=build_error_envelope(
                    code=ErrorCode.CATEGORY_NOT_FOUND,
                    message="Category does not exist",
                    details={"categoryId": categoryId},
                    request_id=getattr(request.state, "request_id", None),
                ),
            )

    projects, next_cursor = list_projects_page(
        session, limit=limit, cursor=cursor, category_id=categoryId
    )
    project_ids = [p.project_id for p in projects]
    latest_job_map: dict[str, str] = {}
    if project_ids:
        rows = session.execute(
            select(Job.project_id, Job.job_id)
            .where(Job.project_id.in_(project_ids))
            .order_by(Job.updated_at_ms.desc())
        ).all()
        for pid, jid in rows:
            if pid not in latest_job_map:
                latest_job_map[pid] = jid

    category_meta = _build_category_meta(session, projects)
    items = [
        _project_to_dto(p, latest_job_map.get(p.project_id), category_meta) for p in projects
    ]
    return ProjectsPageDTO(items=items, nextCursor=next_cursor)


@router.patch("/projects/category-batch", response_model=BatchUpdateCategoryResponse)
def batch_update_project_category(
    request: Request,
    body: BatchUpdateCategoryRequest,
    session: Session = Depends(get_db_session),
):
    if len(body.projectIds) > BATCH_CATEGORY_MAX:
        return JSONResponse(
            status_code=400,
            content=build_error_envelope(
                code=ErrorCode.VALIDATION_ERROR,
                message="Too many project IDs",
                details={"max": BATCH_CATEGORY_MAX, "got": len(body.projectIds)},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    category = get_category_by_id(session, body.categoryId)
    if category is None:
        return JSONResponse(
            status_code=404,
            content=build_error_envelope(
                code=ErrorCode.CATEGORY_NOT_FOUND,
                message="Category does not exist",
                details={"categoryId": body.categoryId},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    updated, failed = batch_update_project_categories(
        session,
        project_ids=body.projectIds,
        category_id=body.categoryId,
    )
    session.commit()
    return BatchUpdateCategoryResponse(updated=updated, failed=failed)


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
    latest_job_id = _get_latest_job_id(session, project_id)
    category_meta = _build_category_meta(session, [project])
    return _project_to_dto(project, latest_job_id, category_meta)


@router.patch("/projects/{project_id}", response_model=ProjectDTO)
def patch_project(
    project_id: str,
    request: Request,
    body: PatchProjectRequest,
    session: Session = Depends(get_db_session),
):
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

    category = get_category_by_id(session, body.categoryId)
    if category is None:
        return JSONResponse(
            status_code=404,
            content=build_error_envelope(
                code=ErrorCode.CATEGORY_NOT_FOUND,
                message="Category does not exist",
                details={"categoryId": body.categoryId},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    update_project_category(session, project, category_id=body.categoryId)
    session.commit()
    latest_job_id = _get_latest_job_id(session, project_id)
    category_meta = _build_category_meta(session, [project])
    return _project_to_dto(project, latest_job_id, category_meta)


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

    session.execute(delete(Job).where(Job.project_id == project_id))
    session.execute(delete(Project).where(Project.project_id == project_id))
    session.commit()

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
