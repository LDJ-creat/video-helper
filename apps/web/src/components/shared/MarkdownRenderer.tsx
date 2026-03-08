import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
    content: string;
    className?: string;
    isStreaming?: boolean;
}

/**
 * A memoized Markdown renderer component.
 * Optimized for SSE streaming by using useMemo and custom styles to reduce layout shifts.
 */
const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = "", isStreaming = false }) => {
    // Memoize the markdown processing to avoid unnecessary re-renders during streaming
    const renderedContent = useMemo(() => {
        return (
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    // Customize components for better styling and performance
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-4 mb-2">{children}</ol>,
                    li: ({ children }) => <li className="mb-1">{children}</li>,
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    code: ({ inline, className, children, ...props }: any) => {
                        return !inline ? (
                            <div className="my-2 p-3 bg-stone-100 rounded-lg overflow-x-auto border border-stone-200">
                                <code className={`${className} text-stone-800 font-mono text-xs`} {...props}>
                                    {children}
                                </code>
                            </div>
                        ) : (
                            <code className="bg-stone-100 px-1 rounded text-orange-700 font-mono text-xs" {...props}>
                                {children}
                            </code>
                        );
                    },
                    // Ensure links open in new tab
                    a: ({ children, href }) => (
                        <a href={href} target="_blank" rel="noopener noreferrer" className="text-orange-600 hover:underline">
                            {children}
                        </a>
                    ),
                    h1: ({ children }) => <h1 className="text-lg font-bold mb-2">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-base font-bold mb-2">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-sm font-bold mb-1">{children}</h3>,
                    blockquote: ({ children }) => (
                        <blockquote className="border-l-4 border-stone-200 pl-4 italic my-2">{children}</blockquote>
                    ),
                }}
            >
                {content}
            </ReactMarkdown>
        );
    }, [content]);

    return (
        <div className={`markdown-body prose prose-stone max-w-none prose-sm leading-relaxed ${className} relative`}>
            {renderedContent}
            {isStreaming && (
                <span className="inline-block w-2 h-4 ml-1 align-middle bg-stone-400 animate-pulse" />
            )}
        </div>
    );
};

export default React.memo(MarkdownRenderer);
