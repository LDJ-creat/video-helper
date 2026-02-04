/**
 * ReactFlow Mindmap Editor Component
 * Story 9-4: ReactFlow editor with autosave
 * 
 * AC1: Edit nodes/edges with debounce autosave and error handling
 * ✅ ENHANCED: Added node editing, deletion, and addition features
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ReactFlow, {
    Node,
    Edge,
    Background,
    Controls,
    MiniMap,
    NodeTypes,
    useNodesState,
    useEdgesState,
    addEdge,
    Connection,
    NodeChange,
    EdgeChange,
    applyNodeChanges,
    applyEdgeChanges,
    Handle,
    Position,
    NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";
import { useSaveMindmap } from "@/lib/api/mindmapQueries";
import { Mindmap } from "@/lib/contracts/mindmap";

// Debounce delay matching note editor (AC: consistent with note strategy)
const AUTOSAVE_DELAY_MS = 1200;

export interface MindmapEditorProps {
    /** Project ID */
    projectId: string;
    /** Result ID */
    resultId: string;
    /** Initial mindmap data */
    initialMindmap: Mindmap;
    /** Callback when save succeeds */
    onSaveSuccess?: () => void;
    /** Callback when save fails */
    onSaveError?: (error: Error) => void;
}

export type SaveStatus = "idle" | "saving" | "saved" | "error";

/**
 * Custom node component (sticky note / index card style)
 * ✅ ENHANCED: Added double-click editing capability
 */
function StickyNoteNode({ data, id, selected }: NodeProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [editValue, setEditValue] = useState(data.label);
    const inputRef = useRef<HTMLInputElement>(null);

    const handleDoubleClick = () => {
        setIsEditing(true);
    };

    useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus();
            inputRef.current.select();
        }
    }, [isEditing]);

    const handleSave = () => {
        const trimmed = editValue.trim();
        if (trimmed && trimmed !== data.label) {
            data.onLabelChange?.(id, trimmed);
        }
        setIsEditing(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleSave();
        } else if (e.key === 'Escape') {
            setEditValue(data.label);
            setIsEditing(false);
        }
    };

    return (
        <div className="relative">
            {/* Target handle (receives connections from other nodes) */}
            <Handle
                type="target"
                position={Position.Left}
                className="w-3 h-3 !bg-yellow-400 !border-2 !border-yellow-600"
            />

            <div
                className={`px-4 py-3 bg-yellow-50 border-2 rounded-lg shadow-sm min-w-[120px] max-w-[200px] transition-all ${selected ? 'border-orange-400 shadow-md' : 'border-yellow-200'
                    }`}
                onDoubleClick={handleDoubleClick}
            >
                {isEditing ? (
                    <input
                        ref={inputRef}
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onBlur={handleSave}
                        onKeyDown={handleKeyDown}
                        className="w-full text-sm font-medium text-stone-800 bg-white border border-orange-300 rounded px-2 py-1 focus:outline-none focus:border-orange-500"
                        onClick={(e) => e.stopPropagation()}
                    />
                ) : (
                    <div className="text-sm font-medium text-stone-800 break-words">
                        {data.label}
                    </div>
                )}
            </div>

            {/* Source handle (creates connections to other nodes) */}
            <Handle
                type="source"
                position={Position.Right}
                className="w-3 h-3 !bg-yellow-400 !border-2 !border-yellow-600"
            />
        </div>
    );
}

const nodeTypes: NodeTypes = {
    stickyNote: StickyNoteNode,
};

/**
 * ✅ Hierarchical layout algorithm for mindmap (horizontal layout)
 * Creates a tree structure with proper positioning
 */
function calculateHierarchicalLayout(nodes: any[], edges: any[]): Node[] {
    // Build adjacency list
    const childrenMap = new Map<string, string[]>();
    const parentMap = new Map<string, string>();

    edges.forEach((edge) => {
        if (!childrenMap.has(edge.source)) {
            childrenMap.set(edge.source, []);
        }
        childrenMap.get(edge.source)!.push(edge.target);
        parentMap.set(edge.target, edge.source);
    });

    // Find root node (node without parent)
    const rootNode = nodes.find(node => !parentMap.has(node.id));
    if (!rootNode) {
        // Fallback to first node if no clear root
        return nodes.map((node, idx) => ({
            ...node,
            position: {
                x: (idx % 3) * 250 + 50,
                y: Math.floor(idx / 3) * 180 + 50
            }
        }));
    }

    // BFS to assign levels and calculate positions
    const nodePositions = new Map<string, { x: number; y: number }>();
    const levelNodes = new Map<number, string[]>();
    const queue: Array<{ id: string; level: number }> = [{ id: rootNode.id, level: 0 }];

    while (queue.length > 0) {
        const { id, level } = queue.shift()!;

        if (!levelNodes.has(level)) {
            levelNodes.set(level, []);
        }
        levelNodes.get(level)!.push(id);

        const children = childrenMap.get(id) || [];
        children.forEach(childId => {
            queue.push({ id: childId, level: level + 1 });
        });
    }

    // Calculate positions for each level (horizontal layout)
    const LEVEL_SPACING_X = 280; // Spacing between levels on X-axis
    const NODE_SPACING_Y = 150;  // Spacing between nodes within a level on Y-axis

    levelNodes.forEach((nodeIds, level) => {
        const totalHeight = (nodeIds.length - 1) * NODE_SPACING_Y;
        const startY = -totalHeight / 2; // Center nodes vertically within the level

        nodeIds.forEach((nodeId, index) => {
            nodePositions.set(nodeId, {
                x: level * LEVEL_SPACING_X + 50, // X position based on level
                y: startY + index * NODE_SPACING_Y + 400 // Y position based on index within level, plus center offset
            });
        });
    });

    // Apply positions to nodes
    return nodes.map(node => ({
        ...node,
        position: nodePositions.get(node.id) || node.position || { x: 0, y: 0 }
    }));
}

export function MindmapEditor({
    projectId,
    resultId,
    initialMindmap,
    onSaveSuccess,
    onSaveError,
}: MindmapEditorProps) {
    const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
    const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
    const saveTimerRef = useRef<NodeJS.Timeout | null>(null);
    const hasPendingChangesRef = useRef(false);
    const router = useRouter();

    // ✅ NEW: Context menu state
    const [contextMenu, setContextMenu] = useState<{
        nodeId: string;
        x: number;
        y: number;
    } | null>(null);

    // ✅ NEW: Selected node state for keyboard shortcuts
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

    const { mutateAsync: saveMindmap } = useSaveMindmap();

    // Convert initial mindmap to ReactFlow format with hierarchical layout
    const tempNodes = initialMindmap.nodes.map((node) => ({
        id: node.id,
        type: "stickyNote",
        position: (node as any).position || { x: 0, y: 0 },
        data: { label: node.label },
    }));

    // ✅ Apply hierarchical layout
    const initialNodes: Node[] = calculateHierarchicalLayout(tempNodes, initialMindmap.edges);

    const initialEdges: Edge[] = initialMindmap.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated: false,
        style: { stroke: "#FDBA74", strokeWidth: 2 },
    }));

    const [nodes, setNodes] = useState<Node[]>(initialNodes);
    const [edges, setEdges] = useState<Edge[]>(initialEdges);

    /**
     * ✅ NEW: Handle label change from node editing
     */
    const handleLabelChange = useCallback((nodeId: string, newLabel: string) => {
        setNodes(nds => nds.map(node =>
            node.id === nodeId
                ? { ...node, data: { ...node.data, label: newLabel } }
                : node
        ));
        hasPendingChangesRef.current = true;
        scheduleAutosave();
    }, []);

    // Update node data to include onLabelChange callback
    useEffect(() => {
        setNodes(nds => nds.map(node => ({
            ...node,
            data: { ...node.data, onLabelChange: handleLabelChange }
        })));
    }, [handleLabelChange]);

    /**
     * ✅ NEW: Delete node and all its descendants
     */
    const handleDeleteNode = useCallback((nodeId: string) => {
        // Find all nodes to delete (including children)
        const nodesToDelete = new Set<string>([nodeId]);
        const edgesToDelete = new Set<string>();

        // BFS to find all descendants
        const queue = [nodeId];
        while (queue.length > 0) {
            const current = queue.shift()!;
            edges.forEach(edge => {
                if (edge.source === current) {
                    nodesToDelete.add(edge.target);
                    queue.push(edge.target);
                }
            });
        }

        // Find all edges to delete
        edges.forEach(edge => {
            if (nodesToDelete.has(edge.source) || nodesToDelete.has(edge.target)) {
                edgesToDelete.add(edge.id);
            }
        });

        // Delete nodes and edges
        setNodes(nds => nds.filter(n => !nodesToDelete.has(n.id)));
        setEdges(eds => eds.filter(e => !edgesToDelete.has(e.id)));

        hasPendingChangesRef.current = true;
        scheduleAutosave();
        setSelectedNodeId(null);
        setContextMenu(null);
    }, [nodes, edges]);

    /**
     * ✅ NEW: Add child node to a parent
     */
    const handleAddChildNode = useCallback((parentId: string) => {
        const parentNode = nodes.find(n => n.id === parentId);
        if (!parentNode) return;

        const timestamp = Date.now();
        const random = Math.random().toString(36).substr(2, 9);
        const newNodeId = `node_new_${timestamp}_${random}`;
        const newEdgeId = `edge_${parentId}_${newNodeId}`;

        // Calculate position for new node (right and slightly below parent)
        const newNode: Node = {
            id: newNodeId,
            type: 'stickyNote',
            position: {
                x: parentNode.position.x + 280,
                y: parentNode.position.y + 50
            },
            data: {
                label: '新节点',
                onLabelChange: handleLabelChange
            }
        };

        const newEdge: Edge = {
            id: newEdgeId,
            source: parentId,
            target: newNodeId,
            type: 'smoothstep',
            animated: false,
            style: { stroke: '#FDBA74', strokeWidth: 2 }
        };

        setNodes(nds => [...nds, newNode]);
        setEdges(eds => [...eds, newEdge]);

        hasPendingChangesRef.current = true;
        scheduleAutosave();
        setContextMenu(null);
    }, [nodes, handleLabelChange]);

    /**
     * ✅ NEW: Add root node
     */
    const handleAddRootNode = useCallback(() => {
        const timestamp = Date.now();
        const random = Math.random().toString(36).substr(2, 9);
        const newNodeId = `node_root_${timestamp}_${random}`;

        // Find the bottommost node to place new root below
        const maxY = nodes.reduce((max, node) => Math.max(max, node.position.y), 0);

        const newNode: Node = {
            id: newNodeId,
            type: 'stickyNote',
            position: {
                x: 50,
                y: maxY + 200
            },
            data: {
                label: '新根节点',
                onLabelChange: handleLabelChange
            }
        };

        setNodes(nds => [...nds, newNode]);
        hasPendingChangesRef.current = true;
        scheduleAutosave();
    }, [nodes, handleLabelChange]);

    /**
     * Handle node changes (drag, select, etc)
     */
    const onNodesChange = useCallback((changes: NodeChange[]) => {
        setNodes((nds) => applyNodeChanges(changes, nds));
        hasPendingChangesRef.current = true;
        scheduleAutosave();
    }, []);

    /**
     * Handle edge changes (select, remove, etc)
     */
    const onEdgesChange = useCallback((changes: EdgeChange[]) => {
        setEdges((eds) => applyEdgeChanges(changes, eds));
        hasPendingChangesRef.current = true;
        scheduleAutosave();
    }, []);

    /**
     * Handle new connections
     */
    const onConnect = useCallback((connection: Connection) => {
        setEdges((eds) => addEdge(connection, eds));
        hasPendingChangesRef.current = true;
        scheduleAutosave();
    }, []);

    /**
     * ✅ NEW: Handle node context menu (right-click)
     */
    const onNodeContextMenu = useCallback((event: React.MouseEvent, node: Node) => {
        event.preventDefault();
        setContextMenu({
            nodeId: node.id,
            x: event.clientX,
            y: event.clientY
        });
    }, []);

    /**
     * ✅ NEW: Handle node selection
     */
    const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
        setSelectedNodeId(node.id);
    }, []);

    /**
     * ✅ NEW: Close context menu when clicking elsewhere
     */
    const onPaneClick = useCallback(() => {
        setContextMenu(null);
        setSelectedNodeId(null);
    }, []);

    /**
     * Schedule debounced autosave (AC1: debounce strategy)
     */
    const scheduleAutosave = useCallback(() => {
        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
        }

        saveTimerRef.current = setTimeout(() => {
            handleSave();
        }, AUTOSAVE_DELAY_MS);
    }, []);

    /**
     * Perform save operation
     */
    const handleSave = useCallback(async () => {
        if (!hasPendingChangesRef.current) return;

        // Convert ReactFlow format to API format
        const mindmapData: Mindmap = {
            nodes: nodes.map((node) => ({
                id: node.id,
                label: node.data.label,
                position: node.position,
            })),
            edges: edges.map((edge) => ({
                id: edge.id,
                source: edge.source,
                target: edge.target,
            })),
        };

        setSaveStatus("saving");

        try {
            await saveMindmap({
                projectId,
                resultId,
                data: { mindmap: mindmapData },
            });
            // ✅ FIX: Only clear pending after successful save (race condition fix)
            hasPendingChangesRef.current = false;
            setSaveStatus("saved");
            setLastSavedAt(new Date());
            onSaveSuccess?.();
        } catch (error) {
            // ✅ FIX: Improved error handling with error type detection
            const err = error as any;
            const status = err?.response?.status;

            if (status === 401 || status === 403) {
                console.error("Auth error - please re-login:", error);
            } else if (status === 404) {
                console.error("Project/Result not found:", error);
            } else if (status >= 400 && status < 500) {
                console.error("Validation error:", error);
            } else {
                console.error("Network/Server error:", error);
            }

            setSaveStatus("error");
            onSaveError?.(error as Error);
        }
    }, [nodes, edges, projectId, resultId, saveMindmap, onSaveSuccess, onSaveError]);

    /**
     * ✅ FIX: Flush save (AC2 - beforeunload/route change)
     */
    const flushSave = useCallback(() => {
        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
        }

        if (hasPendingChangesRef.current) {
            const mindmapData: Mindmap = {
                nodes: nodes.map((node) => ({
                    id: node.id,
                    label: node.data.label,
                    position: node.position,
                })),
                edges: edges.map((edge) => ({
                    id: edge.id,
                    source: edge.source,
                    target: edge.target,
                })),
            };

            const url = `/api/v1/projects/${projectId}/results/${resultId}/mindmap`;

            // Use fetch with keepalive for reliable flush
            fetch(url, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ mindmap: mindmapData }),
                keepalive: true,
            }).catch(() => {
                // Silently fail in flush - best effort
            });
        }
    }, [nodes, edges, projectId, resultId]);

    /**
     * ✅ FIX: Setup beforeunload handler (AC2)
     */
    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (hasPendingChangesRef.current) {
                e.preventDefault();
                flushSave();
            }
        };

        window.addEventListener("beforeunload", handleBeforeUnload);
        return () => {
            window.removeEventListener("beforeunload", handleBeforeUnload);
        };
    }, [flushSave]);

    /**
     * ✅ FIX: Route change handler (AC2 - Next.js app router)
     */
    useEffect(() => {
        const handleRouteChange = () => {
            if (hasPendingChangesRef.current) {
                flushSave();
            }
        };

        const originalPush = router.push;
        const originalReplace = router.replace;
        const originalBack = router.back;

        router.push = ((href: string, options?: any) => {
            handleRouteChange();
            return originalPush(href, options);
        }) as typeof router.push;

        router.replace = ((href: string, options?: any) => {
            handleRouteChange();
            return originalReplace(href, options);
        }) as typeof router.replace;

        router.back = (() => {
            handleRouteChange();
            return originalBack();
        }) as typeof router.back;

        return () => {
            router.push = originalPush;
            router.replace = originalReplace;
            router.back = originalBack;
        };
    }, [router, flushSave]);

    /**
     * Cleanup on unmount - flush save
     */
    useEffect(() => {
        return () => {
            if (saveTimerRef.current) {
                clearTimeout(saveTimerRef.current);
            }
            flushSave();
        };
    }, [flushSave]);

    /**
     * Reset "saved" status after 3 seconds
     */
    useEffect(() => {
        if (saveStatus === "saved") {
            const timer = setTimeout(() => {
                setSaveStatus("idle");
            }, 3000);
            return () => clearTimeout(timer);
        }
    }, [saveStatus]);

    /**
     * ✅ NEW: Keyboard shortcuts (Delete/Backspace to delete selected node)
     */
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.key === 'Delete' || e.key === 'Backspace') && selectedNodeId) {
                // Don't delete if user is editing a node (input is focused)
                const activeElement = document.activeElement;
                if (activeElement?.tagName === 'INPUT') return;

                e.preventDefault();
                handleDeleteNode(selectedNodeId);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [selectedNodeId, handleDeleteNode]);

    return (
        <div className="flex flex-col h-full bg-stone-50">
            {/* Status Bar & Toolbar */}
            <div className="flex items-center justify-between bg-white border-b border-stone-200 px-4 py-2">
                <div className="flex items-center gap-4">
                    <div className="text-sm text-stone-600">
                        思维导图编辑器
                    </div>

                    {/* ✅ NEW: Toolbar */}
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleAddRootNode}
                            className="px-3 py-1 text-sm bg-orange-500 text-white rounded hover:bg-orange-600 transition-colors"
                            title="添加新的根节点"
                        >
                            + 添加根节点
                        </button>
                        <div className="text-xs text-stone-400 border-l border-stone-300 pl-3">
                            双击编辑 | 右键菜单 | Delete删除
                        </div>
                    </div>
                </div>

                {/* Save Status Indicator (AC1) */}
                <div className="flex items-center gap-2 text-sm">
                    {saveStatus === "saving" && (
                        <>
                            <div className="w-3 h-3 border-2 border-orange-600 border-t-transparent rounded-full animate-spin" />
                            <span className="text-stone-600">保存中...</span>
                        </>
                    )}
                    {saveStatus === "saved" && (
                        <>
                            <svg className="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                            <span className="text-green-600">已保存</span>
                            {lastSavedAt && (
                                <span className="text-stone-400">
                                    {lastSavedAt.toLocaleTimeString("zh-CN", {
                                        hour: "2-digit",
                                        minute: "2-digit",
                                    })}
                                </span>
                            )}
                        </>
                    )}
                    {saveStatus === "error" && (
                        <>
                            <svg className="w-4 h-4 text-rose-600" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                            </svg>
                            <span className="text-rose-600">保存失败</span>
                            <button
                                onClick={handleSave}
                                className="text-orange-600 hover:text-orange-700 underline"
                            >
                                重试
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* ReactFlow Canvas */}
            <div className="flex-1 relative">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    onNodeContextMenu={onNodeContextMenu}
                    onNodeClick={onNodeClick}
                    onPaneClick={onPaneClick}
                    nodeTypes={nodeTypes}
                    fitView
                    attributionPosition="bottom-left"
                >
                    <Background color="#e7e5e4" gap={16} />
                    <Controls />
                    <MiniMap
                        nodeColor="#fef3c7"
                        nodeStrokeWidth={3}
                        zoomable
                        pannable
                    />
                </ReactFlow>

                {/* ✅ NEW: Context Menu */}
                {contextMenu && (
                    <>
                        {/* Backdrop to close menu */}
                        <div
                            className="fixed inset-0 z-40"
                            onClick={() => setContextMenu(null)}
                        />

                        {/* Menu */}
                        <div
                            style={{
                                position: 'fixed',
                                top: contextMenu.y,
                                left: contextMenu.x,
                                zIndex: 50
                            }}
                            className="bg-white shadow-lg rounded-lg border border-stone-200 py-1 min-w-[160px]"
                        >
                            <button
                                onClick={() => handleAddChildNode(contextMenu.nodeId)}
                                className="w-full text-left px-4 py-2 text-sm text-stone-700 hover:bg-stone-100 flex items-center gap-2"
                            >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                </svg>
                                添加子节点
                            </button>
                            <div className="border-t border-stone-200 my-1" />
                            <button
                                onClick={() => handleDeleteNode(contextMenu.nodeId)}
                                className="w-full text-left px-4 py-2 text-sm text-rose-600 hover:bg-rose-50 flex items-center gap-2"
                            >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                                删除节点
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
