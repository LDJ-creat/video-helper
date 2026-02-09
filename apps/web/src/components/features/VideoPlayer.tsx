
import { forwardRef, useImperativeHandle, useRef, useState, useEffect } from "react";
import { msToSeconds, formatTime } from "@/lib/utils/timeUtils";

export type VideoPlayerRef = {
    seekTo: (timeMs: number) => void;
    play: () => void;
    pause: () => void;
    getCurrentTime: () => number; // 返回毫秒
    getVideoElement: () => HTMLVideoElement | null;
};

type VideoPlayerProps = {
    src?: string | null;
    className?: string;
    onTimeUpdate?: (currentTimeMs: number) => void;
};

export const VideoPlayer = forwardRef<VideoPlayerRef, VideoPlayerProps>(
    ({ src, className = "", onTimeUpdate }, ref) => {
        const videoRef = useRef<HTMLVideoElement>(null);
        const [isPlaying, setIsPlaying] = useState(false);
        const [currentTime, setCurrentTime] = useState(0);
        const [duration, setDuration] = useState(0);
        const [volume, setVolume] = useState(1);
        const [playbackRate, setPlaybackRate] = useState(1);
        const [showSpeedMenu, setShowSpeedMenu] = useState(false);

        // 暴露控制方法给父组件
        useImperativeHandle(ref, () => ({
            seekTo: (timeMs: number) => {
                if (videoRef.current) {
                    videoRef.current.currentTime = msToSeconds(timeMs);
                }
            },
            play: () => {
                videoRef.current?.play();
            },
            pause: () => {
                videoRef.current?.pause();
            },
            getCurrentTime: () => {
                return videoRef.current ? Math.round(videoRef.current.currentTime * 1000) : 0;
            },
            getVideoElement: () => videoRef.current,
        }));

        // 处理播放/暂停
        const handlePlayPause = (e?: React.MouseEvent) => {
            e?.stopPropagation();
            if (!videoRef.current) return;
            if (isPlaying) {
                videoRef.current.pause();
            } else {
                videoRef.current.play();
            }
        };

        // 快进/快退
        const handleSkip = (seconds: number) => {
            if (!videoRef.current) return;
            videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime + seconds);
        };

        // 进度条拖动
        const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
            if (!videoRef.current) return;
            const time = parseFloat(e.target.value);
            videoRef.current.currentTime = time;
            setCurrentTime(time);
        };

        // 音量调整
        const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
            if (!videoRef.current) return;
            const vol = parseFloat(e.target.value);
            videoRef.current.volume = vol;
            setVolume(vol);
        };

        // 倍速调整
        const handleSpeedChange = (rate: number) => {
            if (!videoRef.current) return;
            videoRef.current.playbackRate = rate;
            setPlaybackRate(rate);
            setShowSpeedMenu(false);
        };

        useEffect(() => {
            const video = videoRef.current;
            if (!video) return;

            const handlePlay = () => setIsPlaying(true);
            const handlePause = () => setIsPlaying(false);
            const handleTimeUpdate = () => {
                setCurrentTime(video.currentTime);
                onTimeUpdate?.(Math.round(video.currentTime * 1000));
            };
            const handleLoadedMetadata = () => {
                setDuration(video.duration);
            };
            const handleRateChange = () => {
                setPlaybackRate(video.playbackRate);
            };

            video.addEventListener("play", handlePlay);
            video.addEventListener("pause", handlePause);
            video.addEventListener("timeupdate", handleTimeUpdate);
            video.addEventListener("loadedmetadata", handleLoadedMetadata);
            video.addEventListener("ratechange", handleRateChange);

            return () => {
                video.removeEventListener("play", handlePlay);
                video.removeEventListener("pause", handlePause);
                video.removeEventListener("timeupdate", handleTimeUpdate);
                video.removeEventListener("loadedmetadata", handleLoadedMetadata);
                video.removeEventListener("ratechange", handleRateChange);
            };
        }, [onTimeUpdate]);

        const safeSrc = (src || "").trim();

        return (
            <div className={`bg-black rounded-lg overflow-hidden flex flex-col group ${className}`}>
                {/* 视频元素容器 - 点击区域 */}
                <div
                    className="relative flex-1 bg-black flex items-center justify-center cursor-pointer"
                    onClick={handlePlayPause}
                >
                    {safeSrc ? (
                        <video
                            ref={videoRef}
                            src={safeSrc}
                            className="w-full h-full max-h-[80vh]"
                            preload="metadata"
                            controls={false} // 使用自定义控件
                        />
                    ) : (
                        <div className="w-full aspect-video flex items-center justify-center bg-black text-stone-300">
                            <div className="text-center px-6">
                                <div className="text-sm font-medium">暂无可播放视频资源</div>
                                <div className="text-xs text-stone-400 mt-1">当前结果仅包含关键帧截图等资源</div>
                            </div>
                        </div>
                    )}

                    {/* 居中播放/暂停动画/图标 (可选，暂不实现复杂动画，仅作为点击反馈区域) */}
                </div>

                {/* 控制栏 */}
                <div
                    className="bg-stone-900/90 backdrop-blur px-4 py-3 space-y-2 shrink-0 transition-opacity duration-300"
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* 进度条 */}
                    <div className="flex items-center gap-3">
                        <span className="text-xs font-mono text-stone-400 min-w-[40px] text-right">{formatTime(currentTime)}</span>
                        <input
                            type="range"
                            min="0"
                            max={duration || 0}
                            step="0.1"
                            value={currentTime}
                            onChange={handleSeek}
                            className="flex-1 h-1 bg-stone-700 rounded-lg appearance-none cursor-pointer accent-orange-600 hover:accent-orange-500 hover:h-1.5 transition-all"
                        />
                        <span className="text-xs font-mono text-stone-400 min-w-[40px]">{formatTime(duration)}</span>
                    </div>

                    {/* 控制按钮行 */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            {/* 播放/暂停 */}
                            <button
                                onClick={(e) => handlePlayPause(e)}
                                className="text-white hover:text-orange-500 transition-colors"
                                disabled={!safeSrc}
                                title={isPlaying ? "暂停 (Space)" : "播放 (Space)"}
                            >
                                {isPlaying ? (
                                    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" /></svg>
                                ) : (
                                    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                                )}
                            </button>

                            {/* 快退/快进 */}
                            <div className="flex items-center gap-2 text-stone-400">
                                <button onClick={() => handleSkip(-10)} className="hover:text-white transition-colors" title="后退 10 秒">
                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8l-5.333 4zM4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8l-5.334 4z" /></svg>
                                </button>
                                <button onClick={() => handleSkip(10)} className="hover:text-white transition-colors" title="前进 10 秒">
                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.933 12.8a1 1 0 000-1.6L6.6 7.2A1 1 0 005 8v8a1 1 0 001.6.8l5.333-4zM19.933 12.8a1 1 0 000-1.6l-5.333-4A1 1 0 0013 8v8a1 1 0 001.6.8l5.333-4z" /></svg>
                                </button>
                            </div>

                            {/* 音量 */}
                            <div className="flex items-center gap-2 group/vol">
                                <button
                                    onClick={() => {
                                        if (!videoRef.current) return;
                                        const newVol = volume === 0 ? 1 : 0;
                                        videoRef.current.volume = newVol;
                                        setVolume(newVol);
                                    }}
                                    className="text-stone-400 hover:text-white transition-colors"
                                >
                                    {volume === 0 ? (
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" /></svg>
                                    ) : (
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" /></svg>
                                    )}
                                </button>
                                <div className="w-0 overflow-hidden group-hover/vol:w-20 transition-all duration-300">
                                    <input
                                        type="range"
                                        min="0"
                                        max="1"
                                        step="0.05"
                                        value={volume}
                                        onChange={handleVolumeChange}
                                        className="w-20 h-1 bg-stone-700 rounded-lg appearance-none cursor-pointer accent-orange-600"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* 右侧控制：倍速 */}
                        <div className="relative">
                            <button
                                onClick={() => setShowSpeedMenu(!showSpeedMenu)}
                                className="text-xs font-medium text-stone-300 hover:text-white bg-stone-800 hover:bg-stone-700 px-2 py-1 rounded transition-colors min-w-[3rem]"
                            >
                                {playbackRate}x
                            </button>
                            {showSpeedMenu && (
                                <div className="absolute bottom-full right-0 mb-2 bg-stone-800 rounded-lg shadow-xl border border-stone-700 py-1 flex flex-col min-w-[5rem] overflow-hidden z-20">
                                    {[0.5, 1.0, 1.25, 1.5, 2.0].map((rate) => (
                                        <button
                                            key={rate}
                                            onClick={() => handleSpeedChange(rate)}
                                            className={`px-3 py-1.5 text-xs text-left hover:bg-stone-700 transition-colors ${playbackRate === rate ? 'text-orange-500 font-bold' : 'text-stone-300'}`}
                                        >
                                            {rate}x
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        );
    }
);

VideoPlayer.displayName = "VideoPlayer";
