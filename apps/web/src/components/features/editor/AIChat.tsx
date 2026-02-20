import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Send, Plus, MessageSquare, Loader2, Bot, User } from "lucide-react";
import { useChatSessions, useSessionMessages, useChatStream } from "@/hooks/useAI";
import { queryKeys } from "@/lib/api/queryKeys";

export function AIChat() {
    const params = useParams();
    const projectId = params?.projectId as string;
    const queryClient = useQueryClient();

    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [input, setInput] = useState("");
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamedContent, setStreamedContent] = useState("");
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const { url: chatUrl } = useChatStream();

    // Data Fetching
    const { data: sessions, isLoading: isLoadingSessions } = useChatSessions(projectId);
    const { data: messages, isLoading: isLoadingMessages } = useSessionMessages(activeSessionId);

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

    // Scroll to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
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
            setStreamedContent(prev => prev + "\n[Error: Failed to send message]");
        } finally {
            setIsStreaming(false);
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
                className={`border-r border-stone-200 bg-stone-100 flex flex-col transition-all duration-300 ease-in-out ${isSidebarOpen ? "w-64 opacity-100" : "w-0 opacity-0 overflow-hidden"
                    }`}
            >
                <div className="p-4 border-b border-stone-200 flex justify-between items-center">
                    <span className="text-sm font-semibold text-stone-500">历史会话</span>
                    <button onClick={handleNewSession} className="p-1 hover:bg-stone-200 rounded text-stone-600" title="新会话">
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
                            className={`w-full text-left px-3 py-2 rounded-md text-sm truncate transition-colors ${activeSessionId === session.id
                                ? "bg-white text-orange-700 font-medium shadow-sm ring-1 ring-stone-200"
                                : "text-stone-600 hover:bg-stone-200"
                                }`}
                        >
                            {session.title || "未命名会话"}
                        </button>
                    ))}
                    {sessions?.length === 0 && (
                        <div className="text-center text-xs text-stone-400 py-8">
                            暂无历史会话
                        </div>
                    )}
                </div>
            </div>

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col bg-white min-w-0">
                {/* Chat Header */}
                <div className="h-14 border-b border-stone-200 flex items-center px-4 justify-between bg-white shrink-0">
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            className={`p-2 hover:bg-stone-100 rounded-lg text-stone-600 transition-colors ${isSidebarOpen ? 'bg-stone-100' : ''}`}
                            title={isSidebarOpen ? "收起侧边栏" : "展开历史记录"}
                        >
                            <MessageSquare size={20} />
                        </button>
                        <span className="font-medium text-stone-700">AI 助手</span>
                    </div>
                    <button
                        onClick={handleNewSession}
                        className="text-xs flex items-center gap-1 px-3 py-1.5 bg-stone-900 text-white rounded-md hover:bg-stone-800 transition-colors"
                    >
                        <Plus size={14} />
                        新会话
                    </button>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-6">
                    {messages?.length === 0 && !streamedContent && (
                        <div className="flex flex-col items-center justify-center h-full text-stone-400 opacity-50">
                            <Bot size={48} className="mb-4" />
                            <p>开始一个新的对话...</p>
                        </div>
                    )}

                    {messages?.map(msg => (
                        <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                            {msg.role === "assistant" && (
                                <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center shrink-0 mt-1">
                                    <Bot size={16} className="text-orange-600" />
                                </div>
                            )}
                            <div className={`max-w-[85%] rounded-2xl px-5 py-3 text-sm leading-relaxed whitespace-pre-wrap shadow-sm ${msg.role === "user"
                                ? "bg-stone-900 text-white rounded-br-none"
                                : "bg-white border border-stone-200 text-stone-800 rounded-bl-none"
                                }`}>
                                {msg.content}
                            </div>
                            {msg.role === "user" && (
                                <div className="w-8 h-8 rounded-full bg-stone-200 flex items-center justify-center shrink-0 mt-1">
                                    <User size={16} className="text-stone-500" />
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Streaming Content Bubble */}
                    {(streamedContent || (isStreaming && !streamedContent)) && (
                        <div className="flex gap-3 justify-start">
                            <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center shrink-0 mt-1">
                                <Bot size={16} className="text-orange-600" />
                            </div>
                            <div className="max-w-[85%] rounded-2xl rounded-bl-none px-5 py-3 text-sm leading-relaxed whitespace-pre-wrap bg-white border border-stone-200 text-stone-800 shadow-sm">
                                {streamedContent}
                                {isStreaming && <span className="inline-block w-2 h-4 ml-1 align-middle bg-stone-400 animate-pulse" />}
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="p-4 border-t border-stone-200 bg-stone-50 shrink-0">
                    <div className="relative max-w-4xl mx-auto">
                        <textarea
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="输入问题..."
                            className="w-full pl-4 pr-12 py-3 rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent resize-none shadow-sm text-sm"
                            rows={1}
                            style={{ minHeight: "44px", maxHeight: "120px" }}
                        />
                        <button
                            onClick={handleSend}
                            disabled={!input.trim() || isStreaming}
                            className="absolute right-2 bottom-2 p-2 bg-stone-900 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-stone-800 transition-all"
                        >
                            {isStreaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
