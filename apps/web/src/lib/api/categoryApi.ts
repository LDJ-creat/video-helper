import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type {
  CategoriesListResponse,
  Category,
  CreateCategoryRequest,
  UpdateCategoryRequest,
} from "../contracts/categoryTypes";
import { config } from "../config";

export async function fetchCategories(): Promise<CategoriesListResponse> {
  const url = `${config.apiBaseUrl}${endpoints.categories()}`;
  return apiFetch<CategoriesListResponse>(url);
}

export async function createCategory(data: CreateCategoryRequest): Promise<Category> {
  const url = `${config.apiBaseUrl}${endpoints.categories()}`;
  return apiFetch<Category>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateCategory(
  categoryId: string,
  data: UpdateCategoryRequest
): Promise<Category> {
  const url = `${config.apiBaseUrl}${endpoints.category(categoryId)}`;
  return apiFetch<Category>(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteCategory(categoryId: string): Promise<void> {
  const url = `${config.apiBaseUrl}${endpoints.category(categoryId)}`;
  await apiFetch<void>(url, { method: "DELETE" });
}
