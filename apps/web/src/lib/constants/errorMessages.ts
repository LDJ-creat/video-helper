import { ERROR_CODES } from "../contracts/errorCodes";
import type { Job } from "../contracts/types";

type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];

export type JobErrorPayload = NonNullable<Job["error"]>;

export type ErrorPresentation = {
    summary: string;
    suggestion: string;
    technical: {
        httpStatus?: number | string;
        outputTail?: string;
        raw: unknown;
    };
};

type TranslateFn = (key: string, values?: Record<string, string | number>) => string;

// Error code to user-friendly action suggestion mapping (legacy fallback)
export const ERROR_SUGGESTIONS: Record<ErrorCode, string> = {
    [ERROR_CODES.VALIDATION_ERROR]: "输入数据不合法，请检查后重试",
    [ERROR_CODES.UNSUPPORTED_SOURCE_TYPE]: "不支持的视频来源类型",
    [ERROR_CODES.INVALID_SOURCE_URL]: "视频 URL 格式不正确或无法访问",
    [ERROR_CODES.PROJECT_NOT_FOUND]: "项目不存在",
    [ERROR_CODES.JOB_NOT_FOUND]: "任务不存在",
    [ERROR_CODES.ASSET_NOT_FOUND]: "资源不存在",
    [ERROR_CODES.RESULT_NOT_FOUND]: "分析结果不存在",
    [ERROR_CODES.FFMPEG_MISSING]: "缺少 ffmpeg 依赖，请安装后重试",
    [ERROR_CODES.YTDLP_MISSING]: "缺少 yt-dlp 依赖，请安装后重试",
    [ERROR_CODES.JOB_STAGE_FAILED]: "任务执行失败，请查看日志了解详情",
    [ERROR_CODES.JOB_CANCELED]: "任务已取消",
    [ERROR_CODES.JOB_NOT_CANCELLABLE]: "该任务无法取消",
    [ERROR_CODES.RESOURCE_EXHAUSTED]: "系统资源不足，请稍后重试",
    [ERROR_CODES.UNAUTHORIZED]: "未授权，请先登录",
    [ERROR_CODES.FORBIDDEN]: "无权访问该资源",
    [ERROR_CODES.PATH_TRAVERSAL_BLOCKED]: "非法路径访问被阻止",
};

export function getErrorSuggestion(errorCode: string): string {
    return ERROR_SUGGESTIONS[errorCode as ErrorCode] || "发生未知错误，请稍后重试";
}

function detailsRecord(details: unknown): Record<string, unknown> | null {
    if (details && typeof details === "object") return details as Record<string, unknown>;
    return null;
}

/**
 * Resolve user-facing error copy using Results.progress.error.* i18n keys.
 */
export function resolveErrorPresentation(error: JobErrorPayload, t: TranslateFn): ErrorPresentation {
    const detailsObj = detailsRecord(error.details);
    const reason = typeof detailsObj?.reason === "string" ? detailsObj.reason : "";
    const step = typeof detailsObj?.step === "string" ? detailsObj.step : "";

    let summary = error.message?.trim() || t("error.genericSummary");
    let suggestion = getErrorSuggestion(error.code);

    if (error.code === ERROR_CODES.JOB_STAGE_FAILED) {
        if (reason === "timeout" && step === "download") {
            summary = t("error.timeoutDownload.summary");
            suggestion = t("error.timeoutDownload.suggestion");
        } else if (reason === "timeout") {
            summary = t("error.timeout.summary");
            suggestion = t("error.timeout.suggestion");
        } else if (reason === "content_blocked") {
            summary = t("error.contentBlocked.summary");
            suggestion = t("error.contentBlocked.suggestion");
        } else {
            summary = error.message?.trim() || t("error.stageFailed.summary");
            suggestion = t("error.stageFailed.suggestion");
        }
    } else if (error.code === ERROR_CODES.INVALID_SOURCE_URL) {
        summary = t("error.invalidUrl.summary");
        suggestion = t("error.invalidUrl.suggestion");
    } else if (error.code === ERROR_CODES.FFMPEG_MISSING) {
        summary = t("error.ffmpegMissing.summary");
        suggestion = t("error.ffmpegMissing.suggestion");
    } else if (error.code === ERROR_CODES.YTDLP_MISSING) {
        summary = t("error.ytdlpMissing.summary");
        suggestion = t("error.ytdlpMissing.suggestion");
    } else if (error.code === ERROR_CODES.RESOURCE_EXHAUSTED) {
        summary = t("error.resourceExhausted.summary");
        suggestion = t("error.resourceExhausted.suggestion");
    } else if (error.code === ERROR_CODES.JOB_CANCELED) {
        summary = t("error.canceled.summary");
        suggestion = t("error.canceled.suggestion");
    } else {
        const key = `error.codes.${error.code}`;
        try {
            const localized = t(key);
            if (localized !== key) suggestion = localized;
        } catch {
            // use fallback suggestion
        }
    }

    const httpStatus = detailsObj?.httpStatus;
    const outputTail = detailsObj?.outputTail;

    return {
        summary,
        suggestion,
        technical: {
            httpStatus: httpStatus != null ? (httpStatus as number | string) : undefined,
            outputTail: typeof outputTail === "string" ? outputTail : undefined,
            raw: error,
        },
    };
}
