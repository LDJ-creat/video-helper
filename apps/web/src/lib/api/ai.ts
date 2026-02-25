import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";

export interface ChatSession {
    id: string;
    projectId: string;
    title: string | null;
    createdAtMs: number;
    updatedAtMs: number;
}

export interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    createdAtMs: number;
}

export interface QuizItem {
    questionHash: string;
    question: string;
    options: string[];
    correctAnswer: string;
    explanation: string;
    userAnswer?: string;
}

export interface Quiz {
    sessionId: string;
    items: QuizItem[];
}

export interface QuizAnswerItem {
    questionHash: string;
    userAnswer: string;
    isCorrect: boolean;
    // content for persistence
    question: string;
    options: string[];
    correctAnswer: string;
    explanation: string;
}

export interface QuizSession {
    id: string;
    projectId: string;
    score: number | null;  // null means in-progress
    createdAtMs: number;
    updatedAtMs: number;
}

export interface QuizDetail {
    sessionId: string;
    projectId: string;
    score: number | null;
    items: QuizItem[]; // Reuses QuizItem from generation DTO, acts as loaded detail
    createdAtMs: number;
}

export async function fetchChatSessions(projectId: string): Promise<ChatSession[]> {
    return apiFetch<ChatSession[]>(endpoints.chatSessions(projectId));
}

export async function fetchSessionMessages(sessionId: string): Promise<ChatMessage[]> {
    return apiFetch<ChatMessage[]>(endpoints.chatSessionMessages(sessionId));
}

export async function generateQuiz(projectId: string, topicFocus?: string, outputLanguage?: string): Promise<Quiz> {
    return apiFetch<Quiz>(endpoints.quizGenerate(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            project_id: projectId,
            topic_focus: topicFocus,
            output_language: outputLanguage
        }),
    });
}

export async function saveQuizV1(
    projectId: string,
    sessionId: string,
    score: number,
): Promise<{ success: boolean }> {
    return apiFetch<{ success: boolean }>(endpoints.quizSave(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            project_id: projectId,
            session_id: sessionId,
            score,
            // items are already persisted on generate; no need to send them again
            items: []
        }),
    });
}

export async function updateQuizItem(
    sessionId: string,
    questionHash: string,
    userAnswer: string,
    isCorrect: boolean
): Promise<{ success: boolean }> {
    return apiFetch<{ success: boolean }>(endpoints.quizSessionItem(sessionId, questionHash), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            user_answer: userAnswer,
            is_correct: isCorrect
        }),
    });
}

export async function fetchQuizSessions(projectId: string): Promise<QuizSession[]> {
    return apiFetch<QuizSession[]>(endpoints.quizSessions(projectId));
}

export async function fetchQuizSessionDetail(sessionId: string): Promise<QuizDetail> {
    return apiFetch<QuizDetail>(endpoints.quizSession(sessionId));
} // chat url export remains below

// Chat streaming is handled via native fetch/EventSource in component or custom hook
// because apiFetch wraps response handling too tightly for streams.
export function getChatCompletionUrl(): string {
    return endpoints.chat();
}
