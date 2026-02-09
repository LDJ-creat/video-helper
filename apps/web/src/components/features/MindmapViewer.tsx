"use client";

import { useCallback } from "react";
import ReactFlow, {
    Node,
    Edge,
    Controls,
    Background,
    BackgroundVariant,
    MiniMap,
    // MiniMap,
    ConnectionMode,
    Position,
} from "reactflow";
import "reactflow/dist/style.css";
import dagre from 'dagre';
import type { Mindmap } from "@/lib/contracts/resultTypes";

type MindmapViewerProps = {
    mindmap: Mindmap;
    isLoading?: boolean;
};

// Layout function using Dagre
function getLayoutedElements(nodes: Node[], edges: Edge[]): Node[] {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    // Set structure for Left-to-Right layout
    dagreGraph.setGraph({ rankdir: 'LR', ranksep: 150, nodesep: 60 });

    // Node dimensions (approximate size of the node style below)
    // padding 12px 16px, minWidth 120px, fontSize 14px
    // Let's estimate wider to avoid overlap
    const nodeWidth = 220;
    const nodeHeight = 80;

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    return nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        const x = nodeWithPosition ? nodeWithPosition.x - nodeWidth / 2 : 0;
        const y = nodeWithPosition ? nodeWithPosition.y - nodeHeight / 2 : 0;

        return {
            ...node,
            targetPosition: Position.Left,
            sourcePosition: Position.Right,
            position: { x, y },
        };
    });
}

export function MindmapViewer({ mindmap, isLoading = false }: MindmapViewerProps) {
    // 1. Create initial nodes without position (will be calculated)
    const initialNodes: Node[] = mindmap.nodes.map((node, idx) => ({
        id: node.id,
        type: "default",
        data: { label: node.label },
        position: { x: 0, y: 0 }, // Placeholder
        style: {
            background: idx === 0 ? "#FFF7ED" : "#FFFFFF", // Root 节点橙色背景
            border: `2px solid ${idx === 0 ? "#FDBA74" : "#E7E5E4"}`,
            borderRadius: "12px",
            padding: "12px 16px",
            fontSize: "14px",
            fontWeight: idx === 0 ? "600" : "400",
            color: "#292524",
            minWidth: "120px",
            textAlign: "center",
        },
    }));

    // 2. Map edges with fallback for legacy data
    const edges: Edge[] = mindmap.edges.map((edge: any) => {
        const source = edge.from || edge.source;
        const target = edge.to || edge.target;
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

    // 3. Apply layout
    const layoutedNodes = getLayoutedElements(initialNodes, edges);

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
                nodesDraggable={false} // 只读模式
                nodesConnectable={false}
                elementsSelectable={false}
            >
                <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#E7E5E4" />
                <Controls showInteractive={false} className="bg-white border border-stone-200 rounded-lg" />
            </ReactFlow>
        </div>
    );
}
