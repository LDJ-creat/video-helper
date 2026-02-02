"use client";

import { useCallback } from "react";
import ReactFlow, {
    Node,
    Edge,
    Controls,
    Background,
    BackgroundVariant,
    MiniMap,
    ConnectionMode,
} from "reactflow";
import "reactflow/dist/style.css";
import type { Mindmap } from "@/lib/contracts/resultTypes";

type MindmapViewerProps = {
    mindmap: Mindmap;
    isLoading?: boolean;
};

export function MindmapViewer({ mindmap, isLoading = false }: MindmapViewerProps) {
    // 转换 mindmap 数据为 React Flow 格式
    const nodes: Node[] = mindmap.nodes.map((node, idx) => ({
        id: node.id,
        type: "default",
        data: { label: node.label },
        position: { x: (idx % 3) * 250, y: Math.floor(idx / 3) * 150 }, // 简单布局，后续可优化
        style: {
            background: idx === 0 ? "#FFF7ED" : "#FFFFFF", // Root 节点橙色背景
            border: `2px solid ${idx === 0 ? "#FDBA74" : "#E7E5E4"}`,
            borderRadius: "12px",
            padding: "12px 16px",
            fontSize: "14px",
            fontWeight: idx === 0 ? "600" : "400",
            color: "#292524",
            minWidth: "120px",
        },
    }));

    const edges: Edge[] = mindmap.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated: false,
        style: { stroke: "#D6D3D1", strokeWidth: 2 },
    }));

    if (isLoading) {
        return (
            <div className="w-full h-[500px] bg-stone-100 rounded-lg animate-pulse flex items-center justify-center">
                <p className="text-stone-500">加载中...</p>
            </div>
        );
    }

    if (nodes.length === 0) {
        return (
            <div className="w-full h-[500px] bg-white rounded-lg border border-stone-200 flex items-center justify-center">
                <p className="text-stone-500">暂无思维导图</p>
            </div>
        );
    }

    return (
        <div className="w-full h-[500px] bg-[#FDFBF7] rounded-lg border border-stone-200 overflow-hidden">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                fitView
                connectionMode={ConnectionMode.Loose}
                nodesDraggable={false} // 只读模式
                nodesConnectable={false}
                elementsSelectable={false}
            >
                <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#E7E5E4" />
                <Controls showInteractive={false} className="bg-white border border-stone-200 rounded-lg" />
                <MiniMap
                    nodeColor={(node) => (node.position.x === 0 && node.position.y === 0 ? "#FDBA74" : "#E7E5E4")}
                    className="bg-white border border-stone-200 rounded-lg"
                />
            </ReactFlow>
        </div>
    );
}
