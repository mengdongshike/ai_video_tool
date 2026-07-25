# AI 口播工坊 — 后端服务

> 面向短视频口播创作者的 AI 全流程自动化后端。从文案生成、语音合成、数字人生成到视频合成与多平台发布，提供完整的 REST API 微服务体系。

---

## 一、项目介绍

### 1.1 它能做什么？

```
输入主题/文案 → AI 生成口播文案 → 克隆/合成语音 → 数字人驱动 → 字幕+BGM合成 → 多平台发布
```

用户只需提供**文案主题**和**参考音频/视频**，后端自动完成从文案到成片的全流程，并通过桌面客户端或 API 直接调用。

### 1.2 核心功能矩阵

| 功能模块 | 具体能力 | 技术实现 |
|---------|---------|---------|
| **文案生成** | 按行业/风格/人设生成口播文案 | DeepSeek API + 提示词模板 |
| **文案改写** | 优化润色、调整风格、品牌词植入 | DeepSeek API |
| **文案提取** | 从抖音/小红书/B站链接提取视频文案 | Whisper + yt-dlp |
| **品牌词管理** | 自定义品牌词，生成时自动软性植入 | SQLite |
| **音色克隆** | 上传 15 秒音频，克隆真人音色 | IndexTTS2 |
| **语音合成** | 文本转语音，8 维情感向量控制 | IndexTTS2 |
| **数字人** | 上传视频+音频，生成口型同步视频 | LatentSync |
| **字幕生成** | 自动切句 + SRT 字幕（按时长等比分配）| TTS 服务内置 |
| **视频合成** | 字幕叠加 + BGM 混音 + 色彩描边 | FFmpeg (libx264) |
| **封面生成** | 抽帧 + 标题/副标题叠加 + 遮罩 | FFmpeg drawtext |
| **项目管理** | 多项目并行，状态追踪，进度存档 | SQLite |
| **模板管理** | 字幕模板、封面模板（字体/颜色/位置）| SQLite |
| **自动任务** | 一键流水线：TTS → 数字人 → 合成 → 发布 | 任务队列引擎 |
| **多平台发布** | 抖音/小红书/快手/视频号，Playwright 自动化 | social-auto-upload |

---

## 二、技术架构

### 2.1 整体架构图

```
┌───────────────────────────────────────────────────────────────┐
│                      FastAPI 主服务 (:8000)                    │
│                                                               │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ general │ │ voices   │ │ videos   │ │ compose          │  │
│  │ copy    │ │ tts      │ │ dh       │ │ watermark/resize │  │
│  │ extract │ │          │ │          │ │ extract-audio    │  │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
│       │           │            │                │             │
│  ┌────┴───────────┴────────────┴────────────────┴─────────┐   │
│  │              数据库层 (database/)                       │   │
│  │  projects | voices | videos | templates | brand_words  │   │
│  │  publish_accounts | publish_records | cover_templates  │   │
│  │  subtitle_templates                                     │   │
│  └────────────────────────┬───────────────────────────────┘   │
│                           │ SQLite (data/app.db)              │
│  ┌────────────────────────┴───────────────────────────────┐   │
│  │              工具层 (utils/)                            │   │
│  │  llm_client | subtitle | upload | logger                │   │
│  │  video_downloader | platform | text_extractor           │   │
│  └───────────────────┬────────────────────────────────────┘   │
│                      │ HTTP (httpx)                            │
└──────────────────────┼────────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
┌───────▼──────────┐     ┌───────────▼──────────┐
│  TTS 微服务       │     │  LatentSync 微服务    │
│  (:8101)         │     │  (:8102)              │
│  venv_tts        │     │  venv_latent          │
│  torch 2.8+cu128 │     │  torch 2.5.1+cu121    │
│                  │     │                       │
│  POST /synthesize│     │  POST /generate       │
│  POST /unload    │     │  GET  /status         │
│                  │     │  POST /unload         │
│  IndexTTS2       │     │  LatentSync Pipeline  │
│  • 音色克隆       │     │  • 口型同步           │
│  • 情感合成       │     │  • DeepCache 加速     │
│  • SRT 字幕生成  │     │                       │
└──────────────────┘     └───────────────────────┘
```

### 2.2 为什么用两个独立 Python 环境？

IndexTTS2 依赖 **torch ≥ 2.8.0**（仅 cu126/cu128/cu129），LatentSync 依赖 **torch 2.5.1**（仅 cu118/cu121/cu124）。两个 torch 版本二进制不兼容，必须分开：

| 环境 | 位置 | torch 版本 | CUDA | 用途 |
|------|------|-----------|------|------|
| `venv_tts` | `venv_tts/` | 2.8.0+cu128 | 12.8 | IndexTTS2（音色克隆 + 语音合成）|
| `venv_latent` | `venv_latent/` | 2.5.1+cu121 | 12.1 | LatentSync（数字人生成）|
| `python/` | `python/` | 嵌入式 Python | - | 宿主 Python（仅 FastAPI + uvicorn + httpx）|

### 2.3 服务间通信

| 调用方 | 被调用方 | 方式 | 说明 |
|--------|---------|------|------|
| API (:8000) → TTS (:8101) | HTTP POST | httpx AsyncClient | 合成语音、卸载模型 |
| API (:8000) → Latent (:8102) | HTTP POST | httpx AsyncClient | 数字人生成、卸载模型 |
| Auto Task → TTS | HTTP POST | httpx Client | 自动流水线中的 TTS 步骤 |
| Auto Task → Latent | HTTP POST | httpx Client | 自动流水线中的数字人步骤 |
| Auto Task → Compose | 函数调用 | 直接 import | 同进程内合成 |
| Auto Task → Publish | subprocess | sau_cli.py | Playwright 浏览器自动化 |

---

## 三、目录结构

```
AI_video_tool/                          ← 后端根目录
│
├── services/                           ← 后端服务
│   ├── api_server.py                   ← FastAPI 主入口 (:8000)
│   ├── tts_service.py                  ← TTS 微服务入口 (:8101)
│   ├── latent_service.py               ← 数字人微服务入口 (:8102)
│   │
│   ├── routes/                         ← 路由层（每个文件一个 APIRouter）
│   │   ├── general.py                  ← 项目管理 + 文案 + 品牌词
│   │   ├── voices.py                   ← 音色管理 + TTS 合成代理
│   │   ├── videos.py                   ← 视频管理 + 数字人生成代理
│   │   ├── compose.py                  ← 视频合成（字幕+BGM+封面）
│   │   ├── settings.py                 ← 系统设置（模型选择 + API Key）
│   │   ├── cookies.py                  ← 平台 Cookie 管理
│   │   ├── extract.py                  ← 文案提取（链接 → 文案）
│   │   ├── templates.py                ← 模板管理
│   │   ├── subtitle_templates.py       ← 字幕模板管理
│   │   ├── cover_templates.py          ← 封面模板管理 + 封面生成
│   │   ├── publish.py                  ← 多平台发布（队列 + Playwright）
│   │   ├── auto_task.py                ← 自动流水线（任务队列引擎）
│   │   └── logs.py                     ← 日志查看
│   │
│   ├── database/                       ← 数据层
│   │   ├── __init__.py                 ← 统一导出
│   │   ├── core.py                     ← DB 连接 / 建表 / 迁移
│   │   ├── projects.py                 ← 项目 CRUD
│   │   ├── voices.py                   ← 音色 CRUD
│   │   ├── videos.py                   ← 视频 CRUD
│   │   ├── templates.py                ← 模板 CRUD
│   │   ├── brand_words.py              ← 品牌词 CRUD
│   │   ├── cover_templates.py          ← 封面模板 CRUD
│   │   ├── subtitle_templates.py       ← 字幕模板 CRUD
│   │   └── publish.py                  ← 发布账号 + 记录 CRUD
│   │
│   └── utils/                          ← 工具层
│       ├── llm_client.py               ← 多模型 LLM 客户端（DeepSeek）
│       ├── subtitle.py                 ← SRT 解析 + FFmpeg 字幕滤镜构建
│       ├── upload.py                   ← 文件上传（音频/视频/BGM）
│       ├── logger.py                   ← 统一日志（控制台 + 滚动文件）
│       ├── video_downloader.py         ← 多平台视频下载
│       ├── platform.py                 ← 平台下载器工厂
│       └── text_extractor.py           ← 视频文案提取（Whisper）
│
├── models/                             ← 模型源码
│   ├── indextts/                       ← IndexTTS2（manifest.json）
│   └── latentsync/                     ← LatentSync（manifest.json + 推理脚本）
│       ├── latentsync/pipelines/       ← 推理管线
│       ├── configs/unet/               ← UNet 配置 (stage1/stage2)
│       ├── configs/syncnet/            ← SyncNet 配置
│       └── checkpoints/                ← VAE 权重
│
├── checkpoints/                        ← 模型权重文件
│   ├── indextts2/                      ← gpt.pth, s2mel.pth, BigVGAN, config.yaml
│   ├── latentsync/                     ← latentsync_unet.pt
│   └── whisper/                        ← Whisper (CTranslate2 格式)
│
├── ffmpeg/                             ← FFmpeg 二进制（ffmpeg.exe + ffprobe.exe）
│
├── fonts/                              ← 字幕/封面字体
│   ├── SourceHanSansSC-Regular-2.otf
│   ├── ZhanKuQingKeHuangYouTi-2.ttf
│   └── ... (8种中文字体)
│
├── templates/                          ← 行业提示词模板
│   └── prompts.json                    ← 5 个行业 × 多风格 × 多人设
│
├── uploads/                            ← 用户上传
│   ├── voices/                         ← 参考音频（自动截取 ≤15s）
│   ├── videos/                         ← 参考视频
│   └── bgm/                            ← 背景音乐
│
├── outputs/                            ← 生成输出
│   ├── audio/                          ← 合成音频 (.wav + .srt)
│   ├── video/                          ← 数字人视频 + 临时文件
│   ├── compose/                        ← 最终合成视频
│   └── covers/                         ← 封面图片
│
├── profiles/                           ← 克隆音色特征文件
│   ├── douyin.txt                      ← 抖音 Cookie
│   ├── xiaohongshu.txt                 ← 小红书 Cookie
│   └── bilibili.txt                    ← B站 Cookie
│
├── data/                               ← 数据存储
│   ├── app.db                          ← SQLite 数据库 (WAL 模式)
│   └── settings.json                   ← 系统配置
│
├── logs/                               ← 日志（按日期滚动）
│   └── api_YYYYMMDD.log
│
├── venv_tts/                           ← TTS 虚拟环境 (torch 2.8.0+cu128)
├── venv_latent/                        ← 数字人虚拟环境 (torch 2.5.1+cu121)
└── python/                             ← 宿主 Python (嵌入式)
```

---

## 四、快速开始

### 4.1 环境要求

| 依赖 | 最低版本 | 推荐 |
|------|---------|------|
| Windows | 10 / 11 | Windows 11 |
| NVIDIA GPU | ≥ 8 GB VRAM | RTX 4060+ (推荐 12GB+) |
| CUDA Driver | ≥ 11.8 | ≥ 12.8 |
| Python（宿主）| 3.10 / 3.11 | 3.11 |
| 磁盘空间 | ~30 GB | 50 GB+（含模型权重）|

### 4.2 模型权重准备

使用前需下载以下模型权重到 `checkpoints/` 目录：

```
checkpoints/
├── indextts2/
│   ├── gpt.pth              ← IndexTTS2 GPT 模型
│   ├── s2mel.pth            ← Semantic-to-Mel 模型
│   ├── BigVGAN/             ← 声码器
│   └── config.yaml          ← 配置文件
├── latentsync/
│   └── latentsync_unet.pt   ← LatentSync UNet 权重
└── whisper/
    └── ct2/                 ← Whisper CTranslate2 模型
        ├── model.bin
        ├── config.json
        ├── tokenizer.json
        └── vocabulary.txt
```

> **注意：** 模型权重文件较大（总计约 20GB+），不包含在代码库中。请参考各模型官方仓库下载。

### 4.3 安装依赖

```bash
# 1. 安装宿主 Python 依赖（在 python/ 或系统 Python 中）
pip install fastapi uvicorn[standard] httpx python-multipart

# 2. 安装 TTS 环境依赖（在 venv_tts 中）
# 先激活 venv_tts，然后安装：
pip install torch==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128
pip install indextts numpy librosa soundfile

# 3. 安装 LatentSync 环境依赖（在 venv_latent 中）
# 先激活 venv_latent，然后安装：
pip install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
pip install diffusers transformers accelerate omegaconf opencv-python
pip install imageio imageio-ffmpeg kornia
```

### 4.4 启动服务

三个服务需要分别启动（建议开三个终端窗口）：

```bash
# 终端 1：启动 API 主服务 (:8000)
cd F:\Hermes\AI_video_tool
python\python.exe services\api_server.py
# 输出: "API Service starting on :8000..."

# 终端 2：启动 TTS 服务 (:8101)
# 使用 venv_tts 环境的 Python
venv_tts\Scripts\python.exe services\tts_service.py
# 输出: "TTS Service starting on :8101..."
# 首次调用 /synthesize 时懒加载 IndexTTS2（约 10 秒）

# 终端 3：启动数字人服务 (:8102)
# 使用 venv_latent 环境的 Python
venv_latent\Scripts\python.exe services\latent_service.py
# 输出: "Latent Service starting on :8102..."
# 首次调用 /generate 时懒加载 LatentSync（约 15 秒）
```

### 4.5 健康检查

```bash
# 检查 API 主服务
curl http://127.0.0.1:8000/health
# → {"status":"ok","service":"ai-video-tool"}

# 检查 TTS 服务
curl -X POST http://127.0.0.1:8101/unload
# → {"status":"unloaded"}

# 检查数字人服务
curl http://127.0.0.1:8102/status
# → {"model_loaded":false,"vram_gb":0.0}
```

---

## 五、API 文档

### 5.1 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |

### 5.2 项目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/projects` | 获取项目列表 |
| `POST` | `/api/projects` | 创建项目 |
| `GET` | `/api/projects/stats` | 项目统计 |
| `GET` | `/api/projects/{id}` | 获取项目详情 |
| `PUT` | `/api/projects/{id}` | 更新项目 |
| `DELETE` | `/api/projects/{id}` | 删除项目 |
| `POST` | `/api/projects/{id}/start` | 项目标记为 running |
| `POST` | `/api/projects/{id}/complete` | 项目标记为 done |
| `POST` | `/api/projects/{id}/fail` | 项目标记为 failed |

**请求/响应示例 — 创建项目：**
```json
POST /api/projects
Body: { "name": "我的第一条口播" }

Response 200:
{
  "id": "a1b2c3d4-...",
  "name": "我的第一条口播",
  "status": "draft",
  "created_at": "2026-07-25T10:00:00"
}
```

### 5.3 文案生成

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/copy/generate` | 生成口播文案 |
| `POST` | `/api/copy/optimize` | 改写/优化文案 |

**请求/响应示例 — 生成文案：**
```json
POST /api/copy/generate
Body: {
  "topic": "如何克服拖延症",
  "style": "口语闲聊风",
  "persona": "知心姐姐",
  "length": 200,
  "brand_words": "",
  "language": "中文",
  "pid": "a1b2c3d4-..."
}

Response 200:
{
  "content": "你有没有这种感受，明明一堆事要做...(完整文案)",
  "word_count": 198
}
```

支持 **8 种风格**：口语闲聊风、犀利通透风、治愈共情风、干货落地风、幽默自嘲风、真诚走心风、反差颠覆风、极简短句风

支持 **21 种人设**：知心姐姐、毒舌博主、暴躁学姐、理性军师、逆袭路人、段子手老铁 等

### 5.4 品牌词管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/copy/brand-words` | 品牌词列表 |
| `POST` | `/api/copy/brand-words` | 添加品牌词 |
| `DELETE` | `/api/copy/brand-words/{word}` | 删除品牌词 |

### 5.5 文案提取

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/extract/text` | 从视频链接提取文案（下载+Whisper）|
| `POST` | `/api/extract/info` | 获取视频信息（不下载）|
| `POST` | `/api/extract/text/clean` | 文本清理 |
| `GET` | `/api/extract/platforms` | 支持的平台列表 |

**请求/响应示例：**
```json
POST /api/extract/text
Body: { "url": "https://www.douyin.com/video/...", "pid": "a1b2..." }

Response 200:
{
  "content": "提取的视频文案...",
  "word_count": 150,
  "video_path": "uploads/videos/douyin_xxx.mp4"
}
```

支持平台：抖音、小红书、B站（需 Cookie）、快手 等。

### 5.6 音色管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/voices` | 音色列表（preset + cloned）|
| `POST` | `/api/voices` | 上传音频并创建音色 |
| `GET` | `/api/voices/stats` | 音色统计 |
| `PUT` | `/api/voices/{id}` | 重命名音色 |
| `DELETE` | `/api/voices/{id}` | 删除音色 |
| `POST` | `/api/voices/{id}/default` | 设为默认音色 |

**请求/响应示例 — 上传音色：**
```
POST /api/voices
Content-Type: multipart/form-data
Fields:
  file: [音频文件 .wav/.mp3/.m4a]
  name: "我的声音"

Response 200:
{
  "id": 1,
  "title": "我的声音",
  "voice_url": "uploads/voices/a1b2_我的声音.wav",
  "audio_path": "uploads/voices/a1b2_我的声音.wav",
  "is_default": false
}
```

> 上传音频超过 **15 秒** 会自动截取前 15 秒。

### 5.7 TTS 语音合成

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/tts/synthesize` | 合成语音（通过 TTS 微服务）|

**请求/响应示例：**
```json
POST /api/tts/synthesize
Body: {
  "text": "大家好，今天我们来聊聊人工智能的最新进展...",
  "profile": "uploads/voices/a1b2_我的声音.wav",
  "pid": "a1b2c3d4-...",
  "emo_text": "兴奋",
  "emo_alpha": 1.0,
  "interval_silence": 200,
  "max_text_tokens_per_segment": 120
}

Response 200:
{
  "audio_url": "outputs/audio/synth_1234567890.wav",
  "subtitle_url": "outputs/audio/synth_1234567890.srt",
  "format": "wav"
}
```

**情感控制参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `emo_vector` | list[float] | null | 8 维情感向量（可选，覆盖面更广）|
| `emo_audio_path` | string | "" | 情感参考音频路径 |
| `emo_text` | string | "" | 情感文字描述（如"开心"、"悲伤"、"愤怒"）|
| `emo_alpha` | float | 1.0 | 情感强度 (0.0~2.0) |
| `interval_silence` | int | 200 | 句间停顿（毫秒）|
| `max_text_tokens_per_segment` | int | 120 | 每段最大 token 数 |

### 5.8 数字人生成

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/dh/generate` | 生成数字人视频 |
| `GET` | `/api/dh/models` | 获取可用模型 |

**请求/响应示例：**
```
POST /api/dh/generate
Content-Type: multipart/form-data
Fields:
  avatar_url: "uploads/videos/ref_video.mp4"
  pid: "a1b2c3d4-..."

Response 200:
{
  "video_url": "outputs/video/dh_synth_1234567890.mp4",
  "format": "mp4"
}
```

> - 带 3 次自动重试机制（处理显存不足导致的连接断开）
> - 超时时间 1800 秒（30 分钟）
> - 支持 DeepCache 加速推理
> - 生成完毕后自动卸载模型释放显存

### 5.9 视频管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/videos` | 视频列表 |
| `POST` | `/api/videos/upload` | 上传视频 |
| `GET` | `/api/videos/stats` | 视频统计 |
| `GET` | `/api/videos/{id}` | 视频详情 |
| `DELETE` | `/api/videos/{id}` | 删除视频 |
| `PUT` | `/api/videos/{id}` | 重命名视频 |
| `POST` | `/api/videos/{id}/thumbnail` | 生成缩略图 |

### 5.10 视频合成

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/compose/video` | 合成视频（字幕+BGM+封面）|
| `POST` | `/api/compose/watermark` | 添加水印 |
| `POST` | `/api/compose/resize` | 调整尺寸 |
| `POST` | `/api/compose/extract-audio` | 提取音频 |
| `GET` | `/api/compose/duration` | 获取视频时长 |

**请求/响应示例 — 合成视频：**
```json
POST /api/compose/video
Body: {
  "video_path": "outputs/video/dh_synth_1234567890.mp4",
  "srt_path": "outputs/audio/synth_1234567890.srt",
  "bgm_path": "uploads/bgm/background.mp3",
  "bgm_volume": 0.3,
  "subtitle_template_id": "1",
  "cover_template_id": "1",
  "cover_title": "AI 改变生活",
  "cover_subtitle": "数字人口播"
}

Response 200:
{
  "file_url": "outputs/compose/final_dh_synth_1234567890.mp4",
  "size_mb": 45.2,
  "cover_url": "outputs/covers/cover_abc123.png"
}
```

合成特性：
- **BGM 处理**：人声增强（压缩器+EQ）+ BGM 自动循环 + 混音
- **字幕渲染**：支持 8 种中文字体、描边、阴影、背景框、对齐方式
- **色彩描边**：字幕字体可配置描边颜色和宽度
- **封面生成**：从视频抽帧 → 叠加标题/副标题 → 遮罩效果

### 5.11 字幕模板

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/subtitle/templates` | 模板列表 |
| `GET` | `/api/subtitle/templates/{id}` | 模板详情 |
| `POST` | `/api/subtitle/templates` | 创建模板 |
| `PUT` | `/api/subtitle/templates/{id}` | 更新模板 |
| `DELETE` | `/api/subtitle/templates/{id}` | 删除模板 |
| `GET` | `/api/subtitle/templates/default` | 获取默认模板 |
| `POST` | `/api/subtitle/templates/{id}/default` | 设为默认 |
| `GET` | `/api/subtitle/fonts` | 可用字体列表 |

### 5.12 封面模板

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/cover/templates` | 模板列表 |
| `GET` | `/api/cover/templates/{id}` | 模板详情 |
| `POST` | `/api/cover/templates` | 创建模板 |
| `PUT` | `/api/cover/templates/{id}` | 更新模板 |
| `DELETE` | `/api/cover/templates/{id}` | 删除模板 |
| `GET` | `/api/cover/templates/default` | 获取默认模板 |
| `POST` | `/api/cover/templates/{id}/default` | 设为默认 |
| `GET` | `/api/cover/fonts` | 可用字体列表 |
| `POST` | `/api/cover/generate` | 生成封面图 |

### 5.13 多平台发布

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/publish/accounts` | 发布账号列表 |
| `POST` | `/api/publish/accounts/login` | 触发扫码登录 |
| `POST` | `/api/publish/accounts/{id}/check` | 检查账号有效 |
| `DELETE` | `/api/publish/accounts/{id}` | 删除账号 |
| `GET` | `/api/publish/platform/status` | 各平台绑定状态 |
| `GET` | `/api/publish/records` | 发布记录列表 |
| `GET` | `/api/publish/records/{id}` | 发布记录详情 |
| `POST` | `/api/publish/video` | 单平台发布 |
| `POST` | `/api/publish/batch` | 多平台批量发布 |

**请求/响应示例 — 批量发布：**
```json
POST /api/publish/batch
Body: {
  "project_id": "a1b2c3d4-...",
  "platforms": ["douyin", "xiaohongshu", "kuaishou"],
  "video_path": "outputs/compose/final_xxx.mp4",
  "title": "AI 改变生活 #数字人",
  "description": "用 AI 生成的数字人口播视频",
  "tags": ["AI", "数字人", "科技"],
  "cover_path": "outputs/covers/cover_abc123.png"
}

Response 200:
{
  "batch_id": "f4e5d6a7",
  "records": [...],
  "message": "批量发布任务已启动"
}
```

支持平台：
| 平台 | 标识 | 颜色 | 登录方式 |
|------|------|------|---------|
| 抖音 | `douyin` | `#fe2c55` | Playwright 扫码 |
| 小红书 | `xiaohongshu` | `#ff2442` | Playwright 扫码 |
| 快手 | `kuaishou` | `#ff4906` | Playwright 扫码 |
| 视频号 | `tencent` | `#07c160` | Playwright 扫码 |

### 5.14 自动流水线

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/auto/submit` | 提交自动任务 |
| `GET` | `/api/auto/queue` | 查看队列状态 |
| `GET` | `/api/auto/queue/{task_id}` | 查看任务详情 |
| `POST` | `/api/auto/queue/{task_id}/cancel` | 取消排队任务 |

**自动流水线步骤：** 文案校验(5%) → TTS合成(30%) → 模型卸载 → 数字人生成(60%) → 模型卸载 → 合成(85%) → 发布(98%) → 完成(100%)

**请求/响应示例：**
```json
POST /api/auto/submit
Body: {
  "copy_text": "今天我们来聊一个扎心的事实...",
  "topic": "AI改变生活",
  "voice_id": 1,
  "ref_video_id": 2,
  "subtitle_template_id": 1,
  "cover_template_id": 1,
  "cover_title": "AI 改变生活",
  "cover_subtitle": "",
  "bgm_path": "uploads/bgm/music.mp3",
  "bgm_volume": 0.3,
  "platforms": ["douyin", "xiaohongshu"],
  "publish_title": "AI 改变生活 #数字人",
  "publish_tags": ["AI", "科技"]
}

Response 200:
{
  "task_id": "a1b2c3d4",
  "project_id": "e5f6g7h8-...",
  "status": "queued",
  "queue_position": 1,
  "message": "任务已添加到队列"
}
```

### 5.15 系统设置

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/settings` | 获取设置 |
| `POST` | `/api/settings` | 保存设置 |

### 5.16 平台 Cookie

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/cookies` | 所有平台 Cookie 状态 |
| `GET` | `/api/cookies/{platform}` | 单平台 Cookie 状态 |
| `POST` | `/api/cookies/{platform}` | 保存 Cookie |
| `POST` | `/api/cookies/{platform}/verify` | 验证 Cookie 有效性 |
| `DELETE` | `/api/cookies/{platform}` | 删除 Cookie |

### 5.17 日志查看

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/logs` | 日志文件列表 |
| `GET` | `/api/logs/{filename}` | 读取日志（支持行数+级别过滤）|

### 5.18 TTS 微服务内部接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/synthesize` | 合成语音 |
| `POST` | `/unload` | 卸载模型释放显存 |

### 5.19 数字人微服务内部接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/generate` | 生成数字人视频 |
| `GET` | `/status` | 模型加载状态+显存 |
| `POST` | `/unload` | 卸载模型释放显存 |

---

## 六、模型配置

### 6.1 文案模型

| 模型 | API 端点 | 模型名 |
|------|---------|--------|
| DeepSeek | `https://api.deepseek.com/v1/chat/completions` | `deepseek-chat` |

配置方式：通过 `POST /api/settings` 设置 API Key，或直接编辑 `data/settings.json`：
```json
{
  "text_model": "deepseek",
  "api_keys": {
    "deepseek": "sk-xxxxxxxxxxxxxxxx"
  }
}
```

### 6.2 IndexTTS2（语音合成）

- **模型目录：** `checkpoints/indextts2/`
- **配置文件：** `checkpoints/indextts2/config.yaml`
- **关键参数：** `use_fp16=true`（半精度推理，节省显存）

### 6.3 LatentSync（数字人）

- **UNet 配置：** `models/latentsync/configs/unet/stage2.yaml`
- **权重文件：** `checkpoints/latentsync/latentsync_unet.pt`
- **VAE：** `models/latentsync/checkpoints/sd-vae-ft-mse/`
- **推理参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `guidance_scale` | 2.0 | 引导强度 |
| `inference_steps` | 15 | 推理步数（DeepCache 启用时为 20）|
| `seed` | 42 | 随机种子 |

### 6.4 Whisper（语音识别）

- **引擎：** faster-whisper (CTranslate2)
- **模型：** `checkpoints/whisper/ct2/`
- **设备：** `cuda`，计算类型 `int8_float16`

---

## 七、环境变量和配置

### 7.1 系统配置（`data/settings.json`）

```json
{
  "text_model": "deepseek",
  "api_keys": {
    "deepseek": "sk-xxxxxxxxxxxxxxxx"
  },
  "whisper_device": "cuda",
  "whisper_compute_type": "int8_float16"
}
```

### 7.2 服务端口

| 服务 | 端口 | 环境变量 | 默认值 |
|------|------|---------|--------|
| API 主服务 | `8000` | - | `127.0.0.1:8000` |
| TTS 微服务 | `8101` | - | `127.0.0.1:8101` |
| 数字人微服务 | `8102` | - | `127.0.0.1:8102` |

> 端口号在源码中硬编码，修改需编辑 `api_server.py`、`tts_service.py`、`latent_service.py`。

### 7.3 FFmpeg 路径

项目自带 FFmpeg 二进制（`ffmpeg/ffmpeg.exe` + `ffprobe.exe`），所有合成操作优先使用本地 FFmpeg。数字人服务会自动将 `ffmpeg/` 目录加入 `PATH`。

### 7.4 数据库

- **文件位置：** `data/app.db`
- **模式：** WAL（Write-Ahead Logging），支持并发读写
- **外键：** 已启用
- **自动迁移：** 启动时自动创建缺失表和列

---

## 八、开发指南

### 8.1 代码规范

- **路由拆分：** 每个业务域一个文件，使用 `APIRouter(prefix="/api")`
- **数据层：** 每个表一个文件，通过 `database/__init__.py` 统一导出
- **工具函数：** 纯函数，不依赖 FastAPI Request 对象
- **微服务间通信：** 通过 HTTP (httpx) 调用，不直接 import

### 8.2 添加新路由

```python
# services/routes/my_feature.py
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["我的功能"])

class MyRequest(BaseModel):
    field: str

@router.post("/my-feature")
def my_endpoint(req: MyRequest):
    return {"result": req.field}
```

然后在 `api_server.py` 中注册：
```python
from routes.my_feature import router as my_router
app.include_router(my_router)
```

### 8.3 添加新 LLM 模型

编辑 `services/utils/llm_client.py`，在 `LLMClient.MODELS` 中添加：
```python
"qwen": {
    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "model": "qwen-plus",
    "auth": lambda key: {"Authorization": f"Bearer {key}"},
    "parse": lambda data: data["choices"][0]["message"]["content"],
},
```

然后在 `data/settings.json` 中添加 API Key：
```json
"api_keys": {
    "deepseek": "sk-...",
    "qwen": "sk-..."
}
```

### 8.4 显存管理策略

- **懒加载：** 模型只在首次调用时加载到 GPU
- **按需卸载：** 进入"音频"页面自动卸载数字人模型，进入"视频"页面自动卸载 TTS 模型
- **流水线卸载：** 自动任务中 TTS 完成后立即卸载 → 数字人生成 → 立即卸载 → 合成（纯 CPU）
- **手动卸载：** `POST /unload` 接口，包含完整的 Python GC + CUDA cache 清理 + malloc_trim

### 8.5 数据库扩展

```python
# 1. 在 database/core.py 的 init_db() 中添加 CREATE TABLE
# 2. 创建 database/my_table.py
# 3. 在 database/__init__.py 中导出
# 4. 自动迁移已有兼容代码（ALTER TABLE ADD COLUMN）
```

### 8.6 日志

所有日志通过 `utils/logger.py` 的统一配置输出：
- **控制台：** 实时查看（stdout）
- **文件：** `logs/api_YYYYMMDD.log`，每个文件最大 5MB，保留 5 个备份
- **API 访问：** `GET /api/logs` 可查看和过滤日志

---

## 九、商业化信息

### 9.1 开源协议

本项目代码采用 **MIT License** 开源。

### 9.2 依赖模型授权

| 组件 | 许可证 | 商用限制 |
|------|--------|---------|
| IndexTTS2 | 模型权重自有协议 | 请遵守模型发布方的使用条款 |
| LatentSync | Apache 2.0 | 可商用 |
| DeepSeek API | 按量计费 | 需注册并充值 |
| Whisper (OpenAI) | MIT | 可商用 |
| FFmpeg | LGPL/GPL | 可商用（注意 GPL 传染性）|

### 9.3 商用授权方案

| 方案 | 价格 | 包含内容 |
|------|------|---------|
| **个人版** | 免费 | 源码使用、社区支持 |
| **专业版** | ¥4,999/年 | 商业授权 + 优先技术支持 + 模型权重打包 + 安装部署协助 |
| **企业版** | ¥19,999/年 | 专业版全部 + 定制开发 + SLA 保障 + 私有化部署方案 + 培训 |

### 9.4 技术支持方案

| 方案 | 响应时间 | 方式 |
|------|---------|------|
| 社区支持 | - | GitHub Issues |
| 标准支持（专业版） | 24h 内 | 企业微信/钉钉 + 远程协助 |
| VIP 支持（企业版） | 4h 内 | 专属技术经理 + 7×24 紧急响应 |

### 9.5 硬件推荐配置

| 场景 | GPU | VRAM | CUDA | 磁盘 |
|------|-----|------|------|------|
| 入门体验 | RTX 3060 | 12 GB | 11.8+ | 50 GB |
| 日常创作 | RTX 4060 Ti | 16 GB | 12.4+ | 100 GB |
| 商业生产 | RTX 4090 | 24 GB | 12.8+ | 200 GB |
| 服务器部署 | A100 / H100 | 40-80 GB | 12.0+ | 500 GB |

---

> 文档生成日期：2026-07-25
> 项目路径：`F:\Hermes\AI_video_tool\`
