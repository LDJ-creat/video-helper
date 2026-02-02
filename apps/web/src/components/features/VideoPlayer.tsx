"use client";

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
    src: string;
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
        const handlePlayPause = () => {
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

            video.addEventListener("play", handlePlay);
            video.addEventListener("pause", handlePause);
            video.addEventListener("timeupdate", handleTimeUpdate);
            video.addEventListener("loadedmetadata", handleLoadedMetadata);

            return () => {
                video.removeEventListener("play", handlePlay);
                video.removeEventListener("pause", handlePause);
                video.removeEventListener("timeupdate", handleTimeUpdate);
                video.removeEventListener("loadedmetadata", handleLoadedMetadata);
            };
        }, [onTimeUpdate]);

        return (
            <div className={`bg-black rounded-lg overflow-hidden ${className}`}>
                {/* 视频元素 */}
                <video
                    ref={videoRef}
                    src={src}
                    className="w-full aspect-video"
                    preload="metadata"
                />

                {/* 控制栏 */}
                <div className="bg-stone-900 px-4 py-3 space-y-2">
                    {/* 进度条 */}
                    <input
                        type="range"
                        min="0"
                        max={duration || 0}
                        step="0.1"
                        value={currentTime}
                        onChange={handleSeek}
                        className="w-full h-1 bg-stone-700 rounded-lg appearance-none cursor-pointer accent-orange-600"
                    />

                    {/* 控制按钮 */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            {/* 快退 10s */}
                            <button
                                onClick={() => handleSkip(-10)}
                                className="text-white hover:text-orange-400 transition-colors"
                                title="后退 10 秒"
                            >
                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8l-5.333 4zM4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8l-5.334 4z" />
                                </svg>
                            </button>

                            {/* 播放/暂停 */}
                            <button
                                onClick={handlePlayPause}
                                className="text-white hover:text-orange-400 transition-colors"
                            >
                                {isPlaying ? (
                                    <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                                    </svg>
                                ) : (
                                    <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M8 5v14l11-7z" />
                                    </svg>
                                )}
                            </button>

                            {/* 快进 10s */}
                            <button
                                onClick={() => handleSkip(10)}
                                className="text-white hover:text-orange-400 transition-colors"
                                title="前进 10 秒"
                            >
                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.933 12.8a1 1 0 000-1.6L6.6 7.2A1 1 0 005 8v8a1 1 0 001.6.8l5.333-4zM19.933 12.8a1 1 0 000-1.6l-5.333-4A1 1 0 0013 8v8a1 1 0 001.6.8l5.333-4z" />
                                </svg>
                            </button>

                            {/* 时间显示 */}
                            <span className="text-xs font-mono text-stone-400 ml-2">
                                {formatTime(currentTime)} / {formatTime(duration)}
                            </span>
                        </div>

                        {/* 音量控制 */}
                        <div className="flex items-center gap-2">
                            <svg className="w-5 h-5 text-stone-400" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
                            </svg>
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.1"
                                value={volume}
                                onChange={handleVolumeChange}
                                className="w-20 h-1 bg-stone-700 rounded-lg appearance-none cursor-pointer accent-orange-600"
                            />
                        </div>
                    </div>
                </div>
            </div>
        );
    }
);

VideoPlayer.displayName = "VideoPlayer";
