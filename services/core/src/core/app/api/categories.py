from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.db.repositories.categories import (
    CategoryNameValidationError,
    count_projects_in_category,
    create_category,
    delete_category,
    ensure_default_category,
    get_category_by_id,
    list_categories,
    update_category_name,
)
from core.db.session import get_db_session
from core.schemas.categories import (
    CategoriesListDTO,
    CategoryDTO,
    CreateCategoryRequest,
    UpdateCategoryRequest,
)


router = APIRouter(tags=["categories"])


def _category_to_dto(category, project_count: int) -> CategoryDTO:
    return CategoryDTO(
        categoryId=category.category_id,
        name=category.name,
        slug=category.slug,
        isSystem=bool(category.is_system),
        projectCount=project_count,
    )


@router.get("/categories", response_model=CategoriesListDTO)
def list_categories_endpoint(session: Session = Depends(get_db_session)):
    ensure_default_category(session)
    session.commit()
    rows = list_categories(session)
    items = [_category_to_dto(cat, count) for cat, count in rows]
    return CategoriesListDTO(items=items)


@router.post("/categories", response_model=CategoryDTO, status_code=201)
def create_category_endpoint(
    request: Request,
    body: CreateCategoryRequest,
    session: Session = Depends(get_db_session),
):
    try:
        row = create_category(session, name=body.name)
        session.commit()
        return _category_to_dto(row, 0)
    except CategoryNameValidationError as e:
        if e.reason == "conflict":
            return JSONResponse(
                status_code=409,
                content=build_error_envelope(
                    code=ErrorCode.CATEGORY_NAME_CONFLICT,
                    message="Category name already exists",
                    details={"reason": e.reason},
                    request_id=getattr(request.state, "request_id", None),
                ),
            )
        status = 400
        return JSONResponse(
            status_code=status,
            content=build_error_envelope(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid category name",
                details={"reason": e.reason},
                request_id=getattr(request.state, "request_id", None),
            ),
        )


@router.patch("/categories/{category_id}", response_model=CategoryDTO)
def update_category_endpoint(
    category_id: str,
    request: Request,
    body: UpdateCategoryRequest,
    session: Session = Depends(get_db_session),
):
    category = get_category_by_id(session, category_id)
    if category is None:
        return JSONResponse(
            status_code=404,
            content=build_error_envelope(
                code=ErrorCode.CATEGORY_NOT_FOUND,
                message="Category does not exist",
                details={"categoryId": category_id},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    try:
        row = update_category_name(session, category, name=body.name)
        session.commit()
        count = count_projects_in_category(session, category_id)
        return _category_to_dto(row, count)
    except CategoryNameValidationError as e:
        if e.reason == "conflict":
            return JSONResponse(
                status_code=409,
                content=build_error_envelope(
                    code=ErrorCode.CATEGORY_NAME_CONFLICT,
                    message="Category name already exists",
                    details={"reason": e.reason},
                    request_id=getattr(request.state, "request_id", None),
                ),
            )
        return JSONResponse(
            status_code=400,
            content=build_error_envelope(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid category name",
                details={"reason": e.reason},
                request_id=getattr(request.state, "request_id", None),
            ),
        )


@router.delete("/categories/{category_id}")
def delete_category_endpoint(
    category_id: str,
    request: Request,
    session: Session = Depends(get_db_session),
):
    category = get_category_by_id(session, category_id)
    if category is None:
        return JSONResponse(
            status_code=404,
            content=build_error_envelope(
                code=ErrorCode.CATEGORY_NOT_FOUND,
                message="Category does not exist",
                details={"categoryId": category_id},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    if category.is_system:
        return JSONResponse(
            status_code=403,
            content=build_error_envelope(
                code=ErrorCode.CATEGORY_NOT_DELETABLE,
                message="System category cannot be deleted",
                details={"categoryId": category_id},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    project_count = count_projects_in_category(session, category_id)
    if project_count > 0:
        return JSONResponse(
            status_code=409,
            content=build_error_envelope(
                code=ErrorCode.CATEGORY_IN_USE,
                message="Category has projects assigned",
                details={"categoryId": category_id, "projectCount": project_count},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    delete_category(session, category)
    session.commit()
    return {"ok": True}
