"use client";

import { useState } from "react";
import { SearchInput } from "@/components/features/SearchInput";
import { SearchResults } from "@/components/features/SearchResults";
import { useSearch } from "@/lib/api/searchQueries";

export default function SearchPage() {
    const [query, setQuery] = useState("");

    const {
        data,
        isLoading,
        isError,
        error,
        hasNextPage,
        isFetchingNextPage,
        fetchNextPage,
    } = useSearch(query);

    return (
        <main className="p-6 max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold mb-6">搜索</h1>

            <div className="mb-6">
                <SearchInput onSearch={setQuery} />
            </div>

            {query && (
                <SearchResults
                    data={data}
                    isLoading={isLoading}
                    isError={isError}
                    error={error}
                    hasNextPage={hasNextPage ?? false}
                    isFetchingNextPage={isFetchingNextPage}
                    fetchNextPage={fetchNextPage}
                />
            )}

            {!query && (
                <div className="text-center text-gray-500 py-12">
                    输入关键词开始搜索
                </div>
            )}
        </main>
    );
}

