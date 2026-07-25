# AI 口播工坊 · 后端服务

> 🔥 **一套代码，搞定 AI 口播视频全流程。** 文案生成 → 语音合成 → 数字人驱动 → 字幕+BGM合成 → 多平台发布。开箱即用，可商用。

---

## 💰 出售与合作

**这不是一个演示项目，这是一个可直接商用部署的完整后端系统。**

### 它能为你省多少钱？

| 环节 | 传统方案 | 用本项目 | 节省 |
|------|---------|---------|------|
| 文案 | 请人写，100-500元/篇 | AI 生成，3秒/篇 | 100% |
| 配音 | 找主播录制，200-800元/条 | 克隆自己的声音，0元 | 100% |
| 出镜 | 自己拍，2-4小时/条 | 数字人驱动，0分钟 | 100% |
| 剪辑 | 人工剪辑，1-3小时/条 | 自动合成字幕+BGM，3分钟 | 95% |
| 发布 | 手动上传各平台 | Playwright 自动发布 | 100% |

**一个创作者用这套工具，每月能省下 8000-15000 元的内容生产成本。**

### 谁适合用？

- 🎬 **MCN / 内容团队**：批量生产口播视频，替代剪辑师和配音员
- 🛒 **电商卖家**：用数字人做产品口播，天天发不重样
- 🎓 **知识付费创作者**：把自己的声音克隆出来，日更不累
- 🏢 **企业培训部门**：标准课件一键生成，不需要专业设备
- 💻 **独立开发者 / SaaS 创业者**：集成到自己的产品里，快速上线 AI 视频能力

### 商用授权方案

| 方案 | 价格 | 包含 |
|------|------|------|
| **开源版** | 免费 | MIT 协议，源码使用，社区 Issues 支持 |
| **专业版** | ¥4,999/年 | 商业授权 + 一对一技术支持 + 模型权重打包 + 安装部署协助 |
| **企业版** | ¥19,999/年 | 专业版全部 + 定制功能开发 + SLA 保障 + 私有化部署 + 培训 |

### 还需要什么？我也可以做

- 🎨 **前端 UI 定制**：根据你的品牌风格重新设计界面
- 🔧 **功能定制**：接入你的业务系统、特定平台 API 对接
- 📦 **一体机部署**：软硬件打包，到手即用
- 📚 **培训服务**：团队内训，从零教到能独立维护

### 联系方式

- 📧 **邮箱**：[你的邮箱]
- 💬 **微信/QQ**：[你的联系方式]
- 🐛 **技术问题**：直接提 [GitHub Issue](https://github.com/mengdongshike/ai_video_tool/issues)
- 💼 **商务合作**：邮件标题注明「AI口播工坊 商业合作」

---

## 🚀 快速体验

```bash
# 1. 环境要求：Windows 10/11 + NVIDIA 显卡(8GB+) + CUDA 12.8
# 2. 下载模型权重到 checkpoints/
# 3. 启动所有服务
cd AI_video_tool
python/python.exe services/api_server.py      # API 服务 :8000
venv_tts/Scripts/python.exe services/tts_service.py    # TTS 服务 :8101
venv_latent/Scripts/python.exe services/latent_service.py  # 数字人服务 :8102

# 4. 健康检查
curl http://localhost:8000/api/health
```

---

## 🧩 一、它能做什么

```
输入主题 → AI 生成文案 → 克隆/合成语音 → 数字人驱动 → 字幕+BGM合成 → 多平台发布
```

| 模块 | 能力 | 技术 |
|------|------|------|
| 文案 | 按行业/风格/人设生成口播文案 | DeepSeek API + 自定义提示词 |
| 语音 | 克隆真人音色，8维情感向量控制 | IndexTTS2 |
| 数字人 | 上传视频+音频，自动对口型 | LatentSync |
| 字幕 | 自动切句生成SRT，按时长等比分配 | TTS 服务内置 |
| 合成 | 字幕叠加 + BGM混音 + 色彩描边 | FFmpeg (libx264) |
| 发布 | 抖音/小红书/快手/视频号自动发布 | Playwright 自动化 |
| 管理 | 多项目并行，音色/视频/模板管理 | SQLite |

---

## 🏗 二、架构

```
┌─────────────────────────────────────────┐
│         FastAPI 主服务 :8000              │
│  路由层( routes/ ) → 数据库层( database/ )│
├──────────────────┬──────────────────────┤
│  TTS 服务 :8101  │  Latent 服务 :8102    │
│  venv_tts        │  venv_latent          │
│  torch 2.8+cu128 │  torch 2.8+cu128      │
│  IndexTTS2       │  LatentSync           │
└──────────────────┴──────────────────────┘
```

### 为什么拆成三个服务？

**因为两个 AI 模型对 torch/CUDA 版本要求冲突。** IndexTTS2 和 LatentSync 不能装在同一环境，所以各用独立 venv，API 服务用宿主 Python 做路由转发。同时按需加载模型、用完卸载，保证 8GB 显存够用。

---

## 📡 三、API 文档

### 文案

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/copy/generate` | 生成口播文案 |
| POST | `/api/copy/optimize` | 优化润色文案 |
| POST | `/api/copy/extract` | 从链接提取文案 |
| GET  | `/api/brand-words` | 品牌词列表 |
| POST | `/api/brand-words` | 添加品牌词 |

### 音色

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/voices` | 音色列表（预置+克隆） |
| POST | `/api/voices/clone` | 上传音频克隆音色 |
| POST | `/api/tts/synthesize` | 合成语音 |
| DELETE | `/api/voices/{id}` | 删除音色 |

### 数字人视频

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/videos` | 参考视频列表 |
| POST | `/api/videos/upload` | 上传参考视频 |
| POST | `/api/dh/generate` | 生成数字人视频 |
| GET  | `/api/dh/models` | 数字人模型列表 |

### 合成

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/compose/video` | 合成最终视频（字幕+BGM） |

### 项目

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目 |
| GET  | `/api/projects/{id}` | 项目详情 |
| PUT  | `/api/projects/{id}` | 更新项目 |
| DELETE | `/api/projects/{id}` | 删除项目 |

### 模板

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/templates?type=sub` | 字幕模板列表 |
| GET  | `/api/templates?type=bgm` | BGM 列表 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/settings` | 系统设置 |
| POST | `/api/settings` | 保存设置 |
| GET  | `/api/health` | 健康检查 |

---

## 🔧 四、目录结构

```
AI_video_tool/
├── services/           # 后端代码
│   ├── api_server.py   # API 主入口 (:8000)
│   ├── tts_service.py  # TTS 微服务 (:8101)
│   ├── latent_service.py # 数字人微服务 (:8102)
│   ├── routes/         # 路由层
│   │   ├── general.py  # 文案/品牌词路由
│   │   ├── voices.py   # 音色/TTS 路由
│   │   ├── videos.py   # 数字人视频路由
│   │   ├── compose.py  # 视频合成路由
│   │   ├── projects.py # 项目 CRUD
│   │   ├── templates.py # 模板路由
│   │   ├── settings.py # 系统设置
│   │   └── upload.py   # 文件上传
│   ├── database/       # 数据层
│   │   ├── core.py     # 数据库初始化
│   │   ├── projects.py # 项目数据操作
│   │   ├── voices.py   # 音色数据操作
│   │   ├── videos.py   # 视频数据操作
│   │   └── templates.py # 模板数据操作
│   └── utils/          # 工具类
│       ├── llm_client.py  # LLM 客户端
│       └── upload.py      # 上传工具
├── models/             # 模型源码
│   ├── indextts/       # IndexTTS2 模型代码
│   └── latentsync/     # LatentSync 模型代码
├── checkpoints/        # 模型权重
│   ├── indextts2/      # IndexTTS2 权重
│   └── latentsync/     # LatentSync 权重
├── data/               # 数据文件
│   ├── app.db          # SQLite 数据库
│   ├── uploads/        # 上传文件
│   ├── outputs/        # 输出文件（音频/视频/字幕）
│   └── settings.json   # 系统设置
├── python/             # 宿主 Python
├── venv_tts/           # TTS 专用虚拟环境
├── venv_latent/        # 数字人专用虚拟环境
├── ffmpeg/             # FFmpeg 可执行文件
└── README.md
```

---

## 🛠 五、开发指南

### 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.10+ |
| CUDA | 12.8 |
| GPU | NVIDIA 8GB+ VRAM |
| FFmpeg | 7.1+ |
| 磁盘 | 50GB+ |

### 添加新路由

```python
# services/routes/your_module.py
from fastapi import APIRouter, Body

router = APIRouter(prefix="/api", tags=["你的模块"])

@router.post("/your-endpoint")
def your_handler(body: dict = Body(...)):
    return {"result": "ok"}
```

然后在 `api_server.py` 中注册：

```python
from routes.your_module import router as your_router
app.include_router(your_router)
```

### 添加新 LLM 模型

编辑 `services/utils/llm_client.py`，在 `MODELS` 字典中添加：

```python
MODELS = {
    "new_model": {
        "url": "https://api.example.com/v1/chat/completions",
        "model": "model-name",
        "auth": lambda key: {"Authorization": f"Bearer {key}"},
        "parse": lambda data: data["choices"][0]["message"]["content"],
    },
}
```

### 数据库迁移

编辑 `services/database/core.py`，在 `init_db()` 后添加迁移：

```python
try:
    conn = get_db()
    conn.execute("ALTER TABLE projects ADD COLUMN new_field TEXT")
    conn.commit()
    conn.close()
except: pass
```

---

## ⚠️ 六、注意事项

1. **模型许可证**：IndexTTS2 和 LatentSync 各有独立开源协议，商用前请确认
2. **显存管理**：8GB 显存需严格按微服务隔离 + 按需加载，否则 OOM
3. **Windows 路径**：FFmpeg 路径含盘符冒号会被解析为分隔符，用正斜杠或拷贝到同目录解决
4. **API Key**：DeepSeek 等接口 key 存 `data/settings.json`，不要提交到仓库

---

## 👨‍💻 作者

**idopop（小刚）** — 独立开发者、音乐人。

一个人、一台笔记本、一腔热血，从零搭建了这套 AI 口播视频系统。如果你也在做类似的事情，或者想用这套工具做内容创业——欢迎联系。

> "不接 VC、不扩团队、做自己喜欢的产品、过自己的生活。" ——小刚

---

[⬆ 回到顶部 - 出售与合作](#出售与合作)
