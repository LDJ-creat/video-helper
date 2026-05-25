"use client";

/** Centered loader for tab/filter changes — avoids swapping the grid for a skeleton. */
export function ProjectsGridSpinner() {
    return (
        <div
            className="flex min-h-[280px] items-center justify-center sm:min-h-[360px]"
            aria-busy="true"
            aria-live="polite"
        >
            <div
                className="h-9 w-9 animate-spin rounded-full border-2 border-stone-200 border-t-stone-700"
                role="status"
            />
        </div>
    );
}
