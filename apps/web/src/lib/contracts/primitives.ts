export type UUID = string;
export type TsMs = number;

export type CursorPage<T> = {
  items: T[];
  nextCursor: string | null;
};
