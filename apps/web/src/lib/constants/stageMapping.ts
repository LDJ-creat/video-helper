import type { JobStage } from "../contracts/types";

/** Stable public stages returned by GET /jobs/{id} (see core/contracts/stages.py). */
export type PublicStage =
    | "ingest"
    | "transcribe"
    | "analyze"
    | "extract_keyframes"
    | "assemble_result";

export const PUBLIC_STAGES_ORDER: readonly PublicStage[] = [
    "ingest",
    "transcribe",
    "analyze",
    "extract_keyframes",
    "assemble_result",
] as const;

export const PUBLIC_STAGE_DISPLAY: Record<PublicStage, string> = {
    ingest: "导入",
    transcribe: "转写",
    analyze: "分析",
    extract_keyframes: "提取关键帧",
    assemble_result: "生成结果",
};

/** i18n keys under Results.progress.stages.* */
export const PUBLIC_STAGE_I18N_KEY: Record<PublicStage, string> = {
    ingest: "ingest",
    transcribe: "transcribe",
    analyze: "analyze",
    extract_keyframes: "extractKeyframes",
    assemble_result: "assembleResult",
};

// Internal worker stages (logs / legacy)
export const STAGE_DISPLAY: Record<JobStage, string> = {
    ingest: "导入",
    transcribe: "转写",
    analyze: "分析",
    speech_to_text: "语音转写",
    chunk_summaries: "分段总结",
    plan: "生成计划",
    assemble_result: "组装结果",
    extract_keyframes: "提取关键帧",
    keyframes: "关键帧",
    keyframe_verify: "关键帧校验",
};

export function isPublicStage(stage: string): stage is PublicStage {
    return (PUBLIC_STAGES_ORDER as readonly string[]).includes(stage);
}

export function getPublicStageDisplay(stage: string | undefined): string {
    if (!stage) return "准备";
    if (isPublicStage(stage)) return PUBLIC_STAGE_DISPLAY[stage];
    return STAGE_DISPLAY[stage as JobStage] || stage;
}

export function getPublicStageIndex(stage: string | undefined): number {
    if (!stage || !isPublicStage(stage)) return 0;
    const idx = PUBLIC_STAGES_ORDER.indexOf(stage);
    return idx >= 0 ? idx : 0;
}

export function getStageDisplay(stage: JobStage | undefined): string {
    if (!stage) return "未知阶段";
    return STAGE_DISPLAY[stage] || stage;
}
