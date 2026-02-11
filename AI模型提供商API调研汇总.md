# 主流AI模型提供商HTTP API调研汇总

> 调研日期：2026-02-11  
> 适用场景：开源项目多模型适配

---

## 1. OpenRouter

| 项目 | 信息 |
|------|------|
| **Base URL** | `https://openrouter.ai/api/v1` |
| **API 文档** | https://openrouter.ai/docs |
| **特点** | 统一接口，支持300+模型，60+提供商 |

### 支持的模型（部分）

| Model ID | 提供商 | 说明 |
|----------|--------|------|
| `anthropic/claude-sonnet-4` | Anthropic | Claude Sonnet 4 |
| `anthropic/claude-sonnet-4.5` | Anthropic | Claude Sonnet 4.5 |
| `anthropic/claude-opus-4` | Anthropic | Claude Opus 4 |
| `anthropic/claude-opus-4.5` | Anthropic | Claude Opus 4.5 |
| `anthropic/claude-3.5-sonnet` | Anthropic | Claude 3.5 Sonnet |
| `anthropic/claude-3.7-sonnet` | Anthropic | Claude 3.7 Sonnet |
| `openai/gpt-4o` | OpenAI | GPT-4o |
| `openai/gpt-4o-mini` | OpenAI | GPT-4o Mini |
| `openai/gpt-4.1` | OpenAI | GPT-4.1 |
| `openai/gpt-4.1-mini` | OpenAI | GPT-4.1 Mini |
| `openai/gpt-4.1-nano` | OpenAI | GPT-4.1 Nano |
| `openai/gpt-5` | OpenAI | GPT-5 |
| `openai/gpt-5-mini` | OpenAI | GPT-5 Mini |
| `openai/o3` | OpenAI | o3 |
| `openai/o4-mini` | OpenAI | o4 Mini |
| `google/gemini-2.5-flash` | Google | Gemini 2.5 Flash |
| `google/gemini-2.5-pro` | Google | Gemini 2.5 Pro |
| `google/gemini-2.5-flash-lite` | Google | Gemini 2.5 Flash Lite |
| `google/gemini-3-pro-preview` | Google | Gemini 3 Pro Preview |
| `x-ai/grok-3` | xAI | Grok 3 |
| `x-ai/grok-4` | xAI | Grok 4 |
| `deepseek/deepseek-chat` | DeepSeek | DeepSeek Chat |
| `deepseek/deepseek-r1` | DeepSeek | DeepSeek R1 |
| `meta-llama/llama-3.1-70b` | Meta | Llama 3.1 70B |

---

## 2. OpenAI

| 项目 | 信息 |
|------|------|
| **Base URL** | `https://api.openai.com/v1` |
| **API 文档** | https://platform.openai.com/docs |
| **鉴权方式** | `Authorization: Bearer $OPENAI_API_KEY` |

### 支持的模型

| Model ID | 上下文窗口 | 说明 |
|----------|-----------|------|
| `gpt-4.1` | 1,047,576 tokens | 复杂任务通用模型 |
| `gpt-4.1-mini` | 1,047,576 tokens | 性价比平衡 |
| `gpt-4.1-nano` | 1,047,576 tokens | 速度最快、成本最低 |
| `gpt-4o` | 128,000 tokens | 多模态（文本/图像/音频） |
| `gpt-4o-mini` | 128,000 tokens | 多模态经济版 |
| `gpt-5` | 400,000 tokens | 旗舰推理模型 |
| `gpt-5-mini` | 400,000 tokens | 轻量推理模型 |
| `gpt-5-pro` | 400,000 tokens | 高级推理 |
| `o3` | 200,000 tokens | 推理模型（已废弃，建议用GPT-5） |
| `o4-mini` | 200,000 tokens | 轻量推理 |
| `gpt-oss-120b` | 131,072 tokens | 开源模型 |
| `gpt-oss-20b` | 131,072 tokens | 小型开源模型 |

---

## 3. Anthropic (Claude)

| 项目 | 信息 |
|------|------|
| **Base URL** | `https://api.anthropic.com` |
| **API 文档** | https://docs.anthropic.com |
| **鉴权方式** | `x-api-key: $ANTHROPIC_API_KEY` |
| **API 版本** | `anthropic-version: 2023-06-01` |

### 支持的模型

| Model ID | 上下文窗口 | 说明 |
|----------|-----------|------|
| `claude-sonnet-4` | 200,000 tokens | Sonnet 4 |
| `claude-sonnet-4.5` | 200,000 tokens | Sonnet 4.5 |
| `claude-opus-4` | 200,000 tokens | Opus 4 旗舰 |
| `claude-opus-4.5` | 200,000 tokens | Opus 4.5 |
| `claude-3.5-sonnet` | 200,000 tokens | Claude 3.5 Sonnet |
| `claude-3.7-sonnet` | 200,000 tokens | Claude 3.7 Sonnet |
| `claude-3.7-sonnet-thinking` | 200,000 tokens | 带思考模式 |
| `claude-haiku-4.5` | 200,000 tokens | 轻量快速 |

---

## 4. DeepSeek (深度求索)

| 项目 | 信息 |
|------|------|
| **Base URL** | `https://api.deepseek.com` 或 `https://api.deepseek.com/v1` |
| **API 文档** | https://platform.deepseek.com |
| **鉴权方式** | `Authorization: Bearer $DEEPSEEK_API_KEY` |
| **特点** | 兼容OpenAI API格式 |

### 支持的模型

| Model ID | 上下文窗口 | 说明 |
|----------|-----------|------|
| `deepseek-chat` | 64,000 tokens | 通用对话模型（V3） |
| `deepseek-reasoner` | 64,000 tokens | 推理模型（R1） |
| `deepseek-coder` | 64,000 tokens | 代码专用 |

---

## 5. 阿里通义千问 (Qwen)

| 项目 | 信息 |
|------|------|
| **Base URL** | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| **API 文档** | https://help.aliyun.com/zh/model-studio |
| **鉴权方式** | `Authorization: Bearer $DASHSCOPE_API_KEY` |
| **特点** | 兼容OpenAI API格式 |

### 支持的模型

| Model ID | 上下文窗口 | 说明 |
|----------|-----------|------|
| `qwen-max` | 32,768 tokens | 通义千问Max |
| `qwen-plus` | 131,072 tokens | 通义千问Plus |
| `qwen-flash` | 131,072 tokens | 通义千问Flash |
| `qwen-turbo` | 8,000 tokens | 轻量快速 |
| `qwen-coder-plus` | 131,072 tokens | 代码专用 |
| `qwen-vl-max` | 32,768 tokens | 视觉理解 |

---

## 6. 火山引擎 (方舟)

| 项目 | 信息 |
|------|------|
| **Base URL (数据面)** | `https://ark.cn-beijing.volces.com/api/v3` |
| **Base URL (Coding)** | `https://ark.cn-beijing.volces.com/api/coding/v3` |
| **API 文档** | https://www.volcengine.com/docs/82379 |
| **鉴权方式** | `Authorization: Bearer $ARK_API_KEY` |
| **特点** | 兼容OpenAI API格式 |

### 支持的模型

| Model ID | 说明 |
|----------|------|
| `doubao-seed-1-6-251015` | 豆包Seed 1.6 |
| `doubao-seed-1-6-250615` | 豆包Seed 1.6 |
| `doubao-pro-32k` | 豆包Pro 32K |
| `doubao-lite-32k` | 豆包Lite 32K |
| `ark-code-latest` | Coding Plan最新版 |
| `doubao-seedream-4-5-251128` | 图像生成 |
| `doubao-seedance-1-0-pro-250528` | 视频生成 |

---

## 7. xAI (Grok)

| 项目 | 信息 |
|------|------|
| **Base URL** | `https://api.x.ai/v1` |
| **API 文档** | https://docs.x.ai |
| **鉴权方式** | `Authorization: Bearer $XAI_API_KEY` |
| **特点** | 兼容OpenAI API格式，2M上下文窗口 |

### 支持的模型

| Model ID | 上下文窗口 | 说明 |
|----------|-----------|------|
| `grok-4-1-fast-reasoning` | 2,000,000 tokens | Grok 4.1 快速推理 |
| `grok-4-1-fast-non-reasoning` | 2,000,000 tokens | Grok 4.1 快速非推理 |
| `grok-4` | 131,072 tokens | Grok 4 |
| `grok-4-fast` | 2,000,000 tokens | Grok 4 快速版 |
| `grok-code-fast-1` | 131,072 tokens | 代码专用 |
| `grok-3` | 131,072 tokens | Grok 3 |
| `grok-3-mini` | 131,072 tokens | Grok 3 Mini |
| `grok-2-vision` | 131,072 tokens | 视觉理解 |
| `grok-beta` | 131,072 tokens | Beta版 |

---

## 8. NVIDIA NIM

| 项目 | 信息 |
|------|------|
| **Base URL** | `https://integrate.api.nvidia.com/v1` |
| **API 文档** | https://build.nvidia.com |
| **鉴权方式** | `Authorization: Bearer $NVIDIA_API_KEY` |
| **特点** | 兼容OpenAI API格式，国内可直接访问 |

### 支持的模型

| Model ID | 说明 |
|----------|------|
| `z-ai/glm-4.7` | 智谱GLM-4.7 |
| `z-ai/glm4.7` | 智谱GLM-4.7 |
| `minimaxai/minimax-m2.1` | MiniMax M2.1 |
| `kimi-k2` | Kimi K2 |
| `meta/llama-3.1-405b-instruct` | Llama 3.1 405B |
| `mistralai/mistral-large` | Mistral Large |

---

## 9. Google AI Studio (Gemini)

| 项目 | 信息 |
|------|------|
| **Base URL** | `https://generativelanguage.googleapis.com/v1beta` |
| **API 文档** | https://ai.google.dev/docs |
| **鉴权方式** | `?key=$GOOGLE_API_KEY` 或 Bearer |
| **特点** | 原生Gemini API，多模态支持 |

### 支持的模型

| Model ID | 上下文窗口 | 说明 |
|----------|-----------|------|
| `gemini-2.5-pro` | 1,048,576 tokens | Gemini 2.5 Pro |
| `gemini-2.5-flash` | 1,048,576 tokens | Gemini 2.5 Flash |
| `gemini-2.5-flash-lite` | 1,048,576 tokens | Gemini 2.5 Flash Lite |
| `gemini-3-pro-preview` | 1,048,576 tokens | Gemini 3 Pro Preview |
| `gemini-1.5-pro` | 2,097,152 tokens | Gemini 1.5 Pro |
| `gemini-1.5-flash` | 1,048,576 tokens | Gemini 1.5 Flash |
| `gemini-embedding-001` | - | 嵌入模型 |

---

## 10. 智谱AI (ChatGLM)

| 项目 | 信息 |
|------|------|
| **Base URL (标准)** | `https://open.bigmodel.cn/api/paas/v4` |
| **Base URL (Coding)** | `https://open.bigmodel.cn/api/coding/paas/v4` |
| **Base URL (Anthropic兼容)** | `https://open.bigmodel.cn/api/anthropic` |
| **API 文档** | https://open.bigmodel.cn |
| **鉴权方式** | `Authorization: Bearer $ZHIPU_API_KEY` |
| **特点** | 兼容OpenAI API格式 |

### 支持的模型

| Model ID | 上下文窗口 | 说明 |
|----------|-----------|------|
| `GLM-4.7` | 128,000 tokens | 旗舰模型 |
| `GLM-4.6` | 128,000 tokens | 高性能 |
| `GLM-4.5` | 128,000 tokens | 标准版 |
| `GLM-4.5-Air` | 128,000 tokens | 轻量版 |
| `GLM-4-Flash` | 128,000 tokens | 极速版 |
| `GLM-4V` | 8,000 tokens | 视觉理解 |

---

## 11. MiniMax

| 项目 | 信息 |
|------|------|
| **Base URL (标准)** | `https://api.minimax.chat/v1` |
| **Base URL (OpenAI兼容)** | `https://api.minimaxi.com/v1` |
| **Base URL (Anthropic兼容)** | `https://api.minimaxi.com/anthropic/v1` |
| **API 文档** | https://www.minimaxi.com |
| **鉴权方式** | `Authorization: Bearer $MINIMAX_API_KEY` |
| **特点** | 兼容OpenAI API格式 |

### 支持的模型

| Model ID | 上下文窗口 | 说明 |
|----------|-----------|------|
| `MiniMax-M2.1` | 128,000 tokens | M2.1 旗舰 |
| `MiniMax-M2` | 128,000 tokens | M2 |
| `MiniMax-Text-01` | 128,000 tokens | 文本模型 |
| `abab6.5s-chat` | 245,000 tokens | abab6.5s 超长上下文 |
| `abab6.5t-chat` | 8,000 tokens | abab6.5t 中文场景 |
| `abab6.5g-chat` | 8,000 tokens | abab6.5g 英文场景 |

---

## 快速参考表

| 提供商 | Base URL | 鉴权头 | 兼容格式 |
|--------|----------|--------|----------|
| OpenRouter | `https://openrouter.ai/api/v1` | Bearer | OpenAI |
| OpenAI | `https://api.openai.com/v1` | Bearer | OpenAI |
| Anthropic | `https://api.anthropic.com` | x-api-key | Anthropic |
| DeepSeek | `https://api.deepseek.com/v1` | Bearer | OpenAI |
| 阿里Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Bearer | OpenAI |
| 火山引擎 | `https://ark.cn-beijing.volces.com/api/v3` | Bearer | OpenAI |
| xAI Grok | `https://api.x.ai/v1` | Bearer | OpenAI |
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | Bearer | OpenAI |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta` | key参数 | Gemini |
| 智谱AI | `https://open.bigmodel.cn/api/paas/v4` | Bearer | OpenAI |
| MiniMax | `https://api.minimax.chat/v1` | Bearer | OpenAI |

---

## 配置示例（OpenAI兼容格式）

```json
{
  "providers": {
    "openrouter": {
      "baseUrl": "https://openrouter.ai/api/v1",
      "apiKey": "sk-or-xxx",
      "models": ["anthropic/claude-sonnet-4", "openai/gpt-4o"]
    },
    "openai": {
      "baseUrl": "https://api.openai.com/v1",
      "apiKey": "sk-xxx",
      "models": ["gpt-4o", "gpt-4.1", "gpt-5"]
    },
    "anthropic": {
      "baseUrl": "https://api.anthropic.com",
      "apiKey": "sk-ant-xxx",
      "apiVersion": "2023-06-01",
      "models": ["claude-sonnet-4", "claude-opus-4"]
    },
    "deepseek": {
      "baseUrl": "https://api.deepseek.com/v1",
      "apiKey": "sk-xxx",
      "models": ["deepseek-chat", "deepseek-reasoner"]
    },
    "qwen": {
      "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "apiKey": "sk-xxx",
      "models": ["qwen-max", "qwen-plus", "qwen-flash"]
    },
    "doubao": {
      "baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
      "apiKey": "xxx",
      "models": ["doubao-seed-1-6-251015", "doubao-pro-32k"]
    },
    "xai": {
      "baseUrl": "https://api.x.ai/v1",
      "apiKey": "xai-xxx",
      "models": ["grok-3", "grok-4"]
    },
    "nvidia": {
      "baseUrl": "https://integrate.api.nvidia.com/v1",
      "apiKey": "nvapi-xxx",
      "models": ["z-ai/glm-4.7", "minimaxai/minimax-m2.1"]
    },
    "gemini": {
      "baseUrl": "https://generativelanguage.googleapis.com/v1beta",
      "apiKey": "xxx",
      "models": ["gemini-2.5-pro", "gemini-2.5-flash"]
    },
    "zhipu": {
      "baseUrl": "https://open.bigmodel.cn/api/paas/v4",
      "apiKey": "xxx",
      "models": ["GLM-4.7", "GLM-4.6", "GLM-4.5"]
    },
    "minimax": {
      "baseUrl": "https://api.minimax.chat/v1",
      "apiKey": "xxx",
      "models": ["MiniMax-M2.1", "abab6.5s-chat"]
    }
  }
}
```

---

## 参考资料

1. [OpenRouter Documentation](https://openrouter.ai/docs)
2. [OpenAI API Reference](https://platform.openai.com/docs)
3. [Anthropic API Documentation](https://docs.anthropic.com)
4. [DeepSeek Platform](https://platform.deepseek.com)
5. [阿里云百炼文档](https://help.aliyun.com/zh/model-studio)
6. [火山方舟文档](https://www.volcengine.com/docs/82379)
7. [xAI Documentation](https://docs.x.ai)
8. [NVIDIA Build](https://build.nvidia.com)
9. [Google AI Studio](https://aistudio.google.com)
10. [智谱AI开放平台](https://open.bigmodel.cn)
11. [MiniMax官网](https://www.minimaxi.com)
