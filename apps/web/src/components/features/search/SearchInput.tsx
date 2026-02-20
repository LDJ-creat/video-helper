"use client";

import { useState, useEffect } from "react";

interface SearchInputProps {
    onSearch: (query: string) => void;
    debounceMs?: number;
    placeholder?: string;
}

export function SearchInput({
    onSearch,
    debounceMs = 300,
    placeholder = "搜索项目或章节..."
}: SearchInputProps) {
    const [inputValue, setInputValue] = useState("");

    useEffect(() => {
        const timer = setTimeout(() => {
            onSearch(inputValue);
        }, debounceMs);

        return () => clearTimeout(timer);
    }, [inputValue, debounceMs, onSearch]);

    return (
        <div className="w-full">
            <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder={placeholder}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
        </div>
    );
}
