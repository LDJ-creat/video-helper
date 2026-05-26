"use client";

export function ProjectGridSkeleton({ count = 8 }: { count?: number }) {
    return (
        <div className="grid gap-6 2xl:gap-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: count }).map((_, i) => (
                <div
                    key={i}
                    className="flex flex-col justify-between rounded-xl 2xl:rounded-2xl border border-stone-100 bg-white p-6 2xl:p-8 shadow-sm"
                >
                    <div className="space-y-4">
                        <div className="flex gap-2">
                            <div className="h-5 w-16 animate-pulse rounded-full bg-stone-100" />
                            <div className="h-5 w-12 animate-pulse rounded-full bg-stone-100" />
                        </div>
                        <div className="space-y-2">
                            <div className="h-5 w-full animate-pulse rounded bg-stone-100" />
                            <div className="h-5 w-2/3 animate-pulse rounded bg-stone-100" />
                            <div className="mt-3 h-3 w-24 animate-pulse rounded bg-stone-50" />
                        </div>
                    </div>
                    <div className="mt-6 h-4 w-28 animate-pulse rounded bg-stone-50" />
                </div>
            ))}
        </div>
    );
}
