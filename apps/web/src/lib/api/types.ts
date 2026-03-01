export type CursorPage<T> = {
  items: T[];
  nextCursor: string | null;
};
