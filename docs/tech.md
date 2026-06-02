# Cross Chat — 技术设计文档 (Tech Design Doc)

> 版本: v0.1-MVP | 日期: 2026-06-02 | 状态: Draft

---

## 1. 概述 (Overview)

Cross Chat 是一个 OBS 直播叠加层工具，将**主播实时语音字幕**、**观众弹幕流**和**智能匹配回复**三者融合为单一视觉组件，通过 OBS Browser Source 叠加到直播画面上。

### 1.1 核心功能

| 功能 | 描述 |
|------|------|
| 语音转字幕 | 主播说话 → 实时转文字，显示为底部/顶部字幕条 |
| 弹幕捕获 | 实时接入 B 站直播间弹幕 WebSocket 流 |
| 智能匹配 | 主播语音与弹幕做关联匹配，高亮被"回复"的弹幕 |
| 视觉叠加 | 线性垂直滚动弹幕栏 + 高亮动画 + 箭头连线 |

### 1.2 设计原则

- **低延迟优先**: 端到端延迟控制在 500ms 以内（语音→字幕，弹幕→显示）
- **渐进式演进**: MVP 用关键词规则，后续升级 embedding 语义匹配
- **可替换组件**: 每个模块可独立替换（如语音引擎从 obs-localvocal 换为自研 C++ 插件）
- **零依赖本地运行**: 所有服务均运行在主播本机，无云端依赖

---

## 2. 系统架构 (System Architecture)

### 2.1 架构分层

```
+---------------------------------------------------------------+
|                         OBS Studio                            |
|                                                               |
|  +------------------+              +----------------------+   |
|  |   LocalVocal     |              |   Browser Source     |   |
|  |   (C++ filter)   |              |   (HTML/CSS/JS)      |   |
|  |                  |              |                      |   |
|  |   Whisper.cpp    |              |   - Danmu scroll     |   |
|  |   -> Text src    |              |   - Host subtitle    |   |
|  |                  |              |   - Highlight+arrow  |   |
|  +--------+---------+              +----------+-----------+   |
|           |                                   |               |
+-----------+-----------------------------------+---------------+
            |                                   |
            |  (file poll)         ws://localhost:8765
            v                                   v
+---------------------------------------------------------------+
|                     Python Backend                            |
|                                                               |
|  +----------------+ +----------------+ +------------------+   |
|  |  Voice Reader  | |  Danmu Client  | |  Match Engine    |   |
|  |                | |                | |                  |   |
|  |  read_file()   | |  blivedm       | |  keyword         |   |
|  |  poll .txt     | |  WS client     | |  match()         |   |
|  +-------+--------+ +-------+--------+ +--------+---------+   |
|          |                  |                   |             |
|          +------------------+-------------------+             |
|                             v                                 |
|              +----------------------------+                   |
|              |    WebSocket Server        |                   |
|              |    (websockets lib)        |                   |
|              |    localhost:8765          |                   |
|              +----------------------------+                   |
+---------------------------------------------------------------+
               |
               |  Bilibili danmu WS (external network)
               v
+-------------------------------+
|        Bilibili CDN           |
|     (Danmu WebSocket)         |
+-------------------------------+
```

### 2.2 部署拓扑

所有组件运行在**同一台主播 PC** 上：

| 组件 | 进程 | 端口/方式 |
|------|------|-----------|
| OBS Studio | 主进程 | - |
| obs-localvocal 滤镜 | OBS 插件 | 输出到文件 `subtitles.txt` |
| Python Backend | 独立进程 | `ws://localhost:8765` |
| Browser Source | Chromium (OBS 内嵌) | 连接 `ws://localhost:8765` |

---

## 3. 组件设计 (Component Design)

### 3.1 语音捕获 (Voice Capture)

**方案**: obs-localvocal (OBS 滤镜插件)

| 属性 | 说明 |
|------|------|
| 底层引擎 | Whisper.cpp (C++, 本地推理) |
| 模型 | `ggml-small.bin` (~466MB, 延迟 <200ms) |
| 输出方式 | 写入 Text (GDI+) 源 + 可选输出到 `.txt` 文件 |
| 延迟 | <200ms (GPU 加速) |
| 语言 | 中文 (zh) |

**文件轮询策略**（Python 侧）:
```python
# 每秒轮询 subtitles.txt，检测增量
# 记录上次读取的文件偏移量，只读新增内容
last_pos = 0
while True:
    with open("subtitles.txt", "r") as f:
        f.seek(last_pos)
        new_text = f.read()
        if new_text:
            latest_host_text = new_text.strip().split("\n")[-1]
            last_pos = f.tell()
    await asyncio.sleep(0.1)  # 100ms 轮询间隔
```

### 3.2 弹幕采集 (Danmu Capture)

**方案**: `blivedm` (Python 库, B 站弹幕 WebSocket 客户端)

| 属性 | 说明 |
|------|------|
| 库 | `blivedm` (pip install) |
| 协议 | B 站非官方弹幕 WebSocket 协议 |
| 数据 | 弹幕消息体: `{uid, uname, msg, timestamp}` |
| 滑动窗口 | 保留最近 30 条弹幕 |
| 重连 | 自动重连，指数退避 |

**核心逻辑**:
```python
from blivedm import BLiveClient

class DanmuClient(BLiveClient):
    async def on_danmaku(self, dm):
        event = {
            "type": "danmu",
            "id": self._seq_id(),
            "uid": dm.uid,
            "uname": dm.uname,
            "text": dm.msg,
            "timestamp": time.time()
        }
        self._danmu_buffer.append(event)
        if len(self._danmu_buffer) > 30:
            self._danmu_buffer.pop(0)
        await self._broadcast()
```

**滑动窗口策略**:
- 窗口大小: 30 条（约 10-30 秒的内容）
- 溢出: FIFO 淘汰
- 匹配时同时考虑全部 30 条，优先级 = 时间衰减 × 关键词命中

### 3.3 匹配引擎 (Matching Engine)

**MVP 阶段: 关键词规则匹配**

```
匹配流程:
1. 取主播最新一句话 (latest_host_text)
2. 对最近 5 条弹幕做关键词交集检查
3. 命中 → 标记为 matched
4. 推送匹配结果给前端
```

```python
def simple_match(host_text: str, danmu_list: list, top_n: int = 5) -> list:
    """MVP 匹配: 关键词交集"""
    if not host_text:
        return []
    
    # 对主播文本做简单分词 (按空格/标点切分)
    host_words = set(host_text.strip().split())
    
    matches = []
    for dm in danmu_list[-top_n:]:
        dm_words = set(dm["text"].strip().split())
        overlap = host_words & dm_words
        if overlap:
            matches.append({
                "danmu_id": dm["id"],
                "keywords": list(overlap),
                "score": len(overlap) / max(len(host_words), 1)
            })
    return matches
```

**后续迭代路径**:
- **Phase 2**: 引入 `sentence-transformers` (all-MiniLM-L6-v2) 做 embedding 余弦相似度匹配
- **Phase 3**: 用 LLM 做上下文理解 + 意图识别

### 3.4 WebSocket 服务器 (Communication Bridge)

**方案**: Python `websockets` 库

| 属性 | 说明 |
|------|------|
| 地址 | `ws://localhost:8765` |
| 模式 | Pub-Sub (服务器主动推送) |
| 客户端 | 1 个 (Browser Source) |
| 推送频率 | 事件驱动，最高 30fps 节流 |

**消息协议** (JSON):

```json
// → 服务器推送: 状态快照
{
  "type": "state_update",
  "seq": 42,
  "timestamp": 1717300000.123,
  "payload": {
    "host_text": "大家好啊欢迎来到直播间",
    "danmu_list": [
      {
        "id": 0,
        "uid": 12345,
        "uname": "观众A",
        "text": "主播好！",
        "timestamp": 1717300000.0
      }
    ],
    "matches": [
      {
        "danmu_id": 0,
        "keywords": ["好"],
        "score": 0.33
      }
    ]
  }
}

// → 服务器推送: 新弹幕事件 (增量)
{
  "type": "new_danmu",
  "seq": 43,
  "payload": {
    "danmu": {
      "id": 1,
      "uid": 67890,
      "uname": "观众B",
      "text": "今天玩什么游戏",
      "timestamp": 1717300001.0
    }
  }
}

// → 服务器推送: 匹配高亮
{
  "type": "match_highlight",
  "seq": 44,
  "payload": {
    "danmu_ids": [0, 3],
    "host_text": "大家好啊",
    "duration_ms": 3000
  }
}
```

### 3.5 前端 UI (Browser Source)

**技术栈**: 原生 HTML + CSS + Vanilla JS (无框架，减小 OBS Browser Source 负担)

**组件树**:
```
<div id="app">
  +-- <div id="host-subtitle-bar">     <!-- 主播字幕条 (底部) -->
  |    \-- <span id="host-text">
  +-- <div id="danmu-container">       <!-- 弹幕滚动容器 -->
  |    +-- <div class="danmu-item">    <!-- 弹幕项 x N -->
  |    |    +-- <span class="danmu-user">
  |    |    +-- <span class="danmu-text">
  |    |    \-- <div class="highlight-arrow">  <!-- 匹配箭头 (条件渲染) -->
  |    \-- ...
  +-- <div id="match-indicator">       <!-- 匹配指示器 -->
```

**CSS 动画规格**:

| 动画 | 属性 | 时长 | 缓动 |
|------|------|------|------|
| 弹幕入场 | `transform: translateX(100%) → 0` | 300ms | ease-out |
| 弹幕退场 | `opacity: 1 → 0; max-height: 60px → 0` | 500ms | ease-in |
| 匹配高亮 | `background-color: transparent → #FFD700 → transparent` | 600ms | ease-in-out |
| 箭头出现 | `opacity: 0 → 1; transform: scale(0) → scale(1)` | 300ms | cubic-bezier |

**状态管理** (无需框架):
```javascript
const state = {
    hostText: "",
    danmuList: [],     // 最多 30 条，FIFO
    matchedIds: new Set(),
    ws: null,
};

// 单一渲染循环 (requestAnimationFrame)
function render() {
    updateHostBar(state.hostText);
    updateDanmuList(state.danmuList, state.matchedIds);
    requestAnimationFrame(render);
}
```

---

## 4. 数据流 (Data Flow)

### 4.1 弹幕到达 → 显示

```
B站 WS ----danmu----> blivedm Client ----on_danmaku()----> danmu_buffer
                                                               |
                                                  simple_match() (if host_text)
                                                               |
                                                               v
                                                  WebSocket broadcast()
                                                               |
                                                               v
                                                  Browser Source ----render()----> DOM update
```

**时序**:
```
T=0ms    B站推送弹幕
T=5ms    blivedm 回调触发
T=6ms    danmu_buffer 写入 + 匹配检查
T=7ms    WebSocket 推送 state_update 到 Browser Source
T=10ms   JS 接收 -> requestAnimationFrame
T=16ms   浏览器渲染下一帧 (60fps)
```

### 4.2 主播语音 → 字幕 + 匹配

```
麦克风 ----audio----> obs-localvocal ----Whisper.cpp----> subtitles.txt
                                                               |
                                                  Python poll (100ms interval)
                                                               |
                                                               v
                                                    latest_host_text update
                                                               |
                                                    simple_match()
                                                               |
                                                               v
                                                    WebSocket broadcast()
                                                               |
                                                               v
                                                    Browser Source
```

**时序**:
```
T=0ms     主播说话
T=150ms   Whisper.cpp 推理完成 -> 写入字幕文本
T=250ms   Python 轮询到新文本 (最坏情况 100ms 间隔)
T=255ms   匹配完成 + WebSocket 推送
T=265ms   Browser Source 渲染
```

### 4.3 页面加载 → 连接

```
Browser Source 加载 ----new WebSocket("ws://localhost:8765")----> Python WS Server
                                                                       |
                                                                       v
                                                              发送当前 state 快照
                                                                       |
                                                                       v
                                                              Browser Source 初始化渲染
```

---

## 5. 项目结构 (Project Structure)

```
cross_chat/
+-- docs/
|   +-- prd.md                  # 产品需求文档
|   \-- tech.md                 # 技术设计文档 (本文档)
+-- backend/
|   +-- mvp_backend.py          # MVP 后端主程序
|   +-- danmu_client.py         # B站弹幕客户端封装
|   +-- matching.py             # 匹配引擎
|   +-- ws_server.py            # WebSocket 服务器
|   \-- requirements.txt        # Python 依赖
+-- frontend/
|   +-- index.html              # Browser Source 入口
|   +-- css/
|   |   \-- overlay.css         # 叠加层样式
|   +-- js/
|   |   +-- ws_client.js        # WebSocket 客户端
|   |   +-- state.js            # 状态管理
|   |   +-- danmu_renderer.js   # 弹幕列表渲染
|   |   +-- host_bar.js         # 主播字幕条
|   |   \-- match_effects.js    # 匹配高亮动画
|   \-- assets/                 # 字体、图标等
\-- README.md                   # 快速开始指南
```

---

## 6. 技术决策 (Technology Decisions)

| 决策 | 选择 | 替代方案 | 理由 |
|------|------|----------|------|
| 语音识别引擎 | obs-localvocal (Whisper.cpp) | faster-whisper (Python), 云端 ASR API | C++ 插件零代码集成 OBS；本地推理低延迟；GPU 加速 |
| 弹幕捕获 | blivedm (Python) | 直接连 B 站 WS, bilibili-api | 封装成熟，几行代码就跑通 |
| 后端语言 | Python 3.11+ | Node.js, Go | 学习成本最低、生态丰富（弹幕库+WebSocket 库）、MVP 迭代快 |
| 前端框架 | 原生 JS (无框架) | React, Vue, Svelte | OBS Browser Source 性能优先，减小 bundle 负担 |
| 通信方式 | WebSocket (本地) | HTTP Polling, Unix Socket | 实时推送、双向通信、浏览器原生支持 |
| 匹配策略 (MVP) | 关键词交集 | TF-IDF, Word2Vec, BERT | 实现简单，规则透明，无外部依赖 |

---

## 7. 实现路线图 (Implementation Roadmap)

### Phase 1: MVP (1-2 周)

| 里程碑 | 交付物 | 验收标准 |
|--------|--------|----------|
| M1: 语音字幕 | obs-localvocal 安装配置 | OBS 中看到实时字幕文本 |
| M2: 弹幕捕获 | Python blivedm 客户端跑通 | 控制台打印直播间弹幕 |
| M3: WebSocket 桥接 | Python WS Server + JS Client 连通 | Browser Source 显示弹幕列表 |
| M4: 匹配高亮 | 关键词匹配 + 前端动画 | 主播说话时相关弹幕高亮 |
| M5: 集成测试 | 全链路联调 | OBS 中叠加显示所有组件 |

### Phase 2: 优化 (1-2 周)

- 引入 `sentence-transformers` embedding 语义匹配
- 弹幕去重 & 反垃圾
- 字幕条样式美化 & 自定义主题
- 匹配准确率调优

### Phase 3: 产品化 (长期)

- 整体迁移为纯 C++ OBS 插件 (性能 + 分发便利)
- 支持多平台弹幕 (抖音、Twitch、YouTube)
- LLM 驱动的上下文理解匹配
- 配置面板 (OBS 插件 UI)

---

## 8. 部署 & 测试 (Deployment & Testing)

### 8.1 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| OBS Studio | 30.0+ | 直播推流主程序 |
| obs-localvocal | latest (2026) | 语音转字幕滤镜 |
| Python | 3.11+ | 后端逻辑 |
| Chrome/Chromium | (OBS 内嵌) | Browser Source 渲染 |

### 8.2 启动步骤

```bash
# 1. 安装依赖
pip install blivedm websockets

# 2. 配置直播间 ID
# 编辑 mvp_backend.py 中的 ROOM_ID

# 3. 启动后端
python backend/mvp_backend.py

# 4. OBS 中:
#    - 添加 obs-localvocal 滤镜到麦克风源
#    - 添加 Browser Source → URL: file:///path/to/frontend/index.html
```

### 8.3 测试策略

| 测试类型 | 方法 | 覆盖 |
|----------|------|------|
| 单元测试 | pytest (后端逻辑: matching, danmu buffer) | 匹配引擎、弹幕窗口 |
| 集成测试 | 模拟 WebSocket 消息 | WS 协议、前端渲染 |
| 端到端测试 | 实际 OBS 场景 | 全链路延迟、视觉效果 |
| 性能测试 | 监控 CPU/内存 | Browser Source 60fps 渲染 |

---

## 9. 附录

### 9.1 关键参考

- [obs-localvocal Releases](https://github.com/royshil/obs-localvocal/releases)
- [blivedm (B站弹幕库)](https://github.com/xfgryujk/blivedm)
- [blivechat (OBS 弹幕样式参考)](https://github.com/xfgryujk/blivechat)
- [Whisper.cpp](https://github.com/ggerganov/whisper.cpp)

### 9.2 术语表

| 术语 | 说明 |
|------|------|
| Danmu / 弹幕 | 观众实时评论，从屏幕右侧滚入 |
| Browser Source | OBS 功能，嵌入 Chromium 渲染网页 |
| LocalVocal | OBS 滤镜插件，基于 Whisper.cpp 的本地语音识别 |


