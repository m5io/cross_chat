# Cross Chat

> 🎙️ OBS 直播增强叠加层 — 主播语音字幕 + 弹幕流 + 智能匹配回复高亮，三合一

Cross Chat 是一款面向 B 站主播的 OBS 直播增强工具。它将**主播实时语音字幕**、**观众弹幕流**和**智能匹配回复高亮**融合为单一可视化叠加层（Browser Source），直接叠加到直播画面上，让观众一眼就能看懂主播在聊什么、在回复谁。

## 效果预览

```
┌─────────────────────────────────────────────┐
│  [观众A]: 主播今天玩什么游戏？    ← 💡 高亮  │
│  [观众B]: 66666                            │
│  [观众C]: 主播声音好好听                     │
│  ────────────────────────────────────────   │
│         🎤 "今天玩原神，刚抽到新角色"        │
└─────────────────────────────────────────────┘
```

## 核心功能

| 功能 | 说明 |
|------|------|
| 🎤 语音转字幕 | 主播说话实时转为文字，显示在画面底部 |
| 📡 弹幕采集 | 接入 B 站弹幕 WebSocket，实时获取弹幕 |
| 🎯 智能匹配 | 主播说的话与弹幕做关键词匹配，自动识别"回复了谁" |
| ✨ 高亮动画 | 被回复的弹幕高亮闪烁 + 箭头连线指向字幕条 |

## 架构概览

```
OBS Studio
├── obs-localvocal (C++ 语音识别滤镜) → Text Source
└── Browser Source (本前端) ←ws://localhost:8765── Python Backend
                                                       │
                                                   B站弹幕 WS
```

- **语音识别**: [obs-localvocal](https://github.com/royshil/obs-localvocal) (Whisper.cpp 本地推理)
- **后端**: Python 3.11+，负责弹幕采集、关键词匹配、WebSocket 桥接
- **前端**: 纯 HTML/CSS/JS，作为 OBS Browser Source 叠加到直播画面

## 环境要求

| 组件 | 要求 |
|------|------|
| OBS Studio | 30.0+ |
| Python | 3.11+ |
| 网络 | 能访问 B 站弹幕 WebSocket |

## 快速开始

### 1. 安装语音识别插件

下载 [obs-localvocal](https://github.com/royshil/obs-localvocal/releases) 并安装：
- OBS → 麦克风音频源 → 右键 → 滤镜 → 添加 **LocalVocal**
- 确认 OBS 中出现 Text (GDI+) 字幕源
- （可选）在 LocalVocal 设置中开启"输出到文件"，用于匹配引擎

### 2. 安装后端依赖

```bash
cd cross_chat
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 3. 启动后端

```bash
cd backend
python mvp_backend.py --room-id 你的直播间号
```

可选参数：
- `--room-id` — B 站直播间 ID（必填）
- `--subtitle-file` — obs-localvocal 字幕文件路径（如开启文件输出）

### 4. 配置 OBS Browser Source

- OBS → 添加源 → **Browser Source**
- URL: `file:///home/xxx/cross_chat/frontend/index.html`（替换为实际路径）
- 调整位置和尺寸以适配你的直播布局

### 5. 开播

开始直播，说话，观察弹幕匹配效果。

## 项目结构

```
cross_chat/
├── backend/
│   ├── mvp_backend.py       # 主入口，组装各模块
│   ├── danmu_client.py      # B站弹幕 WebSocket 客户端
│   ├── ws_server.py         # WebSocket 桥接服务器 (localhost:8765)
│   ├── matching.py          # 关键词匹配引擎
│   └── requirements.txt     # Python 依赖
├── frontend/
│   ├── index.html           # OBS Browser Source 入口
│   ├── css/
│   │   └── overlay.css      # 叠加层样式
│   └── js/
│       ├── app.js           # 前端主逻辑
│       ├── ws_client.js     # WebSocket 客户端
│       ├── state.js         # 状态管理
│       ├── danmu_renderer.js # 弹幕渲染
│       ├── host_bar.js      # 字幕条组件
│       └── match_effects.js # 匹配高亮动画
├── docs/
│   ├── prd.md               # 产品需求文档
│   ├── tech.md              # 技术设计文档
│   └── roadmap.md           # 开发路线图
├── .gitignore
└── README.md
```

## 匹配原理

MVP 阶段使用**关键词交集匹配**：
1. 主播说的话进行分词
2. 与滑动窗口内最近 30 条弹幕逐条计算交集
3. 交集 ≥ 阈值（默认 1 个共同词）则标记为"被回复"
4. 前端高亮该弹幕并显示箭头动画，3 秒后自动消失

后续 Phase 2 将升级为 embedding 语义匹配，提升准确率。

## 开发路线

详见 [docs/roadmap.md](docs/roadmap.md)
- **Phase 1 (MVP)** — 关键词匹配 + 基础 UI
- **Phase 2** — Embedding 语义匹配
- **Phase 3** — C++ OBS 原生插件、多平台支持

## 参考

- [obs-localvocal](https://github.com/royshil/obs-localvocal) — OBS 本地语音识别插件
- [blivedm](https://pypi.org/project/blivedm/) — B 站弹幕 Python 库
- [blivechat](https://github.com/xfgryujk/blivechat) — 弹幕 OBS 叠加层参考实现
