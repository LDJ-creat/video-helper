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

    // Drag state
    const [position, setPosition] = useState({ x: window.innerWidth - 340, y: 100 });
    const [isDragging, setIsDragging] = useState(false);
    const dragStartPos = useRef({ x: 0, y: 0 });

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

    const handleMouseMove = (e: MouseEvent) => {
        if (isDragging) {
            setPosition({
                x: e.clientX - dragStartPos.current.x,
                y: e.clientY - dragStartPos.current.y
            });
        }
    };

    const handleMouseUp = () => {
        setIsDragging(false);
    };

    // Setup drag event listeners
    useEffect(() => {
        if (isDragging) {
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
            return () => {
                document.removeEventListener('mousemove', handleMouseMove);
                document.removeEventListener('mouseup', handleMouseUp);
            };
        }
    }, [isDragging, position]);

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

        // Add listeners to sync UI state
        const handlePlay = () => setIsPlaying(true);
        const handlePause = () => setIsPlaying(false);
        const handleRateChange = () => setPlaybackRate(videoElement.playbackRate);

        videoElement.addEventListener("play", handlePlay);
        videoElement.addEventListener("pause", handlePause);
        videoElement.addEventListener("ratechange", handleRateChange);

        return () => {
            videoElement.removeEventListener("play", handlePlay);
            videoElement.removeEventListener("pause", handlePause);
            videoElement.removeEventListener("ratechange", handleRateChange);
        };
    }, [isVisible, videoElement]);

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
            className="fixed z-[9999] shadow-2xl shadow-stone-900/50 rounded-lg overflow-hidden border border-stone-700 w-80 bg-black select-none"
            style={{
                top: `${position.y}px`,
                left: `${position.x}px`,
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

            {/* Controls */}
            <div className="bg-stone-900 px-3 py-2 flex items-center justify-between border-t border-stone-800">
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
        </div>
    );

    return createPortal(floatingContent, document.body);
}
