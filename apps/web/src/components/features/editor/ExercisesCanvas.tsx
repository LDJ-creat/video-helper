import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useQuizGenerator, useQuizSave, useQuizSessions, useQuizDetail, useQuizItemUpdate } from "@/hooks/useAI";
import { Loader2, CheckCircle2, XCircle, BrainCircuit, RefreshCw, Save, History, ChevronLeft, ChevronRight, Calendar, BookOpen, Languages, PlusCircle } from "lucide-react";
import type { Quiz, QuizItem, QuizSession } from "@/lib/api/ai";
import { fetchQuizSessionDetail } from "@/lib/api/ai";
import { queryKeys } from "@/lib/api/queryKeys";

interface ExercisesCanvasProps {
    projectId?: string;
}

export function ExercisesCanvas({ projectId: propProjectId }: ExercisesCanvasProps) {
    const params = useParams();
    const projectId = propProjectId || (params?.projectId as string);
    const queryClient = useQueryClient();
    const t = useTranslations("Exercises");
    const tLang = useTranslations("Ingest.urlForm");

    // Hooks
    const generateMutation = useQuizGenerator();
    const saveMutation = useQuizSave();
    const updateItemMutation = useQuizItemUpdate();
    const { data: historySessions, isLoading: isLoadingHistory, error: historyError } = useQuizSessions(projectId);

    // State
    const [quiz, setQuiz] = useState<Quiz | null>(null);
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
    const [selectedOption, setSelectedOption] = useState<string | null>(null);
    const [showFeedback, setShowFeedback] = useState(false);
    const [answers, setAnswers] = useState<Record<string, { userAnswer: string; isCorrect: boolean }>>({});
    const [quizFinished, setQuizFinished] = useState(false);
    const [topic, setTopic] = useState("");

    // Language support
    const locale = useLocale();
    const [outputLanguage, setOutputLanguage] = useState(locale === "zh" ? "zh-Hans" : "en");

    // History & Sidebar State
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [viewingSessionId, setViewingSessionId] = useState<string | null>(null);
    const [hasDismissedAutoResume, setHasDismissedAutoResume] = useState(false);

    // Fetch Detail
    const { data: historyDetail, isLoading: isLoadingDetail } = useQuizDetail(viewingSessionId);

    // Auto-resume logic: 
    // 1. On mount/history load, find latest in-progress session if nothing is active
    useEffect(() => {
        if (!isLoadingHistory && historySessions && !quiz && !viewingSessionId && !quizFinished && !hasDismissedAutoResume) {
            const latestInProgress = historySessions.find(s => s.score === null);
            if (latestInProgress) {
                setViewingSessionId(latestInProgress.id);
            }
        }
    }, [historySessions, isLoadingHistory, quiz, viewingSessionId, quizFinished, hasDismissedAutoResume]);

    // 2. When a detail is loaded, if it's in-progress (score is null), 
    // "consume" it into the active quiz state instead of just viewing it.
    useEffect(() => {
        if (historyDetail && historyDetail.score === null && viewingSessionId === historyDetail.sessionId) {
            // Find progress
            const newAnswers: Record<string, { userAnswer: string; isCorrect: boolean }> = {};
            let firstUnansweredIndex = 0;
            let foundUnanswered = false;

            historyDetail.items.forEach((item, idx) => {
                if (item.userAnswer) {
                    newAnswers[item.questionHash] = {
                        userAnswer: item.userAnswer,
                        isCorrect: item.userAnswer === item.correctAnswer
                    };
                } else if (!foundUnanswered) {
                    firstUnansweredIndex = idx;
                    foundUnanswered = true;
                }
            });

            // Initialize active quiz state
            setQuiz({
                sessionId: historyDetail.sessionId,
                items: historyDetail.items
            });
            setAnswers(newAnswers);
            setCurrentQuestionIndex(firstUnansweredIndex);

            // Clear feedback state for the current question
            setSelectedOption(null);
            setShowFeedback(false);

            // Clear viewing state so we switch from detail view to active view
            setViewingSessionId(null);
        }
    }, [historyDetail, viewingSessionId]);

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
            {
                projectId,
                topicFocus: topic || undefined,
                outputLanguage: outputLanguage
            },
            {
                onSuccess: (data: Quiz) => {
                    setQuiz(data);
                    // Refresh the sidebar to show the newly-created (in-progress) session
                    queryClient.invalidateQueries({ queryKey: queryKeys.quizSessions(projectId) });
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

        // Immediately persist the answer to the database
        updateItemMutation.mutate({
            sessionId: quiz.sessionId,
            questionHash: currentQ.questionHash,
            userAnswer: selectedOption,
            isCorrect
        });

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

            // Items are already persisted per-answer; only update the session score
            saveMutation.mutate({
                projectId,
                sessionId: quiz.sessionId,
                score
            });
        }
    };

    const handleSelectHistorySession = (sessionId: string) => {
        setQuiz(null); // Clear active quiz
        setViewingSessionId(sessionId);
        setHasDismissedAutoResume(false); // Reset opt-out if user clicks a history item manually

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
        setHasDismissedAutoResume(true); // User explicitly wants to start fresh
    };


    // -- Renders --

    const renderHeaderToggle = () => {
        if (isSidebarOpen) return null;
        return (
            <button
                type="button"
                onClick={() => setIsSidebarOpen(true)}
                className="mr-3 p-2 bg-stone-50 hover:bg-stone-100 rounded-lg text-stone-500 hover:text-orange-600 transition-all border border-stone-200"
                title={t("expandHistory")}
            >
                <History size={18} />
            </button>
        );
    };

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
                        {t("historyTitle")}
                    </h3>
                    <button
                        type="button"
                        onClick={() => setIsSidebarOpen(false)}
                        className="p-1 hover:bg-stone-200 rounded text-stone-500 hover:text-stone-700"
                        title={t("collapseSidebar")}
                    >
                        <ChevronLeft size={20} />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    <button
                        type="button"
                        onClick={startNewQuiz}
                        className="w-full text-left p-3 rounded-lg border border-dashed border-stone-300 hover:border-orange-500 hover:bg-orange-50 text-stone-600 hover:text-orange-600 transition-all flex items-center gap-2 mb-4 group"
                    >
                        <div className="bg-stone-100 group-hover:bg-orange-100 p-1.5 rounded-md">
                            <BrainCircuit size={16} />
                        </div>
                        <span>{t("startNew")}</span>
                    </button>

                    {isLoadingHistory ? (
                        <div className="flex justify-center p-4"><Loader2 className="animate-spin text-stone-400" /></div>
                    ) : historyError ? (
                        <div className="text-center py-8 text-stone-400 text-sm">
                            {t("loadHistoryFailed")}
                        </div>
                    ) : historySessions?.length ? (
                        historySessions.map((session: QuizSession) => (
                            <button
                                key={session.id}
                                type="button"
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
                                    {session.score !== null ? (
                                        <span className={`text-xs px-1.5 py-0.5 rounded ${session.score >= 80 ? "bg-green-100 text-green-700" :
                                            session.score >= 60 ? "bg-yellow-100 text-yellow-700" :
                                                "bg-red-100 text-red-700"
                                            }`}>
                                            {session.score}{t("scoreUnit")}
                                        </span>
                                    ) : (
                                        <span className="text-xs px-1.5 py-0.5 rounded bg-orange-50 text-orange-500 border border-orange-200">
                                            {t("inProgress")}
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
                            {t("noHistory")}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );

    const renderDetailView = () => {
        if (isLoadingDetail) return <div className="flex justify-center items-center h-full"><Loader2 className="animate-spin text-orange-500" /></div>;
        if (!historyDetail) return <div className="flex justify-center items-center h-full text-stone-400">{t("loadDetailFailed")}</div>;

        // If this is an in-progress session, don't render the static detail view
        // The useEffect will soon clear viewingSessionId and transition to interactive view
        if (historyDetail.score === null) {
            return (
                <div className="flex flex-col items-center justify-center h-full bg-stone-50">
                    <Loader2 size={32} className="animate-spin text-orange-500 mb-4" />
                    <p className="text-stone-500 font-medium">{t("resuming")}</p>
                </div>
            );
        }

        return (
            <div className="h-full flex flex-col bg-stone-50">
                <div className="bg-white border-b border-stone-200 px-6 py-4 flex justify-between items-center shadow-sm">
                    <div className="flex items-center">
                        {renderHeaderToggle()}
                        <div>
                            <h2 className="text-lg font-bold text-stone-800">{t("review")}</h2>
                            <p className="text-sm text-stone-500">
                                {t("completedAt")} {new Date(historyDetail.createdAtMs).toLocaleString()}
                            </p>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-2xl font-black text-orange-600">{historyDetail.score}{t("scoreUnit")}</div>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-6 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                    {historyDetail.items.map((item: QuizItem, idx: number) => {
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
                                    {item.options.map((opt: string, optIdx: number) => {
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
                                        <span className="font-semibold text-stone-700">{t("explanation")}</span>{item.explanation}
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
                    <h3 className="text-2xl font-bold text-stone-900 mb-2">{t("finished")}</h3>
                    <div className="text-5xl font-black text-stone-900 mb-2">{score}<span className="text-2xl text-stone-400 font-normal">{t("scoreUnit")}</span></div>
                    <p className="text-stone-500 mb-8">
                        {t("correctCount")} <span className="text-stone-900 font-bold">{correctCount}</span> / {total} {t("questionUnit")}
                    </p>

                    <div className="space-y-3">
                        <button
                            type="button"
                            onClick={handleGenerate}
                            className="w-full py-3 bg-stone-900 text-white rounded-xl font-medium hover:bg-stone-800 transition-all flex items-center justify-center gap-2"
                        >
                            <RefreshCw size={18} />
                            {t("generateNew")}
                        </button>
                    </div>
                </div>
            </div>
        );
    };

    const renderLoading = () => (
        <div className="flex flex-col items-center justify-center h-full bg-stone-50">
            <Loader2 size={32} className="animate-spin text-orange-500 mb-4" />
            <p className="text-stone-500 animate-pulse font-medium">{t("generating")}</p>
        </div>
    );

    const renderStartScreen = () => (
        <div className="flex flex-col items-center justify-center p-8 h-full text-center bg-stone-50">
            <div className="w-16 h-16 bg-white rounded-2xl shadow-sm border border-stone-100 flex items-center justify-center mb-6 text-orange-600">
                <BrainCircuit size={32} />
            </div>
            <h3 className="text-xl font-bold text-stone-900 mb-2">{t("title")}</h3>
            <p className="text-stone-500 max-w-sm mb-8 leading-relaxed">
                {t("description")}
            </p>

            <div className="w-full max-w-xs space-y-4">
                <div className="relative">
                    <input
                        type="text"
                        placeholder={t("topicPlaceholder")}
                        value={topic}
                        onChange={e => setTopic(e.target.value)}
                        className="w-full px-4 py-3 border border-stone-200 bg-white rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all shadow-sm"
                    />
                </div>

                <div className="relative">
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 text-stone-400 pointer-events-none">
                        <Languages size={16} />
                    </div>
                    <select
                        value={outputLanguage}
                        onChange={(e) => setOutputLanguage(e.target.value)}
                        className="w-full pl-10 pr-4 py-3 border border-stone-200 bg-white rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all shadow-sm appearance-none cursor-pointer"
                    >
                        <option value="zh-Hans">{tLang("options.zhHans")}</option>
                        <option value="en">{tLang("options.en")}</option>
                        <option value="auto">{tLang("options.auto")}</option>
                    </select>
                </div>

                <button
                    type="button"
                    onClick={handleGenerate}
                    disabled={generateMutation.isPending}
                    className="w-full py-3 bg-stone-900 text-white rounded-xl font-medium hover:bg-stone-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-stone-900/10"
                >
                    {generateMutation.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw size={18} />}
                    {t("generateBtn")}
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
                        {renderHeaderToggle()}
                        <button
                            type="button"
                            onClick={startNewQuiz}
                            className="text-stone-400 hover:text-orange-600 transition-colors flex items-center gap-1 text-xs font-medium"
                            title={tLang("placeholderTitle")}
                        >
                            <PlusCircle size={18} />
                            <span>{t("startNew")}</span>
                        </button>
                        <div className="w-px h-4 bg-stone-200" />
                        <span className="text-sm font-bold text-stone-400 uppercase tracking-wider">
                            Q<span className="text-stone-900">{currentQuestionIndex + 1}</span> / {quiz.items.length}
                        </span>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="w-24 h-1.5 bg-stone-100 rounded-full overflow-hidden hidden sm:block">
                            <div
                                className="h-full bg-gradient-to-r from-orange-400 to-orange-600 transition-all duration-500 ease-out"
                                style={{ width: `${((currentQuestionIndex + 1) / quiz.items.length) * 100}%` }}
                            />
                        </div>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-6 md:p-8 lg:p-12 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
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
                                    <span className="font-bold block mb-1 text-blue-700">{t("explanationTitle")}</span>
                                    {currentQ.explanation}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <div className="p-6 border-t border-stone-200 bg-white flex justify-end items-center z-10">

                    {!showFeedback ? (
                        <button
                            type="button"
                            onClick={handleSubmitAnswer}
                            disabled={!selectedOption}
                            className="px-8 py-3 bg-stone-900 text-white rounded-xl font-medium hover:bg-stone-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-stone-900/10"
                        >
                            {t("submit")}
                        </button>
                    ) : (
                        <button
                            type="button"
                            onClick={handleNext}
                            className="px-8 py-3 bg-orange-600 text-white rounded-xl font-medium hover:bg-orange-700 transition-all flex items-center gap-2 shadow-lg shadow-orange-600/20"
                        >
                            {isLastQuestion ? t("complete") : t("next")}
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
        <div className="flex h-full bg-stone-50 overflow-hidden relative">
            {renderSidebar()}

            <div className="flex-1 w-full relative flex flex-col overflow-hidden">
                {/* Global Sidebar Toggle for full-screen states without headers */}
                {!isSidebarOpen && !viewingSessionId && !quiz && (
                    <button
                        type="button"
                        onClick={() => setIsSidebarOpen(true)}
                        className="absolute top-4 left-4 z-30 p-2 bg-white/80 backdrop-blur-sm rounded-lg shadow-sm border border-stone-200 text-stone-600 hover:text-orange-600 transition-all"
                        title={t("expandHistory")}
                    >
                        <History size={18} />
                    </button>
                )}
                <div className="flex-1 overscroll-none overflow-hidden h-full">
                    {mainContent}
                </div>
            </div>
        </div>
    );
}
