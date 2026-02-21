---
name: video-analyzer
description: Analyze videos to extract structured knowledge including mind maps, key highlights, and timestamps. Use when users want to analyze a video (YouTube, Bilibili, or local file), extract video content, generate video summaries, or understand video structure. Triggers: 'analyze video', 'summarize video', 'extract from video', 'video mind map', '视频分析', '总结视频'.
---

# Video Analyzer

Analyze videos using the video-helper backend service to generate structured knowledge artifacts: mind maps, content blocks, highlights with timestamps, and keyframes.

## Quick Start

```bash
# Analyze a YouTube video
python scripts/analyze_video.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Analyze a Bilibili video (output in Chinese)
python scripts/analyze_video.py "https://www.bilibili.com/video/BV1..." --lang zh

# Analyze a local video file
python scripts/analyze_video.py "/path/to/video.mp4" --title "My Video"
```

## Prerequisites

1. **Backend Service**: The skill uses the video-helper backend at `http://localhost:8000`

- By default, `scripts/analyze_video.py` will auto-start the backend if it is not running (local dev only: `localhost:8000`).
- For actual processing, ensure `WORKER_ENABLE=1` is set in the backend environment.

2. **Frontend (Optional)**: For viewing results in browser at `http://localhost:3000`
   - Start with: `cd apps/web && pnpm dev`

3. **Environment Variables**:
   - `VIDEO_HELPER_API_URL`: Backend API URL (default: `http://localhost:8000/api/v1`)
   - `VIDEO_HELPER_FRONTEND_URL`: Frontend URL (default: `http://localhost:3000`)

## Workflow

### Step 1: Verify Backend Health

Before creating analysis jobs, ensure the backend is running:

```bash
curl http://localhost:8000/api/v1/health
```

Expected response: `{"ok": true}`

### Step 2: Submit Video for Analysis

Use the analyze_video.py script. The script handles:

- URL validation and source type detection
- Job creation via API
- Progress polling until completion
- Result URL generation

```bash
python scripts/analyze_video.py "VIDEO_URL_OR_PATH" [options]
```

Options:

- `--title, -t`: Video title (auto-detected for URLs)
- `--lang, -l`: Output language for analysis (e.g., `zh`, `en`)
- `--llm-mode`: `external` (default) or `backend`
- `--no-auto-start-backend`: Disable auto-start when backend is down
- `--timeout`: Max wait time in seconds (default: 600)
- `--json`: Output result as JSON

### Step 3: Retrieve Results

After successful analysis, the script outputs:

- **Project ID**: Unique identifier for the analyzed video
- **Result API**: `GET /api/v1/projects/{projectId}/results/latest`
- **Frontend URL**: Browser link to view interactive results

## Result Structure

The analysis result (`GET /api/v1/projects/{projectId}/results/latest`) contains:

```json
{
  "resultId": "...",
  "projectId": "...",
  "contentBlocks": [
    {
      "blockId": "...",
      "title": "Chapter Title",
      "startMs": 0,
      "endMs": 60000,
      "highlights": [
        {
          "highlightId": "...",
          "text": "Key point extracted from video",
          "startMs": 12000,
          "endMs": 18000,
          "keyframes": [{"assetId": "...", "timeMs": 15000}]
        }
      ]
    }
  ],
  "mindmap": {
    "nodes": [...],
    "edges": [...]
  },
  "assetRefs": [...]
}
```

## Unified Storage

All analysis results are stored in the backend's `DATA_DIR`:

- **Database**: `DATA_DIR/core.sqlite3` (projects, jobs, results, assets)
- **Project Files**: `DATA_DIR/{project_id}/` (videos, audio, keyframes)

This ensures results from both the skill and the frontend are unified and accessible from either interface.

## Error Handling

Common errors and solutions:

| Error                         | Cause                                                  | Solution                                                                                                                   |
| ----------------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| `Backend service unavailable` | Backend not running                                    | Start backend service                                                                                                      |
| `Unsupported video URL`       | URL not supported by yt-dlp                            | Try a different video source                                                                                               |
| `LLM credentials missing`     | No LLM API configured                                  | Set `LLM_API_BASE` and `LLM_API_KEY` or configure via frontend                                                             |
| `Job status = blocked`        | Using `--llm-mode external` and plan not submitted yet | Call `GET /api/v1/jobs/{jobId}/plan-request`, ask editor AI to generate a plan JSON, then `POST /api/v1/jobs/{jobId}/plan` |
| `Job polling timed out`       | Analysis took too long                                 | Increase `--timeout` or check backend logs                                                                                 |

## Examples

### Example 1: Analyze YouTube Video

```
User: Analyze this video for me: https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Action:

```bash
python scripts/analyze_video.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Output:

```
Analysis completed successfully!
Project ID: 2d2f...
Result API: http://localhost:8000/api/v1/projects/2d2f.../results/latest
View in browser: http://localhost:3000/project/2d2f...
```

### Example 2: Analyze Bilibili Video in Chinese

```
User: 分析这个B站视频: https://www.bilibili.com/video/BV1xx411c7mD
```

Action:

```bash
python scripts/analyze_video.py "https://www.bilibili.com/video/BV1xx411c7mD" --lang zh
```

### Example 3: Analyze Local Video File

```
User: I have a video at /home/user/lecture.mp4, please analyze it
```

Action:

```bash
python scripts/analyze_video.py "/home/user/lecture.mp4" --title "Lecture Video"
```

## Supported Video Sources

- **YouTube**: `youtube.com` and `youtu.be` URLs
- **Bilibili**: `bilibili.com` and `b23.tv` URLs
- **Generic URLs**: Any URL supported by yt-dlp
- **Local Files**: `.mp4`, `.mkv`, `.webm`, `.mov`
