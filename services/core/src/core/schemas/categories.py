from __future__ import annotations

from pydantic import BaseModel


class CategoryDTO(BaseModel):
    categoryId: str
    name: str
    slug: str
    isSystem: bool
    projectCount: int


class CategoriesListDTO(BaseModel):
    items: list[CategoryDTO]


class CreateCategoryRequest(BaseModel):
    name: str


class UpdateCategoryRequest(BaseModel):
    name: str
