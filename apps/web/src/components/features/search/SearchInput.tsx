"use client";

import { useState, useEffect, useCallback } from "react";
import { Search, X } from "lucide-react";

interface SearchInputProps {
    onSearch: (query: string) => void;
    debounceMs?: number;
    placeholder?: string;
    /** Controlled value; when omitted, uses internal state */
    value?: string;
    onValueChange?: (value: string) => void;
    clearLabel?: string;
    size?: "default" | "lg";
}

export function SearchInput({
    onSearch,
    debounceMs = 300,
    placeholder = "搜索项目或章节...",
    value: controlledValue,
    onValueChange,
    clearLabel = "清除搜索",
    size = "default",
}: SearchInputProps) {
    const isLg = size === "lg";
    const [internalValue, setInternalValue] = useState("");
    const isControlled = controlledValue !== undefined;
    const inputValue = isControlled ? controlledValue : internalValue;

    const setValue = useCallback(
        (next: string) => {
            if (isControlled) {
                onValueChange?.(next);
            } else {
                setInternalValue(next);
            }
        },
        [isControlled, onValueChange]
    );

    useEffect(() => {
        const timer = setTimeout(() => {
            onSearch(inputValue);
        }, debounceMs);

        return () => clearTimeout(timer);
    }, [inputValue, debounceMs, onSearch]);

    const handleClear = () => {
        setValue("");
        onSearch("");
    };

    const showClear = inputValue.trim().length > 0;

    return (
        <div className="relative w-full">
            <Search
                className={`pointer-events-none absolute top-1/2 -translate-y-1/2 text-stone-400 ${
                    isLg ? "left-4 h-5 w-5" : "left-3 h-4 w-4"
                }`}
                aria-hidden
            />
            <input
                type="text"
                value={inputValue}
                onChange={(e) => setValue(e.target.value)}
                placeholder={placeholder}
                className={`w-full rounded-xl border border-stone-200 bg-white text-stone-900 placeholder:text-stone-400 focus:border-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-200 ${
                    isLg
                        ? "py-3 pl-12 pr-12 text-base"
                        : "py-2.5 pl-10 pr-10 text-sm"
                }`}
            />
            {showClear && (
                <button
                    type="button"
                    onClick={handleClear}
                    aria-label={clearLabel}
                    className={`absolute right-2 top-1/2 flex -translate-y-1/2 items-center justify-center rounded-md text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700 ${
                        isLg ? "h-8 w-8" : "h-7 w-7"
                    }`}
                >
                    <X className={isLg ? "h-5 w-5" : "h-4 w-4"} />
                </button>
            )}
        </div>
    );
}
