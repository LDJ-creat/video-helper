import type { ErrorCode } from "./errorCodes";

export type ErrorEnvelope = {
  error: {
    code: ErrorCode | string;
    message: string;
    details?: unknown;
    requestId?: string;
  };
};
