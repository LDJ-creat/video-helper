import { useRef, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { formatTime } from "@/lib/utils/timeUtils";

type FloatingPlayerProps = {
    videoElement: HTMLVideoElement | null;
    isVisible: boolean;
    onExpand: () => void;
    onClose: () => void;
};

export function FloatingPlayer({ videoElement, isVisible, onExpand, onClose }: FloatingPlayerProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [isMounted, setIsMounted] = useState(false);

    // State for UI sync
    const [isPlaying, setIsPlaying] = useState(false);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [showSpeedMenu, setShowSpeedMenu] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);

    // Layout state
    const [position, setPosition] = useState({ x: window.innerWidth - 440, y: 100 });
    const [size, setSize] = useState({ width: 400 });
    const [isDragging, setIsDragging] = useState(false);
    const [isResizing, setIsResizing] = useState(false);

    const dragStartPos = useRef({ x: 0, y: 0 });
    const resizeStartPos = useRef({ x: 0, width: 0 });

    // Drag handlers
    const handleMouseDown = (e: React.MouseEvent) => {
        if ((e.target as HTMLElement).closest('.drag-handle')) {
            setIsDragging(true);
            dragStartPos.current = {
                x: e.clientX - position.x,
                y: e.clientY - position.y
            };
        }
    };

    const handleResizeMouseDown = (e: React.MouseEvent) => {
        e.stopPropagation();
        e.preventDefault();
        setIsResizing(true);
        resizeStartPos.current = {
            x: e.clientX,
            width: size.width
        };
    };

    // Setup drag and resize event listeners
    useEffect(() => {
        const handleGlobalMouseMove = (e: MouseEvent) => {
            if (isDragging) {
                setPosition({
                    x: e.clientX - dragStartPos.current.x,
                    y: e.clientY - dragStartPos.current.y
                });
            } else if (isResizing) {
                const deltaX = e.clientX - resizeStartPos.current.x;
                const newWidth = Math.max(280, Math.min(800, resizeStartPos.current.width + deltaX));
                setSize({ width: newWidth });
            }
        };

        const handleGlobalMouseUp = () => {
            if (isDragging) setIsDragging(false);
            if (isResizing) setIsResizing(false);
        };

        if (isDragging || isResizing) {
            document.addEventListener('mousemove', handleGlobalMouseMove);
            document.addEventListener('mouseup', handleGlobalMouseUp);
            return () => {
                document.removeEventListener('mousemove', handleGlobalMouseMove);
                document.removeEventListener('mouseup', handleGlobalMouseUp);
            };
        }
    }, [isDragging, isResizing, position, size]);

    useEffect(() => {
        setIsMounted(true);
    }, []);

    // Control main video playback to prevent audio overlap
    useEffect(() => {
        if (!videoElement) return;

        if (isVisible) {
            // FloatingPlayer is visible - mute the main video to avoid audio overlap
            // Store the original muted state and playing state
            const wasPlaying = !videoElement.paused;
            const wasMuted = videoElement.muted;

            videoElement.dataset.wasPlayingBeforeFloat = String(wasPlaying);
            videoElement.dataset.wasMutedBeforeFloat = String(wasMuted);

            // Mute the main video so even if it plays, there's no audio
            videoElement.muted = true;
        } else {
            // FloatingPlayer is hidden - restore main video state
            const wasPlaying = videoElement.dataset.wasPlayingBeforeFloat === 'true';
            const wasMuted = videoElement.dataset.wasMutedBeforeFloat === 'true';

            // Restore muted state
            videoElement.muted = wasMuted;

            // Resume playing if it was playing before
            if (wasPlaying && videoElement.paused) {
                videoElement.play().catch(() => { });
            }
        }
    }, [isVisible, videoElement]);

    useEffect(() => {
        if (!isVisible || !videoElement) return;

        // Sync initial state
        setIsPlaying(!videoElement.paused);
        setPlaybackRate(videoElement.playbackRate);
        setCurrentTime(videoElement.currentTime);
        setDuration(videoElement.duration || 0);

        // Add listeners to sync UI state
        const handlePlay = () => setIsPlaying(true);
        const handlePause = () => setIsPlaying(false);
        const handleRateChange = () => setPlaybackRate(videoElement.playbackRate);
        const handleTimeUpdate = () => {
            setCurrentTime(videoElement.currentTime);
            if (videoElement.duration) setDuration(videoElement.duration);
        };
        const handleLoadedMetadata = () => {
            if (videoElement.duration) setDuration(videoElement.duration);
        };

        videoElement.addEventListener("play", handlePlay);
        videoElement.addEventListener("pause", handlePause);
        videoElement.addEventListener("ratechange", handleRateChange);
        videoElement.addEventListener("timeupdate", handleTimeUpdate);
        videoElement.addEventListener("loadedmetadata", handleLoadedMetadata);

        return () => {
            videoElement.removeEventListener("play", handlePlay);
            videoElement.removeEventListener("pause", handlePause);
            videoElement.removeEventListener("ratechange", handleRateChange);
            videoElement.removeEventListener("timeupdate", handleTimeUpdate);
            videoElement.removeEventListener("loadedmetadata", handleLoadedMetadata);
        };
    }, [isVisible, videoElement]);

    const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
        e.stopPropagation();
        if (!videoElement) return;
        const time = parseFloat(e.target.value);
        videoElement.currentTime = time;
        setCurrentTime(time);
    };

    const handlePlayPause = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!videoElement) return;
        if (videoElement.paused) {
            videoElement.play();
        } else {
            videoElement.pause();
        }
    };

    const handleSpeedChange = (rate: number, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!videoElement) return;
        videoElement.playbackRate = rate;
        setShowSpeedMenu(false);
    }

    if (!isMounted || !isVisible || !videoElement) {
        return null;
    }

    const floatingContent = (
        <div
            ref={containerRef}
            className="fixed z-[9999] shadow-2xl shadow-stone-900/50 rounded-lg overflow-hidden border border-stone-700 bg-black select-none"
            style={{
                top: `${position.y}px`,
                left: `${position.x}px`,
                width: `${size.width}px`,
                cursor: isDragging ? 'grabbing' : 'default'
            }}
            onMouseDown={handleMouseDown}
        >
            {/* Drag Handle & Header */}
            <div className="drag-handle bg-stone-800 h-6 w-full flex items-center justify-center cursor-grab hover:bg-stone-700 transition-colors group">
                <div className="w-8 h-1 bg-stone-600 rounded-full group-hover:bg-stone-500" />
            </div>

            {/* Video Mirror Container - Click to Play/Pause */}
            <div
                className="floating-video-container w-full aspect-video bg-black cursor-pointer relative group overflow-hidden"
                onClick={handlePlayPause}
            >
                {/* Mirror the video element without moving it */}
                <video
                    src={videoElement.src}
                    className="w-full h-full object-contain"
                    ref={(mirrorVideo) => {
                        if (mirrorVideo && videoElement) {
                            // Sync the mirror video with the original
                            mirrorVideo.currentTime = videoElement.currentTime;
                            mirrorVideo.playbackRate = videoElement.playbackRate;
                            mirrorVideo.volume = videoElement.volume;

                            // IMPORTANT: Use the original muted state, not the current one
                            // Because we mute the main video when FloatingPlayer is visible to prevent audio overlap
                            // But we want the mirror video to have sound
                            const originalMutedState = videoElement.dataset.wasMutedBeforeFloat === 'true';
                            mirrorVideo.muted = originalMutedState;

                            // Sync play/pause state
                            if (!videoElement.paused && mirrorVideo.paused) {
                                mirrorVideo.play().catch(() => { });
                            } else if (videoElement.paused && !mirrorVideo.paused) {
                                mirrorVideo.pause();
                            }

                            // Keep syncing time and playback state
                            const syncInterval = setInterval(() => {
                                if (Math.abs(mirrorVideo.currentTime - videoElement.currentTime) > 0.3) {
                                    mirrorVideo.currentTime = videoElement.currentTime;
                                }
                                mirrorVideo.playbackRate = videoElement.playbackRate;

                                if (!videoElement.paused && mirrorVideo.paused) {
                                    mirrorVideo.play().catch(() => { });
                                } else if (videoElement.paused && !mirrorVideo.paused) {
                                    mirrorVideo.pause();
                                }
                            }, 100);

                            return () => clearInterval(syncInterval);
                        }
                    }}
                />

                {/* Hover Overlay for better affordance */}
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity bg-black/10">
                    {isPlaying ? (
                        <div className="bg-black/40 p-2 rounded-full backdrop-blur-sm"><svg className="w-8 h-8 text-white/90" fill="currentColor" viewBox="0 0 24 24"><path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" /></svg></div>
                    ) : (
                        <div className="bg-black/40 p-2 rounded-full backdrop-blur-sm"><svg className="w-8 h-8 text-white/90" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg></div>
                    )}
                </div>
            </div>

            {/* Progress Bar */}
            <div className="bg-stone-900 border-t border-stone-800 px-3 pt-2 pb-1 flex items-center gap-2" onMouseDown={(e) => e.stopPropagation()}>
                <span className="text-[10px] font-mono text-stone-400 min-w-[32px] text-right">{formatTime(currentTime)}</span>
                <input
                    type="range"
                    min="0"
                    max={duration || 0}
                    step="0.1"
                    value={currentTime}
                    onChange={handleSeek}
                    className="flex-1 h-1 bg-stone-700 rounded-lg appearance-none cursor-pointer accent-orange-600 hover:accent-orange-500 hover:h-1.5 transition-all"
                />
                <span className="text-[10px] font-mono text-stone-400 min-w-[32px]">{formatTime(duration)}</span>
            </div>

            {/* Controls */}
            <div className="bg-stone-900 pl-3 pr-5 pb-2 pt-1 flex items-center justify-between relative">
                <div className="flex items-center gap-3">
                    {/* Play/Pause */}
                    <button
                        onClick={handlePlayPause}
                        className="text-white hover:text-orange-500 transition-colors"
                    >
                        {isPlaying ? (
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" /></svg>
                        ) : (
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                        )}
                    </button>

                    {/* Speed Control */}
                    <div className="relative">
                        <button
                            onClick={(e) => { e.stopPropagation(); setShowSpeedMenu(!showSpeedMenu); }}
                            className="text-xs font-medium text-stone-300 hover:text-white bg-stone-800 hover:bg-stone-700 px-1.5 py-0.5 rounded"
                        >
                            {playbackRate}x
                        </button>

                        {showSpeedMenu && (
                            <div className="absolute bottom-full left-0 mb-2 bg-stone-800 rounded shadow-lg border border-stone-700 py-1 flex flex-col min-w-[4rem] z-50">
                                {[0.5, 1.0, 1.25, 1.5, 2.0].map((rate) => (
                                    <button
                                        key={rate}
                                        onClick={(e) => handleSpeedChange(rate, e)}
                                        className={`px-3 py-1 text-xs text-left hover:bg-stone-700 ${playbackRate === rate ? 'text-orange-500 font-bold' : 'text-stone-300'}`}
                                    >
                                        {rate}x
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={onExpand}
                        className="text-stone-300 hover:text-white transition-colors flex items-center gap-1 text-xs"
                        title="还原"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                        </svg>
                    </button>

                    <button
                        onClick={onClose}
                        className="text-stone-400 hover:text-red-400 transition-colors"
                        title="关闭"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            </div>

            {/* Resize Handle */}
            <div
                className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize flex items-end justify-end p-0.5 opacity-50 hover:opacity-100 transition-opacity z-50 group-hover:opacity-100"
                onMouseDown={handleResizeMouseDown}
            >
                <svg className="w-3 h-3 text-stone-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15l-6 6M21 8l-13 13M21 1l-20 20" />
                </svg>
            </div>
        </div>
    );

    return createPortal(floatingContent, document.body);
}
