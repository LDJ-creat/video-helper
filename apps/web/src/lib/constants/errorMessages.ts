import { ERROR_CODES } from "../contracts/errorCodes";

type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];

// Error code to user-friendly action suggestion mapping
export const ERROR_SUGGESTIONS: Record<ErrorCode, string> = {
    // Input validation
    [ERROR_CODES.VALIDATION_ERROR]: "输入数据不合法，请检查后重试",
    [ERROR_CODES.UNSUPPORTED_SOURCE_TYPE]: "不支持的视频来源类型",
    [ERROR_CODES.INVALID_SOURCE_URL]: "视频 URL 格式不正确或无法访问",

    // Not found
    [ERROR_CODES.PROJECT_NOT_FOUND]: "项目不存在",
    [ERROR_CODES.JOB_NOT_FOUND]: "任务不存在",
    [ERROR_CODES.ASSET_NOT_FOUND]: "资源不存在",
    [ERROR_CODES.RESULT_NOT_FOUND]: "分析结果不存在",

    // Missing dependencies
    [ERROR_CODES.FFMPEG_MISSING]: "缺少 ffmpeg 依赖，请安装后重试",
    [ERROR_CODES.YTDLP_MISSING]: "缺少 yt-dlp 依赖，请安装后重试",

    // Job lifecycle
    [ERROR_CODES.JOB_STAGE_FAILED]: "任务执行失败，请查看日志了解详情",
    [ERROR_CODES.JOB_CANCELED]: "任务已取消",
    [ERROR_CODES.JOB_NOT_CANCELLABLE]: "该任务无法取消",

    // Resources
    [ERROR_CODES.RESOURCE_EXHAUSTED]: "系统资源不足，请稍后重试",

    // Auth
    [ERROR_CODES.UNAUTHORIZED]: "未授权，请先登录",
    [ERROR_CODES.FORBIDDEN]: "无权访问该资源",

    // Security
    [ERROR_CODES.PATH_TRAVERSAL_BLOCKED]: "非法路径访问被阻止",
};

export function getErrorSuggestion(errorCode: string): string {
    return ERROR_SUGGESTIONS[errorCode as ErrorCode] || "发生未知错误";
}
