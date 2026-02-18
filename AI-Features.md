# UI/UX Design Spec: Video Helper AI Features

> [!NOTE]
> This specification follows the **Warm Minimalist** design aesthetic established in the project (Stone/Orange palette) and utilizes the `ui-ux-pro-max` guidelines for professional implementation.

## 1. Layout Strategy

### Current Architecture
- **Left Pane:** Mindmap (Sticky)
- **Right Pane:** Video Player (Top) + Note Editor (Bottom/Flex)

### Proposed Architecture
We will transform the **Left Pane** (currently Mindmap only) into a **Structure & Learning Hub**. This allows the **Right Pane** to remain focused on the **Video Source** and **User Notes**, enabling a key workflow: *Watching the video and taking notes while consulting the AI helper.*

#### Structure
The Left Pane will feature a `Tabs` component with three modes:
1.  **思维导图 (Mindmap)** - Visualize structure.
2.  **AI 助手 (AI Chat)** - Q&A interface.
3.  **实战演练 (Canvas)** - Interactive Exercises.

```tsx
// Concept Layout
<div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-screen pb-20">
  
  {/* Left Pane: Sticky Learning Hub */}
  <div className="lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)] bg-white rounded-xl border border-stone-200 overflow-hidden flex flex-col shadow-sm">
    <div className="border-b border-stone-200 px-4 py-3 bg-stone-50/50">
       <TabsList className="w-full grid grid-cols-3">
          <Tab value="mindmap">思维导图</Tab>
          <Tab value="chat">AI 助手</Tab>
          <Tab value="exercises">实战演练</Tab>
       </TabsList>
    </div>
    <div className="flex-1 overflow-hidden relative">
      <TabsContent value="mindmap" className="h-full"><MindmapEditor /></TabsContent>
      <TabsContent value="chat" className="h-full"><AIChat /></TabsContent>
      <TabsContent value="exercises" className="h-full"><ExercisesCanvas /></TabsContent>
    </div>
  </div>

  {/* Right Pane: Video + Notes (Unchanged) */}
  <div className="flex flex-col space-y-6">
     <VideoPlayer />
     <NoteEditor />
  </div>
</div>
```

---

## 2. Feature: AI Chat (AI 助手)

### Core User Experience
A persistent conversational partner that helps users understand the video content. It is context-aware (knows the video transcript and current timestamp) and connects answers back to the source material.

### UI Components

#### 1. Empty State (Onboarding)
When no chat exists, display a clean, welcoming state with clear value proposition and suggestions.
- **Icon**: `Sparkles` (Lucide) in `text-orange-500`.
- **Title**: "关于这个视频，你想了解什么？"
- **Suggested Prompts**: 3-4 clickable chips generated based on video context.
  - "总结这段视频的重点"
  - "解释一下 [核心概念]"
  - "基于这个视频生成一份测验"

#### 2. Message List
- **User Message**: Aligned right. `bg-stone-100` text-stone-900. Rounded-2xl, rounded-tr-sm.
- **AI Message**: Aligned left. `bg-white` (or transparent) text-stone-800.
  - **Avatar**: Project Logo or AI Icon.
  - **Citations**: If the AI references a specific part of the video, it renders a clickable **Timestamp Chip** (e.g., `[04:20]`). Clicking it seeks the video player.
  - **Rich Text**: Supports Markdown (bold, lists, code blocks).

#### 3. Input Area
- **Design**: Floating look or pinned to bottom.
- **Component**: `<TextareaAutosize>` with a max-height.
- **Actions**:
  - `Send` button (Orange-500, rounded-full).
  - `Context` toggle: "Include current video frame" (optional future enforcement).

### Interaction Details
- **Streaming**: Responses should stream in real-time (typewriter effect).
- **Auto-scroll**: Auto-scroll to bottom on new tokens, pause scroll if user scrolls up.
- **History**: Chat history persists per project/result.

---

## 3. Feature: Interactive Exercises (实战演练 - Gemini Canvas Style)

### Core User Experience
An interactive "Canvas" mode where the AI guides the user through active learning. Unlike a static quiz, this is a dynamic flow: Question -> Answer -> AI Feedback -> Next Step.

### UI Layout: The "Learning Card"
The view consists of a centered content area (max-width optimized for reading) focused on one task at a time.

#### 1. Progress / Topic Header
- Top bar showing the current "Learning Goal" or Topic.
- **Progress Bar**: Thin, orange-500 line indicating session progress.

#### 2. The Interaction Stage (Canvas)
Dynamic content area that changes based on the type of exercise:

**Type A: Multiple Choice / Select**
- **Question**: Large, legible typography (`text-lg font-medium`).
- **Options**: Vertical stack of cards.
  - Default: `border-stone-200 hover:border-orange-300 hover:bg-orange-50`.
  - Selected: `border-orange-500 bg-orange-50 ring-1 ring-orange-500`.
  - Correct (after check): `border-green-500 bg-green-50`.
  - Incorrect (after check): `border-red-500 bg-red-50`.

**Type B: Open Ended / Code**
- **Question**: "Write a summary..." or "Refactor this code..."
- **Editor**: Embedded text area or code editor (Monaco/Simple code block).
- **AI Evaluation**: After submission, AI provides a critique (Strength, Weakness, Score) below the input.

#### 3. Feedback & Controls
- **Action Bar**: Sticky at bottom of the container.
- **Primary Button**: "检查答案" (Check) -> "下一题" (Next).
- **Secondary Actions**: "给我提示" (Hint), "太难了" (Skip/Adjust).
- **AI Feedback**: When checking answers, a `Suggestion` block appears:
  - **Core Feedback**: "Correct!" or "Not quite."
  - **Explanation**: "The key difference is..."
  - **Reference**: Link to video timestamp `[05:30]` where this was explained.

### "Gemini Canvas" Vibe
To mimic the "Canvas" feel:
- Use **cards** for distinct logic units.
- Animation: Smooth transitions between questions (fade/slide).
- **Sparkle Effects**: Subtle gradients or glows when AI is generating the next question.

---

## 4. Visual Specs (Component Level)

### Typography
- **Headings**: `font-sans font-semibold text-stone-900`.
- **Body**: `font-sans text-stone-600 leading-relaxed`.
- **Monospace**: `font-mono text-sm` for timestamps and code.

### Colors (Warm Minimalist)
- **Primary Action**: `bg-orange-500 hover:bg-orange-600 text-white`.
- **Secondary Action**: `bg-white border border-stone-200 hover:bg-stone-50 text-stone-700`.
- **Backgrounds**:
  - Main Panel: `bg-white`.
  - Secondary/Hollow: `bg-stone-50`.
  - Active Selection: `bg-orange-50/50`.
- **Borders**: `border-stone-200` (light mode).

### Icons (Lucide React)
- Chat: `MessageSquareText`
- Exercises: `GraduationCap` or `BrainCircuit`
- Notes: `NotebookPen`
- Send: `SendHorizontal`
- Check: `CheckCircle2`
- Hint: `Lightbulb`
