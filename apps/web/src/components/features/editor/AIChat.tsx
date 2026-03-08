import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Send, Plus, MessageSquare, Loader2, Bot, User } from "lucide-react";
import { useTranslations } from "next-intl";
import { useChatSessions, useSessionMessages, useChatStream } from "@/hooks/useAI";
import { queryKeys } from "@/lib/api/queryKeys";
import MarkdownRenderer from "@/components/shared/MarkdownRenderer";

export function AIChat() {
    const params = useParams();
    const projectId = params?.projectId as string;
    const queryClient = useQueryClient();
    const t = useTranslations("AIChat");

    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [input, setInput] = useState("");
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamedContent, setStreamedContent] = useState("");
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const isInitialLoadRef = useRef(true);
    const lastSessionIdRef = useRef<string | null>(null);
    const { url: chatUrl } = useChatStream();

    // Data Fetching
    const { data: sessions, isLoading: isLoadingSessions } = useChatSessions(projectId);
    const { data: messages } = useSessionMessages(activeSessionId);

    // If we just finished streaming and the assistant message is now persisted,
    // clear the local streamed bubble to avoid duplicates.
    useEffect(() => {
        if (isStreaming) return;
        if (!streamedContent) return;
        if (!messages || messages.length === 0) return;

        const last = messages[messages.length - 1];
        if (last.role !== "assistant") return;

        const persisted = (last.content || "").trim();
        const streamed = streamedContent.trim();
        if (!persisted || !streamed) return;

        if (persisted === streamed || persisted.includes(streamed) || streamed.includes(persisted)) {
            setStreamedContent("");
        }
    }, [messages, isStreaming, streamedContent]);

    // Auto-select first session if none selected
    useEffect(() => {
        if (!activeSessionId && sessions && sessions.length > 0) {
            setActiveSessionId(sessions[0].id);
        }
    }, [sessions, activeSessionId]);

    // Reset initial load flag when session changes
    useEffect(() => {
        if (activeSessionId !== lastSessionIdRef.current) {
            isInitialLoadRef.current = true;
            lastSessionIdRef.current = activeSessionId;
        }
    }, [activeSessionId]);

    // Clear optimistic user message once it appears in the persisted messages
    useEffect(() => {
        if (pendingUserMessage && messages?.some(m => m.role === "user" && m.content === pendingUserMessage)) {
            setPendingUserMessage(null);
        }
    }, [messages, pendingUserMessage]);

    // Scroll to bottom
    useEffect(() => {
        if (!messages || messages.length === 0) return;

        if (isInitialLoadRef.current) {
            // Instant jump to bottom for initial load or session switch
            if (scrollContainerRef.current) {
                scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
                isInitialLoadRef.current = false;
            }
        } else {
            // Smooth scroll only when streaming or after initial load
            // Using a small timeout to ensure DOM has updated
            const timer = setTimeout(() => {
                messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [messages, streamedContent]);

    const handleNewSession = () => {
        setActiveSessionId(null);
        setStreamedContent("");
    };

    const handleSend = async () => {
        if (!input.trim() || isStreaming) return;

        const userMessage = input.trim();
        setInput("");
        setIsStreaming(true);
        setStreamedContent("");
        setPendingUserMessage(userMessage);

        // Optimistic update (optional, but good for UX)
        // For simplicity, we'll let the stream handle the display of the new state eventually
        // But to show user message immediately, we might need a local 'pending' message list.
        // For this MVP, we'll rely on the stream start or just waiting.
        // Actually, let's just use a local temp message list or mix it.

        let currentSessionId: string | null = activeSessionId;

        const flushToUI = () => new Promise<void>(resolve => requestAnimationFrame(() => resolve()));

        try {
            const response = await fetch(chatUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: projectId,
                    session_id: activeSessionId, // null for new session
                    message: userMessage
                })
            });

            if (!response.ok) throw new Error("Network response was not ok");
            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                buffer += chunk;

                const parts = buffer.split("\n\n");
                // The last part might be incomplete, so we keep it in the buffer
                buffer = parts.pop() || "";

                for (const part of parts) {
                    if (part.startsWith("data: ")) {
                        const dataStr = part.replace("data: ", "").trim();
                        if (dataStr === "[DONE]") {
                            break;
                        }

                        try {
                            const data = JSON.parse(dataStr);
                            if (data.start_session_id) {
                                currentSessionId = data.start_session_id;
                                setActiveSessionId(currentSessionId);
                                // Refresh sessions list to show new session
                                queryClient.invalidateQueries({ queryKey: queryKeys.chatSessions(projectId) });
                            }
                            if (data.content) {
                                setStreamedContent(prev => prev + data.content);
                                // Allow browser to paint intermediate chunks
                                await flushToUI();
                            }
                        } catch (e) {
                            console.error("Error parsing SSE data", e);
                        }
                    }
                }
            }
        } catch (error) {
            console.error("Chat error:", error);
            setStreamedContent(prev => prev + `\n${t("errorPrefix")}`);
        } finally {
            setIsStreaming(false);
            setPendingUserMessage(null);
            // Refresh messages to get persisted user+assistant messages.
            if (currentSessionId) {
                queryClient.invalidateQueries({ queryKey: queryKeys.chatMessages(currentSessionId) });
            }
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // Combine persisted messages + current streaming state
    // If persistent messages include the user's latest, good. 
    // If not, we should show it? 
    // This is tricky without a proper unified store.
    // Hack: We only show streamed content as an "Assistant" message at the end.
    // But we also need to show the User's message that was just sent!
    // We'll trust the fast backend to save the user message and return it in the immediate refetch? 
    // No, that's slow.
    // We will maintain a local `optimisticMessages` state.

    // Actually, for MVP:
    // Just show `streamedContent` in a special bubble at bottom if `isStreaming` or `streamedContent` exists.
    // Also show the `input` (which we cleared) as a temp user message?
    // Let's keep it simple.

    return (
        <div className="flex h-full bg-stone-50 overflow-hidden relative">
            {/* Sidebar - Session List */}
            <div
                className={`border-r border-stone-200 bg-stone-100 flex flex-col transition-all duration-300 ease-in-out ${isSidebarOpen ? "w-64 2xl:w-80 opacity-100" : "w-0 opacity-0 overflow-hidden"
                    }`}
            >
                <div className="p-4 2xl:p-6 border-b border-stone-200 flex justify-between items-center">
                    <span className="text-sm 2xl:text-lg font-semibold text-stone-500">{t("sidebarTitle")}</span>
                    <button onClick={handleNewSession} className="p-1 hover:bg-stone-200 rounded text-stone-600" title={t("newChat")}>
                        <Plus size={18} />
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {isLoadingSessions && (
                        <div className="flex justify-center p-4">
                            <Loader2 size={16} className="animate-spin text-stone-400" />
                        </div>
                    )}
                    {sessions?.map(session => (
                        <button
                            key={session.id}
                            onClick={() => setActiveSessionId(session.id)}
                            className={`w-full text-left px-3 py-2 2xl:px-5 2xl:py-4 rounded-md text-sm 2xl:text-lg truncate transition-colors ${activeSessionId === session.id
                                ? "bg-white text-orange-700 font-medium shadow-sm ring-1 ring-stone-200"
                                : "text-stone-600 hover:bg-stone-200"
                                }`}
                        >
                            {session.title || t("newChat")}
                        </button>
                    ))}
                    {sessions?.length === 0 && (
                        <div className="text-center text-xs text-stone-400 py-8">
                            {t("noHistory")}
                        </div>
                    )}
                </div>
            </div>

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col bg-white min-w-0">
                {/* Chat Header */}
                <div className="h-14 2xl:h-20 border-b border-stone-200 flex items-center px-4 2xl:px-8 justify-between bg-white shrink-0">
                    <div className="flex items-center gap-2 2xl:gap-4">
                        <button
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            className={`p-2 2xl:p-3 hover:bg-stone-100 rounded-lg text-stone-600 transition-colors ${isSidebarOpen ? 'bg-stone-100' : ''}`}
                            title={isSidebarOpen ? t("collapseSidebar") : t("expandHistory")}
                        >
                            <MessageSquare className="w-5 h-5 2xl:w-7 2xl:h-7" />
                        </button>
                        <span className="font-medium text-stone-700 2xl:text-xl">{t("assistant")}</span>
                    </div>
                    <button
                        onClick={handleNewSession}
                        className="text-xs 2xl:text-base flex items-center gap-1 2xl:gap-2 px-3 py-1.5 2xl:px-5 2xl:py-3 bg-stone-900 text-white rounded-md hover:bg-stone-800 transition-colors"
                    >
                        <Plus className="w-3.5 h-3.5 2xl:w-5 2xl:h-5" />
                        {t("newChat")}
                    </button>
                </div>

                {/* Messages */}
                <div
                    ref={scrollContainerRef}
                    className="flex-1 overflow-y-auto p-4 space-y-6 no-scrollbar"
                >
                    {messages?.length === 0 && !streamedContent && (
                        <div className="flex flex-col items-center justify-center h-full text-stone-400 opacity-50">
                            <Bot size={48} className="mb-4" />
                            <p>{t("startPrompt")}</p>
                        </div>
                    )}

                    {messages?.map(msg => (
                        <div key={msg.id} className={`flex gap-3 2xl:gap-5 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                            {msg.role === "assistant" && (
                                <div className="w-8 h-8 2xl:w-12 2xl:h-12 rounded-full bg-orange-100 flex items-center justify-center shrink-0 mt-1">
                                    <Bot className="text-orange-600 w-4 h-4 2xl:w-6 2xl:h-6" />
                                </div>
                            )}
                            <div className={`max-w-[85%] rounded-2xl 2xl:rounded-3xl px-5 py-3 2xl:px-8 2xl:py-5 text-sm 2xl:text-lg leading-relaxed shadow-sm ${msg.role === "user"
                                ? "bg-stone-900 text-white rounded-br-none"
                                : "bg-white border border-stone-200 text-stone-800 rounded-bl-none"
                                }`}>
                                {msg.role === "user" ? (
                                    <div className="whitespace-pre-wrap">{msg.content}</div>
                                ) : (
                                    <MarkdownRenderer content={msg.content} />
                                )}
                            </div>
                            {msg.role === "user" && (
                                <div className="w-8 h-8 2xl:w-12 2xl:h-12 rounded-full bg-stone-200 flex items-center justify-center shrink-0 mt-1">
                                    <User className="text-stone-500 w-4 h-4 2xl:w-6 2xl:h-6" />
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Optimistic User Message */}
                    {pendingUserMessage && (
                        <div className="flex gap-3 justify-end">
                            <div className="max-w-[85%] rounded-2xl px-5 py-3 text-sm leading-relaxed shadow-sm bg-stone-900 text-white rounded-br-none">
                                <div className="whitespace-pre-wrap">{pendingUserMessage}</div>
                            </div>
                            <div className="w-8 h-8 rounded-full bg-stone-200 flex items-center justify-center shrink-0 mt-1">
                                <User size={16} className="text-stone-500" />
                            </div>
                        </div>
                    )}

                    {/* Streaming Content Bubble */}
                    {(streamedContent || (isStreaming && !streamedContent)) && (
                        <div className="flex gap-3 2xl:gap-5 justify-start">
                            <div className="w-8 h-8 2xl:w-12 2xl:h-12 rounded-full bg-orange-100 flex items-center justify-center shrink-0 mt-1">
                                <Bot className="text-orange-600 w-4 h-4 2xl:w-6 2xl:h-6" />
                            </div>
                            <div className="max-w-[85%] rounded-2xl 2xl:rounded-3xl rounded-bl-none px-5 py-3 2xl:px-8 2xl:py-5 text-sm 2xl:text-lg leading-relaxed bg-white border border-stone-200 text-stone-800 shadow-sm">
                                <MarkdownRenderer content={streamedContent} isStreaming={isStreaming} />
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="p-4 2xl:p-6 border-t border-stone-200 bg-stone-50 shrink-0">
                    <div className="relative max-w-4xl 2xl:max-w-6xl mx-auto">
                        <textarea
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder={t("inputPlaceholder")}
                            className="w-full pl-4 pr-12 py-3 2xl:pl-6 2xl:pr-16 2xl:py-5 rounded-xl 2xl:rounded-2xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent resize-none shadow-sm text-sm 2xl:text-xl"
                            rows={1}
                        />
                        <button
                            onClick={handleSend}
                            disabled={!input.trim() || isStreaming}
                            className="absolute right-2 bottom-2 2xl:right-3 2xl:bottom-3 p-2 2xl:p-3 bg-stone-900 text-white rounded-lg 2xl:rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:bg-stone-800 transition-all"
                        >
                            {isStreaming ? <Loader2 className="animate-spin w-4 h-4 2xl:w-6 2xl:h-6" /> : <Send className="w-4 h-4 2xl:w-6 2xl:h-6" />}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
