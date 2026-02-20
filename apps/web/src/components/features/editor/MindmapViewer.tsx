"use client";

import { useCallback } from "react";
import ReactFlow, {
    Node,
    Edge,
    Controls,
    Background,
    BackgroundVariant,
    ConnectionMode,
    Position,
} from "reactflow";
import "reactflow/dist/style.css";
import dagre from 'dagre';
import type { Mindmap, MindmapNode as MindmapNodeType } from "@/lib/contracts/resultTypes";

type MindmapViewerProps = {
    mindmap: Mindmap;
    isLoading?: boolean;
    onNodeClick?: (node: MindmapNodeType) => void;
};

// Node style presets by type
const nodeStyleMap: Record<string, React.CSSProperties> = {
    root: {
        background: "linear-gradient(135deg, #292524 0%, #44403C 100%)",
        border: "2px solid #57534E",
        borderRadius: "16px",
        padding: "14px 22px",
        fontSize: "16px",
        fontWeight: "700",
        color: "#FAFAF9",
        minWidth: "160px",
        textAlign: "center",
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
    },
    topic: {
        background: "#FFF7ED",
        border: "2px solid #FDBA74",
        borderRadius: "12px",
        padding: "12px 18px",
        fontSize: "14px",
        fontWeight: "600",
        color: "#292524",
        minWidth: "130px",
        textAlign: "center",
        boxShadow: "0 2px 6px rgba(0,0,0,0.06)",
    },
    detail: {
        background: "#FFFFFF",
        border: "1.5px solid #D6D3D1",
        borderRadius: "10px",
        padding: "10px 14px",
        fontSize: "13px",
        fontWeight: "400",
        color: "#57534E",
        minWidth: "100px",
        maxWidth: "200px",
        textAlign: "center",
    },
};

// Estimated node dimensions per type for dagre layout
const nodeDimensions: Record<string, { width: number; height: number }> = {
    root: { width: 240, height: 56 },
    topic: { width: 220, height: 52 },
    detail: { width: 200, height: 48 },
};

function getLayoutedElements(nodes: Node[], edges: Edge[]): Node[] {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({
        rankdir: 'LR',
        ranksep: 120,
        nodesep: 40,
        edgesep: 20,
    });

    nodes.forEach((node) => {
        const dims = nodeDimensions[node.data._type] || nodeDimensions.topic;
        dagreGraph.setNode(node.id, { width: dims.width, height: dims.height });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    return nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        const dims = nodeDimensions[node.data._type] || nodeDimensions.topic;
        const x = nodeWithPosition ? nodeWithPosition.x - dims.width / 2 : 0;
        const y = nodeWithPosition ? nodeWithPosition.y - dims.height / 2 : 0;

        return {
            ...node,
            targetPosition: Position.Left,
            sourcePosition: Position.Right,
            position: { x, y },
        };
    });
}

export function MindmapViewer({ mindmap, isLoading = false, onNodeClick }: MindmapViewerProps) {
    // Build ReactFlow nodes from mindmap data
    const initialNodes: Node[] = mindmap.nodes.map((node) => {
        const nodeType = node.type || "topic";
        const hasLink = !!(node.data?.targetBlockId || node.data?.targetHighlightId);

        return {
            id: node.id,
            type: "default",
            data: {
                label: node.label,
                _type: nodeType,
                _data: node.data,
                _raw: node,
            },
            position: { x: 0, y: 0 },
            style: {
                ...nodeStyleMap[nodeType] || nodeStyleMap.topic,
                cursor: hasLink ? "pointer" : "default",
            },
        };
    });

    // Build edges
    const edges: Edge[] = mindmap.edges.map((edge) => {
        const source = edge.source || (edge as any).from;
        const target = edge.target || (edge as any).to;
        return {
            id: edge.id || `edge-${source}-${target}`,
            source: String(source),
            target: String(target),
            label: edge.label || undefined,
            type: "smoothstep",
            animated: false,
            style: { stroke: "#D6D3D1", strokeWidth: 2 },
            labelStyle: { fill: "#78350f", fontWeight: 500, fontSize: 12 },
            labelBgStyle: { fill: "#fff7ed", fillOpacity: 0.9, rx: 4, ry: 4 },
            labelShowBg: !!edge.label,
        };
    });

    // Apply dagre layout
    const layoutedNodes = getLayoutedElements(initialNodes, edges);

    // Handle node click -> trigger callback with original node data
    const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
        if (!onNodeClick) return;
        const rawNode = node.data._raw as MindmapNodeType;
        if (rawNode?.data?.targetBlockId || rawNode?.data?.targetHighlightId) {
            onNodeClick(rawNode);
        }
    }, [onNodeClick]);

    if (isLoading) {
        return (
            <div className="w-full h-[500px] bg-stone-100 rounded-lg animate-pulse flex items-center justify-center">
                <p className="text-stone-500">加载中...</p>
            </div>
        );
    }

    if (layoutedNodes.length === 0) {
        return (
            <div className="w-full h-[500px] bg-white rounded-lg border border-stone-200 flex items-center justify-center">
                <p className="text-stone-500">暂无思维导图</p>
            </div>
        );
    }

    return (
        <div className="w-full h-[500px] bg-[#FDFBF7] rounded-lg border border-stone-200 overflow-hidden">
            <ReactFlow
                nodes={layoutedNodes}
                edges={edges}
                fitView
                connectionMode={ConnectionMode.Loose}
                nodesDraggable={false}
                nodesConnectable={false}
                elementsSelectable={true}
                onNodeClick={handleNodeClick}
            >
                <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#E7E5E4" />
                <Controls showInteractive={false} className="bg-white border border-stone-200 rounded-lg" />
            </ReactFlow>
        </div>
    );
}
