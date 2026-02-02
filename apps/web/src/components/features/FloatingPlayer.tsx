"use client";

import { useRef, useEffect, useState } from "react";

type FloatingPlayerProps = {
    videoElement: HTMLVideoElement | null;
    isVisible: boolean;
    onExpand: () => void;
    onClose: () => void;
};

export function FloatingPlayer({ videoElement, isVisible, onExpand, onClose }: FloatingPlayerProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [isMounted, setIsMounted] = useState(false);

    useEffect(() => {
        setIsMounted(true);
    }, []);

    useEffect(() => {
        if (!isVisible || !videoElement || !containerRef.current) return;

        // 将 video 元素移动到悬浮容器中
        const container = containerRef.current.querySelector(".floating-video-container");
        if (container && !container.contains(videoElement)) {
            container.appendChild(videoElement);
        }
    }, [isVisible, videoElement]);

    if (!isMounted || !isVisible) {
        return null;
    }

    return (
        <div
            ref={containerRef}
            className="fixed bottom-6 right-6 z-50 animate-in fade-in slide-in-from-bottom-4 duration-300"
        >
            <div className="bg-black rounded-lg shadow-xl shadow-stone-300 border border-stone-200 overflow-hidden">
                {/* Video 容器 */}
                <div className="floating-video-container w-80 aspect-video bg-black" />

                {/* 控制按钮 */}
                <div className="bg-stone-900 px-3 py-2 flex items-center justify-between">
                    <button
                        onClick={onExpand}
                        className="text-white hover:text-orange-400 transition-colors flex items-center gap-1 text-sm"
                        title="回到顶部"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                        </svg>
                        <span>展开</span>
                    </button>

                    <button
                        onClick={onClose}
                        className="text-white hover:text-orange-400 transition-colors"
                        title="关闭悬浮"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    );
}
