import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import { config } from "../config";

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
    const url = `${config.apiBaseUrl}${endpoints.chatSessions(projectId)}`;
    return apiFetch<ChatSession[]>(url);
}

export async function fetchSessionMessages(sessionId: string): Promise<ChatMessage[]> {
    const url = `${config.apiBaseUrl}${endpoints.chatSessionMessages(sessionId)}`;
    return apiFetch<ChatMessage[]>(url);
}

export async function generateQuiz(projectId: string, topicFocus?: string, outputLanguage?: string): Promise<Quiz> {
    const url = `${config.apiBaseUrl}${endpoints.quizGenerate()}`;
    return apiFetch<Quiz>(url, {
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
    const url = `${config.apiBaseUrl}${endpoints.quizSave()}`;
    return apiFetch<{ success: boolean }>(url, {
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
    const url = `${config.apiBaseUrl}${endpoints.quizSessionItem(sessionId, questionHash)}`;
    return apiFetch<{ success: boolean }>(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            user_answer: userAnswer,
            is_correct: isCorrect
        }),
    });
}

export async function fetchQuizSessions(projectId: string): Promise<QuizSession[]> {
    const url = `${config.apiBaseUrl}${endpoints.quizSessions(projectId)}`;
    return apiFetch<QuizSession[]>(url);
}

export async function fetchQuizSessionDetail(sessionId: string): Promise<QuizDetail> {
    const url = `${config.apiBaseUrl}${endpoints.quizSession(sessionId)}`;
    return apiFetch<QuizDetail>(url);
} // chat url export remains below

// Chat streaming is handled via native fetch/EventSource in component or custom hook
// because apiFetch wraps response handling too tightly for streams.
export function getChatCompletionUrl(): string {
    return `${config.apiBaseUrl}${endpoints.chat()}`;
}
