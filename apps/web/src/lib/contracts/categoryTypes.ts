export type Category = {
  categoryId: string;
  name: string;
  slug: string;
  isSystem: boolean;
  projectCount: number;
};

export type CategoriesListResponse = {
  items: Category[];
};

export type CreateCategoryRequest = {
  name: string;
};

export type UpdateCategoryRequest = {
  name: string;
};
