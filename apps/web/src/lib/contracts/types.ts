// Job status and stage types (aligned with API contract)
export type JobStatus = "queued" | "running" | "blocked" | "succeeded" | "failed" | "canceled";

export type JobStage =
  | "ingest"
  | "transcribe"
  | "analyze"
  | "assemble_result"
  | "extract_keyframes";

export type Job = {
  jobId: string;
  projectId: string;
  type: string;
  status: JobStatus;
  stage?: JobStage;
  progress?: number; // 0..1
  error?: {
    code: string;
    message: string;
    details?: unknown;
  } | null;
  updatedAtMs: number;
  createdAtMs?: number;
  startedAtMs?: number;
  finishedAtMs?: number;
};

export type LogEntry = {
  tsMs: number;
  level: "INFO" | "WARN" | "ERROR" | "DEBUG";
  message: string;
  stage?: JobStage;
};

export type LogsResponse = {
  items: LogEntry[];
  nextCursor: string | null;
};
