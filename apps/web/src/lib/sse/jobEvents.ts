export type JobEventType = "heartbeat" | "progress" | "log" | "state";

export type JobEvent = {
  eventId: string;
  tsMs: number;
  jobId: string;
  projectId: string;
  stage: string;
  type: JobEventType;
  progress?: number;
  message?: string;
};
