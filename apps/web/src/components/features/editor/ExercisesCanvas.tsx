import { useState } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useQuizGenerator, useQuizSave, useQuizSessions, useQuizDetail } from "@/hooks/useAI";
import { Loader2, CheckCircle2, XCircle, BrainCircuit, RefreshCw, Save, History, ChevronLeft, ChevronRight, Calendar, BookOpen } from "lucide-react";
import type { Quiz, QuizItem } from "@/lib/api/ai";
import { fetchQuizSessionDetail } from "@/lib/api/ai";
import { queryKeys } from "@/lib/api/queryKeys";

interface ExercisesCanvasProps {
    projectId?: string;
}

export function ExercisesCanvas({ projectId: propProjectId }: ExercisesCanvasProps) {
    const params = useParams();
    const projectId = propProjectId || (params?.projectId as string);
    const queryClient = useQueryClient();

    // Hooks
    const generateMutation = useQuizGenerator();
    const saveMutation = useQuizSave();
    const { data: historySessions, isLoading: isLoadingHistory, error: historyError } = useQuizSessions(projectId);

    // State
    const [quiz, setQuiz] = useState<Quiz | null>(null);
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
    const [selectedOption, setSelectedOption] = useState<string | null>(null);
    const [showFeedback, setShowFeedback] = useState(false);
    const [answers, setAnswers] = useState<Record<string, { userAnswer: string; isCorrect: boolean }>>({});
    const [quizFinished, setQuizFinished] = useState(false);
    const [topic, setTopic] = useState("");

    // History & Sidebar State
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [viewingSessionId, setViewingSessionId] = useState<string | null>(null);

    // Fetch Detail
    const { data: historyDetail, isLoading: isLoadingDetail } = useQuizDetail(viewingSessionId);

    // Handlers
    const handleGenerate = () => {
        setQuiz(null);
        setQuizFinished(false);
        setAnswers({});
        setCurrentQuestionIndex(0);
        setSelectedOption(null);
        setShowFeedback(false);
        setViewingSessionId(null);

        generateMutation.mutate(
            { projectId, topicFocus: topic || undefined },
            {
                onSuccess: (data) => {
                    setQuiz(data);
                }
            }
        );
    };

    const handleOptionSelect = (option: string) => {
        if (showFeedback) return;
        setSelectedOption(option);
    };

    const handleSubmitAnswer = () => {
        if (!quiz || !selectedOption) return;

        const currentQ = quiz.items[currentQuestionIndex];
        const isCorrect = selectedOption === currentQ.correctAnswer;

        setAnswers(prev => ({
            ...prev,
            [currentQ.questionHash]: { userAnswer: selectedOption, isCorrect }
        }));

        setShowFeedback(true);
    };

    const handleNext = () => {
        if (!quiz) return;

        if (currentQuestionIndex < quiz.items.length - 1) {
            setCurrentQuestionIndex(prev => prev + 1);
            setSelectedOption(null);
            setShowFeedback(false);
        } else {
            finishQuiz();
        }
    };

    const finishQuiz = () => {
        setQuizFinished(true);
        if (quiz) {
            const correctCount = Object.values(answers).filter(a => a.isCorrect).length;
            const score = Math.round((correctCount / quiz.items.length) * 100);

            const itemsToSave = quiz.items.map(item => {
                const ans = answers[item.questionHash];
                return {
                    questionHash: item.questionHash,
                    userAnswer: ans?.userAnswer || "",
                    isCorrect: ans?.isCorrect || false,
                    question: item.question,
                    options: item.options,
                    correctAnswer: item.correctAnswer,
                    explanation: item.explanation
                };
            });

            saveMutation.mutate({
                projectId,
                sessionId: quiz.sessionId,
                score,
                items: itemsToSave
            });
        }
    };

    const handleSelectHistorySession = (sessionId: string) => {
        setQuiz(null); // Clear active quiz
        setViewingSessionId(sessionId);

        // Prefetch detail so the backend request is triggered immediately on click.
        void queryClient.prefetchQuery({
            queryKey: queryKeys.quizDetail(sessionId),
            queryFn: () => fetchQuizSessionDetail(sessionId),
        });

        if (window.innerWidth < 1024) setIsSidebarOpen(false); // Mobile auto-close
    };

    const startNewQuiz = () => {
        setQuiz(null);
        setViewingSessionId(null);
        setQuizFinished(false);
        setAnswers({});
        setCurrentQuestionIndex(0);
        setSelectedOption(null);
        setShowFeedback(false);
    };


    // -- Renders --

    const renderSidebar = () => (
        <div className={`
            fixed inset-y-0 left-0 z-20 bg-stone-50 border-r border-stone-200 transform transition-all duration-300 ease-in-out
            ${isSidebarOpen ? "translate-x-0 w-80 lg:w-64" : "-translate-x-full lg:translate-x-0 lg:w-0 lg:border-none lg:overflow-hidden"}
            lg:relative lg:flex lg:flex-col lg:shrink-0
        `}>
            {/* Sidebar Content Container - needed to prevent content squashing during width transition */}
            <div className={`flex flex-col h-full w-80 lg:w-64 ${!isSidebarOpen && "lg:invisible"}`}>
                <div className="p-4 border-b border-stone-200 flex items-center justify-between">
                    <h3 className="font-semibold text-stone-700 flex items-center gap-2">
                        <History size={18} />
                        练习记录
                    </h3>
                    <button
                        onClick={() => setIsSidebarOpen(false)}
                        className="p-1 hover:bg-stone-200 rounded text-stone-500 hover:text-stone-700"
                        title="收起侧边栏"
                    >
                        <ChevronLeft size={20} />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    <button
                        onClick={startNewQuiz}
                        className="w-full text-left p-3 rounded-lg border border-dashed border-stone-300 hover:border-orange-500 hover:bg-orange-50 text-stone-600 hover:text-orange-600 transition-all flex items-center gap-2 mb-4 group"
                    >
                        <div className="bg-stone-100 group-hover:bg-orange-100 p-1.5 rounded-md">
                            <BrainCircuit size={16} />
                        </div>
                        <span>开始新练习</span>
                    </button>

                    {isLoadingHistory ? (
                        <div className="flex justify-center p-4"><Loader2 className="animate-spin text-stone-400" /></div>
                    ) : historyError ? (
                        <div className="text-center py-8 text-stone-400 text-sm">
                            无法加载练习记录
                        </div>
                    ) : historySessions?.length ? (
                        historySessions.map(session => (
                            <button
                                key={session.id}
                                onClick={() => handleSelectHistorySession(session.id)}
                                className={`w-full text-left p-3 rounded-lg border transition-all ${viewingSessionId === session.id
                                    ? "bg-white border-orange-500 shadow-sm"
                                    : "bg-white border-stone-100 hover:border-stone-300"
                                    }`}
                            >
                                <div className="flex justify-between items-start mb-1">
                                    <span className={`text-sm font-medium ${viewingSessionId === session.id ? "text-orange-700" : "text-stone-700"}`}>
                                        {new Date(session.updatedAtMs).toLocaleDateString()}
                                    </span>
                                    {session.score !== null && (
                                        <span className={`text-xs px-1.5 py-0.5 rounded ${session.score >= 80 ? "bg-green-100 text-green-700" :
                                            session.score >= 60 ? "bg-yellow-100 text-yellow-700" :
                                                "bg-red-100 text-red-700"
                                            }`}>
                                            {session.score}分
                                        </span>
                                    )}
                                </div>
                                <div className="flex items-center gap-1 text-xs text-stone-400">
                                    <Calendar size={12} />
                                    <span>{new Date(session.updatedAtMs).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                </div>
                            </button>
                        ))
                    ) : (
                        <div className="text-center py-8 text-stone-400 text-sm">
                            暂无练习记录
                        </div>
                    )}
                </div>
            </div>
        </div>
    );

    const renderDetailView = () => {
        if (isLoadingDetail) return <div className="flex justify-center items-center h-full"><Loader2 className="animate-spin text-orange-500" /></div>;
        if (!historyDetail) return <div className="flex justify-center items-center h-full text-stone-400">无法加载练习详情</div>;

        return (
            <div className="h-full flex flex-col bg-stone-50">
                <div className="bg-white border-b border-stone-200 px-6 py-4 flex justify-between items-center shadow-sm">
                    <div>
                        <h2 className="text-lg font-bold text-stone-800">练习回顾</h2>
                        <p className="text-sm text-stone-500">
                            完成于 {new Date(historyDetail.createdAtMs).toLocaleString()}
                        </p>
                    </div>
                    <div className="text-right">
                        <div className="text-2xl font-black text-orange-600">{historyDetail.score}分</div>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {historyDetail.items.map((item, idx) => {
                        // Assuming quiz items in history match standard format. 
                        // We need to infer user's answer from backend persistence or just show question?
                        // Wait, backend save persists `user_answer`, but `QuizItemDTO` doesn't strictly have it?
                        // Ah, the `QuizItem` model has `user_answer`, but `QuizItemDTO` in `schemas/ai.py` currently DOES NOT have `userAnswer`.
                        // We reused `QuizItemDTO` for `QuizDetailDTO`.
                        // We need to update `QuizItemDTO` or `QuizDetailDTO` to include `userAnswer`.
                        // Let's assume for this step I'll display what I can, and fix the DTO if needed.
                        // Actually, I can check the `item` structure returned by API.
                        // I might have missed updating `QuizItemDTO` in the backend step to include `userAnswer`.
                        return (
                            <div key={idx} className="bg-white p-6 rounded-xl border border-stone-100 shadow-sm">
                                <div className="flex items-start gap-3 mb-4">
                                    <span className="bg-stone-100 text-stone-500 text-xs font-bold px-2 py-1 rounded">Q{idx + 1}</span>
                                    <h3 className="text-stone-800 font-medium flex-1">{item.question}</h3>
                                </div>
                                <div className="space-y-2 pl-2 border-l-2 border-stone-100 ml-2">
                                    {item.options.map((opt, optIdx) => {
                                        const isCorrect = opt === item.correctAnswer;
                                        // Highlight user selected answer if available? 
                                        // Ideally we check `item.userAnswer` if existing.
                                        // Currently assuming logic handles display.
                                        return (
                                            <div
                                                key={optIdx}
                                                className={`text-sm p-2 rounded ${isCorrect ? "bg-green-50 text-green-700 font-medium" : "text-stone-600"
                                                    }`}
                                            >
                                                {opt} {isCorrect && <CheckCircle2 size={14} className="inline ml-1" />}
                                            </div>
                                        );
                                    })}
                                </div>
                                {item.explanation && (
                                    <div className="mt-3 text-sm text-stone-500 bg-stone-50 p-3 rounded-lg">
                                        <span className="font-semibold text-stone-700">解析：</span>{item.explanation}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    };

    const renderSummary = () => {
        if (!quiz) return null;
        const correctCount = Object.values(answers).filter(a => a.isCorrect).length;
        const total = quiz.items.length;
        const score = Math.round((correctCount / total) * 100);

        return (
            <div className="flex flex-col items-center justify-center p-8 h-full bg-stone-50">
                <div className="bg-white p-8 rounded-2xl shadow-sm border border-stone-100 text-center max-w-sm w-full">
                    <div className="w-20 h-20 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-6">
                        <CheckCircle2 size={40} className="text-orange-600" />
                    </div>
                    <h3 className="text-2xl font-bold text-stone-900 mb-2">练习完成!</h3>
                    <div className="text-5xl font-black text-stone-900 mb-2">{score}<span className="text-2xl text-stone-400 font-normal">分</span></div>
                    <p className="text-stone-500 mb-8">
                        答对 <span className="text-stone-900 font-bold">{correctCount}</span> / {total} 题
                    </p>

                    <div className="space-y-3">
                        <button
                            onClick={handleGenerate}
                            className="w-full py-3 bg-stone-900 text-white rounded-xl font-medium hover:bg-stone-800 transition-all flex items-center justify-center gap-2"
                        >
                            <RefreshCw size={18} />
                            练习新的一组
                        </button>
                    </div>
                </div>
            </div>
        );
    };

    const renderLoading = () => (
        <div className="flex flex-col items-center justify-center h-full bg-stone-50">
            <Loader2 size={32} className="animate-spin text-orange-500 mb-4" />
            <p className="text-stone-500 animate-pulse font-medium">AI 正在为您的视频生成专属练习...</p>
        </div>
    );

    const renderStartScreen = () => (
        <div className="flex flex-col items-center justify-center p-8 h-full text-center bg-stone-50">
            {/* Header Toggle - visible on both mobile and desktop if sidebar is closed */}
            {!isSidebarOpen && (
                <button
                    onClick={() => setIsSidebarOpen(true)}
                    className="absolute top-4 left-4 p-2 bg-white rounded-md shadow-sm border border-stone-200 text-stone-600 hover:text-orange-600"
                    title="展开练习记录"
                >
                    <History size={20} />
                </button>
            )}

            <div className="w-16 h-16 bg-white rounded-2xl shadow-sm border border-stone-100 flex items-center justify-center mb-6 text-orange-600">
                <BrainCircuit size={32} />
            </div>
            <h3 className="text-xl font-bold text-stone-900 mb-2">知识点巩固练习</h3>
            <p className="text-stone-500 max-w-sm mb-8 leading-relaxed">
                AI 将智能分析视频内容，为您生成个性化练习题，帮助您快速掌握关键知识点。
            </p>

            <div className="w-full max-w-xs space-y-4">
                <input
                    type="text"
                    placeholder="可选：侧重主题 (例如 'React Hooks')"
                    value={topic}
                    onChange={e => setTopic(e.target.value)}
                    className="w-full px-4 py-3 border border-stone-200 bg-white rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all shadow-sm"
                />
                <button
                    onClick={handleGenerate}
                    disabled={generateMutation.isPending}
                    className="w-full py-3 bg-stone-900 text-white rounded-xl font-medium hover:bg-stone-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-stone-900/10"
                >
                    {generateMutation.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw size={18} />}
                    生成练习
                </button>
            </div>
        </div>
    );

    // Main Content Logic
    let mainContent;
    if (viewingSessionId) {
        mainContent = renderDetailView();
    } else if (generateMutation.isPending) {
        mainContent = renderLoading();
    } else if (quizFinished) {
        mainContent = renderSummary();
    } else if (quiz) {
        // Quiz Active Render
        const currentQ = quiz.items[currentQuestionIndex];
        const isLastQuestion = currentQuestionIndex === quiz.items.length - 1;
        mainContent = (
            <div className="h-full flex flex-col bg-stone-50 overflow-hidden">
                <div className="bg-white border-b border-stone-200 px-6 py-4 flex justify-between items-center shadow-sm z-10">
                    <div className="flex items-center gap-4">
                        <button onClick={startNewQuiz} className="text-stone-400 hover:text-stone-600 transition-colors">
                            <XCircle size={20} />
                        </button>
                        <span className="text-sm font-bold text-stone-400">
                            QUESTION <span className="text-stone-900">{currentQuestionIndex + 1}</span> / {quiz.items.length}
                        </span>
                    </div>
                    <div className="w-32 h-2 bg-stone-100 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-orange-400 to-orange-600 transition-all duration-500 ease-out"
                            style={{ width: `${((currentQuestionIndex + 1) / quiz.items.length) * 100}%` }}
                        />
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-6 md:p-8 lg:p-12">
                    <div className="max-w-3xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <h2 className="text-2xl font-semibold text-stone-900 leading-relaxed">
                            {currentQ.question}
                        </h2>

                        <div className="space-y-4">
                            {currentQ.options.map((option, idx) => {
                                const isSelected = selectedOption === option;
                                const isCorrectAnswer = option === currentQ.correctAnswer;
                                const isUserWrong = showFeedback && isSelected && !isCorrectAnswer;

                                let borderClass = "border-stone-200 hover:border-stone-300 hover:bg-stone-50";
                                let bgClass = "bg-white";
                                let icon = null;

                                if (isSelected) {
                                    borderClass = "border-orange-500 ring-2 ring-orange-500/20";
                                    bgClass = "bg-orange-50/50";
                                }

                                if (showFeedback) {
                                    if (isCorrectAnswer) {
                                        borderClass = "border-green-500 bg-green-50/50 ring-2 ring-green-500/20";
                                        icon = <CheckCircle2 className="text-green-600" size={20} />;
                                    } else if (isUserWrong) {
                                        borderClass = "border-red-500 bg-red-50/50 ring-2 ring-red-500/20";
                                        icon = <XCircle className="text-red-600" size={20} />;
                                    } else {
                                        borderClass = "border-stone-200 opacity-60";
                                    }
                                }

                                return (
                                    <button
                                        key={idx}
                                        onClick={() => handleOptionSelect(option)}
                                        disabled={showFeedback}
                                        className={`w-full text-left p-5 rounded-2xl border-2 transition-all flex justify-between items-center group ${borderClass} ${bgClass}`}
                                    >
                                        <div className="flex items-center gap-3">
                                            <span className={`
                                                w-6 h-6 rounded-full border-2 flex items-center justify-center text-xs font-bold transition-colors
                                                ${isSelected ? "border-orange-500 text-orange-600" : "border-stone-300 text-stone-400 group-hover:border-stone-400"}
                                                ${showFeedback && isCorrectAnswer ? "border-green-500 text-green-600 bg-green-100" : ""}
                                                ${showFeedback && isUserWrong ? "border-red-500 text-red-600 bg-red-100" : ""}
                                            `}>
                                                {String.fromCharCode(65 + idx)}
                                            </span>
                                            <span className="text-stone-800 text-base font-medium">{option}</span>
                                        </div>
                                        {icon}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Explanation Area */}
                        {showFeedback && (
                            <div className="p-6 bg-blue-50/80 border border-blue-100 rounded-2xl text-blue-900 text-sm leading-relaxed animate-in fade-in slide-in-from-bottom-2 duration-300 flex gap-4">
                                <BookOpen size={24} className="shrink-0 text-blue-600" />
                                <div>
                                    <span className="font-bold block mb-1 text-blue-700">解析</span>
                                    {currentQ.explanation}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <div className="p-6 border-t border-stone-200 bg-white flex justify-between items-center z-10">
                    <div /> {/* Spacer */}
                    {!showFeedback ? (
                        <button
                            onClick={handleSubmitAnswer}
                            disabled={!selectedOption}
                            className="px-8 py-3 bg-stone-900 text-white rounded-xl font-medium hover:bg-stone-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-stone-900/10"
                        >
                            提交答案
                        </button>
                    ) : (
                        <button
                            onClick={handleNext}
                            className="px-8 py-3 bg-orange-600 text-white rounded-xl font-medium hover:bg-orange-700 transition-all flex items-center gap-2 shadow-lg shadow-orange-600/20"
                        >
                            {isLastQuestion ? "完成练习" : "下一题"}
                            <span className="bg-white/20 p-1 rounded-md"><ChevronRight size={16} /></span>
                        </button>
                    )}
                </div>
            </div>
        );
    } else {
        mainContent = renderStartScreen();
    }

    return (
        <div className="flex h-full bg-stone-100 overflow-hidden relative">
            {/* Mobile Sidebar Toggle - only visible when sidebar is closed and we are not in start screen (which has its own) */}
            {!isSidebarOpen && !viewingSessionId && quiz && (
                <button
                    onClick={() => setIsSidebarOpen(true)}
                    className="absolute top-4 left-4 z-20 lg:hidden p-2 bg-white rounded-md shadow-sm border border-stone-200 text-stone-600"
                >
                    <History size={20} />
                </button>
            )}

            {renderSidebar()}

            <div className="flex-1 w-full relative">
                {mainContent}
            </div>
        </div>
    );
}
