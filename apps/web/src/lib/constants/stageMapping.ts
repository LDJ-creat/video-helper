import type { JobStage } from "../contracts/types";

// Stage name to display text mapping (Chinese)
// Reference: _bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md Section 1.3
export const STAGE_DISPLAY: Record<JobStage, string> = {
    ingest: "导入",
    transcribe: "转写",
    analyze: "分析",
    assemble_result: "组装结果",
    extract_keyframes: "提取关键帧",
};

export function getStageDisplay(stage: JobStage | undefined): string {
    if (!stage) return "未知阶段";
    return STAGE_DISPLAY[stage] || stage;
}
