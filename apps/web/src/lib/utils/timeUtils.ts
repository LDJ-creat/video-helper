/**
 * 时间单位转换工具（ms ↔ seconds）
 * 后端使用毫秒（ms），HTML5 video 使用秒（seconds）
 */

/**
 * 毫秒转秒（用于播放器 seek）
 * @param ms - 毫秒数
 * @returns 秒数
 */
export function msToSeconds(ms: number): number {
    return ms / 1000;
}

/**
 * 秒转毫秒（用于保存时间点）
 * @param seconds - 秒数
 * @returns 毫秒数
 */
export function secondsToMs(seconds: number): number {
    return Math.round(seconds * 1000);
}

/**
 * 格式化时间显示（MM:SS 或 HH:MM:SS）
 * @param seconds - 秒数
 * @returns 格式化字符串，例如 "04:20" 或 "1:23:45"
 */
export function formatTime(seconds: number): string {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hrs > 0) {
        return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * 格式化时长显示（用于章节时长等）
 * @param startMs - 开始时间（毫秒）
 * @param endMs - 结束时间（毫秒）
 * @returns 格式化字符串，例如 "2分30秒"
 */
export function formatDuration(startMs: number, endMs: number): string {
    const durationSec = (endMs - startMs) / 1000;
    const mins = Math.floor(durationSec / 60);
    const secs = Math.floor(durationSec % 60);

    if (mins > 0) {
        return secs > 0 ? `${mins}分${secs}秒` : `${mins}分钟`;
    }
    return `${secs}秒`;
}
