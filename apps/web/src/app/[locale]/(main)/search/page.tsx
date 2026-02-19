"use client";

import { useState } from "react";
import { SearchInput } from "@/components/features/SearchInput";
import { SearchResults } from "@/components/features/SearchResults";
import { useSearch } from "@/lib/api/searchQueries";
import { useTranslations } from "next-intl";

export default function SearchPage() {
    const t = useTranslations("Search");
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
            <h1 className="text-2xl font-bold mb-6">{t("title")}</h1>

            <div className="mb-6">
                <SearchInput onSearch={setQuery} placeholder={t("placeholder")} />
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
                    {t("startPrompt")}
                </div>
            )}
        </main>
    );
}

