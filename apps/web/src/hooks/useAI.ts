import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    fetchChatSessions,
    fetchSessionMessages,
    generateQuiz,
    saveQuizV1,
    getChatCompletionUrl
} from "../lib/api/ai";
import { queryKeys } from "../lib/api/queryKeys";
import type { ChatSession, ChatMessage, Quiz, QuizAnswerItem } from "../lib/api/ai";

// --- Chat Hooks ---

export function useChatSessions(projectId: string) {
    return useQuery({
        queryKey: queryKeys.chatSessions(projectId),
        queryFn: () => fetchChatSessions(projectId),
        enabled: !!projectId,
    });
}

export function useSessionMessages(sessionId: string | null) {
    return useQuery({
        queryKey: queryKeys.chatMessages(sessionId || ""),
        queryFn: () => fetchSessionMessages(sessionId!),
        enabled: !!sessionId,
    });
}

/**
 * Custom hook for streaming chat.
 * React Query doesn't handle streams natively well, so we use a standard generator approach 
 * but wrap it to manage local state easily.
 */
export function useChatStream() {
    // This is a helper to get the URL for fetch/EventSource
    return {
        url: getChatCompletionUrl()
    };
}


// --- Quiz Hooks ---

export function useQuizGenerator() {
    return useMutation({
        mutationFn: (vars: { projectId: string; topicFocus?: string }) =>
            generateQuiz(vars.projectId, vars.topicFocus),
    });
}

export function useQuizSave() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (vars: {
            projectId: string;
            sessionId: string;
            score: number;
            items: QuizAnswerItem[]
        }) => saveQuizV1(vars.projectId, vars.sessionId, vars.score, vars.items),
        onSuccess: (_, vars) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.quizSessions(vars.projectId) });
        }
    });
}

export function useQuizSessions(projectId: string) {
    return useQuery({
        queryKey: queryKeys.quizSessions(projectId),
        queryFn: () => fetchQuizSessions(projectId),
        enabled: !!projectId,
    });
}

export function useQuizDetail(sessionId: string | null) {
    return useQuery({
        queryKey: queryKeys.quizDetail(sessionId || ""),
        queryFn: () => fetchQuizSessionDetail(sessionId!),
        enabled: !!sessionId,
    });
}
