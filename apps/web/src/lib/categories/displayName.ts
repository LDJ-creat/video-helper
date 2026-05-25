import type { Category } from "../contracts/categoryTypes";

/** Display label for a category; system default uses i18n key at call site. */
export function getCategoryDisplayName(
  category: Pick<Category, "name" | "slug">,
  defaultLabel: string
): string {
  if (category.slug === "default") {
    return defaultLabel;
  }
  return category.name;
}

export function getProjectCategoryDisplayName(
  project: { categoryName?: string; categorySlug?: string },
  defaultLabel: string
): string | null {
  if (!project.categorySlug && !project.categoryName) {
    return null;
  }
  if (project.categorySlug === "default") {
    return defaultLabel;
  }
  return project.categoryName ?? defaultLabel;
}
