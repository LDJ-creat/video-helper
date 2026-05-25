"use client";

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";

const SHOW_DELAY_MS = 450;

const DEBUG =
    typeof process !== "undefined" && process.env.NODE_ENV === "development";

function logTitleTooltip(event: string, payload: Record<string, unknown>) {
    if (!DEBUG) return;
    console.debug("[title-tooltip]", event, payload);
}

export function isTitleTruncated(el: HTMLElement | null): boolean {
    if (!el) return false;

    if (
        el.scrollHeight > el.clientHeight + 1 ||
        el.scrollWidth > el.clientWidth + 1
    ) {
        return true;
    }

    if (el.clientWidth <= 0) return false;

    const text = (el.textContent ?? "").trim();
    if (!text) return false;

    const cs = getComputedStyle(el);
    const measure = document.createElement("div");
    measure.style.position = "fixed";
    measure.style.visibility = "hidden";
    measure.style.pointerEvents = "none";
    measure.style.zIndex = "-1";
    measure.style.left = "-9999px";
    measure.style.width = `${el.clientWidth}px`;
    measure.style.font = cs.font;
    measure.style.fontSize = cs.fontSize;
    measure.style.fontWeight = cs.fontWeight;
    measure.style.lineHeight = cs.lineHeight;
    measure.style.letterSpacing = cs.letterSpacing;
    measure.style.wordBreak = cs.wordBreak;
    measure.style.whiteSpace = "normal";
    measure.textContent = text;
    document.body.appendChild(measure);
    const fullHeight = measure.offsetHeight;
    document.body.removeChild(measure);

    return fullHeight > el.clientHeight + 1;
}

function TitleTooltipPortal({
    open,
    coords,
    text,
}: {
    open: boolean;
    coords: { top: number; left: number };
    text: string;
}) {
    if (!open || typeof document === "undefined") return null;

    return createPortal(
        <div
            role="tooltip"
            className="pointer-events-none fixed z-[30] max-w-[min(24rem,calc(100vw-2rem))] -translate-x-1/2 rounded-lg bg-stone-900 px-3 py-2.5 text-sm leading-snug text-white shadow-xl"
            style={{ top: coords.top, left: coords.left }}
        >
            <span
                className="absolute left-1/2 bottom-full -translate-x-1/2 border-[6px] border-transparent border-b-stone-900"
                aria-hidden
            />
            {text}
        </div>,
        document.body
    );
}

export function useTitleHoverTooltip(text: string) {
    const titleRef = useRef<HTMLHeadingElement>(null);
    const showTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const [open, setOpen] = useState(false);
    const [coords, setCoords] = useState({ top: 0, left: 0 });

    const dismiss = useCallback(() => {
        if (showTimerRef.current) {
            clearTimeout(showTimerRef.current);
            showTimerRef.current = null;
        }
        setOpen(false);
        logTitleTooltip("hide", {});
    }, []);

    useEffect(() => () => {
        if (showTimerRef.current) clearTimeout(showTimerRef.current);
    }, []);

    const showNow = useCallback(() => {
        const el = titleRef.current;
        const truncated = isTitleTruncated(el);
        logTitleTooltip("hover-measure", {
            text: text.slice(0, 60),
            truncated,
            hasRef: !!el,
        });

        if (!el || !truncated) return;

        const rect = el.getBoundingClientRect();
        setCoords({
            top: rect.bottom + 8,
            left: rect.left + rect.width / 2,
        });
        setOpen(true);
        logTitleTooltip("show", { text: text.slice(0, 60) });
    }, [text]);

    const scheduleShow = useCallback(() => {
        if (showTimerRef.current) clearTimeout(showTimerRef.current);
        showTimerRef.current = setTimeout(() => {
            showTimerRef.current = null;
            showNow();
        }, SHOW_DELAY_MS);
    }, [showNow]);

    const titleHoverHandlers = {
        onMouseEnter: scheduleShow,
        onMouseLeave: dismiss,
    };

    const portal = (
        <TitleTooltipPortal open={open} coords={coords} text={text} />
    );

    return { titleRef, titleHoverHandlers, dismiss, portal };
}

type TitleHoverTooltipProps = {
    text: string;
    className?: string;
    titleRef?: RefObject<HTMLHeadingElement | null>;
    hoverHandlers?: {
        onMouseEnter: () => void;
        onMouseLeave: () => void;
    };
};

/** Clamped title; tooltip only when hovering the title (not the whole card). */
export function TitleHoverTooltip({
    text,
    className,
    titleRef: externalRef,
    hoverHandlers,
}: TitleHoverTooltipProps) {
    const internalRef = useRef<HTMLHeadingElement>(null);
    const ref = externalRef ?? internalRef;

    return (
        <h3
            ref={ref}
            className={className}
            onMouseEnter={hoverHandlers?.onMouseEnter}
            onMouseLeave={hoverHandlers?.onMouseLeave}
        >
            {text}
        </h3>
    );
}
