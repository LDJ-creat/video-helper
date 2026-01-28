---
stepsCompleted:
  - step-01-visual-style
  - step-02-layout
  - step-03-components
inputDocuments:
  - develop_design.md
  - prd.md
---

# UX Design Specification - video-helper

**Author:** LDJ
**Date:** 2026-01-28

---

## 1. Design Philosophy

**"Focus & Flow" (专注与流式)** + **"Cozy Studio" (温馨书房)**

- **理念**：界面应像一张整洁、温暖的“书房书桌”。内容（视频/笔记）是主角，UI 框架应退居幕后，但在交互时提供明确反馈。
- **视觉风格**：**Warm Minimalist (暖色极简)**。放弃冷冰冰的科技蓝/灰，转而使用“纸张感”的米白与暖灰，营造沉浸式、低视觉疲劳的长时学习环境。
- **核心体验**：把复习过程从“痛苦的进度条拖拽”变成“愉悦的知识漫游”。
- **布局核心**：**Tri-Pane Focus (三栏/双栏响应式)**。巧妙处理“视频观看”与“笔记整理”的空间冲突，通过 **Sticky Floating Player (智能悬浮播放器)** 保证上下文始终在线。

---

## 2. Color System: "Warm Paper & Ink"

**Mood**: Calm, Organic, Readable. (Based on `ui-ux-pro-max` "Cozy Minimalist")

| 语义 (Role) | 色值建议 (Tailwind Token / Hex) | 视觉感受与用途 |
| :--- | :--- | :--- |
| **Canvas (背景)** | `bg-[#FDFBF7]` (Warm Cream) | 全局背景，像这就泛黄的厚重书页，极度护眼，减少蓝光感。 |
| **Surface (卡片)** | `bg-[#FFFFFF]` + `Warm Shadow` | 纯白卡片在奶油色背景上显得干净、透气。微投影使用暖色调。 |
| **Primary (主交互)** | `bg-stone-800` / `text-stone-700` (Warm Charcoal) | 替代纯黑或亮蓝。用于主按钮、标题。深暖灰给人稳重、专注感。 |
| **Accent (点缀/高亮)** | `text-orange-600` / `bg-orange-100` (Amber/Terracotta) | 像荧光笔但更柔和。用于选中状态、Focus Ring、重要划线。 |
| **Typography (正文)** | `text-stone-800` (Ink) | 深棕灰色，避免高对比度纯黑对眼睛的刺激。 |
| **Typography (次要)** | `text-stone-500` (Pencil) | 像铅笔字迹，用于辅助说明、时间戳。 |
| **Border (边框)** | `border-stone-200` | 柔和的暖灰色边框，用于分割卡片。 |
| **Success** | `text-emerald-600` | 保持清晰的绿色，但降低饱和度以融入暖色调。 |
| **Error** | `text-rose-600` | 保持警示性，但不过分刺眼。 |

---

## 3. Typography

**Base Font**: `Inter` (Next.js Default) or System Sans-Serif.

**Scale Strategy**:
- **Display (H1)**: `text-2xl font-bold tracking-tight text-stone-900` (e.g., Project Title)
- **Header (H2)**: `text-lg font-semibold text-stone-800` (e.g., Chapter Title)
- **Title (H3)**: `text-base font-medium text-stone-900` (e.g., Card Header)
- **Body (Notes)**: `text-base leading-relaxed text-stone-700` (笔记正文字号特意调大，增加阅读舒适度)
- **Meta (Mono)**: `text-xs font-mono text-stone-500` (e.g., `04:20`)

---

## 4. Layout & Interaction Patterns

### A. Result Page Layout (Desktop) - "Tri-Pane Focus"

在大屏模式下，采用 **左视频+导图 / 右笔记** 的不对称布局，最大化利用宽屏优势。

```
+---------------------------------------------------------------+
|  Header (Logo | Project Name | Export | Settings)               |
+---------------------------------------------------------------+
| Panes Container (grid-cols-12 gap-6 p-6)                      |
|                                                               |
| [ Left Pane: Visual (col-span-7) ]     [ Right Pane: Text (col-span-5) ]
|                                                               |
| +----------------------------------+   +-------------------+  |
| | Video Player (Aspect 16:9)       |   | Editor Toolbar    |  |
| |                                  |   +-------------------+  |
| | (Sticky-able)                    |   |                   |  |
| +----------------------------------+   | Note Editor       |  |
|                                        | (Tiptap)          |  |
| +----------------------------------+   |                   |  |
| | Tabs: Mindmap | Keywords | Assets|   | - Title           |  |
| +----------------------------------+   | - Paragraph       |  |
| |                                  |   | - Bullet List     |  |
| | Mindmap Canvas (React Flow)      |   |                   |  |
| | (Infinite Canvas)                |   |                   |  |
| |                                  |   |                   |  |
| +----------------------------------+   +-------------------+  |
+---------------------------------------------------------------+
```

### B. Sticky Floating Player (智能悬浮交互)

为了解决“写笔记/看导图时看不见视频”的问题：

1.  **Trigger (触发)**: 当主视频播放器区域滚动出视口 (Viewport) 顶部时 (Intersection Observer)。
2.  **Transition (过渡)**: 播放器容器由 `static` 变为 `fixed`，伴随 `scale-in` 动画。
3.  **Floating State (悬浮态)**:
    - **Position**: 右下角 `bottom-6 right-6` (或笔记区上方)。
    - **Size**: 宽 `320px`，高 `180px` (16:9)。
    - **Style**: `rounded-lg shadow-xl shadow-stone-200 border border-stone-200 z-50`.
    - **Controls (Mini)**:
      - `Play/Pause`
      - `Rewind 10s` / `Forward 10s`
      - `Expand` (回到顶部原位)
      - `Close` (关闭悬浮，只保留声音或完全暂停)
4.  **Recovery (恢复)**:
    - 用户点击 "Expand" -> 页面平滑滚动回顶部，播放器放回原位。
    - 用户点击 "Close" -> 悬浮窗消失，顶部出现 "Show Video" Toast。

### C. Responsive Strategy (Mobile/Tablet)

- **Mobile (<768px)**: 垂直堆叠 (Stack)。
  - **Top**: Video Player (Sticky behavior modified: sticky to top `-top-0`).
  - **Middle**: Horizontal Scroller for Chapters.
  - **Bottom**: Tab View for Content (Notes / Mindmap / Highlights).
  
---

## 5. Key Component Specs

### 5.1 Card Styles
- **Default**: `bg-white rounded-xl border border-stone-200 shadow-sm`.
- **Hover**: `hover:shadow-md hover:border-stone-300 transition-all duration-200`.

### 5.2 Buttons
- **Primary**: `bg-stone-800 text-white hover:bg-stone-900 active:scale-95`.
- **Secondary**: `bg-stone-100 text-stone-700 hover:bg-stone-200 active:scale-95`.
- **Ghost**: `hover:bg-stone-50 text-stone-600`.

### 5.3 Mindmap Nodes
- **Idea is**: Nodes should look like "Sticky Notes" or "Index Cards".
- **Root Node**: `bg-orange-50 border-orange-200 text-stone-900 font-medium`.
- **Child Node**: `bg-white border-stone-200 text-stone-700`.
- **Connector**: `stroke-stone-300` (Curved bezier lines).

### 5.4 Loading States
- **Skeleton**: 使用 `bg-stone-100` 或 `animate-pulse` 模拟内容块，而非简单的 Spinner。
- **Message**: "Analyzing audio...", "Extracting wisdom..." (Use warm, human copy).

---

## 6. Implementation Checklist

- [ ] Setup Tailwind Config (add `stone`, `cream` colors).
- [ ] Create `Layout` component with Tri-Pane grid.
- [ ] Implement `StickyVideoPlayer` component with Intersection Observer.
- [ ] Customize `Tiptap` editor theme to match "Cozy" style.
- [ ] Customize `React Flow` node styles.
- [ ] Verify accessibility (Contrast ratios for Stone-500+ text on Cream bg).
