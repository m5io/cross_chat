# Cross Chat — MVP 推进计划 (Roadmap)

> 更新: 2026-06-02 | 目标: 1-2 周完成 MVP，跑通全链路

---

## 依赖关系总览

```
Phase 0: 环境准备 ─────────────────────────────────────┐
         │                                              │
         ├── Phase 1: 语音字幕 (obs-localvocal) ────────┤
         │                                              │
         └── Phase 2: 弹幕捕获 (blivedm)                │
                │                                       │
                └── Phase 3: WebSocket 桥梁 ────────────┤
                       │                               │
                       ├── Phase 4: 前端 UI ────────────┤
                       │       │                       │
                       └───────┼── Phase 5: 匹配高亮 ──┤
                               │       │               │
                               └───────┴── Phase 6: 集成联调
```

> Phase 1 和 Phase 2 可并行；Phase 4 可用 mock 数据与 Phase 3 并行开发。

---

## Phase 0: 环境准备

**目标**: 所有工具链就绪，能开始写代码。

| # | 任务 | 优先级 | 预计耗时 | 依赖 | 验收标准 |
|---|------|--------|----------|------|----------|
| 0.1 | 安装 OBS Studio 30.0+ | P0 | 10min | - | OBS 可正常启动 |
| 0.2 | 安装 obs-localvocal 插件 | P0 | 15min | 0.1 | 滤镜列表中出现 LocalVocal |
| 0.3 | 安装 Python 3.11+ | P0 | 20min | - | `python --version` 输出 3.11+ |
| 0.4 | 安装 Python 依赖 (`blivedm`, `websockets`) | P0 | 5min | 0.3 | `pip list` 中可见两个包 |
| 0.5 | 创建项目目录结构 | P0 | 5min | - | `backend/` 和 `frontend/` 目录存在 |

**检查点**: 
- [ ] OBS 能启动
- [x] `python -c "import blivedm; import websockets; print('OK')"` 无报错
- [x] Python 依赖已安装 (venv)
- [x] 项目目录结构已创建

---

## Phase 1: 语音字幕 (obs-localvocal)

**目标**: 主播说话 → OBS 画面显示实时字幕。

| # | 任务 | 优先级 | 预计耗时 | 依赖 | 验收标准 |
|---|------|--------|----------|------|----------|
| 1.1 | 在麦克风音频源上添加 LocalVocal 滤镜 | P0 | 5min | 0.2 | 滤镜添加成功，无报错 |
| 1.2 | 配置模型为 `ggml-small.bin`，语言设为中文 | P0 | 5min | 1.1 | 模型加载完成 |
| 1.3 | 验证 OBS 中出现 Text (GDI+) 字幕源 | P0 | 5min | 1.2 | 对着麦克风说话，字幕源实时更新文字 |
| 1.4 | 开启"输出到文件" → `subtitles.txt` | P1 | 5min | 1.3 | 说话时 `subtitles.txt` 文件内容更新 |

**检查点**:
- [ ] 对着麦克风说话，OBS 画面显示实时中文字幕文字
- [ ] (可选) 文件输出 `subtitles.txt` 正常工作

---

## Phase 2: 弹幕捕获 (blivedm)

**目标**: Python 程序成功连接直播间，实时打印弹幕。

| # | 任务 | 优先级 | 预计耗时 | 依赖 | 验收标准 |
|---|------|--------|----------|------|----------|
| 2.1 | 编写 `backend/danmu_client.py`，基于 blivedm 连接直播间 | P0 | 30min | 0.4 | 运行后控制台打印直播间弹幕 |
| 2.2 | 实现滑动窗口缓存 (最近 30 条)，FIFO 淘汰 | P0 | 15min | 2.1 | 超过 30 条后最旧弹幕被丢弃 |
| 2.3 | 实现断线自动重连 (指数退避) | P1 | 15min | 2.1 | 断网恢复后自动重连成功 |

**参考代码**: 见 [tech.md §3.2](tech.md#32-弹幕采集-danmu-capture)

**检查点**:
- [x] `backend/danmu_client.py` 已创建 (含滑动窗口 + 回调机制)
- [ ] 需要真实直播间 ID 做实际连接测试

---

## Phase 3: WebSocket 桥梁

**目标**: Python 后端把弹幕数据推送到浏览器。

| # | 任务 | 优先级 | 预计耗时 | 依赖 | 验收标准 |
|---|------|--------|----------|------|----------|
| 3.1 | 编写 `backend/ws_server.py`，启动 WebSocket 服务 `ws://localhost:8765` | P0 | 20min | 0.4 | 服务启动，端口监听成功 |
| 3.2 | 实现 `state_update` 消息推送 (弹幕列表 + 占位 host_text) | P0 | 30min | 2.1, 3.1 | 新弹幕到达时自动广播 state_update JSON |
| 3.3 | 编写前端 `frontend/js/ws_client.js`，连接 WS 并打印收到的消息 | P0 | 15min | 3.1 | 浏览器控制台能看到 Python 推送的数据 |
| 3.4 | 用浏览器直接打开 `index.html` 验证 WS 通信 | P0 | 10min | 3.3 | 浏览器 Console 打印出弹幕 JSON 数据 |

**参考代码**: 见 [tech.md §3.4](tech.md#34-websocket-服务器-communication-bridge)

**检查点**:
- [x] `backend/ws_server.py` + `frontend/js/ws_client.js` 已创建
- [x] WebSocket 消息协议已实现 (state_update / new_danmu / match_highlight)
- [ ] 需要启动后端 + 浏览器打开 frontend 做实际连通测试

---

## Phase 4: 前端 UI (Browser Source)

**目标**: 弹幕列表以垂直滚动方式显示，美观可叠加。

| # | 任务 | 优先级 | 预计耗时 | 依赖 | 验收标准 |
|---|------|--------|----------|------|----------|
| 4.1 | 创建 `frontend/index.html` 基础结构 (透明背景、全屏容器) | P0 | 15min | - | 页面渲染为透明背景 |
| 4.2 | 实现弹幕列表组件 (垂直 flex 布局，新弹幕在底部) | P0 | 45min | 3.3 | 收到 WS 消息后弹幕出现在垂直列表中 |
| 4.3 | 实现弹幕滚动动画 (新弹幕入场 fade-in + slide-up) | P0 | 20min | 4.2 | 新弹幕从底部平滑出现 |
| 4.4 | 实现弹幕上限 (最多 30 条 DOM 节点，溢出移除) | P1 | 10min | 4.2 | 超过 30 条后最旧 DOM 节点被移除 |
| 4.5 | 实现主播字幕条组件 (底部/顶部固定) | P0 | 30min | 3.3 | 收到 host_text 后字幕条更新显示 |
| 4.6 | 配置 OBS Browser Source 加载 `file:///path/to/index.html` | P0 | 10min | 4.1 | OBS 中看到叠加层 |
| 4.7 | 样式美化 (字体、颜色、间距) | P1 | 30min | 4.2 | 视觉上接近 blivechat 的观感 |

**参考代码**: 见 [tech.md §3.5](tech.md#35-前端-ui-browser-source)

**检查点**:
- [x] `frontend/index.html` + `css/overlay.css` + JS 模块全部创建
- [x] 弹幕垂直列表 + 入场动画 + 主播字幕条 + 透明背景
- [ ] 需要 OBS Browser Source 加载做视觉验证

---

## Phase 5: 匹配高亮 (Match & Highlight)

**目标**: 主播说话时，相关的弹幕被高亮 + 箭头指示。

| # | 任务 | 优先级 | 预计耗时 | 依赖 | 验收标准 |
|---|------|--------|----------|------|----------|
| 5.1 | 编写 `backend/matching.py` 关键词匹配引擎 | P0 | 30min | 3.2 | 给定 host_text + danmu_list，返回匹配结果 |
| 5.2 | 实现文件轮询读取 `subtitles.txt` (100ms 间隔) | P0 | 20min | 1.4, 3.1 | 检测到新字幕文本后更新 latest_host_text |
| 5.3 | 匹配结果通过 WS 推送到前端 | P0 | 15min | 5.1, 3.2 | 前端收到 match_highlight 消息 |
| 5.4 | 实现前端高亮动画 (金色背景闪烁) | P0 | 20min | 5.3, 4.2 | 匹配的弹幕出现金色闪烁效果 |
| 5.5 | 实现箭头连线效果 (从字幕条指向被回复弹幕) | P1 | 30min | 5.4 | 高亮弹幕旁边出现箭头指示器 |
| 5.6 | 高亮 3 秒后自动消失 | P1 | 10min | 5.4 | 超时后高亮效果移除 |

**参考代码**: 见 [tech.md §3.3](tech.md#33-匹配引擎-matching-engine)

**检查点**:
- [x] `backend/matching.py` 已创建 (标点切分 + 2-gram，无 jieba 依赖)
- [x] 单元测试通过: "大家好啊欢迎来到直播间" 成功匹配 "大家好啊"
- [x] 字幕文件轮询已集成到 `mvp_backend.py`
- [x] 前端高亮动画 + 箭头 + 3 秒自动消失 已实现

---

## Phase 6: 集成联调

**目标**: 全链路跑通，OBS 中视觉效果顺畅。

| # | 任务 | 优先级 | 预计耗时 | 依赖 | 验收标准 |
|---|------|--------|----------|------|----------|
| 6.1 | 编写 `backend/mvp_backend.py` 主程序 (组装所有模块) | P0 | 30min | 2.1, 3.1, 5.1, 5.2 | 一个命令启动所有后端服务 |
| 6.2 | 端到端测试: 开 OBS + 启动后端 + 加载 Browser Source | P0 | 30min | 全部 | 全链路正常工作 |
| 6.3 | 性能检查: 确认 CPU 占用 (<5% Python, <100MB Browser Source) | P1 | 15min | 6.2 | 任务管理器显示资源占用在目标范围内 |
| 6.4 | 延迟测试: 弹幕出现 → 显示 <200ms, 语音 → 高亮 <500ms | P1 | 15min | 6.2 | 延迟达标 |
| 6.5 | 写 `README.md` 快速开始指南 | P1 | 20min | 6.2 | 其他人能按文档 30 分钟内部署成功 |

**检查点**:
- [x] `backend/mvp_backend.py` 已创建 (一键启动所有模块)
- [x] 所有模块导入测试通过
- [ ] 需要真实 B 站直播间 ID + OBS 做端到端验证
- [ ] 需要 obs-localvocal 安装做语音→高亮全链路

---

## 优先级速览

### P0 — 必须完成 (MVP 最小闭环)

| 编号 | 任务 | Phase |
|------|------|-------|
| 0.1-0.5 | 环境准备全部 | 0 |
| 1.1-1.3 | obs-localvocal 安装配置 | 1 |
| 2.1-2.2 | blivedm 弹幕捕获 | 2 |
| 3.1-3.4 | WebSocket 桥梁 | 3 |
| 4.1-4.3, 4.5-4.6 | 前端核心 UI | 4 |
| 5.1-5.4 | 匹配引擎 + 高亮 | 5 |
| 6.1-6.2 | 集成联调 | 6 |

**完成 P0 总计预计耗时: ~7-8 小时**

### P1 — 提升体验 (MVP 完成后)

| 编号 | 任务 | Phase |
|------|------|-------|
| 1.4 | 文件输出字幕 | 1 |
| 2.3 | 断线重连 | 2 |
| 4.4, 4.7 | DOM 上限 + 样式美化 | 4 |
| 5.5-5.6 | 箭头连线 + 超时消失 | 5 |
| 6.3-6.5 | 性能检查 + README | 6 |

**完成 P1 总计预计耗时: ~3 小时**

---

## 建议执行顺序 (Day by Day)

### Day 1 (2-3h): 环境 + 独立模块验证

1. Phase 0 全部 (环境准备)
2. Phase 1 全部 (语音字幕) — 独立，可验证
3. Phase 2 全部 (弹幕捕获) — 独立，可验证

> 验收: OBS 有字幕 + Python 能抓弹幕

### Day 2 (2-3h): 通信 + UI

1. Phase 3 全部 (WebSocket 桥梁)
2. Phase 4 P0 部分 (前端 UI)

> 验收: 浏览器打开能看到弹幕列表滚动

### Day 3 (2-3h): 匹配 + 集成

1. Phase 5 P0 部分 (匹配高亮)
2. Phase 6 全部 (联调 + 文档)

> 验收: OBS 中全链路跑通

---

## 快速启动命令

```bash
# 1. 克隆/进入项目
cd cross_chat

# 2. 安装依赖
pip install blivedm websockets

# 3. 配置直播间 ID (编辑 backend/mvp_backend.py)
# ROOM_ID = 你的直播间号

# 4. 启动后端
python backend/mvp_backend.py

# 5. OBS 操作:
#    - 麦克风源 → 滤镜 → LocalVocal
#    - 添加 Browser Source → URL: file:///path/to/frontend/index.html

# 6. 开始直播 → 说话 → 观察效果
```
